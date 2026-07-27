"""Couche 1 (§6.1) : `reviewer.relire_code` construit correctement son
`ResultatRevue` depuis une sortie structurée — aucun appel LLM réel (voir
`tests/unit/aides_test_agents.py`). Couvre spécifiquement le défaut prudent
sur `verdict` (absent/inattendu → jamais approuvé)."""

from __future__ import annotations

import json

import pytest

from generation.agents import reviewer
from tests.unit.aides_test_agents import ModeleFactice


def test_relire_code_approuve_si_verdict_est_approuve() -> None:
    schema = reviewer._SchemaRevue(verdict="APPROUVE", problemes=None)
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = reviewer.relire_code(modele, "def resoudre(instance): ...")

    assert resultat.approuve is True
    assert resultat.problemes == ()
    assert resultat.commentaires == "aucun problème relevé"


def test_relire_code_rejette_avec_problemes_si_verdict_different() -> None:
    schema = reviewer._SchemaRevue(verdict="A_CORRIGER", problemes=["import os interdit", "pas de docstring"])
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = reviewer.relire_code(modele, "def resoudre(instance): ...")

    assert resultat.approuve is False
    assert resultat.problemes == ("import os interdit", "pas de docstring")
    assert "import os interdit" in resultat.commentaires


def test_relire_code_traite_un_verdict_absent_comme_a_corriger() -> None:
    """Défaut prudent hérité de l'ancien `donnees.get("verdict")` : un champ
    absent ne doit jamais lever d'erreur ni approuver à tort."""
    schema = reviewer._SchemaRevue(verdict=None, problemes=None)
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = reviewer.relire_code(modele, "def resoudre(instance): ...")

    assert resultat.approuve is False
    assert resultat.problemes == ()


def test_relire_code_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(reviewer.ErreurReponseAgentInvalide, match="pas du JSON valide"):
        reviewer.relire_code(modele, "def resoudre(instance): ...")
