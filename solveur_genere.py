from __future__ import annotations
from ortools.sat.python import cp_model
from dsl.schema import (
    InstanceTRCO, Planning, OperationPlanifiee, Tache, Ressource,
    Contrainte, Precedence, CompatibiliteRessourceTache, Echeance,
    CompetenceRequise
)
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Set


def resoudre(instance: InstanceTRCO) -> Optional[Planning]:
    """Résout le FJSP pour une instance TRCO en minimisant le makespan."""
    model = cp_model.CpModel()
    
    # Calcul de l'horizon maximal conservatif
    horizon_max = sum(
        max(crt.duree for crt in instance.compatibilites_ressource_tache
            if crt.tache == tache)
        for tache in instance.taches
    )
    
    # Création des variables
    variables = _creer_variables(model, instance, horizon_max)
    
    # Ajout des contraintes
    _ajouter_contraintes(model, instance, variables)
    
    # Définition de l'objectif
    model.Minimize(variables['makespan'])
    
    # Résolution
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    
    # Extraction de la solution
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return _extraire_solution(solver, instance, variables)
    else:
        return None


def _creer_variables(
    model: cp_model.CpModel,
    instance: InstanceTRCO,
    horizon_max: int
) -> Dict[str, Dict | cp_model.IntVar]:
    """Crée toutes les variables du modèle CP-SAT."""
    # Dictionnaires pour stocker les variables
    interval_vars = {}
    start_vars = {}
    end_vars = {}
    resource_vars = {}
    
    # Indexation des tâches et ressources pour un accès rapide
    tache_to_idx = {tache: idx for idx, tache in enumerate(instance.taches)}
    ressource_to_idx = {ressource: idx for idx, ressource in enumerate(instance.ressources)}
    
    # Création des variables de début et de fin pour chaque tâche
    for tache in instance.taches:
        start_vars[tache] = model.NewIntVar(0, horizon_max, f'start_{tache.id}')
        end_vars[tache] = model.NewIntVar(0, horizon_max, f'end_{tache.id}')
    
    # Création des variables d'intervalle et de ressource pour chaque compatibilité
    for crt in instance.compatibilites_ressource_tache:
        tache = crt.tache
        ressource = crt.ressource
        duree = crt.duree
        
        # Variable d'intervalle
        interval_var = model.NewIntervalVar(
            start_vars[tache], 
            duree, 
            end_vars[tache], 
            f'interval_{tache.id}_{ressource.id}'
        )
        interval_vars[(tache, ressource)] = interval_var
        
        # Variable de ressource (booléenne)
        resource_var = model.NewBoolVar(f'resource_{tache.id}_{ressource.id}')
        resource_vars[(tache, ressource)] = resource_var
        
        # Lier l'intervalle à la variable de ressource
        model.Add(interval_var == resource_var)
    
    # Variable makespan
    makespan = model.NewIntVar(0, horizon_max, 'makespan')
    
    return {
        'interval_vars': interval_vars,
        'start_vars': start_vars,
        'end_vars': end_vars,
        'resource_vars': resource_vars,
        'makespan': makespan
    }


def _ajouter_contraintes(
    model: cp_model.CpModel,
    instance: InstanceTRCO,
    variables: Dict[str, Dict | cp_model.IntVar]
) -> None:
    """Ajoute toutes les contraintes au modèle CP-SAT."""
    start_vars = variables['start_vars']
    end_vars = variables['end_vars']
    resource_vars = variables['resource_vars']
    interval_vars = variables['interval_vars']
    makespan = variables['makespan']
    
    # Contraintes d'assignation : chaque tâche est assignée à exactement une ressource compatible
    for tache in instance.taches:
        compatible_resources = [
            resource_vars[(tache, crt.ressource)] 
            for crt in instance.compatibilites_ressource_tache 
            if crt.tache == tache
        ]
        model.AddExactlyOne(compatible_resources)
    
    # Contraintes de précédence
    for contrainte in instance.contraintes:
        if isinstance(contrainte, Precedence):
            model.Add(end_vars[contrainte.tache_predecesseur] <= start_vars[contrainte.tache_successeur])
    
    # Contraintes de disjonction de ressource
    ressource_to_intervals = defaultdict(list)
    for (tache, ressource), interval_var in interval_vars.items():
        ressource_to_intervals[ressource].append(interval_var)
    
    for ressource, intervals in ressource_to_intervals.items():
        model.AddNoOverlap(intervals)
    
    # Contraintes d'échéance (si présentes)
    for contrainte in instance.contraintes:
        if isinstance(contrainte, Echeance):
            model.Add(end_vars[contrainte.tache] <= contrainte.echeance)
    
    # Définition du makespan
    model.AddMaxEquality(makespan, list(end_vars.values()))


def _extraire_solution(
    solver: cp_model.CpSolver,
    instance: InstanceTRCO,
    variables: Dict[str, Dict | cp_model.IntVar]
) -> Planning:
    """Extrait la solution du solveur et construit l'objet Planning."""
    start_vars = variables['start_vars']
    resource_vars = variables['resource_vars']
    
    operations_planifiees = []
    
    for tache in instance.taches:
        # Trouver la ressource assignée
        for crt in instance.compatibilites_ressource_tache:
            if crt.tache == tache:
                if solver.Value(resource_vars[(tache, crt.ressource)]) == 1:
                    debut = solver.Value(start_vars[tache])
                    operations_planifiees.append(
                        OperationPlanifiee(
                            tache=tache,
                            ressource=crt.ressource,
                            debut=debut
                        )
                    )
                    break
    
    return Planning(operations=operations_planifiees)