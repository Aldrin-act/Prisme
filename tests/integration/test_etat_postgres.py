"""Tests d'intégration pour `api/etat_postgres.py` (§7, extension du modèle
conceptuel) : vérifie que `EtatPostgres` respecte exactement le contrat
d'`EtatAPI` (mêmes méthodes, mêmes types de retour), une fois passé par une
vraie base Postgres plutôt que par un dict en mémoire.
"""

from __future__ import annotations

from api.etat_postgres import EtatPostgres
from dsl.schema import InstanceTRCO, OperationPlanifiee, Planning
from sandbox.runner import ResultatExecution
from validation_engine.feasibility_checker import ResultatFaisabilite, Violation


def _instance_exemple() -> InstanceTRCO:
    return InstanceTRCO.model_validate(
        {
            "taches": [{"id": "T1"}, {"id": "T2"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [
                {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
                {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 15},
                {"type": "precedence", "avant": "T1", "apres": "T2"},
            ],
            "objectifs": [{"type": "minimiser_makespan"}],
        }
    )


def test_instance_round_trip(etat_postgres_test: EtatPostgres) -> None:
    instance = _instance_exemple()
    instance_id = etat_postgres_test.enregistrer_instance("client-test", instance)

    client_id, instance_relue = etat_postgres_test.recuperer_instance(instance_id)

    assert client_id == "client-test"
    assert [t.id for t in instance_relue.taches] == ["T1", "T2"]
    assert len(instance_relue.contraintes) == 3


def test_description_metier_round_trip(etat_postgres_test: EtatPostgres) -> None:
    instance_id = etat_postgres_test.enregistrer_instance(
        "client-test", _instance_exemple(), description_metier="Découpe puis assemblage de la pièce."
    )

    assert etat_postgres_test.recuperer_description_metier(instance_id) == "Découpe puis assemblage de la pièce."


def test_description_metier_absente_pour_une_ingestion_sans_agent(etat_postgres_test: EtatPostgres) -> None:
    instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())

    assert etat_postgres_test.recuperer_description_metier(instance_id) is None


def test_instance_parente_id_absent_par_defaut(etat_postgres_test: EtatPostgres) -> None:
    instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())

    assert etat_postgres_test.recuperer_instance_parente(instance_id) is None


def test_instance_parente_id_round_trip(etat_postgres_test: EtatPostgres) -> None:
    racine_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())
    derivee_id = etat_postgres_test.enregistrer_instance(
        "client-test", _instance_exemple(), instance_parente_id=racine_id
    )

    assert etat_postgres_test.recuperer_instance_parente(derivee_id) == racine_id
    instances = etat_postgres_test.lister_instances(client_id="client-test")
    derivee = next(i for i in instances if i["instance_id"] == derivee_id)
    assert derivee["instance_parente_id"] == racine_id


def test_supprimer_instance_orpheline_les_derivees_sans_les_detruire(etat_postgres_test: EtatPostgres) -> None:
    racine_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())
    derivee_id = etat_postgres_test.enregistrer_instance(
        "client-test", _instance_exemple(), instance_parente_id=racine_id
    )

    etat_postgres_test.supprimer_instance(racine_id)

    etat_postgres_test.recuperer_instance(derivee_id)  # survit
    assert etat_postgres_test.recuperer_instance_parente(derivee_id) is None


def test_nom_projet_round_trip(etat_postgres_test: EtatPostgres) -> None:
    instance_id = etat_postgres_test.enregistrer_instance(
        "client-test", _instance_exemple(), nom_projet="Atelier mécanique"
    )

    assert etat_postgres_test.recuperer_nom_projet(instance_id) == "Atelier mécanique"


def test_nom_projet_absent_par_defaut(etat_postgres_test: EtatPostgres) -> None:
    instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())

    assert etat_postgres_test.recuperer_nom_projet(instance_id) is None


def test_nom_projet_herite_de_linstance_parente(etat_postgres_test: EtatPostgres) -> None:
    racine_id = etat_postgres_test.enregistrer_instance(
        "client-test", _instance_exemple(), nom_projet="Atelier mécanique"
    )
    derivee_id = etat_postgres_test.enregistrer_instance(
        "client-test", _instance_exemple(), instance_parente_id=racine_id
    )

    assert etat_postgres_test.recuperer_nom_projet(derivee_id) == "Atelier mécanique"


