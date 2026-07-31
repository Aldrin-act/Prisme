"""Couche 1 (§6.1), Docker requis. Critère de validation de PH10-T2 : aucun
planning n'est appliqué sans validation humaine explicite, et la décision
(acceptée/refusée) est tracée.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, MinimiserMakespan, Precedence, Ressource, Tache
from scripts.enregistrer_solveur_reference import enregistrer
from solver_store.registry import Registre


def _executer_une_instance(client: TestClient) -> str:
    instance = InstanceTRCO(
        taches=[Tache(id="T1"), Tache(id="T2")],
        ressources=[Ressource(id="R1")],
        contraintes=[
            Precedence(avant="T1", apres="T2"),
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
            CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=5),
        ],
        objectifs=[MinimiserMakespan()],
    )
    reponse_ingestion = client.post("/ingestion/client_test", json=instance.model_dump(mode="json"))
    instance_id = reponse_ingestion.json()["instance_id"]

    # L'exécution se déclenche directement par instance_id, sans intermédiaire.
    reponse = client.post(f"/execution/{instance_id}")
    assert reponse.status_code == 200, reponse.json()
    return reponse.json()["execution_id"]


def test_aucune_decision_avant_validation_explicite(image_sandbox: str, registre_test: Registre) -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[obtenir_registre] = lambda: registre_test

    try:
        enregistrer(registre_test, client_id="client_test")
        client = TestClient(app)
        execution_id = _executer_une_instance(client)

        # PH10-T2 : rien n'est "appliqué" tant que l'humain n'a pas tranché.
        reponse = client.get(f"/executions/{execution_id}/decision")
        assert reponse.status_code == 404

        # Le planning proposé reste inspectable, lui, avant toute décision
        # (PH10-T2, bullet 1 : "présenter le planning pour inspection").
        reponse = client.get(f"/planning/{execution_id}")
        assert reponse.status_code == 200
        assert "durees" in reponse.json()

        reponse = client.post(f"/executions/{execution_id}/decision", json={"decision": "acceptee"})
        assert reponse.status_code == 200

        reponse = client.get(f"/executions/{execution_id}/decision")
        assert reponse.status_code == 200
        corps = reponse.json()
        assert corps["decision"] == "acceptee"
        assert corps["horodatage"]
    finally:
        app.dependency_overrides.clear()


def test_decision_refusee_est_tracee(image_sandbox: str, registre_test: Registre) -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[obtenir_registre] = lambda: registre_test

    try:
        enregistrer(registre_test, client_id="client_test")
        client = TestClient(app)
        execution_id = _executer_une_instance(client)

        reponse = client.post(
            f"/executions/{execution_id}/decision",
            json={"decision": "refusee", "commentaire": "makespan trop élevé"},
        )
        assert reponse.status_code == 200

        corps = client.get(f"/executions/{execution_id}/decision").json()
        assert corps["decision"] == "refusee"
        assert corps["commentaire"] == "makespan trop élevé"
    finally:
        app.dependency_overrides.clear()


def test_decision_invalide_rejetee() -> None:
    client = TestClient(app)
    reponse = client.post("/executions/inconnue/decision", json={"decision": "peut-être"})
    assert reponse.status_code == 404
