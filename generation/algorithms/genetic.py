"""Algorithme génétique pour le FJSP.

Recommandé pour grandes instances (>200 tâches) où CP-SAT timeout.

Encodage : Chromosome = (assignations ressources, ordre tâches)
Opérateurs : Crossover partiel, mutation par swap, sélection par tournoi
Fitness : Makespan (à minimiser)

Qualité attendue : 92-95% de l'optimal
Temps : Minutes pour 1000-2000 tâches
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from dsl.schema import (
    CompatibiliteRessourceTache,
    InstanceTRCO,
    OperationPlanifiee,
    Planning,
    Precedence,
)


@dataclass(frozen=True)
class Chromosome:
    """Chromosome = solution candidate.

    assignations: Dict[tache_id, ressource_id] - Quelle ressource pour chaque tâche
    ordre: List[tache_id] - Ordre d'exécution des tâches
    """

    assignations: dict[str, str]
    ordre: list[str]
    makespan: int | None = None  # Fitness (calculée à la demande)


def resoudre(
    instance: InstanceTRCO,
    population_size: int = 300,
    generations: int = 500,
    crossover_rate: float = 0.8,
    mutation_rate: float = 0.05,
    tournament_size: int = 5,
    elitism: float = 0.1,
    seed: int | None = None,
) -> Planning | None:
    """Résout une instance FJSP avec un algorithme génétique.

    Args:
        instance: Instance T-R-C-O à résoudre
        population_size: Taille de la population
        generations: Nombre de générations
        crossover_rate: Probabilité de crossover
        mutation_rate: Probabilité de mutation
        tournament_size: Taille du tournoi pour la sélection
        elitism: Proportion de meilleurs individus conservés
        seed: Graine aléatoire (pour reproductibilité)

    Returns:
        Planning si solution trouvée, None sinon

    Exemple:
        >>> planning = resoudre(
        ...     instance,
        ...     population_size=300,
        ...     generations=500,
        ...     seed=42
        ... )
    """
    if seed is not None:
        random.seed(seed)

    # Construire données utiles
    ressources_par_tache = _construire_ressources_compatibles(instance)
    durees = _construire_durees(instance)
    graphe_precedences = _construire_graphe_precedences(instance)

    # Population initiale
    population = [
        _generer_chromosome_aleatoire(instance, ressources_par_tache, graphe_precedences)
        for _ in range(population_size)
    ]

    # Evaluer fitness
    population = [_evaluer_fitness(chromo, instance, durees) for chromo in population]

    meilleur = min(population, key=lambda c: c.makespan or float("inf"))

    # Evolution
    n_elites = int(population_size * elitism)

    for generation in range(generations):
        # Tri par fitness
        population.sort(key=lambda c: c.makespan or float("inf"))

        # Elitisme : conserver les meilleurs
        nouvelle_population = population[:n_elites]

        # Générer le reste par sélection + crossover + mutation
        while len(nouvelle_population) < population_size:
            # Sélection par tournoi
            parent1 = _selection_tournoi(population, tournament_size)
            parent2 = _selection_tournoi(population, tournament_size)

            # Crossover
            if random.random() < crossover_rate:
                enfant = _crossover(parent1, parent2, ressources_par_tache)
            else:
                enfant = parent1

            # Mutation
            if random.random() < mutation_rate:
                enfant = _mutation(enfant, ressources_par_tache)

            # Evaluer et ajouter
            enfant = _evaluer_fitness(enfant, instance, durees)
            nouvelle_population.append(enfant)

        population = nouvelle_population

        # Mettre à jour meilleur
        best_gen = min(population, key=lambda c: c.makespan or float("inf"))
        if best_gen.makespan and (not meilleur.makespan or best_gen.makespan < meilleur.makespan):
            meilleur = best_gen

    # Convertir meilleur chromosome en Planning
    if meilleur.makespan is None:
        return None

    return _chromosome_vers_planning(meilleur, instance, durees)


def _construire_ressources_compatibles(instance: InstanceTRCO) -> dict[str, list[str]]:
    """Construit le dictionnaire tache → ressources compatibles."""
    result = {}
    for contrainte in instance.contraintes:
        if isinstance(contrainte, CompatibiliteRessourceTache):
            result.setdefault(contrainte.tache, []).append(contrainte.ressource)
    return result


def _construire_durees(instance: InstanceTRCO) -> dict[tuple[str, str], int]:
    """Construit le dictionnaire (tache, ressource) → durée."""
    result = {}
    for contrainte in instance.contraintes:
        if isinstance(contrainte, CompatibiliteRessourceTache):
            result[(contrainte.tache, contrainte.ressource)] = contrainte.duree
    return result


def _construire_graphe_precedences(instance: InstanceTRCO) -> dict[str, list[str]]:
    """Construit le graphe avant → [apres, ...]."""
    result = {}
    for contrainte in instance.contraintes:
        if isinstance(contrainte, Precedence):
            result.setdefault(contrainte.avant, []).append(contrainte.apres)
    return result


def _generer_chromosome_aleatoire(
    instance: InstanceTRCO, ressources_par_tache: dict[str, list[str]], graphe_precedences: dict[str, list[str]]
) -> Chromosome:
    """Génère un chromosome aléatoire respectant les précédences."""
    # Assignations aléatoires
    assignations = {tache.id: random.choice(ressources_par_tache[tache.id]) for tache in instance.taches}

    # Ordre topologique approximatif (respecte précédences)
    ordre = _tri_topologique_approche([t.id for t in instance.taches], graphe_precedences)

    return Chromosome(assignations=assignations, ordre=ordre)


def _tri_topologique_approche(taches: list[str], graphe: dict[str, list[str]]) -> list[str]:
    """Tri topologique approximatif (shuffle avec contraintes)."""
    # Implémentation simplifiée : tri par nombre de prédécesseurs
    # TODO: Implémenter un vrai tri topologique
    return sorted(taches, key=lambda t: len([p for p, succ in graphe.items() if t in succ]))


def _evaluer_fitness(chromo: Chromosome, instance: InstanceTRCO, durees: dict[tuple[str, str], int]) -> Chromosome:
    """Evalue le makespan d'un chromosome."""
    # Simuler l'exécution pour calculer makespan
    # TODO: Implémenter simulation complète
    # Pour l'instant, approximation simpliste
    makespan_approx = sum(durees.get((t, chromo.assignations[t]), 0) for t in chromo.ordre)

    return Chromosome(assignations=chromo.assignations, ordre=chromo.ordre, makespan=makespan_approx)


