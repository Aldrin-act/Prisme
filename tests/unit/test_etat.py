"""Couche 1 (§6.1) : `EtatAPI` (implémentation en mémoire) — couvre en
particulier `SourceDonnees` (données brutes persistées, rejouables via
l'agent de compréhension, sans historique d'exécution ni pointeur "instance
courante") et le fait qu'une instance possède désormais directement son
propre historique d'exécution, cascade-supprimé avec elle. Miroir de
`tests/integration/test_etat_postgres.py` (même comportement attendu, juste
sans Postgres).
"""

from __future__ import annotations

import pytest

from api.etat import EtatAPI
from dsl.schema import InstanceTRCO, MinimiserMakespan, OperationPlanifiee, Planning
from sandbox.runner import ResultatExecution
from validation_engine.feasibility_checker import ResultatFaisabilite


def _instance_exemple() -> InstanceTRCO:
    return InstanceTRCO.model_validate(
        {
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [
                {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            ],
            "objectifs": [{"type": "minimiser_makespan"}],
        }
    )


def test_description_metier_round_trip() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance(
        "client-test", _instance_exemple(), description_metier="Découpe puis assemblage de la pièce."
    )

    assert etat.recuperer_description_metier(instance_id) == "Découpe puis assemblage de la pièce."


def test_description_metier_absente_pour_une_ingestion_sans_agent() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())

    assert etat.recuperer_description_metier(instance_id) is None


def test_supprimer_instance_purge_sa_description_metier() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance(
        "client-test", _instance_exemple(), description_metier="Découpe puis assemblage de la pièce."
    )

    etat.supprimer_instance(instance_id)

    with pytest.raises(KeyError):
        etat.recuperer_description_metier(instance_id)


def test_enregistrer_instance_depuis_source_trace_la_provenance() -> None:
    etat = EtatAPI()
    source_id = etat.enregistrer_source("client-test", donnees_brutes="brut")
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple(), source_id=source_id)

    instances = etat.lister_instances_pour_source(source_id)
    assert [i["instance_id"] for i in instances] == [instance_id]
    assert instances[0]["structure_contraintes"] == "compatibilite_ressource_tache"


def test_lister_sources_compte_les_instances_generees() -> None:
    etat = EtatAPI()
    source_a = etat.enregistrer_source("client-test", donnees_brutes="brut-a")
    etat.enregistrer_source("client-test", donnees_brutes="brut-b")  # source_b, sans instance générée
    etat.enregistrer_instance("client-test", _instance_exemple(), source_id=source_a)
    etat.enregistrer_instance("client-test", _instance_exemple(), source_id=source_a)

    sources = etat.lister_sources(client_id="client-test")
    compteurs = {s["source_id"]: s["nb_instances"] for s in sources}
    assert compteurs[source_a] == 2


def test_supprimer_source_coupe_la_provenance_sans_toucher_a_linstance() -> None:
    etat = EtatAPI()
    source_id = etat.enregistrer_source("client-test", donnees_brutes="brut")
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple(), source_id=source_id)

    etat.supprimer_source(source_id)

    with pytest.raises(KeyError):
        etat.recuperer_source(source_id)
    etat.recuperer_instance(instance_id)  # survit, indépendante de sa source


def test_supprimer_instance_cascade_ses_executions() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur=None)
    execution_id = etat.enregistrer_execution("solveur-abc", instance_id, resultat)
    etat.enregistrer_decision(execution_id, "acceptee")

    etat.supprimer_instance(instance_id)

    with pytest.raises(KeyError):
        etat.recuperer_instance(instance_id)
    with pytest.raises(KeyError):
        etat.recuperer_execution(execution_id)
    assert etat.decision_pour(execution_id) is None


def test_supprimer_instance_orpheline_les_jobs_generation_sans_les_detruire() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    etat.enregistrer_job_generation("job-1", instance_id, "client-test")

    etat.supprimer_instance(instance_id)

    job = etat.recuperer_job_generation("job-1")  # survit, orphelin
    assert job.instance_id is None


def test_mettre_a_jour_job_generation_persiste_sans_marquer_termine() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    etat.enregistrer_job_generation("job-1", instance_id, "client-test")

    etat.mettre_a_jour_job_generation("job-1", specification="spec produite par l'analyste")

    job = etat.recuperer_job_generation("job-1")
    assert job.specification == "spec produite par l'analyste"
    assert job.termine is False


def test_terminer_job_generation_necrase_pas_un_champ_deja_persiste() -> None:
    """Un plantage en cours de pipeline (§6.6) passe `None` pour les champs
    de contenu non encore connus — ça ne doit jamais effacer ce qu'une
    capture partielle antérieure (`mettre_a_jour_job_generation`) a déjà
    sauvé."""
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    etat.enregistrer_job_generation("job-1", instance_id, "client-test")
    etat.mettre_a_jour_job_generation("job-1", specification="spec déjà produite")

    etat.terminer_job_generation("job-1", reussi=False, erreur="panne simulée")

    job = etat.recuperer_job_generation("job-1")
    assert job.specification == "spec déjà produite"
    assert job.termine is True
    assert job.erreur == "panne simulée"


def test_terminer_job_generation_persiste_la_documentation() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    etat.enregistrer_job_generation("job-1", instance_id, "client-test")

    etat.terminer_job_generation("job-1", reussi=True, documentation="Résumé et limites connues.")

    assert etat.recuperer_job_generation("job-1").documentation == "Résumé et limites connues."


