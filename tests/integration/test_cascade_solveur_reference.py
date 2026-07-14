"""Couche 1 (§6.1), `integration/` : exerce le solveur de référence réel
(OR-Tools CP-SAT) à travers la cascade complète — pas une pure fonction, donc
pas dans `unit/` (voir `tests/unit/test_cascade.py` pour les tests de la
cascade elle-même, sans dépendance à un moteur externe).

Critère de validation de l'Étape 5 : la cascade passe le solveur de
référence (Étape 4) au vert sur les trois briques à la fois.
"""

from __future__ import annotations

from dsl.schema import InstanceTRCO, Planning
from solveur_reference import resoudre
from validation_engine.cascade import evaluer_cascade


def test_solveur_reference_passe_la_cascade_au_vert() -> None:
    def solveur(instance: InstanceTRCO) -> Planning | None:
        return resoudre(instance).planning

    verdict = evaluer_cascade(solveur)

    assert verdict.reussi, verdict.echecs
