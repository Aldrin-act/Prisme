from __future__ import annotations

from collections import defaultdict

from ortools.sat.python import cp_model

from dsl.schema import (
    Echeance,
    InstanceTRCO,
    OperationPlanifiee,
    Planning,
    Precedence,
    Ressource,
    Tache,
)


def resoudre(instance: InstanceTRCO) -> Planning | None:
    """Résout le FJSP pour une instance TRCO en minimisant le makespan."""
    model = cp_model.CpModel()

    # Calcul de l'horizon maximal
    horizon_max = sum(
        max(crt.duree for crt in instance.compatibilites_ressource_tache if crt.tache == tache)
        for tache in instance.taches
    )

    # Création des variables
    intervals, starts, ends, assignment, presence, makespan = _creer_variables(model, instance, horizon_max)

    # Ajout des contraintes
    _ajouter_contraintes(model, instance, intervals, starts, ends, assignment, presence, makespan)

    # Définition de l'objectif
    model.Minimize(makespan)

    # Résolution
    solver = cp_model.CpSolver()
    status = solver.Solve(model)

    # Extraction de la solution
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return _extraire_solution(solver, instance, intervals, assignment)
    else:
        return None


def _creer_variables(
    model: cp_model.CpModel, instance: InstanceTRCO, horizon_max: int
) -> tuple[
    dict[Tache, dict[Ressource, cp_model.IntervalVar]],
    dict[Tache, cp_model.IntVar],
    dict[Tache, cp_model.IntVar],
    dict[Tache, dict[Ressource, cp_model.IntVar]],
    dict[Tache, dict[Ressource, cp_model.IntVar]],
    cp_model.IntVar,
]:
    """Crée toutes les variables du modèle CP-SAT."""
    # Dictionnaires pour stocker les variables
    intervals = {}
    starts = {}
    ends = {}
    assignment = {}
    presence = {}

    # Pour chaque tâche, trouver les ressources compatibles et leurs durées
    ressources_compatibles = defaultdict(list)
    durees = {}
    for crt in instance.compatibilites_ressource_tache:
        ressources_compatibles[crt.tache].append(crt.ressource)
        durees[(crt.tache, crt.ressource)] = crt.duree

    # Création des variables pour chaque tâche
    for tache in instance.taches:
        # Variables de début et de fin
        starts[tache] = model.NewIntVar(0, horizon_max, f"start_{tache.id}")
        ends[tache] = model.NewIntVar(0, horizon_max, f"end_{tache.id}")

        # Variables d'assignment et de présence
        assignment[tache] = {}
        presence[tache] = {}
        intervals[tache] = {}

        for ressource in ressources_compatibles[tache]:
            duree = durees[(tache, ressource)]
            suffix = f"{tache.id}_{ressource.id}"

            # Variable d'intervalle
            interval = model.NewOptionalIntervalVar(
                starts[tache], duree, ends[tache], presence[tache][ressource], f"interval_{suffix}"
            )
            intervals[tache][ressource] = interval

            # Variable d'assignment
            assignment[tache][ressource] = model.NewBoolVar(f"assign_{suffix}")
            presence[tache][ressource] = model.NewBoolVar(f"presence_{suffix}")

    # Variable makespan
    makespan = model.NewIntVar(0, horizon_max, "makespan")

    return intervals, starts, ends, assignment, presence, makespan


def _ajouter_contraintes(
    model: cp_model.CpModel,
    instance: InstanceTRCO,
    intervals: dict[Tache, dict[Ressource, cp_model.IntervalVar]],
    starts: dict[Tache, cp_model.IntVar],
    ends: dict[Tache, cp_model.IntVar],
    assignment: dict[Tache, dict[Ressource, cp_model.IntVar]],
    presence: dict[Tache, dict[Ressource, cp_model.IntVar]],
    makespan: cp_model.IntVar,
) -> None:
    """Ajoute toutes les contraintes au modèle."""
    # Contrainte : chaque tâche est assignée à exactement une ressource compatible
    for tache in instance.taches:
        ressources_compatibles = [ressource for ressource in assignment[tache].keys()]
        model.AddExactlyOne(assignment[tache][r] for r in ressources_compatibles)

    # Lier les variables d'assignment aux variables de présence
    for tache in instance.taches:
        for ressource in assignment[tache]:
            model.Add(presence[tache][ressource] == assignment[tache][ressource])

    # Contraintes de précédence
    for contrainte in instance.contraintes:
        if isinstance(contrainte, Precedence):
            model.Add(starts[contrainte.successeur] >= ends[contrainte.predecesseur])

    # Contraintes de disjonction pour les ressources
    # Regrouper les intervalles par ressource
    intervalles_par_ressource = defaultdict(list)
    for tache in instance.taches:
        for ressource, interval in intervals[tache].items():
            intervalles_par_ressource[ressource].append(interval)

    for ressource, intervalles in intervalles_par_ressource.items():
        model.AddNoOverlap(intervalles)

    # Contraintes d'échéance
    for contrainte in instance.contraintes:
        if isinstance(contrainte, Echeance):
            model.Add(ends[contrainte.tache] <= contrainte.date)

    # Définition du makespan
    model.AddMaxEquality(makespan, [ends[tache] for tache in instance.taches])


def _extraire_solution(
    solver: cp_model.CpSolver,
    instance: InstanceTRCO,
    intervals: dict[Tache, dict[Ressource, cp_model.IntervalVar]],
    assignment: dict[Tache, dict[Ressource, cp_model.IntVar]],
) -> Planning:
    """Extrait la solution du solveur et construit l'objet Planning."""
    operations = []

    for tache in instance.taches:
        # Trouver la ressource assignée
        ressource_assignee = None
        for ressource, var in assignment[tache].items():
            if solver.Value(var):
                ressource_assignee = ressource
                break

        if ressource_assignee is None:
            raise ValueError(f"Aucune ressource assignée pour la tâche {tache.id}")

        # Récupérer le début de l'opération
        start = solver.Value(intervals[tache][ressource_assignee].StartExpr())

        operations.append(OperationPlanifiee(tache=tache, ressource=ressource_assignee, debut=start))

    return Planning(operations=operations)
