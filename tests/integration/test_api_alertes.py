"""Couche 1 (§6.1), Docker requis. Critère de validation de PH10-T1 : un aléa
lève une alerte, et l'opérateur déclenche le recalcul explicitement depuis
l'API (le geste que le dashboard exposera) — jamais automatiquement.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from dsl.schema import CompatibiliteMachineTache, InstanceTRCO, MinimiserMakespan, Precedence, Ressource, Tache
from scripts.enregistrer_solveur_reference import enregistrer
from solver_store.registry import Registre


def test_alerte_levee_puis_declenchee(tmp_path: Path, image_sandbox: str) -> None:
    etat_test = EtatAPI()
    registre_test = Registre(chemin_base=tmp_path / "registre.sqlite3", dossier_artefacts=tmp_path / "artifacts")
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[obtenir_registre] = lambda: registre_test

    try:
        enregistrer(registre_test, client_id="client_test")

        # Précédence + compatibilité (pas seulement compatibilité) pour matcher
        # STRUCTURE_MINIMALE = "compatibilite_machine_tache,precedence", celle
        # sous laquelle le solveur de référence est enregistré (match exact, §7).
        instance = InstanceTRCO(
            taches=[Tache(id="T1"), Tache(id="T2")],
            ressources=[Ressource(id="M1")],
            contraintes=[
                Precedence(avant="T1", apres="T2"),
                CompatibiliteMachineTache(tache="T1", ressource="M1", duree=10),
                CompatibiliteMachineTache(tache="T2", ressource="M1", duree=5),
            ],
            objectifs=[MinimiserMakespan()],
        )

        client = TestClient(app)

        reponse = client.post("/ingestion/client_test", json=instance.model_dump(mode="json"))
        assert reponse.status_code == 200
        instance_id = reponse.json()["instance_id"]

        reponse = client.post(
            "/alertes",
            json={
                "instance_id": instance_id,
                "client_id": "client_test",
                "type_alea": "panne",
                "description": "machine M1 en panne",
            },
        )
        assert reponse.status_code == 200
        alerte_id = reponse.json()["alerte_id"]

        reponse = client.get("/alertes")
        assert reponse.status_code == 200
        alertes = reponse.json()
        alerte = next(a for a in alertes if a["id"] == alerte_id)
        assert alerte["statut"] == "nouvelle"
        assert alerte["execution_id"] is None

        reponse = client.post(f"/alertes/{alerte_id}/declencher")
        assert reponse.status_code == 200
        corps = reponse.json()
        assert corps["reussi"]
        execution_id = corps["execution_id"]

        reponse = client.get("/alertes")
        alerte = next(a for a in reponse.json() if a["id"] == alerte_id)
        assert alerte["statut"] == "traitee"
        assert alerte["execution_id"] == execution_id
    finally:
        app.dependency_overrides.clear()


def test_alerte_sur_instance_inconnue_rejetee() -> None:
    client = TestClient(app)
    reponse = client.post(
        "/alertes",
        json={
            "instance_id": "inconnue",
            "client_id": "client_test",
            "type_alea": "panne",
            "description": "test",
        },
    )
    assert reponse.status_code == 404


def test_declenchement_sur_alerte_inconnue_rejete() -> None:
    client = TestClient(app)
    reponse = client.post("/alertes/inconnue/declencher")
    assert reponse.status_code == 404
