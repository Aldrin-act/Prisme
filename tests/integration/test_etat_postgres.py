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
