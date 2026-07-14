"""Canal opérationnel (§5.1, §5.5) : retourne le planning en JSON, à chaque itération."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.etat import EtatAPI, obtenir_etat

router = APIRouter(prefix="/planning", tags=["planning"])


@router.get("/{execution_id}")
def obtenir_planning(execution_id: str, etat: EtatAPI = Depends(obtenir_etat)) -> dict[str, Any]:
    try:
        _, resultat = etat.recuperer_execution(execution_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="exécution inconnue") from None

    if resultat.planning is None:
        raise HTTPException(status_code=422, detail=resultat.erreur or "aucun planning disponible")

    return resultat.planning.model_dump(mode="json")