def test_nom_projet_explicite_prime_sur_lheritage(etat_postgres_test: EtatPostgres) -> None:
    racine_id = etat_postgres_test.enregistrer_instance(
        "client-test", _instance_exemple(), nom_projet="Atelier mécanique"
    )
    derivee_id = etat_postgres_test.enregistrer_instance(
        "client-test", _instance_exemple(), instance_parente_id=racine_id, nom_projet="Ligne B"
    )

    assert etat_postgres_test.recuperer_nom_projet(derivee_id) == "Ligne B"


def test_nom_projet_herite_survit_a_la_suppression_de_la_racine(etat_postgres_test: EtatPostgres) -> None:
    """`nom_projet` est recopié à l'insertion (pas une clé étrangère comme
    `instance_parente_id`) — contrairement à celui-ci, il ne se vide pas
    quand la racine est supprimée ensuite."""
    racine_id = etat_postgres_test.enregistrer_instance(
        "client-test", _instance_exemple(), nom_projet="Atelier mécanique"
    )
    derivee_id = etat_postgres_test.enregistrer_instance(
        "client-test", _instance_exemple(), instance_parente_id=racine_id
    )

    etat_postgres_test.supprimer_instance(racine_id)

    assert etat_postgres_test.recuperer_nom_projet(derivee_id) == "Atelier mécanique"


def test_lister_noms_projet_compte_et_isole_par_client(etat_postgres_test: EtatPostgres) -> None:
    etat_postgres_test.enregistrer_instance("client-a", _instance_exemple(), nom_projet="Atelier mécanique")
    etat_postgres_test.enregistrer_instance("client-a", _instance_exemple(), nom_projet="Atelier mécanique")
    etat_postgres_test.enregistrer_instance("client-a", _instance_exemple())  # sans nom, exclue
    etat_postgres_test.enregistrer_instance("client-b", _instance_exemple(), nom_projet="Atelier mécanique")

    noms = etat_postgres_test.lister_noms_projet(client_id="client-a")

    assert noms == [{"nom_projet": "Atelier mécanique", "nb_instances": 2}]


def test_lister_instances_filtre_par_nom_projet(etat_postgres_test: EtatPostgres) -> None:
    instance_ciblee = etat_postgres_test.enregistrer_instance(
        "client-test", _instance_exemple(), nom_projet="Atelier mécanique"
    )
    etat_postgres_test.enregistrer_instance("client-test", _instance_exemple(), nom_projet="Ligne B")

    instances = etat_postgres_test.lister_instances(client_id="client-test", nom_projet="Atelier mécanique")

    assert [i["instance_id"] for i in instances] == [instance_ciblee]


def test_recuperer_instance_inconnue_leve_key_error(etat_postgres_test: EtatPostgres) -> None:
    try:
        etat_postgres_test.recuperer_instance("id-inexistant")
    except KeyError:
        return
    raise AssertionError("KeyError attendu pour une instance inconnue")


def test_execution_reussie_round_trip_avec_planning(etat_postgres_test: EtatPostgres) -> None:
    instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())
    planning = Planning(
        operations=[
            OperationPlanifiee(tache="T1", ressource="R1", debut=0),
            OperationPlanifiee(tache="T2", ressource="R1", debut=10),
        ]
    )
    resultat = ResultatExecution(
        planning=planning, verdict_faisabilite=ResultatFaisabilite(violations=()), erreur=None
    )
    assert resultat.reussi

    execution_id = etat_postgres_test.enregistrer_execution("solveur-abc", instance_id, resultat)
    id_solveur, instance_id_relu, resultat_relu = etat_postgres_test.recuperer_execution(execution_id)

    assert id_solveur == "solveur-abc"
    assert instance_id_relu == instance_id
    assert resultat_relu.reussi
    assert resultat_relu.planning is not None
    assert len(resultat_relu.planning.operations) == 2
    assert resultat_relu.verdict_faisabilite is not None
    assert resultat_relu.verdict_faisabilite.legal


def test_execution_en_echec_round_trip_sans_planning(etat_postgres_test: EtatPostgres) -> None:
    instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())
    violations = (
        Violation(
            type="incompatibilite_ressource_tache",
            message="pas de ressource compatible",
            tache="T3",
            ressource=None,
        ),
    )
    resultat = ResultatExecution(
        planning=None, verdict_faisabilite=ResultatFaisabilite(violations=violations), erreur=None
    )
    assert not resultat.reussi

    execution_id = etat_postgres_test.enregistrer_execution("solveur-abc", instance_id, resultat)
    _, _, resultat_relu = etat_postgres_test.recuperer_execution(execution_id)

    assert resultat_relu.planning is None
    assert resultat_relu.verdict_faisabilite is not None
    assert not resultat_relu.verdict_faisabilite.legal
    assert resultat_relu.verdict_faisabilite.violations[0].message == "pas de ressource compatible"


