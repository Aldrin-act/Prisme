"""Pont entre un adaptateur ERP réel et le canal d'ingestion standard —
pour que le dashboard puisse charger une instance depuis de vraies données
sans que quelqu'un tape du JSON à la main. Ne fait rien de plus que
`/ingestion/{client_id}` une fois la traduction faite : mêmes garde-fous
(§6.7), même stockage. Aujourd'hui : GreenSIG (`adapters/greensig/`) seul.

Ne masque jamais un rejet de `traduire()` (ex. tâches sans compatibilité
machine-tâche, §6.7) derrière un succès partiel — l'échec explicite est
volontaire (voir `adapters/greensig/mapping/regles.md`, limite 3) : mieux
vaut que l'utilisateur du dashboard voie l'erreur telle quelle qu'une
instance silencieusement tronquée.
"""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from adapters.greensig import extraire_payload, traduire
from api.etat import EtatAPI, obtenir_etat, structure_contraintes
from api.input_validation import erreurs_serialisables

CLIENT_ID_GREENSIG = "greensig"

router = APIRouter(prefix="/adapters", tags=["adapters"])


@router.post("/greensig/ingerer")
def ingerer_depuis_greensig(etat: EtatAPI = Depends(obtenir_etat)) -> dict[str, str]:
    try:
        payload = extraire_payload()
    except psycopg.OperationalError as erreur:
        raise HTTPException(status_code=503, detail="base GreenSIG (db_greensig) injoignable") from erreur

    try:
        instance = traduire(payload)
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    instance_id = etat.enregistrer_instance(CLIENT_ID_GREENSIG, instance)
    return {"instance_id": instance_id, "structure_contraintes": structure_contraintes(instance)}
