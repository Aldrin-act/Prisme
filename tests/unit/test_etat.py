"""Couche 1 (§6.1) : `EtatAPI` (implémentation en mémoire) — couvre en
particulier l'inversion Projet↔Instance (§annexe modèle Instance/Projet) :
une instance est un gabarit réutilisable (règles métier d'un secteur donné),
un projet en réutilise une comme instance courante et porte son propre
planning attitré, indépendant des autres projets utilisant la même
instance. Miroir de `tests/integration/test_etat_postgres.py` (même
comportement attendu, juste sans Postgres).
"""

from __future__ import annotations

import pytest

from api.etat import ClientIncompatible, EtatAPI, InstanceEnUsage
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


def _projet_avec_instance(etat: EtatAPI, client_id: str) -> tuple[str, str]:
    instance_id = etat.enregistrer_instance(client_id, _instance_exemple())
    projet_id = etat.enregistrer_projet(client_id, donnees_brutes="")
    etat.associer_instance_projet(projet_id, instance_id)
    return projet_id, instance_id


def test_associer_instance_projet_fait_de_linstance_linstance_courante() -> None:
    etat = EtatAPI()
    projet_id, instance_id = _projet_avec_instance(etat, "client-test")

    assert etat.recuperer_projet(projet_id).instance_id == instance_id


def test_associer_instance_projet_refuse_client_incompatible() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-a", _instance_exemple())
    projet_id = etat.enregistrer_projet("client-b", donnees_brutes="")

    with pytest.raises(ClientIncompatible):
        etat.associer_instance_projet(projet_id, instance_id)


def test_deux_projets_partagent_une_instance_avec_historiques_independants() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    projet_a = etat.enregistrer_projet("client-test", donnees_brutes="")
    projet_b = etat.enregistrer_projet("client-test", donnees_brutes="")
    etat.associer_instance_projet(projet_a, instance_id)
    etat.associer_instance_projet(projet_b, instance_id)

    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur=None)
    etat.enregistrer_execution("solveur-abc", projet_a, instance_id, resultat)

    executions_a = [e for e in etat.lister_executions() if e["projet_id"] == projet_a]
    executions_b = [e for e in etat.lister_executions() if e["projet_id"] == projet_b]
    assert len(executions_a) == 1
    assert len(executions_b) == 0


def test_supprimer_instance_refuse_si_projet_la_reference() -> None:
    etat = EtatAPI()
    projet_id, instance_id = _projet_avec_instance(etat, "client-test")

    with pytest.raises(InstanceEnUsage):
        etat.supprimer_instance(instance_id)

    etat.recuperer_instance(instance_id)  # toujours là


def test_supprimer_instance_sevre_les_executions_historiques_sans_les_detruire() -> None:
    etat = EtatAPI()
    projet_id, instance_id = _projet_avec_instance(etat, "client-test")
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur=None)
    execution_id = etat.enregistrer_execution("solveur-abc", projet_id, instance_id, resultat)

    autre_instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    etat.associer_instance_projet(projet_id, autre_instance_id)  # détache pour pouvoir supprimer
    etat.supprimer_instance(instance_id)

    _, _, instance_id_relu, _ = etat.recuperer_execution(execution_id)
    assert instance_id_relu is None


def test_supprimer_projet_cascade_sa_propre_execution_sans_toucher_a_linstance() -> None:
    etat = EtatAPI()
    projet_id, instance_id = _projet_avec_instance(etat, "client-test")
    resultat = ResultatExecution(planning=None, verdict_faisabilite=None, erreur=None)
    execution_id = etat.enregistrer_execution("solveur-abc", projet_id, instance_id, resultat)

    etat.supprimer_projet(projet_id)

    with pytest.raises(KeyError):
        etat.recuperer_projet(projet_id)
    with pytest.raises(KeyError):
        etat.recuperer_execution(execution_id)
    etat.recuperer_instance(instance_id)  # survit, réutilisable par d'autres projets


def test_lister_projets_filtre_par_instance_courante() -> None:
    etat = EtatAPI()
    instance_id = etat.enregistrer_instance("client-test", _instance_exemple())
    projet_a = etat.enregistrer_projet("client-test", donnees_brutes="")
    etat.enregistrer_projet("client-test", donnees_brutes="")  # projet_b, sans instance associée
    etat.associer_instance_projet(projet_a, instance_id)

    projets_pour_instance = etat.lister_projets(instance_id=instance_id)
    assert [p["projet_id"] for p in projets_pour_instance] == [projet_a]
    assert projets_pour_instance[0]["structure_contraintes"] == "compatibilite_ressource_tache"
