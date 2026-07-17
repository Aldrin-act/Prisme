"""Couche 1 (§6.1), `integration/` : les causes "données" et "aucune" de la
boucle diagnostique (PH10-T3) ont besoin d'un solveur réellement sain sur le
banc synthétique et les cas de référence pour être isolées proprement — un
vrai solveur OR-Tools (`scripts/_solveur_minimal.py`, fixture de dev/démo/test),
donc `integration/` et pas `unit/` (voir `tests/unit/test_attribution.py`
pour les causes "code" et "specification_dsl", avec des solveurs bogués en
pur Python).
"""

from __future__ import annotations

from diagnostics import diagnostiquer
from dsl.schema import OperationPlanifiee, Planning
from scripts._solveur_minimal import resoudre
from validation_engine.synthetic_bench import generer_catalogue


def test_cause_attribuee_aux_donnees_quand_le_planning_de_production_est_illegal() -> None:
    # "taille_2_chaine_simple" a une vraie chaîne de précédence : mettre
    # toutes les opérations à l'instant 0 viole la précédence pour de bon
    # (contrairement à un cas à tâche unique, où ce serait encore légal).
    cas_bench = next(c for c in generer_catalogue() if c.nom == "taille_2_chaine_simple")
    # Planning de production corrompu : toutes les opérations à l'instant 0,
    # sans respecter la précédence — alors que le solveur lui-même est sain
    # (il n'a même pas été appelé pour produire ce planning fautif).
    planning_corrompu = Planning(
        operations=[
            OperationPlanifiee(tache=operation.tache, ressource=operation.ressource, debut=0)
            for operation in cas_bench.planning_optimal.operations
        ]
    )

    diagnostic = diagnostiquer(
        resoudre,
        cas_bench.instance,
        planning_corrompu,
        motif_declenchement="signalement humain : planning de production illisible",
    )

    assert diagnostic.cause == "donnees"
    assert diagnostic.details
    assert diagnostic.humain_decide


def test_aucune_cause_quand_solveur_et_planning_de_production_sont_sains() -> None:
    cas_bench = generer_catalogue()[0]

    diagnostic = diagnostiquer(
        resoudre,
        cas_bench.instance,
        cas_bench.planning_optimal,
        motif_declenchement="signalement humain : préférence non modélisée",
    )

    assert diagnostic.cause == "aucune"
    assert diagnostic.details == ()
    assert diagnostic.humain_decide