def test_lister_executions_filtre_par_client_de_linstance() -> None:
    etat = EtatAPI()
    instance_a = etat.enregistrer_instance("client-a", _instance_exemple())
    instance_b = etat.enregistrer_instance("client-b", _instance_exemple())
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur=None)
    etat.enregistrer_execution("solveur-abc", instance_a, resultat)
    etat.enregistrer_execution("solveur-abc", instance_b, resultat)

    executions_a = etat.lister_executions(client_id="client-a")
    assert [e["instance_id"] for e in executions_a] == [instance_a]


def _instance_modifiee() -> InstanceTRCO:
    return InstanceTRCO.model_validate(
        {
            "taches": [{"id": "T1"}, {"id": "T2"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [
                {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 5},
                {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 5},
            ],
            "objectifs": [{"type": "minimiser_makespan"}],
        }
    )


def test_modifier_instance_round_trip() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())

    nouvelle_instance = _instance_modifiee()
    resultat = etat.modifier_instance(instance_id, nouvelle_instance)

    assert resultat is nouvelle_instance
    client_id, instance_relue = etat.recuperer_instance(instance_id)
    assert client_id == "client-test"
    assert [t.id for t in instance_relue.taches] == ["T1", "T2"]


def test_modifier_instance_preserve_lhistorique_dexecution() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur=None)
    execution_id = etat.enregistrer_execution("solveur-abc", instance_id, resultat)

    etat.modifier_instance(instance_id, _instance_modifiee())

    etat.recuperer_execution(execution_id)  # toujours présente, aucune cascade
    executions = etat.lister_executions(client_id="client-test")
    assert [e["execution_id"] for e in executions] == [execution_id]


def test_modifier_instance_inconnue_leve_key_error() -> None:
    etat = EtatAPI()

    with pytest.raises(KeyError):
        etat.modifier_instance("id-inexistant", _instance_modifiee())


def test_dernier_planning_pour_instance_absente_renvoie_none() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())

    assert etat.dernier_planning_pour_instance(instance_id) is None


def test_dernier_planning_pour_instance_ignore_les_executions_echouees() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    echec = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="instance infaisable")
    etat.enregistrer_execution("solveur-abc", instance_id, echec)

    assert etat.dernier_planning_pour_instance(instance_id) is None


def test_dernier_planning_pour_instance_prend_la_plus_recente_reussie() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    planning_ancien = Planning(operations=[OperationPlanifiee(tache="T1", ressource="R1", debut=0)])
    planning_recent = Planning(operations=[OperationPlanifiee(tache="T1", ressource="R1", debut=5)])
    verdict_legal = ResultatFaisabilite(violations=())
    etat.enregistrer_execution("solveur-abc", instance_id, ResultatExecution(planning_ancien, verdict_legal, None))
    etat.enregistrer_execution("solveur-abc", instance_id, ResultatExecution(planning_recent, verdict_legal, None))

    assert etat.dernier_planning_pour_instance(instance_id) == planning_recent


def test_planning_ajuste_absent_renvoie_none() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="instance infaisable")
    execution_id = etat.enregistrer_execution("solveur-abc", instance_id, resultat)

    assert etat.recuperer_planning_ajuste(execution_id) is None


def test_planning_ajuste_round_trip() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="instance infaisable")
    execution_id = etat.enregistrer_execution("solveur-abc", instance_id, resultat)
    planning_ajuste = Planning(operations=[OperationPlanifiee(tache="T1", ressource="R1", debut=7)])

    etat.enregistrer_planning_ajuste(execution_id, planning_ajuste)

    assert etat.recuperer_planning_ajuste(execution_id) == planning_ajuste


def test_planning_ajuste_ecrase_la_revision_precedente() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="instance infaisable")
    execution_id = etat.enregistrer_execution("solveur-abc", instance_id, resultat)
    etat.enregistrer_planning_ajuste(
        execution_id, Planning(operations=[OperationPlanifiee(tache="T1", ressource="R1", debut=0)])
    )

    planning_recent = Planning(operations=[OperationPlanifiee(tache="T1", ressource="R1", debut=9)])
    etat.enregistrer_planning_ajuste(execution_id, planning_recent)

    assert etat.recuperer_planning_ajuste(execution_id) == planning_recent


def test_supprimer_instance_purge_le_planning_ajuste() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="instance infaisable")
    execution_id = etat.enregistrer_execution("solveur-abc", instance_id, resultat)
    etat.enregistrer_planning_ajuste(
        execution_id, Planning(operations=[OperationPlanifiee(tache="T1", ressource="R1", debut=0)])
    )

    etat.supprimer_instance(instance_id)

    assert execution_id not in etat.plannings_ajustes


def test_date_modification_posee_a_la_creation() -> None:
    etat = EtatAPI()
    etat.enregistrer_instance("client-test", _instance_exemple())

    instances = etat.lister_instances(client_id="client-test")
    assert instances[0]["date_modification"] is not None


def test_date_modification_mise_a_jour_par_modifier_instance() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    etat.dates_modification[instance_id] = "2020-01-01T00:00:00"  # forcer une valeur antérieure connue

    etat.modifier_instance(instance_id, _instance_modifiee())

    nouvelle_date = etat.lister_instances(client_id="client-test")[0]["date_modification"]
    assert nouvelle_date != "2020-01-01T00:00:00"


def test_date_modification_mise_a_jour_par_modifier_objectifs() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    etat.dates_modification[instance_id] = "2020-01-01T00:00:00"

    etat.modifier_objectifs(instance_id, [MinimiserMakespan()])

    nouvelle_date = etat.lister_instances(client_id="client-test")[0]["date_modification"]
    assert nouvelle_date != "2020-01-01T00:00:00"


def test_supprimer_instance_purge_sa_date_modification() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())

    etat.supprimer_instance(instance_id)

    assert instance_id not in etat.dates_modification