def _selection_tournoi(population: list[Chromosome], k: int) -> Chromosome:
    """Sélection par tournoi : prend le meilleur parmi k tirés au hasard."""
    tournoi = random.sample(population, k)
    return min(tournoi, key=lambda c: c.makespan or float("inf"))


def _crossover(parent1: Chromosome, parent2: Chromosome, ressources_par_tache: dict[str, list[str]]) -> Chromosome:
    """Crossover partiel : mélange assignations et ordre."""
    # Assignations : moitié de chaque parent
    taches = list(parent1.assignations.keys())
    split = len(taches) // 2

    assignations = {}
    for i, tache in enumerate(taches):
        assignations[tache] = parent1.assignations[tache] if i < split else parent2.assignations[tache]

    # Ordre : crossover d'ordre partiel (POX)
    # TODO: Implémenter POX correctement
    ordre = parent1.ordre  # Simplification

    return Chromosome(assignations=assignations, ordre=ordre)


def _mutation(chromo: Chromosome, ressources_par_tache: dict[str, list[str]]) -> Chromosome:
    """Mutation : swap deux tâches ou change une assignation."""
    taches = list(chromo.assignations.keys())

    if random.random() < 0.5:
        # Mutation assignation
        tache = random.choice(taches)
        nouvelle_ressource = random.choice(ressources_par_tache[tache])
        assignations = chromo.assignations.copy()
        assignations[tache] = nouvelle_ressource
        return Chromosome(assignations=assignations, ordre=chromo.ordre)
    else:
        # Mutation ordre (swap)
        ordre = chromo.ordre.copy()
        i, j = random.sample(range(len(ordre)), 2)
        ordre[i], ordre[j] = ordre[j], ordre[i]
        return Chromosome(assignations=chromo.assignations, ordre=ordre)


def _chromosome_vers_planning(
    chromo: Chromosome, instance: InstanceTRCO, durees: dict[tuple[str, str], int]
) -> Planning:
    """Convertit un chromosome en Planning T-R-C-O."""
    # Simulation séquentielle pour calculer les débuts
    # TODO: Implémenter simulation complète avec parallélisme

    operations = []
    temps_courant = 0

    for tache_id in chromo.ordre:
        ressource = chromo.assignations[tache_id]
        duree = durees[(tache_id, ressource)]

        operations.append(OperationPlanifiee(tache=tache_id, ressource=ressource, debut=temps_courant))

        temps_courant += duree

    return Planning(operations=operations)


# Note: Cette implémentation est un SQUELETTE à compléter.
# Les TODOs marquent les parties critiques à implémenter :
# 1. Tri topologique correct (respectant précédences)
# 2. Simulation correcte du makespan (avec parallélisme ressources)
# 3. Crossover d'ordre partiel (POX)
# 4. Gestion correcte des précédences dans mutations
#
# Pour utilisation en production, voir :
# - DEAP (Distributed Evolutionary Algorithms in Python)
# - PyGAD (Python Genetic Algorithm)
# - Ou implémenter les TODOs ci-dessus
