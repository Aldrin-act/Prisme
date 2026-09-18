"""Sources de données (§5.4 bis) : persiste des données brutes (export ERP sans
adaptateur dédié, collé ou déposé par un humain) séparément de leur
conversion — une même donnée brute peut être reconvertie plusieurs fois via
l'agent de compréhension (nouvel essai après un rejet, DSL affiné...) sans
jamais devoir être re-saisie. Le même garde-fou déterministe (§6.7) juge
chaque tentative, comme pour tout autre payload.

Volontairement minimal : une source ne porte ni pointeur "instance courante"
ni historique d'exécution — chaque instance générée s'exécute directement
par son propre `instance_id` (`POST /execution/{instance_id}`), sans jamais
passer par une source. `lister_instances_pour_source` reste l'historique de
provenance (quelles instances cette source a produites), pas un lien
d'usage.

Distinct de `POST /adapters/comprehension/ingerer` (conversion immédiate,
sans persistance de la donnée brute ni d'historique) — les deux chemins
coexistent, celui-ci est le chemin recommandé depuis le dashboard.

Le `client_id` d'une source vient toujours du compte authentifié, jamais
d'une valeur fournie par la requête (sauf pour un admin ciblant un autre
client explicitement) — voir `api/autorisation.py`.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Literal

import httpx
import psycopg
from fastapi import APIRouter, Depends, HTTPException
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ValidationError

from adapters.agent_comprehension import (
    comprendre_donnees_erp,
    construire_prompt_comprehension,
    dsn_lecture_seule_pour_client,
    explorer_base_de_donnees,
)
from adapters.competence_derivation import ResultatTraduction
from adapters.csv_import import ErreurFichierInvalide as ErreurFichierCsvInvalide
from adapters.csv_import import traduire as traduire_csv
from adapters.json_import import ErreurPayloadInvalide as ErreurPayloadJsonInvalide
from adapters.json_import import traduire as traduire_json
from api.autorisation import client_id_pour_filtre, verifier_acces_client
from api.etat import EtatAPI, obtenir_etat, structure_contraintes
from api.input_validation import erreurs_serialisables, valider_payload_trco
from api.routes.auth import obtenir_utilisateur_courant
from generation.agents.base import ErreurReponseAgentInvalide
from generation.agents.client_llm import construire_modele_comprehension

if TYPE_CHECKING:
    from estimation import EstimateurDuree

router = APIRouter(prefix="/sources", tags=["sources"])


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


class ErreurStructureNonReconnue(Exception):
    """Le texte brut d'une source ne peut être scindé ni en JSON canonique, ni
    en blocs CSV Tâches/Ressources/Contraintes identifiables — reste éligible
    à l'agent de compréhension (`generer_instance`), qui interprète n'importe
    quel texte libre, structuré ou non."""


# Un export multi-fichiers concaténé par le formulaire (Front/prismatron-solver-forge/
# src/routes/_authenticated/donnees.tsx, `FormulaireNouvelleSource`) marque chaque
# fichier par son nom d'origine — c'est le signal le plus fiable pour reconstituer
# les trois fichiers attendus par `adapters.csv_import.traduire`, avant de retomber
# sur une détection par en-tête de colonnes (voir `_type_par_entete`).
_MARQUEUR_BLOC = re.compile(r"^--- (.+?) ---$", re.MULTILINE)

_MOTS_CLES_PAR_TABLE = {"taches": "tache", "ressources": "ressource", "contraintes": "contrainte"}


def _decouper_blocs_csv(texte: str) -> list[tuple[str, str]]:
    """Scinde un texte multi-fichiers en `(nom_original, contenu)` — un texte
    sans marqueur `--- nom ---` est traité comme un unique bloc anonyme
    (`nom_original` vide)."""
    positions = list(_MARQUEUR_BLOC.finditer(texte))
    if not positions:
        return [("", texte.strip())]
    blocs = []
    for i, marqueur in enumerate(positions):
        fin = positions[i + 1].start() if i + 1 < len(positions) else len(texte)
        blocs.append((marqueur.group(1), texte[marqueur.end() : fin].strip()))
    return blocs


def _type_par_nom_fichier(nom: str) -> str | None:
    nom = nom.lower()
    return next((table for table, mot_cle in _MOTS_CLES_PAR_TABLE.items() if mot_cle in nom), None)


def _type_par_entete(bloc: str) -> str | None:
    """Détection de repli quand le nom de fichier n'est pas parlant — d'après
    les colonnes qui n'existent que dans un seul des trois fichiers attendus
    (voir `adapters/csv_import/traducteur.py`, colonnes requises/optionnelles).
    `taches.csv` n'a plus de colonne qui lui soit propre (seulement `id`/`nom`,
    partagées avec `ressources.csv`) : un bloc `taches` anonyme ne peut donc
    plus être identifié ici — il retombe sur le dernier repli par élimination
    dans `_reconstruire_fichiers_csv` ci-dessous."""
    premiere_ligne = bloc.split("\n", 1)[0] if bloc else ""
    colonnes = {c.strip().lower() for c in premiere_ligne.split(",")}
    if "type" in colonnes:
        return "contraintes"
    if "competences" in colonnes:
        return "ressources"
    return None


def _reconstruire_fichiers_csv(texte: str) -> tuple[bytes, bytes, bytes]:
    blocs = _decouper_blocs_csv(texte)
    assignation: dict[str, str] = {}
    non_assignes: list[str] = []
    for nom, contenu in blocs:
        table = _type_par_nom_fichier(nom) or _type_par_entete(contenu)
        if table and table not in assignation:
            assignation[table] = contenu
        else:
            non_assignes.append(contenu)

    # Dernier repli : un bloc restant sans type reconnu comble une case encore
    # vide, dans l'ordre — mieux qu'un rejet si deux des trois fichiers ont été
    # identifiés sans ambiguïté et qu'il n'en reste qu'un.
    for table in ("taches", "ressources", "contraintes"):
        if table not in assignation and non_assignes:
            assignation[table] = non_assignes.pop(0)

    manquantes = [t for t in ("taches", "ressources", "contraintes") if t not in assignation]
    if manquantes:
        raise ErreurStructureNonReconnue(
            f"fichier(s) non identifié(s) : {', '.join(manquantes)} "
            "(attendu : un bloc Tâches, un Ressources, un Contraintes — par nom de fichier ou en-tête de colonnes)"
        )
    return (
        assignation["taches"].encode("utf-8"),
        assignation["ressources"].encode("utf-8"),
        assignation["contraintes"].encode("utf-8"),
    )


def _traduire_deterministe(donnees_brutes: str) -> ResultatTraduction:
    """JSON canonique (`adapters.json_import`) si le texte entier en est un ;
    sinon CSV Tâches/Ressources/Contraintes (`adapters.csv_import`), reconstitués
    depuis le texte brut. Lève `ErreurStructureNonReconnue` si ni l'un ni
    l'autre n'est identifiable ; laisse passer telles quelles
    `ErreurFichierCsvInvalide`/`ErreurPayloadJsonInvalide`/`ValidationError`
    quand la structure est identifiée mais son contenu invalide."""
    texte = donnees_brutes.strip()
    estimateur_duree = _estimateur_duree_optionnel()
    try:
        payload = json.loads(texte)
    except (json.JSONDecodeError, ValueError):
        payload = None
    if isinstance(payload, dict):
        return traduire_json(payload, estimateur_duree=estimateur_duree)

    taches_csv, ressources_csv, contraintes_csv = _reconstruire_fichiers_csv(texte)
    return traduire_csv(taches_csv, ressources_csv, contraintes_csv, estimateur_duree=estimateur_duree)


class RequeteCreationSource(BaseModel):
    donnees_brutes: str
    nom: str | None = None
    client_id: str | None = None  # admin uniquement : cible un client autre que le sien


def _client_id_effectif(requete_client_id: str | None, utilisateur: dict) -> str:
    if utilisateur.get("role") == "admin" and requete_client_id:
        return requete_client_id
    client_id = utilisateur.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="compte sans client_id associé")
    return client_id


@router.post("")
def creer_source(
    requete: RequeteCreationSource,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str]:
    client_id = _client_id_effectif(requete.client_id, utilisateur)
    source_id = etat.enregistrer_source(client_id, requete.donnees_brutes, requete.nom)
    return {"source_id": source_id}


@router.get("")
def lister_sources(
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> list[dict[str, object]]:
    return etat.lister_sources(client_id=client_id_pour_filtre(utilisateur))


@router.get("/{source_id}")
def obtenir_source(
    source_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    try:
        source = etat.recuperer_source(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="source inconnue") from None

    verifier_acces_client(utilisateur, source.client_id)

    return {
        "source_id": source.id,
        "client_id": source.client_id,
        "nom": source.nom,
        "donnees_brutes": source.donnees_brutes,
        "date_creation": source.date_creation,
        "instances": etat.lister_instances_pour_source(source_id),
    }


@router.delete("/{source_id}", status_code=204)
def supprimer_source(
    source_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> None:
    """Ne supprime que la donnée brute — les instances déjà générées à partir
    d'elle restent intactes et exécutables, seul le lien de provenance
    disparaît."""
    try:
        source = etat.recuperer_source(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="source inconnue") from None

    verifier_acces_client(utilisateur, source.client_id)
    etat.supprimer_source(source_id)


@router.get("/{source_id}/prompt-comprehension")
def previsualiser_prompt_comprehension(
    source_id: str,
    instructions_complementaires: str | None = None,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str]:
    """Aperçu du prompt système + utilisateur que `POST /{source_id}/generer-instance`
    enverrait réellement à l'agent de compréhension — construit via
    `adapters.agent_comprehension.construire_prompt_comprehension`, sans jamais appeler le LLM
    (gratuit, immédiat), pour qu'un humain puisse vérifier ce qui sera envoyé avant de
    déclencher une génération qui, elle, a un vrai coût en tokens. `instructions_complementaires`
    (paramètre de requête, optionnel) : mêmes instructions que celles qu'on passerait à
    `POST /{source_id}/generer-instance`, pour que l'aperçu reflète vraiment ce qui serait
    envoyé."""
    try:
        source = etat.recuperer_source(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="source inconnue") from None

    verifier_acces_client(utilisateur, source.client_id)

    prompt_systeme, prompt_utilisateur = construire_prompt_comprehension(
        source.donnees_brutes, instructions_complementaires
    )
    return {"prompt_systeme": prompt_systeme, "prompt_utilisateur": prompt_utilisateur}


class RequetePromptComprehension(BaseModel):
    donnees_brutes: str
    # Contexte métier libre optionnel — voir construire_prompt_comprehension. Jamais un moyen de
    # réécrire les règles de traduction elles-mêmes, seulement un aperçu de ce qui serait envoyé.
    instructions_complementaires: str | None = None


@router.post("/prompt-comprehension")
def previsualiser_prompt_comprehension_sans_source(
    requete: RequetePromptComprehension,
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str]:
    """Même aperçu que `GET /{source_id}/prompt-comprehension` ci-dessus, mais pour des données
    brutes pas encore enregistrées en source — utilisé par le formulaire de création (avant
    toute soumission), là où la route ci-dessus exige un `source_id` déjà persistant. Rien n'est
    lu depuis l'état (aucune fuite de données d'un autre client possible), seule
    l'authentification est requise, pas de vérification de propriété."""
    prompt_systeme, prompt_utilisateur = construire_prompt_comprehension(
        requete.donnees_brutes, requete.instructions_complementaires
    )
    return {"prompt_systeme": prompt_systeme, "prompt_utilisateur": prompt_utilisateur}


