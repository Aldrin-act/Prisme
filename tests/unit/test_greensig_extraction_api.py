"""Couche 1 (§6.1) : `extraction_api.py` ne fait jamais de connexion réseau réelle en test —
`httpx.MockTransport` simule les réponses paginées de l'API publique GreenSIG, jamais un vrai
serveur (contrairement au chemin DB, où `greensig_dsn` saute si `db_greensig` est injoignable)."""

from __future__ import annotations

import httpx
import pytest

from adapters.greensig.extraction_api import config_api_par_defaut, extraire_payload_api
from adapters.greensig.schema_greensig_api import PayloadGreenSIGApi


def _page(resultats: list[dict], suivante: str | None = None) -> httpx.Response:
    return httpx.Response(
        200, json={"count": len(resultats), "next": suivante, "previous": None, "results": resultats}
    )


def test_extraction_recupere_les_cinq_ressources() -> None:
    appels: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        appels.append(request.url.path)
        if request.url.path.endswith("/taches/"):
            return _page([{"id": 1, "reference": "T1", "type_tache": "Tonte", "equipes": ["Équipe Nord"]}])
        if request.url.path.endswith("/equipes/"):
            return _page([{"id": 100, "nom_equipe": "Équipe Nord", "actif": True}])
        return _page([])

    client = httpx.Client(base_url="http://testserver/", transport=httpx.MockTransport(handler))

    payload = extraire_payload_api(client=client)

    assert isinstance(payload, PayloadGreenSIGApi)
    assert [t.reference for t in payload.taches] == ["T1"]
    assert [e.nom_equipe for e in payload.equipes] == ["Équipe Nord"]
    assert payload.operateurs == []
    assert payload.absences == []
    assert payload.jours_feries == []
    assert sorted(appels) == [
        "/absences/",
        "/equipes/",
        "/jours-feries/",
        "/operateurs/",
        "/taches/",
    ]


def test_extraction_suit_la_pagination_jusqua_epuisement() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path != "/taches/":
            return _page([])
        if request.url.params.get("page") == "2":
            return _page([{"id": 2, "reference": "T2", "type_tache": "Élagage"}])
        return _page(
            [{"id": 1, "reference": "T1", "type_tache": "Tonte"}], suivante="http://testserver/taches/?page=2"
        )

    client = httpx.Client(base_url="http://testserver/", transport=httpx.MockTransport(handler))

    payload = extraire_payload_api(client=client)

    assert {t.reference for t in payload.taches} == {"T1", "T2"}


def test_config_api_par_defaut_lit_les_variables_denvironnement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GREENSIG_API_BASE_URL", "http://exemple.local/api/public/v1/")
    monkeypatch.setenv("GREENSIG_API_KEY", "ma-cle")

    base_url, cle = config_api_par_defaut()

    assert base_url == "http://exemple.local/api/public/v1/"
    assert cle == "ma-cle"


def test_config_api_par_defaut_leve_si_variable_absente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GREENSIG_API_BASE_URL", raising=False)
    monkeypatch.delenv("GREENSIG_API_KEY", raising=False)

    with pytest.raises(KeyError):
        config_api_par_defaut()
