"""Réception du payload T-R-C-O canonique venant d'un adaptateur ERP (§5.1, §5.5)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from api.etat import EtatAPI, obtenir_etat, structure_contraintes
from api.input_validation import valider_payload_trco

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/{client_id}")
def ingerer_instance(
    client_id: str, payload: dict[str, Any], etat: EtatAPI = Depends(obtenir_etat)
) -> dict[str, str]:
    """Valide le payload (garde-fou amont, §6.7) et le met en attente d'exécution."""
    instance = valider_payload_trco(payload)
    instance_id = etat.enregistrer_instance(client_id, instance)
    return {"instance_id": instance_id, "structure_contraintes": structure_contraintes(instance)}
