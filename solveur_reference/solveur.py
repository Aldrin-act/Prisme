"""Solveur CP-SAT de référence pour le noyau minimal (précédence, compatibilité
machine-tâche, durées, minimiser le makespan).

Étape volontairement absente de la roadmap (§8) mais jugée indispensable
avant de faire générer un solveur par l'IA (Étape 4) : (1) elle prouve que le
noyau est effectivement résoluble et calibre les attentes de performance ;
(2) elle devient un cas de référence pour la fidélité sémantique
(§6.2 brique 3) et la cible que le code généré devra égaler.

Ce module est **écrit à la main, définitivement** — contrairement au code
qui sortira de `generation/`, il n'est jamais figé/persisté par
`solver_store/` ni régénéré : il vit en dehors du cycle « générer une fois,
réexécuter ensuite » et sert d'étalon externe à ce cycle.

Modélisation FJSP classique en CP-SAT : un intervalle optionnel par couple
(tâche, ressource compatible), une contrainte « exactement une ressource
choisie » par tâche, une contrainte de non-chevauchement par ressource, la
précédence reliant les dates de début/fin réelles des tâches (pas les
intervalles par ressource), et le makespan comme maximum des fins.

Règle de compatibilité (à garder synchronisée avec
`validation_engine/feasibility_checker.py`, §6.7) : une tâche sans aucune
contrainte `CompatibiliteMachineTache` n'est pas restreinte — elle peut
utiliser n'importe quelle ressource déclarée dans l'instance.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from ortools.sat.python import cp_model

from dsl.schema import (
    CompatibiliteMachineTache,
    InstanceTRCO,
    OperationPlanifiee,
    Planning,
    Precedence,
)

StatutResolution = Literal["optimal", "faisable", "infaisable", "inconnu"]

_STATUTS_CP_SAT: dict[int, StatutResolution] = {
    cp_model.OPTIMAL: "optimal",
    cp_model.FEASIBLE: "faisable",
    cp_model.INFEASIBLE: "infaisable",
}


@dataclass(frozen=True)
class ResultatResolution:
    """Le résultat d'une résolution : statut, planning s'il existe, makespan, temps."""

    statut: StatutResolution
    planning: Planning | None
    makespan: int | None
    temps_resolution_s: float


def resoudre(instance: InstanceTRCO, limite_temps_s: float = 30.0) -> ResultatResolution:
    """Construit et résout le modèle CP-SAT du noyau minimal pour `instance`."""
    modele = cp_model.CpModel()

    horizon = sum(tache.duree for tache in instance.taches)
    toutes_ressources = {ressource.id for ressource in instance.ressources}

    ressources_compatibles: dict[str, set[str]] = defaultdict(set)
    for contrainte in instance.contraintes:
        if isinstance(contrainte, CompatibiliteMachineTache):
            ressources_compatibles[contrainte.tache].add(contrainte.ressource)

    debut_tache: dict[str, cp_model.IntVar] = {}
    fin_tache: dict[str, cp_model.IntVar] = {}
    presence_par_couple: dict[tuple[str, str], cp_model.BoolVarT] = {}
    intervalles_par_ressource: dict[str, list[cp_model.IntervalVar]] = defaultdict(list)

    for tache in instance.taches:
        # Pas de contrainte déclarée = pas de restriction (même règle que le
        # vérificateur de faisabilité, §6.7).
        candidats = ressources_compatibles.get(tache.id) or toutes_ressources

        debut = modele.NewIntVar(0, horizon, f"debut_{tache.id}")
        fin = modele.NewIntVar(0, horizon, f"fin_{tache.id}")
        modele.Add(fin == debut + tache.duree)
        debut_tache[tache.id] = debut
        fin_tache[tache.id] = fin

        presences = []
        for ressource_id in candidats:
            presence = modele.NewBoolVar(f"presence_{tache.id}_{ressource_id}")
            intervalle = modele.NewOptionalIntervalVar(
                debut, tache.duree, fin, presence, f"intervalle_{tache.id}_{ressource_id}"
            )
            intervalles_par_ressource[ressource_id].append(intervalle)
            presence_par_couple[(tache.id, ressource_id)] = presence
            presences.append(presence)
        modele.AddExactlyOne(presences)

    for ressource in instance.ressources:
        modele.AddNoOverlap(intervalles_par_ressource[ressource.id])

    for contrainte in instance.contraintes:
        if isinstance(contrainte, Precedence):
            modele.Add(fin_tache[contrainte.avant] <= debut_tache[contrainte.apres])

    makespan = modele.NewIntVar(0, horizon, "makespan")
    modele.AddMaxEquality(makespan, list(fin_tache.values()))
    modele.Minimize(makespan)

    solveur = cp_model.CpSolver()
    solveur.parameters.max_time_in_seconds = limite_temps_s

    debut_horloge = time.perf_counter()
    statut_brut = solveur.Solve(modele)
    temps_resolution_s = time.perf_counter() - debut_horloge

    statut = _STATUTS_CP_SAT.get(statut_brut, "inconnu")
    if statut not in ("optimal", "faisable"):
        return ResultatResolution(
            statut=statut, planning=None, makespan=None, temps_resolution_s=temps_resolution_s
        )

    operations: list[OperationPlanifiee] = []
    for tache in instance.taches:
        candidats = ressources_compatibles.get(tache.id) or toutes_ressources
        ressource_choisie = next(
            ressource_id
            for ressource_id in candidats
            if solveur.Value(presence_par_couple[(tache.id, ressource_id)])
        )
        operations.append(
            OperationPlanifiee(
                tache=tache.id,
                ressource=ressource_choisie,
                debut=solveur.Value(debut_tache[tache.id]),
            )
        )

    return ResultatResolution(
        statut=statut,
        planning=Planning(operations=operations),
        makespan=solveur.Value(makespan),
        temps_resolution_s=temps_resolution_s,
    )
