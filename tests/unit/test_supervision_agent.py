"""Couche 1 (§6.1) : `supervision.agent.proposer_actions` via un faux modèle
(voir `tests/unit/aides_test_agents.py`) — aucun appel LLM réel, même
convention que `tests/unit/test_benchmarker.py`."""

from __future__ import annotations

import json

import pytest

from supervision import agent
from supervision.agent import ErreurReponseAgentInvalide, FaitSignal, proposer_actions
from tests.unit.aides_test_agents import ModeleFactice

_FAITS = (
    FaitSignal(reference="signature_orpheline:i1", description="Aucun solveur actif ne correspond."),
    FaitSignal(reference="echecs_repetes:i2", description="3 échecs consécutifs."),
)


def test_proposer_actions_construit_le_resultat_depuis_le_schema() -> None:
    schema = agent._SchemaSupervision(
        propositions=[
            agent._SchemaPropositionUnitaire(
                reference="signature_orpheline:i1", resume="Régénération nécessaire.", priorite="haute"
            ),
            agent._SchemaPropositionUnitaire(
                reference="echecs_repetes:i2", resume="Diagnostic recommandé.", priorite="moyenne"
            ),
        ]
    )
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    resultat = proposer_actions(modele, _FAITS)

    assert len(resultat.propositions) == 2
    par_ref = {p.reference: p for p in resultat.propositions}
    assert par_ref["signature_orpheline:i1"].priorite == "haute"
    assert par_ref["echecs_repetes:i2"].resume == "Diagnostic recommandé."


def test_proposer_actions_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(ErreurReponseAgentInvalide, match="pas du JSON valide"):
        proposer_actions(modele, _FAITS)
