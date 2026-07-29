"""Couche 1 (§6.1) : `generateur.generer_code_depuis_plan` construit
correctement son `ResultatGenerationBrute` depuis une sortie structurée —
aucun appel LLM réel (voir `tests/unit/aides_test_agents.py`).
`generer_code_solveur` (mode simple, Étape 4) reste sur un simple `.invoke()`/
`extraire_bloc_code`, sans sortie structurée — non retesté ici."""

from __future__ import annotations

import json

import pytest

from generation.agents import generateur
from tests.unit.aides_test_agents import ModeleFactice


def test_generer_code_depuis_plan_construit_le_resultat_depuis_le_schema() -> None:
    schema = generateur._SchemaGenerationCode(code="def resoudre(instance):\n    return None\n")
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = generateur.generer_code_depuis_plan(modele, "plan technique", algorithme="cp_sat")

    assert resultat.code_source == "def resoudre(instance):\n    return None\n"


def test_generer_code_depuis_plan_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(generateur.ErreurReponseAgentInvalide, match="pas du JSON valide"):
        generateur.generer_code_depuis_plan(modele, "plan technique")
