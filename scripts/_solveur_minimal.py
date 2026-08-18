"""Solveur CP-SAT minimal — **fixture de dev/démo/test, pas un composant du
système** (aucune route API n'en dépend). Préfixé `_` : pas un script
autonome comme les autres modules de `scripts/`, juste un module partagé
entre `enregistrer_solveur_reference.py` et quelques tests qui ont besoin
d'un "solveur réel connu-bon" pour prouver autre chose que la résolution
elle-même (le bouclage store→sandbox→garde-fou de l'Étape 7, l'attribution
de cause "données"/"aucune" du diagnostic, le niveau "faisabilité seule" du
banc synthétique) — même rôle que les solveurs bogués en pur Python de
`tests/unit/test_attribution.py`, juste correct au lieu de délibérément
cassé. Reste sous l'allowlist AST de `generation/validation_statique.py`
(ortools, dsl, collections, dataclasses, typing) : un test peut le geler et
l'exécuter en sandbox comme n'importe quel code généré.
"""

from __future__ import annotations

from collections import defaultdict

from ortools.sat.python import cp_model

from dsl.schema import (
    CompatibiliteRessourceTache,
    InstanceTRCO,
    OperationPlanifiee,
    Planning,
    Precedence,
)


def resoudre(
    instance: InstanceTRCO,
    limite_temps_s: float = 30.0,
    planning_precedent: Planning | None = None,
    horizon_gele_jours: int = 0,
) -> Planning | None:
    """Modélisation FJSP classique en CP-SAT — voir `dsl.schema.InstanceTRCO` :
    un intervalle optionnel par couple (tâche, ressource compatible), une
    ressource choisie par tâche, non-chevauchement par ressource,
    précédence, minimisation du makespan.

    `planning_precedent`/`horizon_gele_jours` (Phase 2, replanification à horizon glissant,
    additif — `resoudre(instance)`/`resoudre(instance, limite_temps_s=...)` continuent de
    marcher sans changement) : toute opération de `planning_precedent` dont `debut <
    horizon_gele_jours` est fixée (même ressource, même début), voir
    `generation/prompts/generation_solveur.md`."""
    modele = cp_model.CpModel()

    ressources_compatibles: dict[str, set[str]] = defaultdict(set)
    duree: dict[tuple[str, str], int] = {}
    for contrainte in instance.contraintes:
        if isinstance(contrainte, CompatibiliteRessourceTache):
            ressources_compatibles[contrainte.tache].add(contrainte.ressource)
            duree[(contrainte.tache, contrainte.ressource)] = contrainte.duree

    horizon = sum(max(duree[(tache.id, r)] for r in ressources_compatibles[tache.id]) for tache in instance.taches)

    debut_tache: dict[str, cp_model.IntVar] = {}
    fin_tache: dict[str, cp_model.IntVar] = {}
    presence_par_couple: dict[tuple[str, str], cp_model.BoolVarT] = {}
    intervalles_par_ressource: dict[str, list[cp_model.IntervalVar]] = defaultdict(list)

    for tache in instance.taches:
        candidats = ressources_compatibles[tache.id]  # non vide : garanti par InstanceTRCO (§6.7)

        debut = modele.NewIntVar(0, horizon, f"debut_{tache.id}")
        fin = modele.NewIntVar(0, horizon, f"fin_{tache.id}")
        debut_tache[tache.id] = debut
        fin_tache[tache.id] = fin

        presences = []
        for ressource_id in candidats:
            d = duree[(tache.id, ressource_id)]
            presence = modele.NewBoolVar(f"presence_{tache.id}_{ressource_id}")
            intervalle = modele.NewOptionalIntervalVar(
                debut, d, fin, presence, f"intervalle_{tache.id}_{ressource_id}"
            )
            intervalles_par_ressource[ressource_id].append(intervalle)
            presence_par_couple[(tache.id, ressource_id)] = presence
            presences.append(presence)
        modele.AddExactlyOne(presences)

    if horizon_gele_jours > 0 and planning_precedent is not None:
        for operation in planning_precedent.operations:
            if operation.debut >= horizon_gele_jours:
                continue
            couple = (operation.tache, operation.ressource)
            if couple not in presence_par_couple:
                continue  # tâche/ressource plus valide dans l'instance courante
            modele.Add(presence_par_couple[couple] == 1)
            modele.Add(debut_tache[operation.tache] == operation.debut)

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
    statut = solveur.Solve(modele)

    if statut not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    operations = [
        OperationPlanifiee(
            tache=tache.id,
            ressource=next(
                ressource_id
                for ressource_id in ressources_compatibles[tache.id]
                if solveur.Value(presence_par_couple[(tache.id, ressource_id)])
            ),
            debut=solveur.Value(debut_tache[tache.id]),
        )
        for tache in instance.taches
    ]
    return Planning(operations=operations)
