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

from typing import Any

import psycopg
from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ValidationError

from adapters.agent_comprehension import comprendre_donnees_erp
from adapters.csv_import import ErreurFichierInvalide as ErreurFichierCsvInvalide
from adapters.csv_import import traduire as traduire_csv
from adapters.greensig import extraire_payload, traduire
from adapters.json_import import ErreurPayloadInvalide as ErreurPayloadJsonInvalide
from adapters.json_import import traduire as traduire_json
from api.autorisation import verifier_acces_client
from api.etat import EtatAPI, obtenir_etat, structure_contraintes
from api.input_validation import erreurs_serialisables, valider_payload_trco
from api.routes.auth import obtenir_utilisateur_courant
from generation.agents.base import ErreurReponseAgentInvalide
from generation.agents.client_llm import construire_modele_comprehension

CLIENT_ID_GREENSIG = "greensig"

router = APIRouter(prefix="/adapters", tags=["adapters"])


@router.post("/greensig/ingerer")
def ingerer_depuis_greensig(
    nom_projet: str | None = None,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str]:
    try:
        payload = extraire_payload()
    except psycopg.OperationalError as erreur:
        raise HTTPException(status_code=503, detail="base GreenSIG (db_greensig) injoignable") from erreur

    try:
        instance = traduire(payload)
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    instance_id = etat.enregistrer_instance(CLIENT_ID_GREENSIG, instance, nom_projet=nom_projet)
    return {"instance_id": instance_id, "structure_contraintes": structure_contraintes(instance)}


@router.post("/csv/{client_id}")
async def ingerer_depuis_csv(
    client_id: str,
    taches: UploadFile = File(...),
    ressources: UploadFile = File(...),
    contraintes: UploadFile = File(...),
    nom_projet: str | None = None,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str]:
    """Ingestion depuis trois fichiers CSV séparés (§5.4) — Tâches, Ressources
    et Contraintes (`adapters/csv_import/`), format standard pour l'import
    de données tabulaires."""
    verifier_acces_client(utilisateur, client_id)
    for fichier in (taches, ressources, contraintes):
        if not (fichier.filename or "").lower().endswith(".csv"):
            nom = fichier.filename or "(sans nom)"
            raise HTTPException(status_code=422, detail=f"{nom} doit être un fichier .csv")

    taches_octets, ressources_octets, contraintes_octets = (
        await taches.read(),
        await ressources.read(),
        await contraintes.read(),
    )
    try:
        instance = traduire_csv(taches_octets, ressources_octets, contraintes_octets)
    except ErreurFichierCsvInvalide as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    instance_id = etat.enregistrer_instance(client_id, instance, nom_projet=nom_projet)
    return {"instance_id": instance_id, "structure_contraintes": structure_contraintes(instance)}


@router.post("/json/{client_id}")
def ingerer_depuis_json_avec_competences(
    client_id: str,
    payload: dict[str, Any] = Body(...),
    nom_projet: str | None = None,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str]:
    """Ingestion depuis un JSON « brut avec compétences » (§5.4, `adapters/json_import/`)
    — sur-ensemble strict d'une instance T-R-C-O canonique : une tâche peut y
    porter une durée estimée (`duree_estimee_minutes`), permettant de dériver
    sa compatibilité depuis des `CompetenceRequise`/`Ressource.competences`
    plutôt que de la déclarer à la main. Un payload sans rien de tout ça est
    ingéré tel quel, sans transformation."""
    verifier_acces_client(utilisateur, client_id)
    try:
        instance = traduire_json(payload)
    except ErreurPayloadJsonInvalide as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    instance_id = etat.enregistrer_instance(client_id, instance, nom_projet=nom_projet)
    return {"instance_id": instance_id, "structure_contraintes": structure_contraintes(instance)}


class RequeteComprehension(BaseModel):
    client_id: str
    donnees_brutes: str
    nom_projet: str | None = None


