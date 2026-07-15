"""Couche 1 (§6.1) : la boucle diagnostique (PH10-T3, `diagnostics/attribution.py`)
est du code écrit à la main, déterministe. Deux solveurs délibérément bogués
(même esprit que `tests/unit/test_cascade.py`) exercent chacun une cause
distincte de l'élimination code → données → spécification DSL :

- un solveur qui ignore la précédence échoue déjà sur la vérité terrain
  (banc synthétique, Étape 3) → cause "code" ;
- un solveur correct sur précédence/contention mais qui choisit toujours la
  première ressource compatible passe le banc (une seule ressource
  compatible par tâche, par construction du banc), mais échoue sur le cas de
  référence à choix de ressource réel → cause "specification_dsl".

La cause "données" a besoin d'un solveur réellement sain sur les deux
premières briques pour être isolée proprement — voir
`tests/integration/test_attribution.py` (solveur de référence réel, OR-Tools).
"""

from __future__ import annotations

from collections import defaultdict, deque

from diagnostics import diagnostiquer
from dsl.schema import CompatibiliteMachineTache, InstanceTRCO, OperationPlanifiee, Planning, Precedence
from validation_engine.synthetic_bench import generer_catalogue


def _solveur_ignore_precedence(instance: InstanceTRCO) -> Planning:
    """Planifie chaque tâche à l'instant 0, sur sa première ressource
    compatible — sans jamais regarder la précédence ni la contention. Échoue
    donc déjà sur le banc synthétique (vérité terrain) : cause "code"."""
    compat: dict[str, set[str]] = defaultdict(set)
    for contrainte in instance.contraintes:
        if isinstance(contrainte, CompatibiliteMachineTache):
            compat[contrainte.tache].add(contrainte.ressource)
    return Planning(
        operations=[
            OperationPlanifiee(tache=tache.id, ressource=sorted(compat[tache.id])[0], debut=0)
            for tache in instance.taches
        ]
    )


def _solveur_mauvais_choix_ressource(instance: InstanceTRCO) -> Planning:
    """Ordonnanceur glouton correct sur précédence et contention (tri
    topologique, démarrage au plus tôt), mais qui choisit toujours la
    première ressource compatible par ordre alphabétique — indifférent au
    banc (une seule ressource compatible par tâche, par construction), mais
    faux sur un cas de référence à choix de ressource réel."""
    compat: dict[str, set[str]] = defaultdict(set)
    duree_par_couple: dict[tuple[str, str], int] = {}
    for contrainte in instance.contraintes:
        if isinstance(contrainte, CompatibiliteMachineTache):
            compat[contrainte.tache].add(contrainte.ressource)
            duree_par_couple[(contrainte.tache, contrainte.ressource)] = contrainte.duree

    predecesseurs: dict[str, list[str]] = defaultdict(list)
    successeurs: dict[str, list[str]] = defaultdict(list)
    for contrainte in instance.contraintes:
        if isinstance(contrainte, Precedence):
            predecesseurs[contrainte.apres].append(contrainte.avant)
            successeurs[contrainte.avant].append(contrainte.apres)

    degre_entrant = {tache.id: len(predecesseurs.get(tache.id, [])) for tache in instance.taches}
    file = deque(sorted(tache_id for tache_id, degre in degre_entrant.items() if degre == 0))
    ordre: list[str] = []
    while file:
        tache_id = file.popleft()
        ordre.append(tache_id)
        for suivant in sorted(successeurs.get(tache_id, [])):
            degre_entrant[suivant] -= 1
            if degre_entrant[suivant] == 0:
                file.append(suivant)

    fin_tache: dict[str, int] = {}
    disponible_ressource: dict[str, int] = defaultdict(int)
    operations = []
    for tache_id in ordre:
        ressource = sorted(compat[tache_id])[0]
        pret = max((fin_tache[predecesseur] for predecesseur in predecesseurs.get(tache_id, [])), default=0)
        debut = max(pret, disponible_ressource[ressource])
        fin = debut + duree_par_couple[(tache_id, ressource)]
        fin_tache[tache_id] = fin
        disponible_ressource[ressource] = fin
        operations.append(OperationPlanifiee(tache=tache_id, ressource=ressource, debut=debut))

    return Planning(operations=operations)


def test_cause_attribuee_au_code_quand_le_banc_echoue() -> None:
    cas_bench = generer_catalogue()[0]
    diagnostic = diagnostiquer(
        _solveur_ignore_precedence,
        cas_bench.instance,
        cas_bench.planning_optimal,
        motif_declenchement="KPI dégradé : makespan très supérieur à l'attendu",
    )

    assert diagnostic.cause == "code"
    assert diagnostic.details
    assert diagnostic.humain_decide
    assert diagnostic.motif_declenchement == "KPI dégradé : makespan très supérieur à l'attendu"


def test_cause_attribuee_a_la_specification_dsl_quand_seule_la_fidelite_echoue() -> None:
    cas_bench = generer_catalogue()[0]
    diagnostic = diagnostiquer(
        _solveur_mauvais_choix_ressource,
        cas_bench.instance,
        cas_bench.planning_optimal,
        motif_declenchement="signalement humain : plan jugé absurde",
    )

    assert diagnostic.cause == "specification_dsl"
    assert diagnostic.details
    assert diagnostic.humain_decide
