"""Couche 1 (§6.1) : `analyste.analyser_mission` construit correctement son
`ResultatAnalyse` depuis une sortie structurée — aucun appel LLM réel (voir
`tests/unit/aides_test_agents.py`)."""

from __future__ import annotations

import json

import pytest

from generation.agents import analyste
from tests.unit.aides_test_agents import ModeleFactice


def test_analyser_mission_construit_le_resultat_depuis_le_schema() -> None:
    schema = analyste._SchemaAnalyse(
        entrees="Instance T-R-C-O", sorties="Planning", contraintes_a_couvrir=["c1", "c2"]
    )
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = analyste.analyser_mission(modele)

    assert resultat.entrees == "Instance T-R-C-O"
    assert resultat.sorties == "Planning"
    assert resultat.contraintes_a_couvrir == ("c1", "c2")
    assert "### Entrées" in resultat.en_texte()


def test_analyser_mission_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(analyste.ErreurReponseAgentInvalide, match="pas du JSON valide"):
        analyste.analyser_mission(modele)
