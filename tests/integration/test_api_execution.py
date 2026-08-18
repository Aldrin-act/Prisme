"""Couche 1 (§6.1), Docker + PostgreSQL requis. `POST /execution/{instance_id}?horizon_gele_jours=...`
bout en bout (Phase 2, replanification à horizon glissant) : `client_isole` isole état et store —
même patron que `test_api_planifier.py`/`test_api_ingestion.py` — `image_sandbox` fournit un vrai
conteneur pour un solveur réellement enregistré et exécuté (`scripts/_solveur_minimal.py`, étendu
de façon additive avec `planning_precedent`/`horizon_gele_jours`).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import scripts._solveur_minimal as _module_solveur_minimal
from api.app import app
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from solver_store.registry import Registre
from validation_engine.cascade import VerdictCascade


@pytest.fixture
def client_isole(registre_test: Registre) -> Iterator[tuple[TestClient, EtatAPI]]:
    """Un client de test avec état et store isolés — jamais le store réel du dépôt."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[obtenir_registre] = lambda: registre_test
    try:
        yield TestClient(app), etat_test
    finally:
        app.dependency_overrides.clear()


def _payload_valide() -> dict:
    return {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def _enregistrer_solveur_minimal(registre: Registre) -> None:
    """Enregistre `_solveur_minimal.py` (déjà étendu, Phase 2) — verdict vert « à blanc », comme
    `test_solveur_valide_stocke_puis_execute_en_sandbox` : ce test vérifie le câblage
    route → sandbox → état, pas la cascade elle-même (déjà couverte ailleurs)."""
    code_source = Path(_module_solveur_minimal.__file__).read_text(encoding="utf-8")
    registre.enregistrer_solveur(
        code_source=code_source,
        structure_contraintes="compatibilite_ressource_tache",
        verdict_cascade=VerdictCascade(diagnostics=()),
        client_id="client_a",
    )


def test_horizon_gele_sans_historique_solve_normalement(
    image_sandbox: str, client_isole: tuple[TestClient, EtatAPI], registre_test: Registre
) -> None:
    """Première exécution de cette instance : `horizon_gele_jours>0` est demandé mais il n'existe
    encore aucun planning précédent — rien à figer, le solve se déroule normalement."""
    client, _ = client_isole
    _enregistrer_solveur_minimal(registre_test)
    instance_id = client.post("/ingestion/client_a", json=_payload_valide()).json()["instance_id"]

    reponse = client.post(f"/execution/{instance_id}", params={"horizon_gele_jours": 5})

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["reussi"] is True, corps["erreur"]
    assert corps["horizon_gele_jours"] == 5
    assert corps["planning_precedent_utilise"] is False


def test_horizon_gele_avec_historique_reutilise_le_dernier_planning_reussi(
    image_sandbox: str, client_isole: tuple[TestClient, EtatAPI], registre_test: Registre
) -> None:
    """Deuxième exécution de la même instance, après un premier succès : `horizon_gele_jours>0`
    trouve bien un planning précédent à transmettre — transparence humaine, jamais silencieux."""
    client, _ = client_isole
    _enregistrer_solveur_minimal(registre_test)
    instance_id = client.post("/ingestion/client_a", json=_payload_valide()).json()["instance_id"]

    premiere = client.post(f"/execution/{instance_id}")
    assert premiere.json()["reussi"] is True, premiere.json()["erreur"]

    deuxieme = client.post(f"/execution/{instance_id}", params={"horizon_gele_jours": 5})

    assert deuxieme.status_code == 200
    corps = deuxieme.json()
    assert corps["reussi"] is True, corps["erreur"]
    assert corps["planning_precedent_utilise"] is True


def test_horizon_gele_negatif_est_rejete(client_isole: tuple[TestClient, EtatAPI]) -> None:
    client, _ = client_isole
    instance_id = client.post("/ingestion/client_a", json=_payload_valide()).json()["instance_id"]

    reponse = client.post(f"/execution/{instance_id}", params={"horizon_gele_jours": -1})

    assert reponse.status_code == 422
