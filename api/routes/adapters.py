"""Pont entre un adaptateur ERP et le canal d'ingestion standard — pour que
le dashboard puisse charger une instance depuis de vraies données sans que
quelqu'un tape du JSON à la main. Ne fait rien de plus que
`/ingestion/{client_id}` une fois la traduction faite : mêmes garde-fous
(§6.7), même stockage. Deux chemins :

- GreenSIG (`adapters/greensig/`) — adaptateur écrit à la main, déterministe,
  gratuit. Le chemin par défaut, à privilégier dès qu'un `translator.py`
  existe pour l'ERP concerné.
- Comprehension (`adapters/agent_comprehension/`) — agent LLM, pour un ERP
  sans adaptateur dédié. Propose une traduction, jamais une vérité : le même
  garde-fou déterministe tranche, comme pour GreenSIG.

Ne masque jamais un rejet de traduction (ex. tâches sans compatibilité
ressource-tâche, §6.7) derrière un succès partiel — l'échec explicite est
volontaire (voir `adapters/greensig/mapping/regles.md`, limite 3) : mieux
vaut que l'utilisateur du dashboard voie l'erreur telle quelle qu'une
instance silencieusement tronquée.
"""

from __future__ import annotations

import psycopg
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ValidationError

from adapters.agent_comprehension import comprendre_donnees_erp
from adapters.greensig import extraire_payload, traduire
from adapters.tableur import ErreurFichierInvalide
from adapters.tableur import traduire as traduire_tableur
from api.etat import EtatAPI, obtenir_etat, structure_contraintes
from api.input_validation import erreurs_serialisables, valider_payload_trco
from generation.agents.base import ErreurReponseAgentInvalide
from generation.agents.client_llm import AppelLLM, construire_appel_llm

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


@router.post("/tableur/{client_id}")
async def ingerer_depuis_tableur(
    client_id: str, fichier: UploadFile = File(...), etat: EtatAPI = Depends(obtenir_etat)
) -> dict[str, str]:
    """Ingestion depuis le gabarit xlsx (§5.4, `docs/dsl/gabarit_ingestion_trco.xlsx`) —
    la voie « je remplis un tableur » plutôt que « j'écris du JSON »."""
    if not (fichier.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(status_code=422, detail="le fichier doit être un classeur Excel (.xlsx)")

    contenu = await fichier.read()
    try:
        instance = traduire_tableur(contenu)
    except ErreurFichierInvalide as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    instance_id = etat.enregistrer_instance(client_id, instance)
    return {"instance_id": instance_id, "structure_contraintes": structure_contraintes(instance)}


class RequeteComprehension(BaseModel):
    client_id: str
    donnees_brutes: str


@router.post("/comprehension/ingerer")
def ingerer_via_comprehension(
    requete: RequeteComprehension,
    etat: EtatAPI = Depends(obtenir_etat),
    appel_llm: AppelLLM = Depends(construire_appel_llm),
) -> dict[str, object]:
    try:
        resultat = comprendre_donnees_erp(appel_llm, requete.donnees_brutes)
    except ErreurReponseAgentInvalide as erreur:
        raise HTTPException(status_code=502, detail=f"agent de compréhension : {erreur}") from erreur

    instance = valider_payload_trco(resultat.instance_brute)  # lève déjà un 422 si invalide

    instance_id = etat.enregistrer_instance(requete.client_id, instance)
    return {
        "instance_id": instance_id,
        "structure_contraintes": structure_contraintes(instance),
        "avertissements": list(resultat.avertissements),
    }
