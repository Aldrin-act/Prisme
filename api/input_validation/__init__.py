"""Garde-fou amont (§6.7) : le payload T-R-C-O reçu est-il cohérent avant de
lancer le solveur ? Point d'entrée unique, quel que soit le canal d'arrivée
(API ou adaptateur ERP) — `dsl.validation.charger_instance`, ici traduit en
`HTTPException` pour les routes FastAPI.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from pydantic import ValidationError

from dsl.schema import InstanceTRCO
from dsl.validation import charger_instance


def _erreurs_serialisables(erreur: ValidationError) -> list[dict[str, Any]]:
    """Ne garde que les champs garantis sérialisables en JSON — `ctx` peut
    contenir des objets Python bruts (ex. l'exception d'un validateur)."""
    return [
        {"loc": entree["loc"], "msg": entree["msg"], "type": entree["type"]}
        for entree in erreur.errors(include_url=False)
    ]


def valider_payload_trco(payload: dict[str, Any]) -> InstanceTRCO:
    try:
        return charger_instance(payload)
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=_erreurs_serialisables(erreur)) from erreur
