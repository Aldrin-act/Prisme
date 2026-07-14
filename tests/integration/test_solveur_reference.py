"""Couche 1 (§6.1) : le solveur de référence est écrit à la main — mais ce
test vit dans `integration/`, pas `unit/`, parce qu'il exerce un moteur
externe réel (OR-Tools CP-SAT), pas une fonction pure. Critère de
validation : retrouve l'optimum connu par construction (Étape 3) sur chaque
instance du banc synthétique, et produit un planning que le vérificateur de
faisabilité (Étape 2) confirme légal — les trois étapes bouclées ensemble.
"""

from __future__ import annotations

from solveur_reference import resoudre
from validation_engine.feasibility_checker import verifier_faisabilite
from validation_engine.synthetic_bench import generer_catalogue


def test_solveur_reference_retrouve_l_optimum_connu() -> None:
    for cas in generer_catalogue():
        resultat = resoudre(cas.instance, limite_temps_s=10.0)

        assert resultat.statut == "optimal", (cas.nom, resultat.statut)
        assert resultat.makespan == cas.optimum, (cas.nom, resultat.makespan, cas.optimum)

        assert resultat.planning is not None
        verdict = verifier_faisabilite(cas.instance, resultat.planning)
        assert verdict.legal, (cas.nom, verdict.violations)
