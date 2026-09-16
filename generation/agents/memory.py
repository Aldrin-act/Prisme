"""Mémoire intra-boucle de l'agent Debugger (voir `generation/agents/debugger.py`,
`generation/graph.py::_noeud_debugger`) — bornée à une seule tentative de
génération, jamais persistée au-delà, jamais partagée entre deux
instances/générations différentes : ne viole pas la clause « pas de mémoire
entre deux exécutions » de la définition d'agent du projet, une « exécution »
y désignant une tentative de génération complète (§ « génère une fois,
réexécute plusieurs fois », `CLAUDE.md`), jamais un appel LLM isolé.

Pure texte, aucun état de module : chaque tentative de génération construit
sa propre liste d'entrées dans `EtatGeneration.historique_debugger`
(`generation/graph.py`), remise à `[]` par `_noeud_testeur` au tout début de
chaque nouvelle génération. Ce module ne fait que formater — lire/écrire
cette liste reste la responsabilité de `_noeud_debugger`."""

from __future__ import annotations

AUCUNE_TENTATIVE = "Aucune tentative précédente dans cette génération."

_LONGUEUR_MAX_PROBLEME = 300


def formater_entree(
    numero: int, probleme: str, cause: str, *, cible: str | None = None, correctif: str | None = None
) -> str:
    """Une ligne d'historique pour la tentative `numero` — `probleme` tronqué
    pour ne pas faire grandir le prompt sans borne sur les dix tentatives
    possibles (`MAX_TENTATIVES_REPARATION`). `cible` (`"solveur"` ou
    `"tests"`) uniquement pour le chemin `corriger_solveur_ou_tests`
    (§6.6bis) ; `None` pour `corriger_code`, où c'est toujours le solveur.

    `correctif` : ce que le Debugger a réellement modifié à cette tentative, tel qu'il le
    résume lui-même — sans lui, la consigne « ne rejoue jamais un correctif déjà tenté » était
    invérifiable (seule la cause supposée restait en mémoire, jamais le changement fait)."""
    probleme_tronque = probleme[:_LONGUEUR_MAX_PROBLEME]
    entree = f"Tentative {numero} : problème = {probleme_tronque} → "
    if cible is not None:
        entree += f"{cible} corrigé, "
    entree += f"cause identifiée = {cause}"
    if correctif:
        entree += f" ; correctif appliqué = {correctif[:_LONGUEUR_MAX_PROBLEME]}"
    return entree
