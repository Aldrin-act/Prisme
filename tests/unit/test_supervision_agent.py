"""Couche 1 (§6.1) : `supervision.agent.proposer_actions` et
`supervision.agent.detecter_signaux_llm` via un faux modèle (voir
`tests/unit/aides_test_agents.py`) — aucun appel LLM réel, même convention
que `tests/unit/test_benchmarker.py`."""

from __future__ import annotations

import json

import pytest

from supervision import agent
from supervision.agent import (
    ErreurReponseAgentInvalide,
    ExecutionSupervision,
    FaitSignal,
    InstanceSupervision,
    SolveurSupervision,
    detecter_signaux_llm,
    proposer_actions,
)
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


_INSTANCES = (
    InstanceSupervision(
        instance_id="i1",
        structure_contraintes="compatibilite_ressource_tache",
        signature_objectifs="minimiser_makespan",
        date_modification="2026-01-05T00:00:00",
    ),
)
_SOLVEURS = (
    SolveurSupervision(id="s1", structure_contraintes="precedence", signature_objectifs="minimiser_makespan"),
)
_EXECUTIONS = (
    ExecutionSupervision(
        execution_id="e1", instance_id="i1", id_solveur="s1", date_execution="2026-01-01T00:00:00", reussi=False
    ),
)


def test_detecter_signaux_llm_construit_le_resultat_depuis_le_schema() -> None:
    schema = agent._SchemaDetectionSupervision(
        signaux=[
            agent._SchemaSignalDetecte(instance_id="i1", type_signal="signature_orpheline"),
        ]
    )
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    signaux = detecter_signaux_llm(modele, _INSTANCES, _SOLVEURS, _EXECUTIONS)

    assert len(signaux) == 1
    assert signaux[0].instance_id == "i1"
    assert signaux[0].type_signal == "signature_orpheline"


def test_detecter_signaux_llm_transporte_les_champs_specifiques_a_chaque_type() -> None:
    schema = agent._SchemaDetectionSupervision(
        signaux=[
            agent._SchemaSignalDetecte(
                instance_id="i1",
                type_signal="instance_a_replanifier",
                raison="modifiee_apres_derniere_execution",
                id_solveur_disponible="s1",
            ),
            agent._SchemaSignalDetecte(
                instance_id="i1", type_signal="echecs_repetes", id_solveur="s1", execution_ids=["e1"]
            ),
        ]
    )
    modele = ModeleFactice(raw_content=json.dumps(schema.model_dump()), parsed=schema)

    signaux = detecter_signaux_llm(modele, _INSTANCES, _SOLVEURS, _EXECUTIONS)

    assert len(signaux) == 2
    replanifier, echecs = signaux
    assert replanifier.raison == "modifiee_apres_derniere_execution"
    assert replanifier.id_solveur_disponible == "s1"
    assert echecs.id_solveur == "s1"
    assert echecs.execution_ids == ("e1",)


def test_detecter_signaux_llm_leve_une_erreur_explicite_sur_reponse_non_conforme() -> None:
    modele = ModeleFactice(raw_content="pas du JSON valide", parsed=None, parsing_error=ValueError("mal formé"))

    with pytest.raises(ErreurReponseAgentInvalide, match="pas du JSON valide"):
        detecter_signaux_llm(modele, _INSTANCES, _SOLVEURS, _EXECUTIONS)
