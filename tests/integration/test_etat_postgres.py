"""Tests d'intégration pour `api/etat_postgres.py` (§7, extension du modèle
conceptuel) : vérifie que `EtatPostgres` respecte exactement le contrat
d'`EtatAPI` (mêmes méthodes, mêmes types de retour), une fois passé par une
vraie base Postgres plutôt que par un dict en mémoire.
"""

from __future__ import annotations

import pytest

from api.etat import ClientIncompatible, InstanceEnUsage
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


def _projet_avec_instance(
    etat: EtatPostgres, client_id: str, instance: InstanceTRCO | None = None
) -> tuple[str, str]:
    """Aide commune : une instance, un projet qui la réutilise comme
    instance courante (§annexe modèle Instance/Projet) — le chemin obligé
    depuis l'inversion Projet↔Instance pour pouvoir exécuter."""
    instance_id = etat.enregistrer_instance(client_id, instance or _instance_exemple())
    projet_id = etat.enregistrer_projet(client_id, donnees_brutes="")
    etat.associer_instance_projet(projet_id, instance_id)
    return projet_id, instance_id


def test_instance_round_trip(etat_postgres_test: EtatPostgres) -> None:
    instance = _instance_exemple()
    instance_id = etat_postgres_test.enregistrer_instance("client-test", instance)

    client_id, instance_relue = etat_postgres_test.recuperer_instance(instance_id)

    assert client_id == "client-test"
    assert [t.id for t in instance_relue.taches] == ["T1", "T2"]
    assert len(instance_relue.contraintes) == 3


def test_recuperer_instance_inconnue_leve_key_error(etat_postgres_test: EtatPostgres) -> None:
    try:
        etat_postgres_test.recuperer_instance("id-inexistant")
    except KeyError:
        return
    raise AssertionError("KeyError attendu pour une instance inconnue")


def test_execution_reussie_round_trip_avec_planning(etat_postgres_test: EtatPostgres) -> None:
    projet_id, instance_id = _projet_avec_instance(etat_postgres_test, "client-test")
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

    execution_id = etat_postgres_test.enregistrer_execution("solveur-abc", projet_id, instance_id, resultat)
    id_solveur, projet_id_relu, instance_id_relu, resultat_relu = etat_postgres_test.recuperer_execution(
        execution_id
    )

    assert id_solveur == "solveur-abc"
    assert projet_id_relu == projet_id
    assert instance_id_relu == instance_id
    assert resultat_relu.reussi
    assert resultat_relu.planning is not None
    assert len(resultat_relu.planning.operations) == 2
    assert resultat_relu.verdict_faisabilite is not None
    assert resultat_relu.verdict_faisabilite.legal


def test_execution_en_echec_round_trip_sans_planning(etat_postgres_test: EtatPostgres) -> None:
    projet_id, instance_id = _projet_avec_instance(etat_postgres_test, "client-test")
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

    execution_id = etat_postgres_test.enregistrer_execution("solveur-abc", projet_id, instance_id, resultat)
    _, _, _, resultat_relu = etat_postgres_test.recuperer_execution(execution_id)

    assert resultat_relu.planning is None
    assert resultat_relu.verdict_faisabilite is not None
    assert not resultat_relu.verdict_faisabilite.legal
    assert resultat_relu.verdict_faisabilite.violations[0].message == "pas de ressource compatible"


def test_lister_instances_et_executions(etat_postgres_test: EtatPostgres) -> None:
    projet_id, instance_id = _projet_avec_instance(etat_postgres_test, "client-test")
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="erreur d'exécution")
    etat_postgres_test.enregistrer_execution("solveur-abc", projet_id, instance_id, resultat)

    instances = etat_postgres_test.lister_instances()
    assert len(instances) == 1
    assert instances[0]["executee"] is True
    assert instances[0]["structure_contraintes"] == "compatibilite_ressource_tache,precedence"

    executions = etat_postgres_test.lister_executions()
    assert len(executions) == 1
    assert executions[0]["projet_id"] == projet_id
    assert executions[0]["reussi"] is False
    assert executions[0]["erreur"] == "erreur d'exécution"
    assert executions[0]["decision"] is None


