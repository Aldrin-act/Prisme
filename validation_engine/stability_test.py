"""Test de stabilité de génération (§6.5) : le même DSL, résolu N fois par le
même solveur, doit produire des plannings équivalents (mêmes propriétés,
même qualité — ici, même makespan). En Étape 6, cette mécanique tournera sur
N *générations* différentes du même code plutôt que N appels d'un solveur
déjà figé ; l'un et l'autre partagent le même critère : légalité à chaque
essai, et un seul makespan observé sur l'ensemble des essais.
"""

from __future__ import annotations

from dataclasses import dataclass

from dsl.schema import InstanceTRCO
from validation_engine.cascade import Solveur
from validation_engine.feasibility_checker import verifier_faisabilite
from validation_engine.makespan import calculer_makespan


@dataclass(frozen=True)
class ResultatStabilite:
    stable: bool
    makespans: tuple[int | None, ...]
    diagnostics: tuple[str, ...]


def tester_stabilite(solveur: Solveur, instance: InstanceTRCO, n_essais: int = 5) -> ResultatStabilite:
    """Exécute `solveur` `n_essais` fois sur `instance` et compare les résultats."""
    makespans: list[int | None] = []
    diagnostics: list[str] = []

    for essai in range(n_essais):
        planning = solveur(instance)
        if planning is None:
            makespans.append(None)
            diagnostics.append(f"essai {essai} : le solveur n'a produit aucun planning")
            continue

        verdict = verifier_faisabilite(instance, planning)
        if not verdict.legal:
            makespans.append(None)
            diagnostics.append(
                f"essai {essai} : planning illégal ({', '.join(v.type for v in verdict.violations)})"
            )
            continue

        makespans.append(calculer_makespan(instance, planning))

    valeurs_legales = [makespan for makespan in makespans if makespan is not None]
    stable = not diagnostics and len(valeurs_legales) == n_essais and len(set(valeurs_legales)) == 1
    return ResultatStabilite(stable=stable, makespans=tuple(makespans), diagnostics=tuple(diagnostics))
