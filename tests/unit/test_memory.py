"""Couche 1 (§6.1) : `generation.agents.memory` — formatage pur de la
mémoire intra-boucle du Debugger, aucun état de module, aucun appel LLM."""

from __future__ import annotations

from generation.agents import memory


def test_formater_entree_sans_cible() -> None:
    entree = memory.formater_entree(1, "import os interdit", "import non autorisé")

    assert entree == "Tentative 1 : problème = import os interdit → cause identifiée = import non autorisé"


def test_formater_entree_avec_cible() -> None:
    entree = memory.formater_entree(2, "test échoué en sandbox", "attente erronée", cible="tests")

    assert entree == (
        "Tentative 2 : problème = test échoué en sandbox → tests corrigé, cause identifiée = attente erronée"
    )


def test_formater_entree_tronque_un_probleme_trop_long() -> None:
    probleme_long = "x" * 1000

    entree = memory.formater_entree(1, probleme_long, "cause")

    assert "x" * 300 in entree
    assert "x" * 301 not in entree


def test_aucune_tentative_est_un_texte_non_vide() -> None:
    assert memory.AUCUNE_TENTATIVE
