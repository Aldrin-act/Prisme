"""Couche 1 (§6.1) : `debugger.corriger_code` construit correctement son
`ResultatCorrection` depuis une sortie structurée — aucun appel LLM réel
(voir `tests/unit/aides_test_agents.py`)."""

from __future__ import annotations

import json

import pytest

from generation.agents import debugger
from tests.unit.aides_test_agents import ModeleFactice


def test_corriger_code_construit_le_resultat_depuis_le_schema() -> None:
    schema = debugger._SchemaCorrection(code="def resoudre(instance):\n    return None\n", cause="import interdit")
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = debugger.corriger_code(modele, "code cassé", "import os interdit")

    assert resultat.code_source == "def resoudre(instance):\n    return None\n"
    assert resultat.cause == "import interdit"


def test_corriger_code_defaut_prudent_si_cause_absente() -> None:
    schema = debugger._SchemaCorrection(code="def resoudre(instance):\n    return None\n", cause=None)
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = debugger.corriger_code(modele, "code cassé", "problème")

    assert resultat.cause == "non précisée"


def test_corriger_code_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(debugger.ErreurReponseAgentInvalide, match="pas du JSON valide"):
        debugger.corriger_code(modele, "code cassé", "problème")
