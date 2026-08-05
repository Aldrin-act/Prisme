"""Boucle périodique de l'agent de supervision (§2, MT7) — pas de nouvelle
dépendance (pas d'APScheduler) : un `threading.Thread` démon, même
convention que le fil de génération SSE (`api/routes/generation.py`).

Désactivée par défaut (`PRISME_SUPERVISION_ACTIVE`, même style que
`PRISME_AUTH_DESACTIVEE` dans `api/routes/auth.py`) — ne doit jamais se
déclencher pendant `pytest` ni un `uvicorn --reload` occasionnel sans
opt-in explicite : appelle un LLM et écrit en base à chaque passe.
"""

from __future__ import annotations

import logging
import os
import threading

from api.dependencies import obtenir_registre
from api.etat import obtenir_etat
from generation.agents.client_llm import construire_modele_pour_agent
from supervision.orchestrateur import analyser_et_proposer

_LOGGER = logging.getLogger(__name__)

_INTERVALLE_PAR_DEFAUT_SECONDES = 3600


def _actif() -> bool:
    return os.getenv("PRISME_SUPERVISION_ACTIVE", "").strip().lower() in ("1", "true", "yes")


def _intervalle_secondes() -> float:
    brut = os.getenv("PRISME_SUPERVISION_INTERVALLE_SECONDES", "").strip()
    return float(brut) if brut else _INTERVALLE_PAR_DEFAUT_SECONDES


def _boucle(arret: threading.Event, intervalle: float) -> None:
    etat = obtenir_etat()
    registre = obtenir_registre()
    while not arret.wait(intervalle):
        modele = construire_modele_pour_agent("supervision")
        for client in etat.lister_clients():
            client_id = client["client_id"]
            try:
                analyser_et_proposer(etat, registre, modele, client_id)
            except Exception:  # noqa: BLE001 — un client en échec (LLM, réseau...) ne doit jamais arrêter la boucle
                _LOGGER.exception("analyse de supervision en échec pour client_id=%r", client_id)


def demarrer_planificateur() -> threading.Event:
    """No-op (renvoie un `Event` déjà signalé) tant que
    `PRISME_SUPERVISION_ACTIVE` n'est pas positionné — voir docstring du
    module. Sinon démarre le fil et renvoie l'`Event` d'arrêt, à `.set()`
    pour un arrêt immédiat (pas d'attente de la fin de l'intervalle en
    cours)."""
    arret = threading.Event()
    if not _actif():
        arret.set()
        return arret

    fil = threading.Thread(target=_boucle, args=(arret, _intervalle_secondes()), daemon=True)
    fil.start()
    return arret
