"""Couche 1 (§6.1), `integration/` : `executer_code_genere` exécute
réellement du code Python (`exec()`), pas une fonction pure — d'où
`integration/` plutôt que `unit/` (voir `tests/unit/test_validation_statique.py`
pour la validation statique seule).

Le code utilisé ici est écrit à la main (pas issu d'un LLM) : c'est le solveur heuristique de
`scripts/_solveur_minimal.py`, il sert
uniquement à vérifier le mécanisme générique — validation statique puis
`exec()` puis extraction de `resoudre` — indépendamment de la qualité de ce
qu'un LLM produirait réellement (voir `scripts/mesurer_taux_succes_generation.py`
pour ça).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, MinimiserMakespan, Ressource, Tache
from generation.executer import ErreurExecutionGeneree, executer_code_genere
from scripts import _solveur_minimal
from validation_engine.feasibility_checker import verifier_faisabilite

CODE_SOLVEUR_MINIMAL = Path(_solveur_minimal.__file__).read_text(encoding="utf-8")


def test_code_valide_est_execute_et_resout_correctement() -> None:
    instance = InstanceTRCO(
        taches=[Tache(id="T1")],
        ressources=[Ressource(id="R1")],
        contraintes=[CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10)],
        objectifs=[MinimiserMakespan()],
    )

    solveur = executer_code_genere(CODE_SOLVEUR_MINIMAL)
    planning = solveur(instance)

    assert planning is not None
    verdict = verifier_faisabilite(instance, planning)
    assert verdict.legal, verdict.violations


def test_code_qui_echoue_la_validation_statique_n_est_pas_execute() -> None:
    with pytest.raises(ErreurExecutionGeneree, match="validation statique refusée"):
        executer_code_genere("import os\n")


def test_code_sans_fonction_resoudre_est_rejete() -> None:
    with pytest.raises(ErreurExecutionGeneree, match="resoudre"):
        executer_code_genere("x = 1\n")