def test_lister_instances_et_executions(etat_postgres_test: EtatPostgres) -> None:
    instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="erreur d'exécution")
    etat_postgres_test.enregistrer_execution("solveur-abc", instance_id, resultat)

    instances = etat_postgres_test.lister_instances()
    assert len(instances) == 1
    assert instances[0]["executee"] is True
    assert instances[0]["structure_contraintes"] == "compatibilite_ressource_tache,precedence"

    executions = etat_postgres_test.lister_executions()
    assert len(executions) == 1
    assert executions[0]["instance_id"] == instance_id
    assert executions[0]["reussi"] is False
    assert executions[0]["erreur"] == "erreur d'exécution"
    assert executions[0]["decision"] is None


def test_decision_humaine(etat_postgres_test: EtatPostgres) -> None:
    instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="peu importe")
    execution_id = etat_postgres_test.enregistrer_execution("solveur-abc", instance_id, resultat)

    assert etat_postgres_test.decision_pour(execution_id) is None

    etat_postgres_test.enregistrer_decision(execution_id, "acceptee", commentaire="RAS")
    decision = etat_postgres_test.decision_pour(execution_id)

    assert decision is not None
    assert decision.decision == "acceptee"
    assert decision.commentaire == "RAS"

    # Ré-enregistrer écrase la précédente (même sémantique que EtatAPI, un dict par execution_id)
    etat_postgres_test.enregistrer_decision(execution_id, "refusee")
    decision = etat_postgres_test.decision_pour(execution_id)
    assert decision.decision == "refusee"
    assert decision.commentaire is None


# --- Sources de données : persistance légère, rejouable via l'agent de
# compréhension, sans historique d'exécution ni pointeur "instance courante" ---


def test_enregistrer_instance_depuis_source_trace_la_provenance(etat_postgres_test: EtatPostgres) -> None:
    source_id = etat_postgres_test.enregistrer_source("client-test", donnees_brutes="brut")
    instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple(), source_id=source_id)

    instances = etat_postgres_test.lister_instances_pour_source(source_id)
    assert [i["instance_id"] for i in instances] == [instance_id]


def test_lister_sources_compte_les_instances_generees(etat_postgres_test: EtatPostgres) -> None:
    source_a = etat_postgres_test.enregistrer_source("client-test", donnees_brutes="brut-a")
    etat_postgres_test.enregistrer_source("client-test", donnees_brutes="brut-b")  # source_b, sans instance
    etat_postgres_test.enregistrer_instance("client-test", _instance_exemple(), source_id=source_a)
    etat_postgres_test.enregistrer_instance("client-test", _instance_exemple(), source_id=source_a)

    sources = etat_postgres_test.lister_sources(client_id="client-test")
    compteurs = {s["source_id"]: s["nb_instances"] for s in sources}
    assert compteurs[source_a] == 2


def test_supprimer_source_coupe_la_provenance_sans_toucher_a_linstance(etat_postgres_test: EtatPostgres) -> None:
    source_id = etat_postgres_test.enregistrer_source("client-test", donnees_brutes="brut")
    instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple(), source_id=source_id)

    etat_postgres_test.supprimer_source(source_id)

    try:
        etat_postgres_test.recuperer_source(source_id)
        raise AssertionError("KeyError attendu pour une source supprimée")
    except KeyError:
        pass
    etat_postgres_test.recuperer_instance(instance_id)  # survit, indépendante de sa source


# --- Suppression d'instance : cascade son propre historique d'exécution ---


def test_supprimer_instance_cascade_ses_executions(etat_postgres_test: EtatPostgres) -> None:
    instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur=None)
    execution_id = etat_postgres_test.enregistrer_execution("solveur-abc", instance_id, resultat)
    etat_postgres_test.enregistrer_decision(execution_id, "acceptee")

    etat_postgres_test.supprimer_instance(instance_id)

    try:
        etat_postgres_test.recuperer_instance(instance_id)
        raise AssertionError("KeyError attendu pour une instance supprimée")
    except KeyError:
        pass
    try:
        etat_postgres_test.recuperer_execution(execution_id)
        raise AssertionError("KeyError attendu pour une exécution cascade-supprimée")
    except KeyError:
        pass
    assert etat_postgres_test.decision_pour(execution_id) is None


