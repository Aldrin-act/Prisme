from __future__ import annotations

import math
import random
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from dsl.schema import (
    CompatibiliteRessourceTache,
    Echeance,
    InstanceTRCO,
    OperationPlanifiee,
    Planning,
    Precedence,
    Tache,
)

# ---------------------------------------------------------------------------
# Algorithme génétique pour FJSP noyau minimal T-R-C-O
# ---------------------------------------------------------------------------
# Paramètres fixes (déterministes) suggérés par le Benchmarker
_POP_SIZE = 400
_GENERATIONS = 600
_CROSSOVER_RATE = 0.85
_BASE_MUTATION_RATE = 0.08
_TOURNAMENT_SIZE = 5
_ELITISM_FRAC = 0.1
_SEED = 42
_ADAPTIVE_THRESH_STD = 1e-6   # seuil d'écart-type des fitness pour déclencher
_ADAPTIVE_MUTATION_RATE = 0.15
_ADAPTIVE_DURATION = 10       # nombre de générations où la mutation est augmentée

# Type chromosome : liste de tuples (tache_id, indice_ressource, priorite_float)
Chromosome = List[Tuple[str, int, float]]


def _extraire_compatibilites_par_tache(
    instance: InstanceTRCO,
) -> Dict[str, List[Tuple[str, int]]]:
    """Construit un mapping tache_id -> [(ressource_id, duree), ...] trié déterministe."""
    compat_map: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    for c in instance.contraintes:
        if isinstance(c, CompatibiliteRessourceTache):
            compat_map[c.tache].append((c.ressource, c.duree))
    # Tri déterministe par ressource_id puis durée
    for tid in compat_map:
        compat_map[tid].sort(key=lambda x: (x[0], x[1]))
    return dict(compat_map)


def _extraire_precedences(instance: InstanceTRCO) -> List[Tuple[str, str]]:
    """Retourne une liste de (avant, apres)."""
    return [
        (c.avant, c.apres)
        for c in instance.contraintes
        if isinstance(c, Precedence)
    ]


def _extraire_echeances(instance: InstanceTRCO) -> Dict[str, int]:
    """Retourne un mapping tache_id -> echeance (int)."""
    return {
        c.tache: c.echeance
        for c in instance.contraintes
        if isinstance(c, Echeance)
    }


