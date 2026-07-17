"""Canal opérationnel (§5.1, §5.5) : retourne le planning en JSON, à chaque itération."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.etat import EtatAPI, obtenir_etat
from dsl.schema import CompatibiliteRessourceTache

router = APIRouter(prefix="/planning", tags=["planning"])


@router.get("/{execution_id}")
def obtenir_planning(execution_id: str, etat: EtatAPI = Depends(obtenir_etat)) -> dict[str, Any]:
    try:
        _, instance_id, resultat = etat.recuperer_execution(execution_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="exécution inconnue") from None

    if resultat.planning is None:
        raise HTTPException(status_code=422, detail=resultat.erreur or "aucun planning disponible")

    # Durées ajoutées pour le Gantt du dashboard : `Planning` n'a délibérément
    # pas de champ durée (§ dsl/schema/planning.py) — elle vit sur
    # `CompatibiliteRessourceTache`, propre au couple (tâche, ressource).
    _, instance = etat.recuperer_instance(instance_id)
    durees = {
        f"{contrainte.tache}|{contrainte.ressource}": contrainte.duree
        for contrainte in instance.contraintes
        if isinstance(contrainte, CompatibiliteRessourceTache)
    }

    return {**resultat.planning.model_dump(mode="json"), "durees": durees}
