"""Couche 1 (§6.1) : `testeur.generer_tests` construit correctement son
`ResultatTests` depuis une sortie structurée — aucun appel LLM réel (voir
`tests/unit/aides_test_agents.py`)."""

from __future__ import annotations

import json

import pytest

from generation.agents import testeur
from tests.unit.aides_test_agents import ModeleFactice


def test_generer_tests_construit_le_resultat_depuis_le_schema() -> None:
    schema = testeur._SchemaTests(code_tests="def test_x():\n    assert True\n")
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = testeur.generer_tests(modele, "def resoudre(instance): ...")

    assert resultat.code_tests == "def test_x():\n    assert True\n"


def test_generer_tests_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(testeur.ErreurReponseAgentInvalide, match="pas du JSON valide"):
        testeur.generer_tests(modele, "def resoudre(instance): ...")