def _decoder(
    chromosome: Chromosome,
    instance: InstanceTRCO,
    compat_map: Dict[str, List[Tuple[str, int]]],
    precedences: List[Tuple[str, str]],
    echeances: Dict[str, int],
) -> Optional[Planning]:
    """
    Serial schedule generation scheme (SSGS) :
    - Trie les tâches du chromosome par priorite_float croissant.
    - Parcourt cette liste : si toutes les précédences sont satisfaites, place la tâche ;
      sinon la repousse en fin de liste.
    - Place la tâche à l'instant max(fin_max_avant, premier créneau libre de la ressource).
    - Vérifie l'échéance : si violée, chromosome invalide -> None.
    - Retourne un Planning légal ou None.
    """
    # Mapping pour retrouver facilement la durée associée à un tuple (tache, ressource)
    duree_map: Dict[Tuple[str, str], int] = {}
    for tid, lst in compat_map.items():
        for rid, dur in lst:
            duree_map[(tid, rid)] = dur

    # Index par tache_id pour retrouver le tuple du chromosome
    chr_by_tache = {t[0]: t for t in chromosome}

    # Relations de précédence
    pred_map: Dict[str, List[str]] = defaultdict(list)  # apres -> [avant]
    succ_map: Dict[str, List[str]] = defaultdict(list)  # avant -> [apres]
    for avant, apres in precedences:
        pred_map[apres].append(avant)
        succ_map[avant].append(apres)

    # Tri initial par priorite_float croissant
    ordered = sorted(chromosome, key=lambda x: x[1])  # par indice? Non, par priorite_float: x[2]
    ordered = sorted(chromosome, key=lambda x: x[2])

    # Initialisation des structures de planning
    fin_taches: Dict[str, int] = {}         # tache_id -> fin
    debuts: Dict[str, int] = {}             # tache_id -> debut
    ressource_utilisee: Dict[str, str] = {} # tache_id -> ressource_id

    # Disponibilité des ressources : liste de créneaux occupés par ressource
    occup_res: Dict[str, List[Tuple[int, int]]] = defaultdict(list)

    # Boucle constructive avec repoussage
    remaining = ordered[:]
    max_passes = len(remaining) * len(remaining)  # évite boucle infinie
    passes = 0

    while remaining and passes < max_passes:
        passes += 1
        tache_id, indice_res, prio = remaining.pop(0)

        # Vérifier précédences
        prets = all(avant in fin_taches for avant in pred_map.get(tache_id, []))
        if not prets:
            # Repousser à la fin
            remaining.append((tache_id, indice_res, prio))
            continue

        # Récupérer la ressource et la durée
        compat_list = compat_map[tache_id]
        if indice_res < 0 or indice_res >= len(compat_list):
            # Indice invalide -> chromosome défectueux, on le rejette
            return None
        ressource_id, duree = compat_list[indice_res]

        # Instant de début au plus tôt = max des fins des tâches "avant"
        debut_min = 0
        for avant in pred_map.get(tache_id, []):
            if fin_taches[avant] > debut_min:
                debut_min = fin_taches[avant]

        # Trouver le premier créneau libre de la ressource
        # Les créneaux sont triés par date de début
        crenaux = sorted(occup_res[ressource_id], key=lambda x: x[0])
        debut_possible = debut_min
        for c_debut, c_fin in crenaux:
            if debut_possible + duree <= c_debut:
                break
            if debut_possible < c_fin:
                debut_possible = c_fin

        # Placer la tâche
        fin = debut_possible + duree

        # Vérifier échéance
        if tache_id in echeances and fin > echeances[tache_id]:
            return None  # chromosome invalide

        # Enregistrer
        debuts[tache_id] = debut_possible
        fin_taches[tache_id] = fin
        ressource_utilisee[tache_id] = ressource_id
        occup_res[ressource_id].append((debut_possible, fin))

    if remaining:
        # Bloqué (précédences cycliques ou impossibles) -> None
        return None

    # Construire le Planning
    operations = []
    for tache_id, indice_res, prio in chromosome:
        operations.append(
            OperationPlanifiee(
                tache=tache_id,
                ressource=ressource_utilisee[tache_id],
                debut=debuts[tache_id],
            )
        )
    return Planning(operations=operations)


def _fitness(
    chromosome: Chromosome,
    instance: InstanceTRCO,
    compat_map: Dict[str, List[Tuple[str, int]]],
    precedences: List[Tuple[str, str]],
    echeances: Dict[str, int],
) -> int:
    """Retourne le makespan (entier) ou math.inf si chromosome invalide."""
    planning = _decoder(chromosome, instance, compat_map, precedences, echeances)
    if planning is None:
        return math.inf
    # makespan = max des fins
    # On ne stocke pas les fins explicitement dans le planning, on recalcule depuis les opérations.
    makespan = 0
    # On a besoin des durées pour calculer les fins, mais on peut les retrouver via compat_map.
    duree_map: Dict[Tuple[str, str], int] = {}
    for tid, lst in compat_map.items():
        for rid, dur in lst:
            duree_map[(tid, rid)] = dur
    for op in planning.operations:
        fin = op.debut + duree_map[(op.tache, op.ressource)]
        if fin > makespan:
            makespan = fin
    return makespan


