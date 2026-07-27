"""Couche 1 (§6.1) : `orchestrateur.planifier` construit correctement son
`ResultatOrchestration` depuis une sortie structurée — aucun appel LLM réel
(voir `tests/unit/aides_test_agents.py`)."""

from __future__ import annotations

import json

import pytest

from generation.agents import orchestrateur
from tests.unit.aides_test_agents import ModeleFactice


def test_planifier_construit_le_plan_depuis_le_schema() -> None:
    schema = orchestrateur._SchemaOrchestration(
        plan=[
            orchestrateur._SchemaEtapePlan(agent="analyste", instruction="Analyser la mission."),
            orchestrateur._SchemaEtapePlan(agent="architecte", instruction="Concevoir le modèle."),
        ]
    )
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = orchestrateur.planifier(modele)

    assert len(resultat.plan) == 2
    assert resultat.plan[0] == orchestrateur.EtapePlan(agent="analyste", instruction="Analyser la mission.")
    assert resultat.plan[1] == orchestrateur.EtapePlan(agent="architecte", instruction="Concevoir le modèle.")


def test_planifier_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(orchestrateur.ErreurReponseAgentInvalide, match="pas du JSON valide"):
        orchestrateur.planifier(modele)
