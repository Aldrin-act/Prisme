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

import json
from typing import TYPE_CHECKING, Any

import httpx
import psycopg
from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ValidationError

from adapters.agent_comprehension import (
    comprendre_donnees_erp,
    dsn_lecture_seule_pour_client,
    explorer_base_de_donnees,
)
from adapters.csv_import import ErreurFichierInvalide as ErreurFichierCsvInvalide
from adapters.csv_import import traduire as traduire_csv
from adapters.greensig import extraire_et_traduire
from adapters.json_import import ErreurPayloadInvalide as ErreurPayloadJsonInvalide
from adapters.json_import import traduire as traduire_json
from api.autorisation import verifier_acces_client
from api.etat import EtatAPI, obtenir_etat, structure_contraintes
from api.input_validation import erreurs_serialisables, valider_payload_trco
from api.routes.auth import obtenir_utilisateur_courant
from generation.agents.base import ErreurReponseAgentInvalide
from generation.agents.client_llm import construire_modele_comprehension

if TYPE_CHECKING:
    from estimation import EstimateurDuree

CLIENT_ID_GREENSIG = "greensig"

router = APIRouter(prefix="/adapters", tags=["adapters"])


def _estimateur_duree_optionnel() -> EstimateurDuree | None:
    """`estimation` (scikit-learn) est un extra optionnel (`uv sync --extra
    estimation`) — import paresseux, même motif que `docker` dans
    `sandbox/runner.py`. Absent, l'ingestion se comporte comme avant : une
    durée manquante reste une erreur explicite (`CompetenceSansDureeEstimee`),
    jamais devinée silencieusement."""
    try:
        from estimation import estimateur_par_defaut
    except ImportError:
        return None
    return estimateur_par_defaut()


@router.post("/greensig/ingerer")
def ingerer_depuis_greensig(
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str]:
    try:
        instance = extraire_et_traduire()
    except (psycopg.OperationalError, httpx.HTTPError) as erreur:
        raise HTTPException(status_code=503, detail="service GreenSIG injoignable") from erreur
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    instance_id = etat.enregistrer_instance(CLIENT_ID_GREENSIG, instance, canal_ingestion="api")
    return {"instance_id": instance_id, "structure_contraintes": structure_contraintes(instance)}


def _valider_delimiteur(delimiteur: str) -> None:
    if len(delimiteur) != 1:
        raise HTTPException(status_code=422, detail=f"delimiteur doit être un seul caractère, reçu {delimiteur!r}")