class RequeteGenererInstance(BaseModel):
    # Optionnel, corps de requête lui-même optionnel (voir `generer_instance` ci-dessous) —
    # aucun appelant existant n'a besoin de changer quoi que ce soit.
    instructions_complementaires: str | None = None


@router.post("/{source_id}/generer-instance")
def generer_instance(
    source_id: str,
    requete: RequeteGenererInstance | None = None,
    etat: EtatAPI = Depends(obtenir_etat),
    modele: BaseChatModel = Depends(construire_modele_comprehension),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Rejouable à volonté sur la même source : chaque appel ajoute une
    instance à son historique de provenance, il ne remplace jamais les
    précédentes. L'instance produite s'exécute directement par son propre
    `instance_id` — aucune association supplémentaire n'est nécessaire.

    `requete.instructions_complementaires` (optionnel, jamais persisté sur la source elle-même —
    une tentative peut vouloir des instructions différentes de la précédente) : voir
    `construire_prompt_comprehension`."""
    try:
        source = etat.recuperer_source(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="source inconnue") from None

    verifier_acces_client(utilisateur, source.client_id)

    instructions = requete.instructions_complementaires if requete else None
    try:
        resultat = comprendre_donnees_erp(modele, source.donnees_brutes, instructions)
    except ErreurReponseAgentInvalide as erreur:
        raise HTTPException(status_code=502, detail=f"agent de compréhension : {erreur}") from erreur

    instance = valider_payload_trco(resultat.instance_brute)  # lève déjà un 422 si invalide

    instance_id = etat.enregistrer_instance(
        source.client_id,
        instance,
        source_id=source_id,
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


@router.post("/{source_id}/generer-instance-deterministe")
def generer_instance_deterministe(
    source_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Alternative à `generer_instance` sans appel LLM : traduit le texte brut
    déjà enregistré via les adaptateurs déterministes (`adapters.json_import`/
    `adapters.csv_import`) s'il est déjà structuré — gratuit, instantané, mais
    n'aboutit que si ce texte est un JSON canonique ou un export CSV
    Tâches/Ressources/Contraintes reconstituable ; sinon 422, direction
    `generer_instance` (l'agent), qui interprète n'importe quel texte libre."""
    try:
        source = etat.recuperer_source(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="source inconnue") from None

    verifier_acces_client(utilisateur, source.client_id)

    try:
        resultat = _traduire_deterministe(source.donnees_brutes)
    except ErreurStructureNonReconnue as erreur:
        raise HTTPException(
            status_code=422,
            detail=f"conversion déterministe impossible : {erreur} — utilisez « Générer une instance » (agent).",
        ) from erreur
    except (ErreurFichierCsvInvalide, ErreurPayloadJsonInvalide) as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    try:
        est_json = isinstance(json.loads(source.donnees_brutes.strip()), dict)
    except (json.JSONDecodeError, ValueError):
        est_json = False
    instance_id = etat.enregistrer_instance(
        source.client_id,
        resultat.instance,
        source_id=source_id,
        canal_ingestion="json" if est_json else "csv",
    )
    return {
        "instance_id": instance_id,
        "structure_contraintes": structure_contraintes(resultat.instance),
        "avertissements": list(resultat.avertissements),
    }


_TIMEOUT_EXPLORATION_API_SECONDES = 15.0
# Garde-fou taille — évite qu'une réponse gigantesque (mauvaise URL, endpoint
# non paginé sur un gros jeu de données) ne remonte telle quelle jusqu'au
# textarea "Données brutes" du navigateur.
_TAILLE_MAX_REPONSE_API_OCTETS = 5_000_000


class AuthentificationAPI(BaseModel):
    type: Literal["aucune", "cle_api", "porteur", "basique"] = "aucune"
    en_tete: str | None = None  # cle_api : nom de l'en-tête (ex. "X-API-Key")
    valeur: str | None = None  # cle_api : valeur de la clé
    jeton: str | None = None  # porteur : Authorization: Bearer <jeton>
    utilisateur: str | None = None  # basique
    mot_de_passe: str | None = None  # basique


class RequeteExplorationAPI(BaseModel):
    url: str
    methode: Literal["GET", "POST"] = "GET"
    authentification: AuthentificationAPI = AuthentificationAPI()
    corps: str | None = None  # POST uniquement ; ignoré en GET
    en_tetes: dict[str, str] | None = None


class ErreurReponseAPITropVolumineuse(Exception):
    def __init__(self, taille_octets: int) -> None:
        super().__init__(
            f"réponse trop volumineuse ({taille_octets} octets, max {_TAILLE_MAX_REPONSE_API_OCTETS})"
        )


def _appeler_api(requete: RequeteExplorationAPI, client: httpx.Client | None = None) -> str:
    """Un seul appel HTTP — identifiants (clé/jeton/mot de passe) jamais
    persistés ni journalisés, utilisés une fois pour cet appel puis oubliés,
    même principe que la connexion BDD à la volée qu'on remplace ici. Le
    corps de la réponse est renvoyé tel quel, texte ou JSON, sans
    interprétation : c'est `comprendre_donnees_erp` (l'agent de
    compréhension), en aval, une fois la source enregistrée, qui en fera
    quelque chose. `client` injectable (même motif que
    `adapters/greensig/extraction_api.py::extraire_payload_api`) pour les
    tests, jamais de connexion réseau réelle en test."""
    en_tetes = dict(requete.en_tetes or {})
    auth = requete.authentification
    if auth.type == "cle_api" and auth.en_tete and auth.valeur:
        en_tetes[auth.en_tete] = auth.valeur
    elif auth.type == "porteur" and auth.jeton:
        en_tetes["Authorization"] = f"Bearer {auth.jeton}"
    auth_basique = (
        (auth.utilisateur, auth.mot_de_passe or "") if auth.type == "basique" and auth.utilisateur else None
    )

    client_reel = client or httpx.Client(timeout=_TIMEOUT_EXPLORATION_API_SECONDES)
    try:
        reponse = client_reel.request(
            requete.methode,
            requete.url,
            headers=en_tetes or None,
            content=requete.corps.encode("utf-8") if requete.corps else None,
            auth=auth_basique,
        )
        reponse.raise_for_status()
    finally:
        if client is None:
            client_reel.close()

    corps_octets = len(reponse.content)
    if corps_octets > _TAILLE_MAX_REPONSE_API_OCTETS:
        raise ErreurReponseAPITropVolumineuse(corps_octets)
    return reponse.text


@router.post("/explorer-api")
def explorer_api(
    requete: RequeteExplorationAPI,
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Interroge une API HTTP quelconque (URL/authentification fournies par
    la requête, jamais enregistrées) pour un ERP sans adaptateur dédié —
    généralise le principe de `adapters/greensig/extraction_api.py`
    (spécifique à GreenSIG, 5 ressources fixes, jamais utilisé ici) à
    n'importe quelle API dont on ne connaît pas la forme à l'avance : un seul
    appel, le corps de la réponse est renvoyé tel quel.

    Ne persiste rien : le texte renvoyé est destiné à remplir le champ
    « Données brutes » du formulaire de création de source, pour relecture
    humaine avant tout enregistrement — exactement comme le contenu d'un
    fichier CSV/JSON déposé à la main. Une réponse paginée ne renvoie que sa
    première page ; visez directement l'URL/les paramètres qui renvoient tout
    en un seul appel si l'API le permet."""
    try:
        corps = _appeler_api(requete)
    except httpx.HTTPStatusError as erreur:
        detail = erreur.response.text[:300]
        raise HTTPException(
            status_code=422, detail=f"réponse en erreur ({erreur.response.status_code}) : {detail}"
        ) from erreur
    except httpx.HTTPError as erreur:
        raise HTTPException(status_code=422, detail=f"appel API impossible : {erreur}") from erreur
    except ErreurReponseAPITropVolumineuse as erreur:
        raise HTTPException(status_code=422, detail=str(erreur)) from erreur

    return {"donnees_brutes": corps}


_TAILLE_MAX_REPONSE_BDD_OCTETS = 5_000_000  # même garde-fou/raison que _TAILLE_MAX_REPONSE_API_OCTETS
_SCHEMAS_PAR_DEFAUT: tuple[str, ...] = ("public",)


class RequeteExplorationBDD(BaseModel):
    client_id: str | None = None  # admin uniquement, même convention que RequeteCreationSource
    schemas: list[str] | None = None


@router.post("/explorer-bdd")
def explorer_bdd(
    requete: RequeteExplorationBDD,
    modele: BaseChatModel = Depends(construire_modele_comprehension),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Explore en lecture seule la base d'un client déjà configurée côté
    serveur (`dsn_lecture_seule_pour_client` — jamais un DSN fourni dans la
    requête elle-même, contrainte de sécurité anti-SSRF, à la différence
    d'`explorer_api` ci-dessus qui accepte URL/authentification par appel).

    Ne persiste rien, même principe non-persistant qu'`explorer_api` : le
    JSON renvoyé est destiné à remplir le champ « Données brutes » du
    formulaire de création de source, pour relecture humaine avant tout
    enregistrement (`POST /sources`)."""
    client_id = _client_id_effectif(requete.client_id, utilisateur)

    dsn = dsn_lecture_seule_pour_client(client_id)
    if dsn is None:
        raise HTTPException(
            status_code=404, detail=f"exploration BDD non configurée pour ce client ({client_id!r})"
        )

    schemas = tuple(requete.schemas) if requete.schemas else _SCHEMAS_PAR_DEFAUT

    try:
        resultat = explorer_base_de_donnees(modele, dsn, schemas=schemas)
    except ErreurReponseAgentInvalide as erreur:
        raise HTTPException(status_code=502, detail=f"agent d'exploration : {erreur}") from erreur
    except psycopg.OperationalError as erreur:
        raise HTTPException(status_code=503, detail="base de données injoignable pour ce client") from erreur
    except psycopg.Error as erreur:
        raise HTTPException(status_code=502, detail=f"requête d'exploration a échoué : {erreur}") from erreur

    donnees_brutes = json.dumps(resultat.donnees_json, ensure_ascii=False)
    taille = len(donnees_brutes.encode("utf-8"))
    if taille > _TAILLE_MAX_REPONSE_BDD_OCTETS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"résultat d'exploration trop volumineux ({taille} octets, max {_TAILLE_MAX_REPONSE_BDD_OCTETS})"
            ),
        )

    return {
        "donnees_brutes": donnees_brutes,
        "avertissements": list(resultat.avertissements),
        "requetes_executees": list(resultat.requetes_executees),
    }
