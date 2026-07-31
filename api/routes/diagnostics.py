"""Boucle diagnostique en direct (§5.7, PH10-T3) : attribue la cause d'un
planning de production jugé mauvais, en rejouant le solveur réellement
enregistré (via le sandbox) sur le banc synthétique et les cas de référence.

Route volontairement plus lente que les autres (voir
`diagnostics/solveur_sandbox.py`) — appelée uniquement sur action humaine
explicite depuis le dashboard, jamais en arrière-plan.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from diagnostics import construire_solveur_sandbox, diagnostiquer
from solver_store.registry import Registre

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.post("/{execution_id}")
def diagnostiquer_execution(
    execution_id: str,
    payload: dict[str, Any],
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
) -> dict[str, Any]:
    try:
        id_solveur, instance_id, resultat = etat.recuperer_execution(execution_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="exécution inconnue") from None

    if resultat.planning is None:
        raise HTTPException(
            status_code=422, detail="aucun planning produit pour cette exécution, rien à diagnostiquer"
        )

    # instance_id est garanti exister : supprimer_instance cascade-supprime
    # ses propres exécutions plutôt que de les orpheliner.
    _, instance = etat.recuperer_instance(instance_id)
    solveur = construire_solveur_sandbox(registre, id_solveur)

    diagnostic = diagnostiquer(
        solveur,
        instance,
        resultat.planning,
        motif_declenchement=payload["motif_declenchement"],
    )

    return {
        "cause": diagnostic.cause,
        "motif_declenchement": diagnostic.motif_declenchement,
        "details": diagnostic.details,
        "proposition": diagnostic.proposition,
        "humain_decide": diagnostic.humain_decide,
    }
