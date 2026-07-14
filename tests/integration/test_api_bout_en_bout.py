"""Couche 1 (§6.1), Docker requis. Critère de validation de l'Étape 8, bout
en bout : un format propriétaire ERP simulé entre par l'adaptateur, ressort
en planning JSON via l'API, et le code du solveur est exportable via le
canal d'audit.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from adapters.erp_reference import OperationERP, PayloadERP, PosteERP, traduire
from api.app import app
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from scripts.enregistrer_solveur_reference import STRUCTURE_MINIMALE, enregistrer
from solver_store.registry import Registre


def test_bout_en_bout_erp_vers_planning_et_audit(tmp_path: Path, image_sandbox: str) -> None:
    etat_test = EtatAPI()
    registre_test = Registre(
        chemin_base=tmp_path / "registre.sqlite3", dossier_artefacts=tmp_path / "artifacts"
    )
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[obtenir_registre] = lambda: registre_test

    try:
        id_solveur = enregistrer(registre_test, client_id="client_test")

        payload_erp = PayloadERP(
            operations=[
                OperationERP(code_operation="OP10", duree_minutes=20, poste_id="POSTE_A"),
                OperationERP(
                    code_operation="OP20",
                    duree_minutes=15,
                    poste_id="POSTE_B",
                    operation_precedente="OP10",
                ),
            ],
            postes=[PosteERP(code_poste="POSTE_A"), PosteERP(code_poste="POSTE_B")],
        )
        instance = traduire(payload_erp)

        client = TestClient(app)

        reponse = client.post("/ingestion/client_test", json=instance.model_dump(mode="json"))
        assert reponse.status_code == 200
        corps_ingestion = reponse.json()
        assert corps_ingestion["structure_contraintes"] == STRUCTURE_MINIMALE
        instance_id = corps_ingestion["instance_id"]

        reponse = client.post(f"/execution/{instance_id}", params={"client_id": "client_test"})
        assert reponse.status_code == 200
        corps_execution = reponse.json()
        assert corps_execution["reussi"], corps_execution["erreur"]
        execution_id = corps_execution["execution_id"]

        reponse = client.get(f"/planning/{execution_id}")
        assert reponse.status_code == 200
        planning = reponse.json()
        assert {operation["tache"] for operation in planning["operations"]} == {"OP10", "OP20"}

        reponse = client.get(f"/audit/{execution_id}")
        assert reponse.status_code == 200
        corps_audit = reponse.json()
        assert corps_audit["id_solveur"] == id_solveur
        assert "def resoudre" in corps_audit["code_source"]
    finally:
        app.dependency_overrides.clear()