def test_supprimer_instance_cascade_le_planning_associe(etat_postgres_test: EtatPostgres) -> None:
    instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())
    planning = Planning(operations=[OperationPlanifiee(tache="T1", ressource="R1", debut=0)])
    resultat = ResultatExecution(
        planning=planning, verdict_faisabilite=ResultatFaisabilite(violations=()), erreur=None
    )
    execution_id = etat_postgres_test.enregistrer_execution("solveur-abc", instance_id, resultat)

    etat_postgres_test.supprimer_instance(instance_id)

    try:
        etat_postgres_test.recuperer_execution(execution_id)
        raise AssertionError("KeyError attendu pour une exécution cascade-supprimée")
    except KeyError:
        pass


def test_supprimer_instance_orpheline_les_jobs_generation_sans_les_detruire(
    etat_postgres_test: EtatPostgres,
) -> None:
    instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())
    etat_postgres_test.enregistrer_job_generation("job-1", instance_id, "client-test")

    etat_postgres_test.supprimer_instance(instance_id)

    job = etat_postgres_test.recuperer_job_generation("job-1")  # survit, orphelin
    assert job.instance_id is None


# --- Propositions de l'agent de supervision (MT7) ---------------------------


def test_proposition_supervision_round_trip(etat_postgres_test: EtatPostgres) -> None:
    instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())

    proposition_id = etat_postgres_test.enregistrer_proposition(
        client_id="client-test",
        type_signal="signature_orpheline",
        action_suggeree="regenerer_solveur",
        resume="Aucun solveur ne correspond.",
        priorite="haute",
        details=("structure=compatibilite_ressource_tache",),
        instance_id=instance_id,
        structure_contraintes="compatibilite_ressource_tache",
        signature_objectifs="minimiser_makespan",
    )

    proposition = etat_postgres_test.recuperer_proposition(proposition_id)
    assert proposition.client_id == "client-test"
    assert proposition.type_signal == "signature_orpheline"
    assert proposition.action_suggeree == "regenerer_solveur"
    assert proposition.instance_id == instance_id
    assert proposition.details == ("structure=compatibilite_ressource_tache",)
    assert proposition.decision is None


def test_decider_proposition(etat_postgres_test: EtatPostgres) -> None:
    proposition_id = etat_postgres_test.enregistrer_proposition(
        client_id="client-test",
        type_signal="echecs_repetes",
        action_suggeree="diagnostiquer",
        resume="3 échecs consécutifs.",
        priorite="moyenne",
        details=(),
        execution_ids=("exec-1", "exec-2", "exec-3"),
    )

    etat_postgres_test.decider_proposition(proposition_id, "acceptee", commentaire="OK")
    proposition = etat_postgres_test.recuperer_proposition(proposition_id)

    assert proposition.decision == "acceptee"
    assert proposition.commentaire == "OK"
    assert proposition.horodatage_decision is not None
    assert proposition.execution_ids == ("exec-1", "exec-2", "exec-3")


def test_lister_propositions_filtre_en_attente(etat_postgres_test: EtatPostgres) -> None:
    id_en_attente = etat_postgres_test.enregistrer_proposition(
        client_id="client-test",
        type_signal="instance_a_replanifier",
        action_suggeree="executer",
        resume="À exécuter.",
        priorite="basse",
        details=(),
    )
    id_decidee = etat_postgres_test.enregistrer_proposition(
        client_id="client-test",
        type_signal="instance_a_replanifier",
        action_suggeree="executer",
        resume="À exécuter aussi.",
        priorite="basse",
        details=(),
    )
    etat_postgres_test.decider_proposition(id_decidee, "refusee")

    toutes = etat_postgres_test.lister_propositions(client_id="client-test")
    en_attente = etat_postgres_test.lister_propositions(client_id="client-test", en_attente_seulement=True)

    assert {p["proposition_id"] for p in toutes} == {id_en_attente, id_decidee}
    assert {p["proposition_id"] for p in en_attente} == {id_en_attente}


def test_supprimer_instance_orpheline_les_propositions_sans_les_detruire(
    etat_postgres_test: EtatPostgres,
) -> None:
    instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())
    proposition_id = etat_postgres_test.enregistrer_proposition(
        client_id="client-test",
        type_signal="signature_orpheline",
        action_suggeree="regenerer_solveur",
        resume="Aucun solveur ne correspond.",
        priorite="haute",
        details=(),
        instance_id=instance_id,
    )

    etat_postgres_test.supprimer_instance(instance_id)

    proposition = etat_postgres_test.recuperer_proposition(proposition_id)  # survit, orpheline
    assert proposition.instance_id is None