@router.post("/csv/{client_id}")
async def ingerer_depuis_csv(
    client_id: str,
    taches: UploadFile = File(...),
    ressources: UploadFile = File(...),
    contraintes: UploadFile = File(...),
    commandes: UploadFile | None = File(None),
    delimiteur: str = ",",
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Ingestion depuis trois fichiers CSV séparés (§5.4) — Tâches, Ressources
    et Contraintes (`adapters/csv_import/`), format standard pour l'import
    de données tabulaires. `commandes` (optionnel, quatrième fichier) relie
    des tâches à une commande cliente et une date limite — dérive une
    échéance par tâche liée (`adapters/commande_derivation.py`), jamais
    transmis au solveur tel quel. `delimiteur` (un seul caractère, `,` par
    défaut) s'applique aux quatre fichiers identiquement."""
    verifier_acces_client(utilisateur, client_id)
    _valider_delimiteur(delimiteur)
    fichiers_requis = (taches, ressources, contraintes)
    for fichier in (*fichiers_requis, *((commandes,) if commandes is not None else ())):
        if not (fichier.filename or "").lower().endswith(".csv"):
            nom = fichier.filename or "(sans nom)"
            raise HTTPException(status_code=422, detail=f"{nom} doit être un fichier .csv")

    taches_octets, ressources_octets, contraintes_octets = (
        await taches.read(),
        await ressources.read(),
        await contraintes.read(),
    )
    commandes_octets = await commandes.read() if commandes is not None else None
    try:
        resultat = traduire_csv(
            taches_octets,
            ressources_octets,
            contraintes_octets,
            commandes_octets,
            estimateur_duree=_estimateur_duree_optionnel(),
            delimiteur=delimiteur,
        )
    except ErreurFichierCsvInvalide as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    instance_id = etat.enregistrer_instance(client_id, resultat.instance, canal_ingestion="csv")
    return {
        "instance_id": instance_id,
        "structure_contraintes": structure_contraintes(resultat.instance),
        "avertissements": list(resultat.avertissements),
    }


@router.post("/json/{client_id}")
def ingerer_depuis_json_avec_competences(
    client_id: str,
    payload: dict[str, Any] = Body(...),
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Ingestion depuis un JSON « brut avec compétences » (§5.4, `adapters/json_import/`)
    — sur-ensemble strict d'une instance T-R-C-O canonique : une tâche peut y
    porter une durée estimée (`duree_estimee_minutes`), permettant de dériver
    sa compatibilité depuis des `CompetenceRequise`/`Ressource.competences`
    plutôt que de la déclarer à la main. Un payload sans rien de tout ça est
    ingéré tel quel, sans transformation."""
    verifier_acces_client(utilisateur, client_id)
    try:
        resultat = traduire_json(payload, estimateur_duree=_estimateur_duree_optionnel())
    except ErreurPayloadJsonInvalide as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    instance_id = etat.enregistrer_instance(client_id, resultat.instance, canal_ingestion="json")
    return {
        "instance_id": instance_id,
        "structure_contraintes": structure_contraintes(resultat.instance),
        "avertissements": list(resultat.avertissements),
    }


class RequeteComprehension(BaseModel):
    client_id: str
    donnees_brutes: str


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
        canal_ingestion="agent_ia",
    )
    return {
        "instance_id": instance_id,
        "structure_contraintes": structure_contraintes(instance),
        "description_metier": resultat.description_metier,
        "avertissements": list(resultat.avertissements),
        "justifications": [{"contrainte": j.contrainte, "raison": j.raison} for j in resultat.justifications],
    }


_TAILLE_MAX_REPONSE_BDD_OCTETS = 5_000_000  # même garde-fou/raison que POST /sources/explorer-bdd


class RequeteIngestionBDD(BaseModel):
    client_id: str
    schemas: list[str] | None = None


@router.post("/bdd/ingerer")
def ingerer_depuis_bdd(
    requete: RequeteIngestionBDD,
    etat: EtatAPI = Depends(obtenir_etat),
    modele: BaseChatModel = Depends(construire_modele_comprehension),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Enchaîne exploration BDD (`POST /sources/explorer-bdd`) et agent de
    compréhension (`POST /comprehension/ingerer` ci-dessus) en un seul
    appel — même principe immédiat, sans persister ni la donnée brute
    explorée ni de `SourceDonnees` intermédiaire. Le DSN reste résolu côté
    serveur par `client_id` (`dsn_lecture_seule_pour_client`, jamais fourni
    dans la requête — même contrainte de sécurité anti-SSRF).

    Pour relire les données explorées avant de créer l'instance (plus
    prudent), préférer `POST /sources/explorer-bdd` puis `POST
    /comprehension/ingerer` séparément."""
    verifier_acces_client(utilisateur, requete.client_id)

    dsn = dsn_lecture_seule_pour_client(requete.client_id)
    if dsn is None:
        raise HTTPException(
            status_code=404, detail=f"exploration BDD non configurée pour ce client ({requete.client_id!r})"
        )

    schemas = tuple(requete.schemas) if requete.schemas else ("public",)

    try:
        exploration = explorer_base_de_donnees(modele, dsn, schemas=schemas)
    except ErreurReponseAgentInvalide as erreur:
        raise HTTPException(status_code=502, detail=f"agent d'exploration : {erreur}") from erreur
    except psycopg.OperationalError as erreur:
        raise HTTPException(status_code=503, detail="base de données injoignable pour ce client") from erreur
    except psycopg.Error as erreur:
        raise HTTPException(status_code=502, detail=f"requête d'exploration a échoué : {erreur}") from erreur

    donnees_brutes = json.dumps(exploration.donnees_json, ensure_ascii=False)
    taille = len(donnees_brutes.encode("utf-8"))
    if taille > _TAILLE_MAX_REPONSE_BDD_OCTETS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"résultat d'exploration trop volumineux ({taille} octets, max {_TAILLE_MAX_REPONSE_BDD_OCTETS})"
            ),
        )

    try:
        resultat = comprendre_donnees_erp(modele, donnees_brutes)
    except ErreurReponseAgentInvalide as erreur:
        raise HTTPException(status_code=502, detail=f"agent de compréhension : {erreur}") from erreur

    instance = valider_payload_trco(resultat.instance_brute)  # lève déjà un 422 si invalide

    instance_id = etat.enregistrer_instance(
        requete.client_id,
        instance,
        description_metier=resultat.description_metier,
        canal_ingestion="api",
    )
    return {
        "instance_id": instance_id,
        "structure_contraintes": structure_contraintes(instance),
        "description_metier": resultat.description_metier,
        "avertissements": [*exploration.avertissements, *resultat.avertissements],
        "justifications": [{"contrainte": j.contrainte, "raison": j.raison} for j in resultat.justifications],
        "requetes_executees": list(exploration.requetes_executees),
    }


class RequeteCsvLocal(BaseModel):
    """Requête pour ingérer depuis un dossier CSV local sur le serveur."""

    chemin_dossier: str
    client_id: str
    delimiteur: str = ","


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
    _valider_delimiteur(requete.delimiteur)

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
        resultat = traduire_csv(
            taches_octets,
            ressources_octets,
            contraintes_octets,
            estimateur_duree=_estimateur_duree_optionnel(),
            delimiteur=requete.delimiteur,
        )
    except ErreurFichierCsvInvalide as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur
    instance = resultat.instance

    # Enregistrer l'instance
    instance_id = etat.enregistrer_instance(requete.client_id, instance, canal_ingestion="csv")

    # Préparer la réponse avec statistiques
    return {
        "instance_id": instance_id,
        "structure_contraintes": structure_contraintes(instance),
        "avertissements": list(resultat.avertissements),
        "statistiques": {
            "taches": len(instance.taches),
            "ressources": len(instance.ressources),
            "contraintes": len(instance.contraintes),
            "objectifs": len(instance.objectifs),
        },
        "chemin_source": requete.chemin_dossier,
    }
