"""Couche 1 (§6.1), `integration/` : le second niveau du banc synthétique
(§6.4, PH3-T3) n'a pas d'optimum connu — sa vérité terrain est plus faible
que le niveau 1 (`construction_inverse.py`) : seule la faisabilité (Étape 2)
du planning produit par un solveur réel est garantie vérifiable, jamais son
optimalité. Exerce le solveur de référence réel (OR-Tools), donc
`integration/` et pas `unit/` (voir `tests/unit/test_synthetic_bench.py`
pour la validation structurelle seule, sans moteur externe).
"""

from __future__ import annotations

from solveur_reference import resoudre
from validation_engine.feasibility_checker import verifier_faisabilite
from validation_engine.synthetic_bench import generer_catalogue_faisabilite_seule


def test_solveur_reference_produit_un_planning_legal_sur_le_niveau_faisabilite_seule() -> None:
    for cas in generer_catalogue_faisabilite_seule():
        planning = resoudre(cas.instance, limite_temps_s=10.0)

        assert planning is not None, cas.nom
        verdict = verifier_faisabilite(cas.instance, planning)
        assert verdict.legal, (cas.nom, verdict.violations)
