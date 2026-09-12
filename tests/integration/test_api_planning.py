"""Couche 1 (§6.1), PostgreSQL requis (aucun Docker — ces routes ne touchent jamais le sandbox).
`POST /planning/{execution_id}/ajuster` + `GET /planning/{execution_id}/ajuste` bout en bout
(Gantt interactif, Phase 3) : `client_isole` isole état et store — même patron que
`test_api_execution.py`. L'exécution ciblée est semée directement via `EtatAPI` (pas besoin d'un
vrai solveur/sandbox : ces routes ne lisent que `execution_id -> instance_id`).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from dsl.schema import InstanceTRCO, OperationPlanifiee, Planning
from sandbox.runner import ResultatExecution
from solver_store.registry import Registre


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


def _instance_exemple() -> InstanceTRCO:
    return InstanceTRCO.model_validate(
        {
            "taches": [{"id": "T1"}, {"id": "T2"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [
                {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 5},
                {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 5},
                {"type": "precedence", "avant": "T1", "apres": "T2"},
            ],
            "objectifs": [{"type": "minimiser_makespan"}],
        }
    )


def _semer_execution(etat: EtatAPI) -> str:
    instance_id = etat.enregistrer_instance("client_a", _instance_exemple())
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="jamais exécutée pour de vrai")
    return etat.enregistrer_execution("solveur-abc", instance_id, resultat)


def test_ajuster_planning_legal_persiste_et_se_relit(client_isole: tuple[TestClient, EtatAPI]) -> None:
    client, etat_test = client_isole
    execution_id = _semer_execution(etat_test)
    planning_legal = {
        "operations": [
            {"tache": "T1", "ressource": "R1", "debut": 0},
            {"tache": "T2", "ressource": "R1", "debut": 5},
        ]
    }

    reponse = client.post(f"/planning/{execution_id}/ajuster", json=planning_legal)

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["legal"] is True
    assert corps["violations"] == []
    assert corps["planning"]["operations"] == planning_legal["operations"]
    # Ancrage calendaire du Gantt (voir GanttChart côté frontend) — une révision ajustée porte
    # la même date que l'exécution d'origine, jamais une nouvelle date "au moment de l'ajustement".
    assert corps["planning"]["date_execution"] == etat_test.recuperer_date_execution(execution_id)

    relu = client.get(f"/planning/{execution_id}/ajuste")
    assert relu.status_code == 200
    assert relu.json()["operations"] == planning_legal["operations"]
    assert relu.json()["date_execution"] == etat_test.recuperer_date_execution(execution_id)


def test_ajuster_planning_illegal_renvoie_les_violations_sans_persister(
    client_isole: tuple[TestClient, EtatAPI],
) -> None:
    client, etat_test = client_isole
    execution_id = _semer_execution(etat_test)
    # T2 démarre avant même la fin de T1 sur la même ressource — viole à la fois la précédence
    # et le non-chevauchement.
    planning_illegal = {
        "operations": [
            {"tache": "T1", "ressource": "R1", "debut": 0},
            {"tache": "T2", "ressource": "R1", "debut": 0},
        ]
    }

    reponse = client.post(f"/planning/{execution_id}/ajuster", json=planning_illegal)

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["legal"] is False
    assert len(corps["violations"]) > 0
    assert corps["planning"] is None

    relu = client.get(f"/planning/{execution_id}/ajuste")
    assert relu.status_code == 200
    assert relu.json() is None


def test_obtenir_planning_inclut_la_date_execution(client_isole: tuple[TestClient, EtatAPI]) -> None:
    """`GET /planning/{execution_id}` (pas seulement `/ajuste`) porte lui aussi l'ancrage
    calendaire du Gantt — voir GanttChart côté frontend, qui en dépend pour son jour 0."""
    client, etat_test = client_isole
    instance_id = etat_test.enregistrer_instance("client_a", _instance_exemple())
    planning = Planning(
        operations=[
            OperationPlanifiee(tache="T1", ressource="R1", debut=0),
            OperationPlanifiee(tache="T2", ressource="R1", debut=5),
        ]
    )
    resultat = ResultatExecution(planning=planning, verdict_faisabilite=None, erreur=None)
    execution_id = etat_test.enregistrer_execution("solveur-abc", instance_id, resultat)

    reponse = client.get(f"/planning/{execution_id}")

    assert reponse.status_code == 200
    assert reponse.json()["date_execution"] == etat_test.recuperer_date_execution(execution_id)


def test_obtenir_planning_ajuste_absent_renvoie_null(client_isole: tuple[TestClient, EtatAPI]) -> None:
    client, etat_test = client_isole
    execution_id = _semer_execution(etat_test)

    reponse = client.get(f"/planning/{execution_id}/ajuste")

    assert reponse.status_code == 200
    assert reponse.json() is None


def test_ajuster_planning_execution_inconnue_est_404(client_isole: tuple[TestClient, EtatAPI]) -> None:
    client, _ = client_isole

    reponse = client.post("/planning/id-inexistant/ajuster", json={"operations": []})

    assert reponse.status_code == 404


def test_obtenir_planning_ajuste_execution_inconnue_est_404(client_isole: tuple[TestClient, EtatAPI]) -> None:
    client, _ = client_isole

    reponse = client.get("/planning/id-inexistant/ajuste")

    assert reponse.status_code == 404
