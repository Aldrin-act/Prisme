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
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[obtenir_registre] = lambda: registre_test

    try:
        instance = InstanceTRCO(
            taches=[Tache(id="T1")],
            ressources=[Ressource(id="R1")],
            contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
            objectifs=[MinimiserMakespan()],
        )
        client = TestClient(app)
        instance_id = client.post("/ingestion/client_test", json=instance.model_dump(mode="json")).json()[
            "instance_id"
        ]
        id_solveur = enregistrer(registre_test, instance_id=instance_id, client_id="client_test")

        reponse = client.get("/supervision/solveurs")
        assert reponse.status_code == 200
        solveurs = reponse.json()
        solveur = next(s for s in solveurs if s["id"] == id_solveur)

        assert solveur["client_id"] == "client_test"
        assert solveur["structure_contraintes"] == "compatibilite_ressource_tache,precedence"
        assert "code_source" not in solveur
    finally:
        app.dependency_overrides.clear()


def _modele_factice_detection_et_redaction(signal_detection: dict, reference: str) -> ModeleFactice:
    """`analyser_et_proposer` invoque le même modèle pour deux schémas différents — détection
    (`_SchemaDetectionSupervision`, doit désigner le signal attendu par le test) puis rédaction
    (`_SchemaSupervision`, `reference` recopiée telle quelle) — voir
    `ModeleFactice.reponses_par_schema`."""
    schema_detection = agent_module._SchemaDetectionSupervision(
        signaux=[agent_module._SchemaSignalDetecte(**signal_detection)]
    )
    schema_propositions = agent_module._SchemaSupervision(
        propositions=[
            agent_module._SchemaPropositionUnitaire(
                reference=reference, resume="Résumé de test.", priorite="haute"
            )
        ]
    )
    return ModeleFactice(
        raw_content=json.dumps(schema_propositions.model_dump()),
        parsed=schema_propositions,
        reponses_par_schema={
            agent_module._SchemaDetectionSupervision: (
                json.dumps(schema_detection.model_dump()),
                schema_detection,
                None,
            ),
            agent_module._SchemaSupervision: (
                json.dumps(schema_propositions.model_dump()),
                schema_propositions,
                None,
            ),
        },
    )


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
        app.dependency_overrides[construire_modele_supervision] = lambda: _modele_factice_detection_et_redaction(
            {"instance_id": instance_id, "type_signal": "signature_orpheline"}, reference
        )

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
        app.dependency_overrides[construire_modele_supervision] = lambda: _modele_factice_detection_et_redaction(
            {"instance_id": instance_id, "type_signal": "signature_orpheline"}, reference
        )
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
        id_solveur = enregistrer(registre_test, instance_id=instance_id, client_id="client_test")
        reference = f"instance_a_replanifier:{instance_id}"
        app.dependency_overrides[construire_modele_supervision] = lambda: _modele_factice_detection_et_redaction(
            {
                "instance_id": instance_id,
                "type_signal": "instance_a_replanifier",
                "raison": "jamais_executee",
                "id_solveur_disponible": id_solveur,
            },
            reference,
        )
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
        enregistrer(registre_test, instance_id=instance_id, client_id="client_test")

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


def _modele_factice_commande_en_retard(reference: str) -> ModeleFactice:
    """`commande_en_retard` est détecté sans LLM (`supervision.detecteurs.
    detecter_commandes_en_retard`) — la détection LLM des trois autres signaux tourne quand même
    (`analyser_et_proposer` ne peut jamais l'éviter), on la fait donc répondre vide pour isoler
    le signal testé ici. La rédaction, elle, reste un appel LLM normal pour ce signal."""
    schema_detection = agent_module._SchemaDetectionSupervision(signaux=[])
    schema_propositions = agent_module._SchemaSupervision(
        propositions=[
            agent_module._SchemaPropositionUnitaire(
                reference=reference, resume="Résumé de test.", priorite="haute"
            )
        ]
    )
    return ModeleFactice(
        raw_content=json.dumps(schema_propositions.model_dump()),
        parsed=schema_propositions,
        reponses_par_schema={
            agent_module._SchemaDetectionSupervision: (
                json.dumps(schema_detection.model_dump()),
                schema_detection,
                None,
            ),
            agent_module._SchemaSupervision: (
                json.dumps(schema_propositions.model_dump()),
                schema_propositions,
                None,
            ),
        },
    )


