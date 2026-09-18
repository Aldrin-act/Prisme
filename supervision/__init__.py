"""Agent de supervision (§2, MT7) : détecte des signaux (signature orpheline,
échecs répétés, instance en attente de replanification) sur l'historique
d'un client, **atelier par atelier** (une instance à la fois), et propose
une action à un humain — jamais une action
automatique. Détection et rédaction passent chacune par un appel LLM
distinct (voir `supervision/agent.py`) ; `supervision/detecteurs.py`
rassemble les faits bruts et valide ce que le LLM en tire,
`supervision/orchestrateur.py` enchaîne les deux et persiste,
`supervision/planificateur.py` déclenche le cycle périodiquement."""

from __future__ import annotations

from supervision.adequation import EvaluationSolveur, SolveurHorsAtelier, evaluer_solveur, solveur_a_evaluer
from supervision.agent import (
    FaitSignal,
    PropositionLLM,
    ResultatSupervision,
    detecter_signaux_llm,
    proposer_actions,
)
from supervision.detecteurs import (
    SignalEchecsRepetes,
    SignalInstanceAReplanifier,
    SignalInstanceJugeeInfaisable,
    SignalSignatureOrpheline,
    SignalSolveurARegenerer,
    detecter_signaux,
    detecter_signaux_instance,
)
from supervision.orchestrateur import analyser_et_proposer, analyser_instance

__all__ = [
    "EvaluationSolveur",
    "SignalSolveurARegenerer",
    "SignalInstanceJugeeInfaisable",
    "evaluer_solveur",
    "solveur_a_evaluer",
    "FaitSignal",
    "PropositionLLM",
    "ResultatSupervision",
    "SignalEchecsRepetes",
    "SignalInstanceAReplanifier",
    "SignalSignatureOrpheline",
    "SolveurHorsAtelier",
    "analyser_et_proposer",
    "analyser_instance",
    "detecter_signaux",
    "detecter_signaux_instance",
    "detecter_signaux_llm",
    "proposer_actions",
]