@router.post("/comprehension/ingerer")
def ingerer_via_comprehension(
    requete: RequeteComprehension,
    etat: EtatAPI = Depends(obtenir_etat),
    modele: BaseChatModel = Depends(construire_modele_comprehension),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    verifier_acces_client(utilisateur, requete.client_id)
    try:
        resultat = comprendre_donnees_erp(modele, requete.donnees_brutes)
    except ErreurReponseAgentInvalide as erreur:
        raise HTTPException(status_code=502, detail=f"agent de compréhension : {erreur}") from erreur

    instance = valider_payload_trco(resultat.instance_brute)  # lève déjà un 422 si invalide

    instance_id = etat.enregistrer_instance(
        requete.client_id,
        instance,
        description_metier=resultat.description_metier,
        nom_projet=requete.nom_projet,
    )
    return {
        "instance_id": instance_id,
        "structure_contraintes": structure_contraintes(instance),
        "description_metier": resultat.description_metier,
        "avertissements": list(resultat.avertissements),
        "justifications": [{"contrainte": j.contrainte, "raison": j.raison} for j in resultat.justifications],
    }


class RequeteCsvLocal(BaseModel):
    """Requête pour ingérer depuis un dossier CSV local sur le serveur."""

    chemin_dossier: str
    client_id: str
    nom_projet: str | None = None


@router.post("/csv-local/ingerer")
def ingerer_depuis_csv_local(
    requete: RequeteCsvLocal,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, Any]:
    """Ingestion depuis un dossier local contenant trois fichiers CSV
    (taches.csv, ressources.csv, contraintes.csv).

    Utile pour :
    - Imports en masse depuis le serveur
    - Tests et développement
    - Scripts automatisés d'ingestion

    Args:
        requete: Contient le chemin du dossier et le client_id

    Returns:
        Instance ID, structure des contraintes et statistiques

    Raises:
        404: Dossier ou fichiers CSV introuvables
        422: Fichiers CSV invalides ou instance non valide
    """
    from pathlib import Path

    verifier_acces_client(utilisateur, requete.client_id)

    # Vérifier que le dossier existe
    dossier = Path(requete.chemin_dossier)
    if not dossier.exists():
        raise HTTPException(status_code=404, detail=f"Dossier introuvable : {requete.chemin_dossier}")

    if not dossier.is_dir():
        raise HTTPException(status_code=404, detail=f"Le chemin n'est pas un dossier : {requete.chemin_dossier}")

    # Vérifier que les trois fichiers existent
    fichier_taches = dossier / "taches.csv"
    fichier_ressources = dossier / "ressources.csv"
    fichier_contraintes = dossier / "contraintes.csv"

    fichiers_manquants = []
    if not fichier_taches.exists():
        fichiers_manquants.append("taches.csv")
    if not fichier_ressources.exists():
        fichiers_manquants.append("ressources.csv")
    if not fichier_contraintes.exists():
        fichiers_manquants.append("contraintes.csv")

    if fichiers_manquants:
        raise HTTPException(
            status_code=404,
            detail=f"Fichier(s) manquant(s) dans {requete.chemin_dossier}: {', '.join(fichiers_manquants)}",
        )

    # Lire les fichiers
    try:
        taches_octets = fichier_taches.read_bytes()
        ressources_octets = fichier_ressources.read_bytes()
        contraintes_octets = fichier_contraintes.read_bytes()
    except Exception as erreur:
        raise HTTPException(
            status_code=500, detail=f"Erreur lors de la lecture des fichiers : {erreur}"
        ) from erreur

    # Traduire en instance TRCO
    try:
        instance = traduire_csv(taches_octets, ressources_octets, contraintes_octets)
    except ErreurFichierCsvInvalide as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    # Enregistrer l'instance
    instance_id = etat.enregistrer_instance(requete.client_id, instance, nom_projet=requete.nom_projet)

    # Préparer la réponse avec statistiques
    return {
        "instance_id": instance_id,
        "structure_contraintes": structure_contraintes(instance),
        "statistiques": {
            "taches": len(instance.taches),
            "ressources": len(instance.ressources),
            "contraintes": len(instance.contraintes),
            "objectifs": len(instance.objectifs),
        },
        "chemin_source": requete.chemin_dossier,
    }
