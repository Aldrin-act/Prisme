"""Couche 1 (§6.1), `integration/` : `executer_code_genere` exécute
réellement du code Python via OR-Tools, pas une fonction pure — d'où
`integration/` plutôt que `unit/` (voir `tests/unit/test_validation_statique.py`
pour la validation statique seule, sans dépendance externe).

Le code utilisé ici est écrit à la main (pas issu d'un LLM) : il sert
uniquement à vérifier le mécanisme générique — validation statique puis
`exec()` puis extraction de `resoudre` — indépendamment de la qualité de ce
qu'un LLM produirait réellement (voir `scripts/mesurer_taux_succes_generation.py`
pour ça).
"""

from __future__ import annotations

import pytest

from dsl.schema import InstanceTRCO, MinimiserMakespan, Ressource, Tache
from generation.executer import ErreurExecutionGeneree, executer_code_genere
from validation_engine.feasibility_checker import verifier_faisabilite

CODE_SOLVEUR_MINIMAL = """
from __future__ import annotations

from collections import defaultdict

from ortools.sat.python import cp_model

from dsl.schema import CompatibiliteMachineTache, OperationPlanifiee, Planning, Precedence


def resoudre(instance):
    modele = cp_model.CpModel()
    horizon = sum(tache.duree for tache in instance.taches)
    toutes_ressources = {ressource.id for ressource in instance.ressources}

    compat = defaultdict(set)
    for contrainte in instance.contraintes:
        if isinstance(contrainte, CompatibiliteMachineTache):
            compat[contrainte.tache].add(contrainte.ressource)

    debut = {}
    fin = {}
    presence = {}
    intervalles = defaultdict(list)

    for tache in instance.taches:
        candidats = compat.get(tache.id) or toutes_ressources
        d = modele.NewIntVar(0, horizon, f"debut_{tache.id}")
        f = modele.NewIntVar(0, horizon, f"fin_{tache.id}")
        modele.Add(f == d + tache.duree)
        debut[tache.id] = d
        fin[tache.id] = f

        presences_tache = []
        for ressource_id in candidats:
            p = modele.NewBoolVar(f"presence_{tache.id}_{ressource_id}")
            intervalle = modele.NewOptionalIntervalVar(d, tache.duree, f, p, f"iv_{tache.id}_{ressource_id}")
            intervalles[ressource_id].append(intervalle)
            presence[(tache.id, ressource_id)] = p
            presences_tache.append(p)
        modele.AddExactlyOne(presences_tache)

    for ressource in instance.ressources:
        modele.AddNoOverlap(intervalles[ressource.id])

    for contrainte in instance.contraintes:
        if isinstance(contrainte, Precedence):
            modele.Add(fin[contrainte.avant] <= debut[contrainte.apres])

    makespan = modele.NewIntVar(0, horizon, "makespan")
    modele.AddMaxEquality(makespan, list(fin.values()))
    modele.Minimize(makespan)

    solveur = cp_model.CpSolver()
    statut = solveur.Solve(modele)
    if statut not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    operations = []
    for tache in instance.taches:
        candidats = compat.get(tache.id) or toutes_ressources
        ressource_choisie = next(r for r in candidats if solveur.Value(presence[(tache.id, r)]))
        operations.append(
            OperationPlanifiee(tache=tache.id, ressource=ressource_choisie, debut=solveur.Value(debut[tache.id]))
        )
    return Planning(operations=operations)
"""


def test_code_valide_est_execute_et_resout_correctement() -> None:
    instance = InstanceTRCO(
        taches=[Tache(id="T1", duree=10)],
        ressources=[Ressource(id="M1")],
        contraintes=[],
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
