"""Couche 1 (§6.1) : parties pures et déterministes de l'agent Benchmarker,
et `benchmarker_algorithmes` lui-même via un faux modèle (voir
`tests/unit/aides_test_agents.py`) — aucun appel LLM réel."""

from __future__ import annotations

import json

import pytest

from dsl.schema import InstanceTRCO
from generation.agents import benchmarker
from generation.agents.benchmarker import (
    ErreurReponseAgentInvalide,
    analyser_caracteristiques_instance,
    creer_instance_exemple_defaut,
    parametres_cascade_pour_algorithme,
)
from tests.unit.aides_test_agents import ModeleFactice


def test_parametres_cascade_pour_algorithme_cp_sat_est_strict() -> None:
    assert parametres_cascade_pour_algorithme("cp_sat") == (0.0, True)


@pytest.mark.parametrize(
    "algorithme",
    ["genetic", "aco", "simulated_annealing", "tabu_search", "dispatching", "greedy_local", "inconnu"],
)
def test_parametres_cascade_pour_algorithme_algorithme_approche(algorithme: str) -> None:
    assert parametres_cascade_pour_algorithme(algorithme) == (0.10, False)


def test_creer_instance_exemple_defaut_est_une_instance_valide() -> None:
    instance_dict = creer_instance_exemple_defaut()
    instance = InstanceTRCO.model_validate(instance_dict)
    assert len(instance.taches) == 10
    assert len(instance.ressources) == 5


def test_creer_instance_exemple_defaut_est_classee_petite() -> None:
    carac = analyser_caracteristiques_instance(creer_instance_exemple_defaut())
    assert carac.taille_categorie == "petite"


@pytest.mark.parametrize(
    ("nb_taches", "categorie_attendue"),
    [(10, "petite"), (60, "moyenne"), (300, "grande"), (1200, "très grande")],
)
def test_analyser_caracteristiques_instance_classifie_par_taille(nb_taches: int, categorie_attendue: str) -> None:
    instance_json = {
        "taches": [{"id": f"T{i}"} for i in range(nb_taches)],
        "ressources": [{"id": "R1"}],
        "contraintes": [
            {"type": "compatibilite_ressource_tache", "tache": f"T{i}", "ressource": "R1", "duree": 10}
            for i in range(nb_taches)
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }
    carac = analyser_caracteristiques_instance(instance_json)
    assert carac.nb_taches == nb_taches
    assert carac.taille_categorie == categorie_attendue


def _instance_minimale_avec_objectifs(objectifs: list[dict]) -> dict:
    return {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}],
        "objectifs": objectifs,
    }


def test_analyser_caracteristiques_instance_sans_objectifs() -> None:
    carac = analyser_caracteristiques_instance(_instance_minimale_avec_objectifs([]))
    assert carac.types_objectifs == ()
    assert carac.nb_objectifs == 0
    assert carac.equilibrage_methode_approchee_en_cpsat is False


def test_analyser_caracteristiques_instance_objectifs_combines_tries_et_distincts() -> None:
    instance_json = _instance_minimale_avec_objectifs(
        [
            {"type": "minimiser_makespan", "poids": 0.7},
            {"type": "equilibrer_charge", "poids": 0.3, "methode": "ecart_max"},
        ]
    )
    carac = analyser_caracteristiques_instance(instance_json)
    assert carac.types_objectifs == ("equilibrer_charge", "minimiser_makespan")
    assert carac.nb_objectifs == 2
    assert carac.equilibrage_methode_approchee_en_cpsat is False


@pytest.mark.parametrize("methode", ["variance", "gini"])
def test_analyser_caracteristiques_instance_detecte_equilibrage_approche_en_cpsat(methode: str) -> None:
    instance_json = _instance_minimale_avec_objectifs([{"type": "equilibrer_charge", "methode": methode}])
    carac = analyser_caracteristiques_instance(instance_json)
    assert carac.equilibrage_methode_approchee_en_cpsat is True


def test_analyser_caracteristiques_instance_equilibrage_ecart_max_nest_pas_approche() -> None:
    instance_json = _instance_minimale_avec_objectifs([{"type": "equilibrer_charge", "methode": "ecart_max"}])
    carac = analyser_caracteristiques_instance(instance_json)
    assert carac.equilibrage_methode_approchee_en_cpsat is False


def test_benchmarker_algorithmes_construit_le_resultat_depuis_le_schema() -> None:
    schema = benchmarker._SchemaBenchmark(
        recommandation=benchmarker._SchemaRecommandation(
            algorithme="genetic",
            raison="Instance trop grande pour CP-SAT.",
            parametres={"population_size": 300},
            temps_estime="minutes",
            qualite_attendue="très bonne (>95%)",
            alternatives=["aco", "tabu_search"],
        ),
        comparaison="| Algo | Qualité |\n|---|---|",
    )
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = benchmarker.benchmarker_algorithmes(modele, creer_instance_exemple_defaut())

    assert resultat.recommandation.algorithme == "genetic"
    assert resultat.recommandation.parametres_suggeres == {"population_size": 300}
    assert resultat.recommandation.alternatives == ["aco", "tabu_search"]
    assert resultat.comparaison == "| Algo | Qualité |\n|---|---|"
    assert resultat.caracteristiques.nb_taches == 10


def test_benchmarker_algorithmes_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(ErreurReponseAgentInvalide, match="pas du JSON valide"):
        benchmarker.benchmarker_algorithmes(modele, creer_instance_exemple_defaut())
