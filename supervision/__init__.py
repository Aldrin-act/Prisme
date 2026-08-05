"""Agent de supervision (§2, MT7) : détecte des signaux (signature orpheline,
échecs répétés, instance en attente de replanification) sur l'historique
d'un client et propose une action à un humain — jamais une action
automatique. Voir `supervision/detecteurs.py`, `supervision/agent.py`,
`supervision/orchestrateur.py`, `supervision/planificateur.py`."""

from __future__ import annotations

from supervision.agent import FaitSignal, PropositionLLM, ResultatSupervision, proposer_actions
from supervision.detecteurs import (
    SignalEchecsRepetes,
    SignalInstanceAReplanifier,
    SignalSignatureOrpheline,
    detecter_echecs_repetes,
    detecter_signature_et_replanification,
)
from supervision.orchestrateur import analyser_et_proposer

__all__ = [
    "FaitSignal",
    "PropositionLLM",
    "ResultatSupervision",
    "SignalEchecsRepetes",
    "SignalInstanceAReplanifier",
    "SignalSignatureOrpheline",
    "analyser_et_proposer",
    "detecter_echecs_repetes",
    "detecter_signature_et_replanification",
    "proposer_actions",
]
