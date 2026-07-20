from __future__ import annotations
from ortools.sat.python import cp_model
from dsl.schema import (
    InstanceTRCO, Planning, OperationPlanifiee, Tache, Ressource, Contrainte,
    Precedence, CompatibiliteRessourceTache, Echeance, CompetenceRequise
)
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any


def resoudre(instance: InstanceTRCO) -> Optional[Planning]:
    """Résout le FJSP pour une instance TRCO en minimisant le makespan."""
    
    # Calcul de l'horizon maximal conservatif
    horizon_max = sum(
        max(crt.duree for crt in instance.compatibilites_ressource_tache
            if crt.tache == tache)
        for tache in instance.taches
    )
    
    # Création du modèle CP-SAT
    modele = cp_model.CpModel()
    
    # Création des variables
    variables = _creer_variables(modele, instance, horizon_max)
    
    # Ajout des contraintes
    _ajouter_contraintes(modele, variables, instance)
    
    # Définition de l'objectif
    modele.Minimize(variables['makespan'])
    
    # Résolution
    solveur = cp_model.CpSolver()
    statut = solveur.Solve(modele)
    
    # Extraction de la solution
    if statut in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return _extraire_solution(solveur, variables, instance)
    else:
        return None


def _creer_variables(
    modele: cp_model.CpModel,
    instance: InstanceTRCO,
    horizon_max: int
) -> Dict[str, Any]:
    """Crée toutes les variables du modèle CP-SAT."""
    
    # Dictionnaires pour stocker les variables
    intervals_per_operation = {}
    presence_literals = {}
    start_end_per_task = {}
    
    # Création des variables de début et fin pour chaque tâche
    for tache in instance.taches:
        start_task = modele.NewIntVar(0, horizon_max, f'start_{tache.id}')
        end_task = modele.NewIntVar(0, horizon_max, f'end_{tache.id}')
        start_end_per_task[tache] = (start_task, end_task)
    
    # Création des intervalles optionnels et littéraux de présence
    for crt in instance.compatibilites_ressource_tache:
        tache = crt.tache
        ressource = crt.ressource
        duree = crt.duree
        
        # Variable intervalle optionnelle
        interval = modele.NewOptionalIntervalVar(
            start=modele.NewIntVar(0, horizon_max, f'start_{tache.id}_{ressource.id}'),
            size=duree,
            end=modele.NewIntVar(0, horizon_max, f'end_{tache.id}_{ressource.id}'),
            is_present=modele.NewBoolVar(f'presence_{tache.id}_{ressource.id}'),
            name=f'interval_{tache.id}_{ressource.id}'
        )
        
        intervals_per_operation[(tache, ressource)] = interval
        presence_literals[(tache, ressource)] = interval.IsPresent()
    
    # Variable makespan
    makespan = modele.NewIntVar(0, horizon_max, 'makespan')
    
    return {
        'intervals_per_operation': intervals_per_operation,
        'presence_literals': presence_literals,
        'start_end_per_task': start_end_per_task,
        'makespan': makespan
    }


def _ajouter_contraintes(
    modele: cp_model.CpModel,
    variables: Dict[str, Any],
    instance: InstanceTRCO
) -> None:
    """Ajoute toutes les contraintes au modèle CP-SAT."""
    
    intervals_per_operation = variables['intervals_per_operation']
    presence_literals = variables['presence_literals']
    start_end_per_task = variables['start_end_per_task']
    makespan = variables['makespan']
    
    # Contrainte : une seule ressource par tâche
    for tache in instance.taches:
        literals = [
            presence_literals[(tache, crt.ressource)]
            for crt in instance.compatibilites_ressource_tache
            if crt.tache == tache
        ]
        modele.AddExactlyOne(literals)
    
    # Contrainte : liaison entre début/fin de tâche et intervalles optionnels
    for crt in instance.compatibilites_ressource_tache:
        tache = crt.tache
        ressource = crt.ressource
        interval = intervals_per_operation[(tache, ressource)]
        presence_literal = presence_literals[(tache, ressource)]
        start_task, end_task = start_end_per_task[tache]
        
        # Si l'intervalle est présent, son début/fin doit correspondre à celui de la tâche
        modele.Add(start_task == interval.Start()).OnlyEnforceIf(presence_literal)
        modele.Add(end_task == interval.End()).OnlyEnforceIf(presence_literal)
    
    # Contrainte : disjonction des ressources
    ressources_intervals = defaultdict(list)
    for (tache, ressource), interval in intervals_per_operation.items():
        ressources_intervals[ressource].append(interval)
    
    for ressource, intervals in ressources_intervals.items():
        modele.AddNoOverlap(intervals)
    
    # Contrainte : précédence entre tâches
    for contrainte in instance.contraintes:
        if isinstance(contrainte, Precedence):
            tache_precedente = contrainte.tache_precedente
            tache_suivante = contrainte.tache_suivante
            start_suivante, _ = start_end_per_task[tache_suivante]
            _, end_precedente = start_end_per_task[tache_precedente]
            modele.Add(end_precedente <= start_suivante)
    
    # Contrainte : échéances (si présentes)
    for contrainte in instance.contraintes:
        if isinstance(contrainte, Echeance):
            tache = contrainte.tache
            _, end_task = start_end_per_task[tache]
            modele.Add(end_task <= contrainte.echeance)
    
    # Définition du makespan
    end_tasks = [end_task for _, end_task in start_end_per_task.values()]
    modele.AddMaxEquality(makespan, end_tasks)


def _extraire_solution(
    solveur: cp_model.CpSolver,
    variables: Dict[str, Any],
    instance: InstanceTRCO
) -> Optional[Planning]:
    """Extrait la solution du solveur et construit l'objet Planning."""
    
    presence_literals = variables['presence_literals']
    start_end_per_task = variables['start_end_per_task']
    
    operations_planifiees = []
    
    for tache in instance.taches:
        start_task, end_task = start_end_per_task[tache]
        start = solveur.Value(start_task)
        
        # Trouver la ressource sélectionnée pour cette tâche
        ressource_selectionnee = None
        for crt in instance.compatibilites_ressource_tache:
            if crt.tache == tache:
                presence_literal = presence_literals[(tache, crt.ressource)]
                if solveur.Value(presence_literal):
                    ressource_selectionnee = crt.ressource
                    duree = crt.duree
                    break
        
        if ressource_selectionnee is None:
            return None  # Aucune ressource sélectionnée (ne devrait pas arriver)
        
        operations_planifiees.append(
            OperationPlanifiee(
                tache=tache,
                ressource=ressource_selectionnee,
                debut=start
            )
        )
    
    return Planning(operations=operations_planifiees)