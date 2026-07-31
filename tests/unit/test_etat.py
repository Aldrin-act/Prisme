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
from dsl.schema import InstanceTRCO
from sandbox.runner import ResultatExecution


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


def test_lister_executions_filtre_par_client_de_linstance() -> None:
    etat = EtatAPI()
    instance_a = etat.enregistrer_instance("client-a", _instance_exemple())
    instance_b = etat.enregistrer_instance("client-b", _instance_exemple())
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur=None)
    etat.enregistrer_execution("solveur-abc", instance_a, resultat)
    etat.enregistrer_execution("solveur-abc", instance_b, resultat)

    executions_a = etat.lister_executions(client_id="client-a")
    assert [e["instance_id"] for e in executions_a] == [instance_a]
