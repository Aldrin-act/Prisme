"""Réception du payload T-R-C-O canonique venant d'un adaptateur ERP (§5.1, §5.5)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.autorisation import verifier_acces_client
from api.etat import EtatAPI, obtenir_etat, structure_contraintes
from api.input_validation import valider_payload_trco
from api.routes.auth import obtenir_utilisateur_courant

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.post("/{client_id}")
def ingerer_instance(
    client_id: str,
    payload: dict[str, Any],
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str]:
    """Valide le payload (garde-fou amont, §6.7) et le met en attente d'exécution."""
    verifier_acces_client(utilisateur, client_id)
    instance = valider_payload_trco(payload)
    instance_id = etat.enregistrer_instance(client_id, instance)
    return {"instance_id": instance_id, "structure_contraintes": structure_contraintes(instance)}


@router.delete("/{instance_id}", status_code=204)
def supprimer_instance(
    instance_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> None:
    """Supprime une instance et son historique d'exécution — n'affecte jamais
    les solveurs enregistrés (indépendants, §7)."""
    try:
        client_id, _ = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)
    etat.supprimer_instance(instance_id)
