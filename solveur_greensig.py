from __future__ import annotations

import random

from dsl.schema import (
    CompatibiliteRessourceTache,
    Echeance,
    InstanceTRCO,
    OperationPlanifiee,
    Planning,
    Precedence,
)


def _decoder(chromosome: list[str], instance: InstanceTRCO) -> list[OperationPlanifiee] | None:
    """Implémente le 'serial schedule generation scheme'."""
    # Index des compatibilités par tâche
    compatibilites_par_tache: dict[str, list[CompatibiliteRessourceTache]] = {}
    for c in instance.contraintes:
        if isinstance(c, CompatibiliteRessourceTache):
            compatibilites_par_tache.setdefault(c.tache, []).append(c)

    # Index des précédences
    precedences_apres: dict[str, list[Precedence]] = {}
    for c in instance.contraintes:
        if isinstance(c, Precedence):
            precedences_apres.setdefault(c.apres, []).append(c)

    # Index des échéances
    echeances_par_tache: dict[str, int] = {}
    for c in instance.contraintes:
        if isinstance(c, Echeance):
            echeances_par_tache[c.tache] = c.echeance

    # Dictionnaires d'état
    fin_tache: dict[str, int] = {}
    ressource_disponibilite: dict[str, int] = {r.id: 0 for r in instance.ressources}
    planning_dict: dict[str, OperationPlanifiee] = {}

    while len(planning_dict) < len(instance.taches):
        progres = False
        for tache_id in chromosome:
            if tache_id in planning_dict:
                continue

            # Vérifier les précédences
            taches_avant = [p.avant for p in precedences_apres.get(tache_id, [])]
            precedences_ok = all(avant in planning_dict for avant in taches_avant)
            if not precedences_ok:
                continue

            # Calculer le début au plus tôt
            debut_au_plus_tot = max((fin_tache[avant] for avant in taches_avant), default=0)

            meilleur_debut = float("inf")
            meilleure_fin = float("inf")
            meilleure_operation = None

            compatibilites = compatibilites_par_tache.get(tache_id, [])
            if not compatibilites:
                continue  # Tâche sans ressource compatible, instance infaisable

            for comp in compatibilites:
                res_id = comp.ressource
                duree = comp.duree
                debut_possible = max(debut_au_plus_tot, ressource_disponibilite[res_id])
                fin_possible = debut_possible + duree

                # Vérifier l'échéance
                if tache_id in echeances_par_tache:
                    echeance = echeances_par_tache[tache_id]
                    if fin_possible > echeance:
                        continue  # Violation d'échéance, impossible sur cette ressource

                if debut_possible < meilleur_debut or (
                    debut_possible == meilleur_debut and fin_possible < meilleure_fin
                ):
                    meilleur_debut = debut_possible
                    meilleure_fin = fin_possible
                    meilleure_operation = OperationPlanifiee(
                        tache=tache_id, ressource=comp.ressource, debut=debut_possible
                    )

            if meilleure_operation is None:
                # Aucune ressource compatible trouvée qui respecte les contraintes dures
                # Instance infaisable
                return None

            planning_dict[tache_id] = meilleure_operation
            fin_tache[tache_id] = meilleure_fin
            ressource_disponibilite[meilleure_operation.ressource] = meilleure_fin
            progres = True

        if not progres:
            # Blocage : cycle de précédences
            return None

    return list(planning_dict.values())


def _calculer_fitness(planning: list[OperationPlanifiee], instance: InstanceTRCO) -> int:
    """Retourne le makespan (max des heures de fin) d'un planning décodé."""
    if not planning:
        return float("inf")
    return max(op.debut + _duree_operation(op, instance) for op in planning)


def _duree_operation(op: OperationPlanifiee, instance: InstanceTRCO) -> int:
    """Retrouve la durée d'une opération depuis l'instance."""
    for c in instance.contraintes:
        if isinstance(c, CompatibiliteRessourceTache):
            if c.tache == op.tache and c.ressource == op.ressource:
                return c.duree
    return 0  # Ne devrait jamais arriver si le planning est légal


def _generer_population_initiale(taille: int, liste_id_taches: list[str], rng: random.Random) -> list[list[str]]:
    """Génère une population de 'taille' chromosomes aléatoires."""
    population = []
    for _ in range(taille):
        chromosome = liste_id_taches.copy()
        rng.shuffle(chromosome)
        population.append(chromosome)
    return population