def _initialiser_population(
    taches_ids: List[str],
    compat_map: Dict[str, List[Tuple[str, int]]],
    rng: random.Random,
) -> List[Chromosome]:
    """Génère une population aléatoire de taille _POP_SIZE."""
    population = []
    for _ in range(_POP_SIZE):
        chromo = []
        for tid in taches_ids:
            nb_res = len(compat_map[tid])
            indice_res = rng.randint(0, nb_res - 1) if nb_res > 0 else 0
            prio = rng.random()
            chromo.append((tid, indice_res, prio))
        population.append(chromo)
    return population


def _selection_tournoi(
    population: List[Chromosome],
    fitnesses: List[int],
    rng: random.Random,
) -> Chromosome:
    """Tournoi binaire de taille _TOURNAMENT_SIZE."""
    indices = rng.sample(range(len(population)), _TOURNAMENT_SIZE)
    best_idx = min(indices, key=lambda i: fitnesses[i])
    return population[best_idx]


def _croisement(
    parent1: Chromosome,
    parent2: Chromosome,
    rng: random.Random,
) -> Chromosome:
    """Uniform crossover avec réparation des doublons."""
    assert len(parent1) == len(parent2)
    n = len(parent1)
    enfant = []
    for i in range(n):
        if rng.random() < 0.5:
            enfant.append(parent1[i])
        else:
            enfant.append(parent2[i])
    return _reparer_doublons(enfant, parent1, parent2, rng)


def _reparer_doublons(
    enfant: Chromosome,
    parent1: Chromosome,
    parent2: Chromosome,
    rng: random.Random,
) -> Chromosome:
    """
    Garantit que chaque tâche apparaît exactement une fois.
    Si une tâche est en double, on remplace une occurrence par une tâche manquante
    en conservant indice_ressource et priorite_float du parent donneur (alternativement p1/p2).
    """
    taches_set = {t[0] for t in enfant}
    if len(taches_set) == len(enfant) and len(enfant) == len(set(t[0] for t in enfant)):
        return enfant

    all_taches = sorted(set(t[0] for t in parent1))  # déterministe
    missing = [tid for tid in all_taches if tid not in taches_set]
    duplicates = []
    seen = set()
    for i, tup in enumerate(enfant):
        if tup[0] in seen:
            duplicates.append(i)
        else:
            seen.add(tup[0])

    # Pour chaque doublon, remplacer par un missing
    for idx, miss_id in zip(duplicates, missing):
        # On choisit un donneur alternativement parent1/parent2 pour conserver indice/prio
        donneur = parent1 if rng.random() < 0.5 else parent2
        # Trouver ce miss_id dans le donneur
        donneur_tuple = next(t for t in donneur if t[0] == miss_id)
        enfant[idx] = donneur_tuple

    # Vérification finale (au cas où il y aurait encore des doublons résiduels, on refait)
    if len(set(t[0] for t in enfant)) != len(enfant):
        # Nettoyage agressif : on réindexe
        mapping = {t[0]: t for t in parent1}
        for i in range(len(enfant)):
            tid = enfant[i][0]
            if enfant.count(enfant[i]) > 1:  # doublon
                # Remplacer par un missing restant
                pass
        # Simplification : on reconstruit depuis parent1 et on permute les doublons
        nouvelle = list(parent1)
        rng.shuffle(nouvelle)
        # Assure unicité en prenant les premières occurrences
        seen2 = set()
        result = []
        for tup in nouvelle:
            if tup[0] not in seen2:
                result.append(tup)
                seen2.add(tup[0])
        enfant = result

    return enfant


def _mutation(
    chromosome: Chromosome,
    compat_map: Dict[str, List[Tuple[str, int]]],
    rng: random.Random,
    mutation_rate: float,
) -> Chromosome:
    """Mutation indépendante par tuple avec probabilité mutation_rate."""
    nouveau = []
    for tache_id, indice_res, prio in chromosome:
        if rng.random() < mutation_rate:
            if rng.random() < 0.5:
                # Changer ressource
                nb = len(compat_map[tache_id])
                if nb > 0:
                    indice_res = rng.randint(0, nb - 1)
            else:
                # Changer priorite
                prio = rng.random()
        nouveau.append((tache_id, indice_res, prio))
    return nouveau


