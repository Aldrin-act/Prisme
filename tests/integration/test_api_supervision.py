"""Couche 1 (§6.1) : le canal de supervision est en lecture seule et ne doit
jamais exposer le code source d'un solveur (`code_source` reste réservé à
`/audit/{execution_id}`, sur demande explicite — §5.1, §5.5). Les cas qui
n'ont pas besoin d'une exécution réelle en sandbox n'exigent pas Docker ;
seul le scénario ingestion -> exécution en a besoin.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, MinimiserMakespan, Precedence, Ressource, Tache
from scripts.enregistrer_solveur_reference import enregistrer
from solver_store.registry import Registre


def test_listes_vides_sur_etat_neuf() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test

    try:
        client = TestClient(app)
        assert client.get("/supervision/instances").json() == []
        assert client.get("/supervision/executions").json() == []
    finally:
        app.dependency_overrides.clear()


def test_sante_repond_toujours_200() -> None:
    client = TestClient(app)
    reponse = client.get("/supervision/sante")
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["api"] is True
    assert isinstance(corps["sandbox_docker"], bool)


def test_solveurs_enregistres_sans_code_source(registre_test: Registre) -> None:
    app.dependency_overrides[obtenir_registre] = lambda: registre_test

    try:
        id_solveur = enregistrer(registre_test, client_id="client_test")

        client = TestClient(app)
        reponse = client.get("/supervision/solveurs")
        assert reponse.status_code == 200
        solveurs = reponse.json()
        solveur = next(s for s in solveurs if s["id"] == id_solveur)

        assert solveur["client_id"] == "client_test"
        assert solveur["structure_contraintes"] == "compatibilite_ressource_tache,precedence"
        assert "code_source" not in solveur
    finally:
        app.dependency_overrides.clear()


def test_cycle_ingestion_execution_visible_en_supervision(image_sandbox: str, registre_test: Registre) -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[obtenir_registre] = lambda: registre_test

    try:
        enregistrer(registre_test, client_id="client_test")

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

        client = TestClient(app)

        instance_id = client.post("/ingestion/client_test", json=instance.model_dump(mode="json")).json()[
            "instance_id"
        ]

        instances = client.get("/supervision/instances").json()
        instance_supervisee = next(i for i in instances if i["instance_id"] == instance_id)
        assert instance_supervisee["executee"] is False

        execution_id = client.post(f"/execution/{instance_id}?client_id=client_test").json()["execution_id"]

        instances = client.get("/supervision/instances").json()
        instance_supervisee = next(i for i in instances if i["instance_id"] == instance_id)
        assert instance_supervisee["executee"] is True

        executions = client.get("/supervision/executions").json()
        execution_supervisee = next(e for e in executions if e["execution_id"] == execution_id)
        assert execution_supervisee["instance_id"] == instance_id
        assert execution_supervisee["client_id"] == "client_test"
        assert execution_supervisee["reussi"] is True
        assert execution_supervisee["decision"] is None
    finally:
        app.dependency_overrides.clear()
