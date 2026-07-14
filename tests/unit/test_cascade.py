"""Couche 1 (§6.1) : la cascade est du code écrit à la main, déterministe.
Critère de validation de l'Étape 5 : la cascade passe le solveur de
référence (Étape 4) au vert, et détecte, brique par brique, deux solveurs
délibérément bogués — l'un doit échouer dès la faisabilité, l'autre doit la
franchir (et même l'optimalité sur le banc) mais échouer spécifiquement à la
fidélité sur un cas de référence, exactement le genre de bug qu'aucune des
deux autres briques ne peut voir.

Les deux solveurs « bogués » sont de simples fonctions Python — pas de
CP-SAT — pour que ces tests ne dépendent que de la logique de la cascade
elle-même, jamais d'OR-Tools.
"""

from __future__ import annotations

from collections import defaultdict, deque

from dsl.schema import (
    CompatibiliteMachineTache,
    InstanceTRCO,
    OperationPlanifiee,
    Planning,
    Precedence,
)
from validation_engine.cascade import evaluer_fidelite_reference, evaluer_optimalite_banc


def _solveur_ignore_precedence(instance: InstanceTRCO) -> Planning:
    """Planifie chaque tâche à l'instant 0, sur son premier compatible —
    sans jamais regarder la précédence ni la contention de ressource.
    """
    compat: dict[str, set[str]] = defaultdict(set)
    for contrainte in instance.contraintes:
        if isinstance(contrainte, CompatibiliteMachineTache):
            compat[contrainte.tache].add(contrainte.ressource)
    toutes_ressources = {ressource.id for ressource in instance.ressources}

    operations = [
        OperationPlanifiee(
            tache=tache.id,
            ressource=sorted(compat.get(tache.id) or toutes_ressources)[0],
            debut=0,
        )
        for tache in instance.taches
    ]
    return Planning(operations=operations)


def _planifier_glouton(instance: InstanceTRCO, choisir_ressource) -> Planning:
    """Ordonnanceur glouton correct sur la précédence et la contention : tri
    topologique, chaque tâche démarre au plus tôt possible compte tenu de ses
    prédécesseurs et de la disponibilité de la ressource choisie. Le choix
    entre plusieurs ressources compatibles est délégué à `choisir_ressource`.
    """
    duree = {tache.id: tache.duree for tache in instance.taches}
    compat: dict[str, set[str]] = defaultdict(set)
    for contrainte in instance.contraintes:
        if isinstance(contrainte, CompatibiliteMachineTache):
            compat[contrainte.tache].add(contrainte.ressource)
    toutes_ressources = {ressource.id for ressource in instance.ressources}

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
        candidats = sorted(compat.get(tache_id) or toutes_ressources)
        ressource = choisir_ressource(candidats)
        pret = max((fin_tache[predecesseur] for predecesseur in predecesseurs.get(tache_id, [])), default=0)
        debut = max(pret, disponible_ressource[ressource])
        fin = debut + duree[tache_id]
        fin_tache[tache_id] = fin
        disponible_ressource[ressource] = fin
        operations.append(OperationPlanifiee(tache=tache_id, ressource=ressource, debut=debut))

    return Planning(operations=operations)


def _solveur_mauvais_choix_ressource(instance: InstanceTRCO) -> Planning:
    """Correct sur la précédence et la contention ; mais choisit toujours la
    première ressource compatible (par ordre alphabétique), sans jamais tenir
    compte de la contention *globale* que ce choix peut créer ailleurs.
    """
    return _planifier_glouton(instance, lambda candidats: candidats[0])


def test_solveur_qui_ignore_la_precedence_echoue_a_la_faisabilite() -> None:
    verdict = evaluer_optimalite_banc(_solveur_ignore_precedence)

    assert not verdict.reussi
    assert all(echec.brique_en_echec == "faisabilite" for echec in verdict.echecs)


def test_solveur_avec_mauvais_choix_de_ressource_passe_faisabilite_et_optimalite_sur_le_banc() -> None:
    verdict_banc = evaluer_optimalite_banc(_solveur_mauvais_choix_ressource)

    assert verdict_banc.reussi, verdict_banc.echecs


def test_solveur_avec_mauvais_choix_de_ressource_echoue_seulement_a_la_fidelite() -> None:
    verdict_reference = evaluer_fidelite_reference(_solveur_mauvais_choix_ressource)

    par_nom = {diagnostic.nom: diagnostic for diagnostic in verdict_reference.diagnostics}
    assert par_nom["precedence_simple"].reussi
    assert par_nom["choix_ressource_attendu"].brique_en_echec == "fidelite"
