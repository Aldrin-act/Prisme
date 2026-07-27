"""Couche 1 (§6.1) : `documentation.documenter_code` construit correctement
son `ResultatDocumentation` depuis une sortie structurée — aucun appel LLM
réel (voir `tests/unit/aides_test_agents.py`)."""

from __future__ import annotations

import json

import pytest

from generation.agents import documentation
from tests.unit.aides_test_agents import ModeleFactice


def test_documenter_code_construit_le_resultat_depuis_le_schema() -> None:
    schema = documentation._SchemaDocumentation(resume="Résout le FJSP.", limites_connues="Aucune précédence.")
    modele = ModeleFactice(
        raw_content=json.dumps({"resume": schema.resume, "limites_connues": schema.limites_connues}), parsed=schema
    )

    resultat = documentation.documenter_code(modele, "def resoudre(instance): ...")

    assert resultat.resume == "Résout le FJSP."
    assert resultat.limites_connues == "Aucune précédence."
    assert resultat.reponse_brute == json.dumps(
        {"resume": schema.resume, "limites_connues": schema.limites_connues}
    )
    assert resultat.en_texte() == "Résout le FJSP.\n\nLimites connues : Aucune précédence."


def test_documenter_code_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(documentation.ErreurReponseAgentInvalide, match="pas du JSON valide"):
        documentation.documenter_code(modele, "def resoudre(instance): ...")
