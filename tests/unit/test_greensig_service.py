"""Couche 1 (§6.1) : `service.py` est le seul point qui connaît les deux chemins d'intégration
GreenSIG — ce test vérifie uniquement le dispatch (`GREENSIG_MODE`), la logique de traduction de
chaque chemin étant déjà testée séparément (`test_greensig_adapter.py` pour le chemin base directe,
`test_greensig_translator_api.py` pour le chemin API)."""

from __future__ import annotations

import pytest

from adapters.greensig import service
from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, MinimiserMakespan, Ressource, Tache


def _instance_factice(id_tache: str) -> InstanceTRCO:
    return InstanceTRCO(
        taches=[Tache(id=id_tache)],
        ressources=[Ressource(id="R1")],
        contraintes=[CompatibiliteRessourceTache(tache=id_tache, ressource="R1", duree=1)],
        objectifs=[MinimiserMakespan()],
    )


def _echoue(*_args: object, **_kwargs: object) -> None:
    pytest.fail("chemin de l'autre mode appelé par erreur")


def test_mode_db_par_defaut(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GREENSIG_MODE", raising=False)
    monkeypatch.setattr(service, "extraire_payload", lambda: "payload-db")
    monkeypatch.setattr(service, "traduire", lambda payload: _instance_factice("depuis-db"))
    monkeypatch.setattr(service, "extraire_payload_api", _echoue)
    monkeypatch.setattr(service, "traduire_api", _echoue)

    instance = service.extraire_et_traduire()

    assert {t.id for t in instance.taches} == {"depuis-db"}


def test_mode_api_via_variable_denvironnement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GREENSIG_MODE", "api")
    monkeypatch.setattr(service, "extraire_payload_api", lambda: "payload-api")
    monkeypatch.setattr(
        service, "traduire_api", lambda payload, date_reference=None: _instance_factice("depuis-api")
    )
    monkeypatch.setattr(service, "extraire_payload", _echoue)
    monkeypatch.setattr(service, "traduire", _echoue)

    instance = service.extraire_et_traduire()

    assert {t.id for t in instance.taches} == {"depuis-api"}


def test_mode_explicite_prime_sur_la_variable_denvironnement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GREENSIG_MODE", "db")
    monkeypatch.setattr(service, "extraire_payload_api", lambda: "payload-api")
    monkeypatch.setattr(
        service, "traduire_api", lambda payload, date_reference=None: _instance_factice("depuis-api")
    )
    monkeypatch.setattr(service, "extraire_payload", _echoue)
    monkeypatch.setattr(service, "traduire", _echoue)

    instance = service.extraire_et_traduire(mode="api")

    assert {t.id for t in instance.taches} == {"depuis-api"}