def test_decision_humaine(etat_postgres_test: EtatPostgres) -> None:
    projet_id, instance_id = _projet_avec_instance(etat_postgres_test, "client-test")
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur="peu importe")
    execution_id = etat_postgres_test.enregistrer_execution("solveur-abc", projet_id, instance_id, resultat)

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


# --- Inversion Projet↔Instance : une instance est un gabarit réutilisable,
# chaque projet qui la réutilise a son propre planning attitré (§annexe) ---


def test_deux_projets_partagent_une_instance_avec_historiques_independants(
    etat_postgres_test: EtatPostgres,
) -> None:
    instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())
    projet_a = etat_postgres_test.enregistrer_projet("client-test", donnees_brutes="")
    projet_b = etat_postgres_test.enregistrer_projet("client-test", donnees_brutes="")
    etat_postgres_test.associer_instance_projet(projet_a, instance_id)
    etat_postgres_test.associer_instance_projet(projet_b, instance_id)

    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur=None)
    etat_postgres_test.enregistrer_execution("solveur-abc", projet_a, instance_id, resultat)

    assert len(etat_postgres_test.lister_instances_pour_projet(projet_a)) == 0  # historique de génération, pas ça
    assert etat_postgres_test.recuperer_projet(projet_a).instance_id == instance_id
    assert etat_postgres_test.recuperer_projet(projet_b).instance_id == instance_id

    executions_a = [e for e in etat_postgres_test.lister_executions() if e["projet_id"] == projet_a]
    executions_b = [e for e in etat_postgres_test.lister_executions() if e["projet_id"] == projet_b]
    assert len(executions_a) == 1
    assert len(executions_b) == 0  # projet_b n'a exécuté rien de son côté, historique indépendant


def test_associer_instance_projet_refuse_client_incompatible(etat_postgres_test: EtatPostgres) -> None:
    instance_id = etat_postgres_test.enregistrer_instance("client-a", _instance_exemple())
    projet_id = etat_postgres_test.enregistrer_projet("client-b", donnees_brutes="")

    with pytest.raises(ClientIncompatible):
        etat_postgres_test.associer_instance_projet(projet_id, instance_id)


def test_supprimer_instance_refuse_si_projet_la_reference(etat_postgres_test: EtatPostgres) -> None:
    projet_id, instance_id = _projet_avec_instance(etat_postgres_test, "client-test")

    with pytest.raises(InstanceEnUsage):
        etat_postgres_test.supprimer_instance(instance_id)

    # Toujours là, aucune suppression partielle.
    etat_postgres_test.recuperer_instance(instance_id)
    assert etat_postgres_test.recuperer_projet(projet_id).instance_id == instance_id


def test_supprimer_instance_sevre_les_executions_historiques_sans_les_detruire(
    etat_postgres_test: EtatPostgres,
) -> None:
    projet_id, instance_id = _projet_avec_instance(etat_postgres_test, "client-test")
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur=None)
    execution_id = etat_postgres_test.enregistrer_execution("solveur-abc", projet_id, instance_id, resultat)

    # Détache le projet avant de pouvoir supprimer (autre instance quelconque).
    autre_instance_id = etat_postgres_test.enregistrer_instance("client-test", _instance_exemple())
    etat_postgres_test.associer_instance_projet(projet_id, autre_instance_id)

    etat_postgres_test.supprimer_instance(instance_id)

    # L'exécution survit — elle appartient au projet, jamais à l'instance —
    # seule sa référence informative `instance_id` est coupée.
    _, _, instance_id_relu, _ = etat_postgres_test.recuperer_execution(execution_id)
    assert instance_id_relu is None


def test_supprimer_projet_cascade_sa_propre_execution_sans_toucher_a_linstance(
    etat_postgres_test: EtatPostgres,
) -> None:
    projet_id, instance_id = _projet_avec_instance(etat_postgres_test, "client-test")
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur=None)
    execution_id = etat_postgres_test.enregistrer_execution("solveur-abc", projet_id, instance_id, resultat)

    etat_postgres_test.supprimer_projet(projet_id)

    with pytest.raises(KeyError):
        etat_postgres_test.recuperer_projet(projet_id)
    with pytest.raises(KeyError):
        etat_postgres_test.recuperer_execution(execution_id)
    # L'instance, elle, survit — réutilisable par d'autres projets.
    etat_postgres_test.recuperer_instance(instance_id)