def _selection_tournoi(
    population: list[list[str]], fitnesses: list[int], taille_tournoi: int, rng: random.Random
) -> list[str]:
    """Sélectionne un chromosome par tournoi."""
    indices = rng.choices(range(len(population)), k=taille_tournoi)
    meilleur_idx = min(indices, key=lambda i: fitnesses[i])
    return population[meilleur_idx][:]


def _croisement_two_point(parent1: list[str], parent2: list[str], rng: random.Random) -> list[str]:
    """Applique un croisement d'ordre en deux points."""
    taille = len(parent1)
    if taille < 2:
        return parent1[:]
    point1 = rng.randint(0, taille - 2)
    point2 = rng.randint(point1 + 1, taille - 1)

    enfant = [None] * taille
    # Conserver le segment central de parent1
    segment = parent1[point1 : point2 + 1]
    segment_set = set(segment)
    enfant[point1 : point2 + 1] = segment

    # Remplir le reste avec parent2, en respectant l'ordre
    idx_enfant = (point2 + 1) % taille
    for gene in parent2:
        if gene not in segment_set:
            enfant[idx_enfant] = gene
            idx_enfant = (idx_enfant + 1) % taille
    return enfant


def _mutation_insert_and_swap(chromosome: list[str], rng: random.Random) -> list[str]:
    """Effectue une mutation par insertion et échange."""
    taille = len(chromosome)
    if taille < 2:
        return chromosome[:]
    chromosome_mute = chromosome[:]
    choix = rng.random()
    if choix < 0.5:
        # Swap
        i, j = rng.sample(range(taille), 2)
        chromosome_mute[i], chromosome_mute[j] = chromosome_mute[j], chromosome_mute[i]
    else:
        # Insert
        i = rng.randint(0, taille - 1)
        gene = chromosome_mute.pop(i)
        j = rng.randint(0, taille - 1)
        chromosome_mute.insert(j, gene)
    return chromosome_mute


def resoudre(instance: InstanceTRCO) -> Planning | None:
    """Résout le FJSP par algorithme génétique."""
    liste_id_taches = [t.id for t in instance.taches]
    if not liste_id_taches:
        return Planning(operations=[])

    rng = random.Random(42)

    population_size = 400
    generations = 600
    crossover_rate = 0.85
    mutation_rate_base = 0.03
    tournament_size = 5
    elitism_count = max(1, int(population_size * 0.08))

    population = _generer_population_initiale(population_size, liste_id_taches, rng)

    def evaluer(chromosome):
        planning = _decoder(chromosome, instance)
        if planning is None:
            return float("inf")
        return _calculer_fitness(planning, instance)

    fitnesses = [evaluer(ind) for ind in population]

    meilleur_chromosome = None
    meilleure_fitness = float("inf")

    stagnation_count = 0
    mutation_rate = mutation_rate_base

    for generation in range(generations):
        # Évaluer la meilleure solution courante
        meilleure_courante_idx = min(range(population_size), key=lambda i: fitnesses[i])
        if fitnesses[meilleure_courante_idx] < meilleure_fitness:
            meilleure_fitness = fitnesses[meilleure_courante_idx]
            meilleur_chromosome = population[meilleure_courante_idx][:]
            stagnation_count = 0
        else:
            stagnation_count += 1

        # Adaptive mutation
        if stagnation_count > 10:
            mutation_rate = min(0.3, mutation_rate * 1.1)
        else:
            mutation_rate = max(mutation_rate_base, mutation_rate * 0.95)

        nouvelle_population = []

        # Élitisme
        indices_tries = sorted(range(population_size), key=lambda i: fitnesses[i])
        for i in range(elitism_count):
            nouvelle_population.append(population[indices_tries[i]][:])

        while len(nouvelle_population) < population_size:
            parent1 = _selection_tournoi(population, fitnesses, tournament_size, rng)
            parent2 = _selection_tournoi(population, fitnesses, tournament_size, rng)

            if rng.random() < crossover_rate:
                enfant = _croisement_two_point(parent1, parent2, rng)
            else:
                enfant = parent1[:]

            if rng.random() < mutation_rate:
                enfant = _mutation_insert_and_swap(enfant, rng)

            nouvelle_population.append(enfant)

        population = nouvelle_population
        fitnesses = [evaluer(ind) for ind in population]

    # Décodage final du meilleur chromosome
    if meilleur_chromosome is None:
        return None

    planning_ops = _decoder(meilleur_chromosome, instance)
    if planning_ops is None:
        return None

    return Planning(operations=planning_ops)