def _std_fitness(fitnesses: List[int]) -> float:
    """Écart-type de la population (en ignorant les inf)."""
    finite = [f for f in fitnesses if f != math.inf]
    if len(finite) < 2:
        return 0.0
    mean = sum(finite) / len(finite)
    variance = sum((x - mean) ** 2 for x in finite) / len(finite)
    return math.sqrt(variance)


def resoudre(instance: InstanceTRCO) -> Optional[Planning]:
    """
    Résout le FJSP noyau T-R-C-O par algorithme génétique.
    Retourne un Planning légal avec le meilleur makespan trouvé,
    ou None si l'instance est infaisable.
    """
    rng = random.Random(_SEED)

    # Extraction des données
    compat_map = _extraire_compatibilites_par_tache(instance)
    precedences = _extraire_precedences(instance)
    echeances = _extraire_echeances(instance)
    taches_ids = sorted(compat_map.keys())  # déterministe

    if not taches_ids:
        return Planning(operations=[])

    # Initialisation
    population = _initialiser_population(taches_ids, compat_map, rng)
    fitnesses = [
        _fitness(chromo, instance, compat_map, precedences, echeances)
        for chromo in population
    ]

    meilleur_chromo = None
    meilleur_fitness = math.inf

    generation = 0
    adaptive_counter = 0  # compte à rebours pour mutation adaptative
    mutation_rate = _BASE_MUTATION_RATE

    while generation < _GENERATIONS:
        # Évaluation déjà faite (en entrée de boucle, sauf première itération)
        # Élitisme : on garde les meilleurs
        nb_elites = max(1, int(_ELITISM_FRAC * _POP_SIZE))
        # Tri des indices par fitness croissante
        ranked_indices = sorted(range(len(population)), key=lambda i: fitnesses[i])
        elites = [population[i] for i in ranked_indices[:nb_elites]]

        # Mise à jour du meilleur global
        for idx in ranked_indices:
            if fitnesses[idx] < meilleur_fitness:
                meilleur_fitness = fitnesses[idx]
                meilleur_chromo = population[idx]

        # Nouvelle population
        nouvelle_pop = elites[:]

        while len(nouvelle_pop) < _POP_SIZE:
            parent1 = _selection_tournoi(population, fitnesses, rng)
            parent2 = _selection_tournoi(population, fitnesses, rng)

            if rng.random() < _CROSSOVER_RATE:
                enfant = _croisement(parent1, parent2, rng)
            else:
                enfant = parent1[:]  # copie

            enfant = _mutation(enfant, compat_map, rng, mutation_rate)
            nouvelle_pop.append(enfant)

        population = nouvelle_pop
        fitnesses = [
            _fitness(chromo, instance, compat_map, precedences, echeances)
            for chromo in population
        ]

        # Mutation adaptative
        std_dev = _std_fitness(fitnesses)
        if adaptive_counter > 0:
            adaptive_counter -= 1
            if adaptive_counter == 0:
                mutation_rate = _BASE_MUTATION_RATE
        elif std_dev < _ADAPTIVE_THRESH_STD:
            mutation_rate = _ADAPTIVE_MUTATION_RATE
            adaptive_counter = _ADAPTIVE_DURATION

        generation += 1

    # Dernière évaluation du meilleur
    for chromo, fit in zip(population, fitnesses):
        if fit < meilleur_fitness:
            meilleur_fitness = fit
            meilleur_chromo = chromo

    if meilleur_fitness == math.inf or meilleur_chromo is None:
        return None

    # Décoder le meilleur chromosome pour obtenir un Planning valide
    planning = _decoder(meilleur_chromo, instance, compat_map, precedences, echeances)
    return planning
