"""Couche 1 (§6.1) : `api.comparaison_scenarios` est calcul pur sur une instance et un planning
déjà produits — aucune E/S, aucun appel solveur."""

from __future__ import annotations

from api.comparaison_scenarios import calculer_metriques
from dsl.schema import (
    CompatibiliteRessourceTache,
    Echeance,
    InstanceTRCO,
    MinimiserMakespan,
    OperationPlanifiee,
    Planning,
    Ressource,
    Tache,
)


def _instance(**overrides: object) -> InstanceTRCO:
    base: dict[str, object] = {
        "taches": [Tache(id="T1"), Tache(id="T2")],
        "ressources": [Ressource(id="R1"), Ressource(id="R2")],
        "contraintes": [
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=5),
            CompatibiliteRessourceTache(tache="T2", ressource="R2", duree=3),
        ],
        "objectifs": [MinimiserMakespan()],
    }
    base.update(overrides)
    return InstanceTRCO(**base)


def _planning(*operations: OperationPlanifiee) -> Planning:
    return Planning(operations=list(operations))


def test_makespan_est_la_fin_de_la_derniere_operation() -> None:
    instance = _instance()
    planning = _planning(
        OperationPlanifiee(tache="T1", ressource="R1", debut=0),  # fin = 5
        OperationPlanifiee(tache="T2", ressource="R2", debut=5),  # fin = 8
    )

    metriques = calculer_metriques(instance, planning)

    assert metriques.makespan == 8


def test_taux_utilisation_par_ressource_relatif_au_makespan() -> None:
    instance = _instance()
    planning = _planning(
        OperationPlanifiee(tache="T1", ressource="R1", debut=0),  # occupe R1 5/10
        OperationPlanifiee(tache="T2", ressource="R2", debut=7),  # occupe R2 3/10, fin=10
    )

    metriques = calculer_metriques(instance, planning)

    assert metriques.makespan == 10
    assert metriques.taux_utilisation_par_ressource == {"R1": 50.0, "R2": 30.0}


def test_planning_vide_donne_un_makespan_nul_sans_lever() -> None:
    instance = _instance()
    metriques = calculer_metriques(instance, _planning())

    assert metriques.makespan == 0
    assert metriques.taux_utilisation_par_ressource == {}
    assert metriques.taches_en_retard == ()


def test_tache_en_retard_detectee() -> None:
    instance = _instance(
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=5),
            CompatibiliteRessourceTache(tache="T2", ressource="R2", duree=3),
            Echeance(tache="T1", echeance=3),  # T1 finit à 5, en retard sur 3
        ]
    )
    planning = _planning(OperationPlanifiee(tache="T1", ressource="R1", debut=0))

    metriques = calculer_metriques(instance, planning)

    assert metriques.taches_en_retard == ("T1",)


def test_tache_dans_les_temps_n_est_pas_en_retard() -> None:
    instance = _instance(
        contraintes=[
            CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=5),
            CompatibiliteRessourceTache(tache="T2", ressource="R2", duree=3),
            Echeance(tache="T1", echeance=5),  # T1 finit pile à 5 : respectée
        ]
    )
    planning = _planning(OperationPlanifiee(tache="T1", ressource="R1", debut=0))

    metriques = calculer_metriques(instance, planning)

    assert metriques.taches_en_retard == ()


def test_tache_sans_echeance_declaree_ne_peut_jamais_etre_en_retard() -> None:
    instance = _instance()  # aucune Echeance déclarée
    planning = _planning(OperationPlanifiee(tache="T1", ressource="R1", debut=0))

    metriques = calculer_metriques(instance, planning)

    assert metriques.taches_en_retard == ()


def test_en_dict_serialise_tous_les_champs() -> None:
    instance = _instance()
    planning = _planning(OperationPlanifiee(tache="T1", ressource="R1", debut=0))

    metriques = calculer_metriques(instance, planning)
    resultat = metriques.en_dict()

    assert resultat == {
        "makespan": 5,
        "taux_utilisation_par_ressource": {"R1": 100.0},
        "taches_en_retard": [],
    }
