"""Couche 1 (§6.1) : le canal de supervision est en lecture seule et ne doit
jamais exposer le code source d'un solveur (`code_source` reste réservé à
`/audit/{execution_id}`, sur demande explicite — §5.1, §5.5). Les cas qui
n'ont pas besoin d'une exécution réelle en sandbox n'exigent pas Docker ;
seul le scénario ingestion -> exécution en a besoin.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from api.app import app
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, MinimiserMakespan, Precedence, Ressource, Tache
from generation.agents.client_llm import construire_modele_supervision
from scripts.enregistrer_solveur_reference import enregistrer
from solver_store.registry import Registre
from supervision import agent as agent_module
from tests.unit.aides_test_agents import ModeleFactice


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


def _modele_factice_avec_reference(reference: str) -> ModeleFactice:
    schema = agent_module._SchemaSupervision(
        propositions=[
            agent_module._SchemaPropositionUnitaire(
                reference=reference, resume="Résumé de test.", priorite="haute"
            )
        ]
    )
    return ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)


def test_lister_propositions_vide_sur_etat_neuf() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test

    try:
        client = TestClient(app)
        assert client.get("/supervision/propositions").json() == []
    finally:
        app.dependency_overrides.clear()


def test_analyser_detecte_une_signature_orpheline_via_lapi(registre_test: Registre) -> None:
    """Aucun solveur enregistré pour ce client : l'instance ingérée doit
    ressortir en `signature_orpheline` — pas de Docker requis, aucune
    exécution n'a lieu."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[obtenir_registre] = lambda: registre_test

    try:
        client = TestClient(app)
        instance = InstanceTRCO(
            taches=[Tache(id="T1")],
            ressources=[Ressource(id="R1")],
            contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
            objectifs=[MinimiserMakespan()],
        )
        instance_id = client.post("/ingestion/client_test", json=instance.model_dump(mode="json")).json()[
            "instance_id"
        ]
        reference = f"signature_orpheline:{instance_id}"
        app.dependency_overrides[construire_modele_supervision] = lambda: _modele_factice_avec_reference(reference)

        reponse = client.post("/supervision/analyser", json={"client_id": "client_test"})
        assert reponse.status_code == 200, reponse.json()
        propositions = reponse.json()
        assert len(propositions) == 1
        assert propositions[0]["type_signal"] == "signature_orpheline"
        assert propositions[0]["action_suggeree"] == "regenerer_solveur"
        assert propositions[0]["instance_id"] == instance_id
        assert propositions[0]["decision"] is None

        propositions_listees = client.get("/supervision/propositions").json()
        assert len(propositions_listees) == 1
    finally:
        app.dependency_overrides.clear()


def test_decider_refusee_ne_declenche_aucune_action(registre_test: Registre) -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[obtenir_registre] = lambda: registre_test

    try:
        client = TestClient(app)
        instance = InstanceTRCO(
            taches=[Tache(id="T1")],
            ressources=[Ressource(id="R1")],
            contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
            objectifs=[MinimiserMakespan()],
        )
        instance_id = client.post("/ingestion/client_test", json=instance.model_dump(mode="json")).json()[
            "instance_id"
        ]
        reference = f"signature_orpheline:{instance_id}"
        app.dependency_overrides[construire_modele_supervision] = lambda: _modele_factice_avec_reference(reference)
        proposition_id = client.post("/supervision/analyser", json={"client_id": "client_test"}).json()[0][
            "proposition_id"
        ]

        reponse = client.post(f"/supervision/propositions/{proposition_id}/decision", json={"decision": "refusee"})
        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        assert corps["decision"] == "refusee"
        assert "resultat" not in corps
    finally:
        app.dependency_overrides.clear()


def test_decider_acceptee_executer_declenche_une_execution(image_sandbox: str, registre_test: Registre) -> None:
    """Signal `instance_a_replanifier` (solveur déjà disponible, instance
    jamais exécutée) : accepter doit déclencher une vraie exécution
    sandboxée, exactement comme `POST /execution/{instance_id}`."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[obtenir_registre] = lambda: registre_test

    try:
        enregistrer(registre_test, client_id="client_test")
        client = TestClient(app)

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
        instance_id = client.post("/ingestion/client_test", json=instance.model_dump(mode="json")).json()[
            "instance_id"
        ]
        reference = f"instance_a_replanifier:{instance_id}"
        app.dependency_overrides[construire_modele_supervision] = lambda: _modele_factice_avec_reference(reference)
        proposition_id = client.post("/supervision/analyser", json={"client_id": "client_test"}).json()[0][
            "proposition_id"
        ]

        reponse = client.post(
            f"/supervision/propositions/{proposition_id}/decision", json={"decision": "acceptee"}
        )
        assert reponse.status_code == 200, reponse.json()
        resultat = reponse.json()["resultat"]
        assert resultat["action"] == "executer"
        assert resultat["reussi"] is True

        executions = client.get("/supervision/executions").json()
        assert any(e["execution_id"] == resultat["execution_id"] for e in executions)
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

        # L'exécution se déclenche directement par instance_id, sans intermédiaire.
        execution_id = client.post(f"/execution/{instance_id}").json()["execution_id"]

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