def test_analyser_detecte_une_commande_en_retard_via_lapi(image_sandbox: str, registre_test: Registre) -> None:
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
        enregistrer(registre_test, instance_id=instance_id, client_id="client_test")

        # T1 finit au jour 10 (durée déclarée par sa seule compatibilité ressource-tâche) — une
        # commande avec date_limite=5 est donc en retard.
        reponse_execution = client.post(f"/execution/{instance_id}")
        assert reponse_execution.status_code == 200, reponse_execution.json()

        commande_id = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["T1"], "date_limite": 5}
        ).json()["commande_id"]

        reference = f"commande_en_retard:{commande_id}"
        app.dependency_overrides[construire_modele_supervision] = lambda: _modele_factice_commande_en_retard(
            reference
        )

        reponse = client.post("/supervision/analyser", json={"client_id": "client_test"})
        assert reponse.status_code == 200, reponse.json()
        propositions = reponse.json()
        assert len(propositions) == 1
        assert propositions[0]["type_signal"] == "commande_en_retard"
        assert propositions[0]["action_suggeree"] == "aucune"
        assert propositions[0]["commande_id"] == commande_id
        assert propositions[0]["instance_id"] == instance_id

        # Accepter un signal purement informatif ne déclenche aucune route système.
        executions_avant = client.get("/supervision/executions").json()
        reponse_decision = client.post(
            f"/supervision/propositions/{propositions[0]['proposition_id']}/decision",
            json={"decision": "acceptee"},
        )
        assert reponse_decision.status_code == 200, reponse_decision.json()
        assert reponse_decision.json()["resultat"] == {"action": "aucune"}
        executions_apres = client.get("/supervision/executions").json()
        assert len(executions_apres) == len(executions_avant)
    finally:
        app.dependency_overrides.clear()


def test_deux_commandes_en_retard_meme_instance_via_lapi(image_sandbox: str, registre_test: Registre) -> None:
    """Dédoublonnage par (type_signal, instance_id, commande_id) : deux commandes en retard sur
    la même instance produisent bien deux propositions distinctes, jamais une seule qui en
    masquerait une autre."""
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
        enregistrer(registre_test, instance_id=instance_id, client_id="client_test")

        reponse_execution = client.post(f"/execution/{instance_id}")
        assert reponse_execution.status_code == 200, reponse_execution.json()

        commande_id_1 = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["T1"], "date_limite": 5}
        ).json()["commande_id"]
        commande_id_2 = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["T1"], "date_limite": 2}
        ).json()["commande_id"]

        schema_detection = agent_module._SchemaDetectionSupervision(signaux=[])
        schema_propositions = agent_module._SchemaSupervision(
            propositions=[
                agent_module._SchemaPropositionUnitaire(
                    reference=f"commande_en_retard:{commande_id_1}", resume="R1.", priorite="haute"
                ),
                agent_module._SchemaPropositionUnitaire(
                    reference=f"commande_en_retard:{commande_id_2}", resume="R2.", priorite="haute"
                ),
            ]
        )
        modele = ModeleFactice(
            raw_content=json.dumps(schema_propositions.model_dump()),
            parsed=schema_propositions,
            reponses_par_schema={
                agent_module._SchemaDetectionSupervision: (
                    json.dumps(schema_detection.model_dump()),
                    schema_detection,
                    None,
                ),
                agent_module._SchemaSupervision: (
                    json.dumps(schema_propositions.model_dump()),
                    schema_propositions,
                    None,
                ),
            },
        )
        app.dependency_overrides[construire_modele_supervision] = lambda: modele

        propositions = client.post("/supervision/analyser", json={"client_id": "client_test"}).json()

        commande_ids_proposees = {
            p["commande_id"] for p in propositions if p["type_signal"] == "commande_en_retard"
        }
        assert commande_ids_proposees == {commande_id_1, commande_id_2}
    finally:
        app.dependency_overrides.clear()
