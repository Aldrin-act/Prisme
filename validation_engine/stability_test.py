"""Test de stabilité de génération (§6.5) : le même DSL, résolu N fois par le
même solveur, doit produire des plannings équivalents (mêmes propriétés,
même qualité — ici, même makespan). En Étape 6, cette mécanique tournera sur
N *générations* différentes du même code plutôt que N appels d'un solveur
déjà figé ; l'un et l'autre partagent le même critère : légalité à chaque
essai, et un seul makespan observé sur l'ensemble des essais.

En plus du verdict tout-ou-rien (`stable`), `ResultatStabilite.taux_generations_valides`
expose la métrique quantifiable demandée par PH5-T4 (« taux de générations
valides sur N essais ») — utile pour le mémoire même quand `stable` est faux :
un solveur peut être légal 4 essais sur 5 (taux = 0.8) sans être stable pour
autant (si le makespan légal varie).
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

    @property
    def taux_generations_valides(self) -> float:
        """La part des essais ayant produit un planning légal (Étape 2), sur
        l'ensemble des essais — la métrique quantifiable exposée pour PH5-T4,
        indépendante de `stable` (un solveur peut être majoritairement légal
        sans être stable, si le makespan légal varie d'un essai à l'autre)."""
        if not self.makespans:
            return 0.0
        essais_valides = sum(1 for makespan in self.makespans if makespan is not None)
        return essais_valides / len(self.makespans)


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
