"""Canal d'audit (§5.1, §5.5) : expose le code du solveur sur demande explicite
(transparence, souveraineté) — jamais renvoyé par le canal opérationnel."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from solver_store.registry import ErreurIntegriteSolveur, Registre

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/{execution_id}")
def obtenir_code_source(
    execution_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
) -> dict[str, str]:
    try:
        id_solveur, _ = etat.recuperer_execution(execution_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="exécution inconnue") from None

    try:
        artefact = registre.recuperer_solveur(id_solveur)
    except (KeyError, ErreurIntegriteSolveur) as erreur:
        raise HTTPException(status_code=500, detail=str(erreur)) from erreur

    return {"id_solveur": id_solveur, "code_source": artefact.code_source}
