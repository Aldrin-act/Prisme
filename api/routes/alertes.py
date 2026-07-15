"""Alertes d'aléa atelier et déclenchement humain du recalcul (§2.3, PH10-T1).

Le cycle réactif documenté (§2.3) : un aléa survient (panne, commande
urgente, retard) → le système lève une alerte → un humain la voit et
déclenche explicitement le recalcul → le solveur s'exécute sur l'état
courant. Ce module ne détecte jamais un aléa automatiquement — signaler
un aléa est toujours un appel explicite (hors périmètre du noyau minimal
de surveiller réellement l'atelier) ; seul le déclenchement du recalcul,
lui, doit rester un geste humain explicite (jamais automatique).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import obtenir_registre
from api.etat import EtatAPI, TypeAlea, obtenir_etat
from api.routes.execution import executer_pour_instance
from solver_store.registry import Registre

router = APIRouter(prefix="/alertes", tags=["alertes"])


@router.post("")
def lever_alerte(payload: dict[str, Any], etat: EtatAPI = Depends(obtenir_etat)) -> dict[str, str]:
    """Signale un aléa atelier sur une instance déjà ingérée. Corps attendu :
    `{"instance_id": str, "client_id": str, "type_alea": "panne"|"commande_urgente"|"retard",
    "description": str}`."""
    instance_id = payload["instance_id"]
    try:
        etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    type_alea: TypeAlea = payload["type_alea"]
    if type_alea not in ("panne", "commande_urgente", "retard"):
        raise HTTPException(status_code=422, detail=f"type_alea inconnu : {type_alea!r}")

    alerte_id = etat.lever_alerte(
        instance_id=instance_id,
        client_id=payload["client_id"],
        type_alea=type_alea,
        description=payload["description"],
    )
    return {"alerte_id": alerte_id}


@router.get("")
def lister_alertes(etat: EtatAPI = Depends(obtenir_etat)) -> list[dict[str, Any]]:
    return [
        {
            "id": alerte.id,
            "instance_id": alerte.instance_id,
            "client_id": alerte.client_id,
            "type_alea": alerte.type_alea,
            "description": alerte.description,
            "horodatage": alerte.horodatage,
            "statut": alerte.statut,
            "execution_id": alerte.execution_id,
        }
        for alerte in etat.lister_alertes()
    ]


@router.post("/{alerte_id}/declencher")
def declencher_recalcul(
    alerte_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    registre: Registre = Depends(obtenir_registre),
) -> dict[str, str | bool]:
    """Le déclenchement humain explicite du recalcul (§2.3 étape 3, PH10-T1) —
    jamais automatique : cette route n'est appelée que sur une action humaine
    depuis le dashboard."""
    try:
        alerte = etat.recuperer_alerte(alerte_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="alerte inconnue") from None

    execution_id, resultat = executer_pour_instance(etat, registre, alerte.instance_id, alerte.client_id)
    etat.marquer_alerte_traitee(alerte_id, execution_id)

    return {"execution_id": execution_id, "reussi": resultat.reussi}
