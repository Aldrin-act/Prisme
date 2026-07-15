"""Validation humaine des plannings proposés (§2.3 étape 6, PH10-T2).

Aucun planning n'est appliqué sans validation humaine explicite : ce module
ne fait qu'enregistrer la décision (acceptée/refusée), tracée avec horodatage
— jamais d'application automatique. Dans ce PoC, « application » se limite à
l'existence de cette décision ; il n'y a pas de vraie exécution usine à
déclencher (hors périmètre du noyau minimal).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.etat import Decision, EtatAPI, obtenir_etat

router = APIRouter(prefix="/executions", tags=["validation"])


@router.post("/{execution_id}/decision")
def enregistrer_decision(
    execution_id: str, payload: dict[str, Any], etat: EtatAPI = Depends(obtenir_etat)
) -> dict[str, str]:
    try:
        etat.recuperer_execution(execution_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="exécution inconnue") from None

    decision: Decision = payload["decision"]
    if decision not in ("acceptee", "refusee"):
        raise HTTPException(status_code=422, detail=f"decision inconnue : {decision!r}")

    etat.enregistrer_decision(execution_id, decision, commentaire=payload.get("commentaire"))
    return {"execution_id": execution_id, "decision": decision}


@router.get("/{execution_id}/decision")
def obtenir_decision(execution_id: str, etat: EtatAPI = Depends(obtenir_etat)) -> dict[str, Any]:
    try:
        etat.recuperer_execution(execution_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="exécution inconnue") from None

    decision = etat.decision_pour(execution_id)
    if decision is None:
        raise HTTPException(status_code=404, detail="aucune décision encore prise pour cette exécution")

    return {
        "execution_id": decision.execution_id,
        "decision": decision.decision,
        "horodatage": decision.horodatage,
        "commentaire": decision.commentaire,
    }
