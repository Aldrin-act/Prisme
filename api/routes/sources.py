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

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ValidationError

from adapters.agent_comprehension import comprendre_donnees_erp
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

router = APIRouter(prefix="/sources", tags=["sources"])


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
    (voir `adapters/csv_import/traducteur.py`, colonnes requises/optionnelles)."""
    premiere_ligne = bloc.split("\n", 1)[0] if bloc else ""
    colonnes = {c.strip().lower() for c in premiere_ligne.split(",")}
    if "type" in colonnes:
        return "contraintes"
    if "competences" in colonnes:
        return "ressources"
    if "duree_estimee_jours" in colonnes:
        return "taches"
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
    try:
        payload = json.loads(texte)
    except (json.JSONDecodeError, ValueError):
        payload = None
    if isinstance(payload, dict):
        return traduire_json(payload)

    taches_csv, ressources_csv, contraintes_csv = _reconstruire_fichiers_csv(texte)
    return traduire_csv(taches_csv, ressources_csv, contraintes_csv)


class RequeteCreationSource(BaseModel):
    donnees_brutes: str
    nom: str | None = None
    client_id: str | None = None  # admin uniquement : cible un client autre que le sien
    # Capturé une fois ici, réutilisé à chaque reconversion (generer_instance/
    # generer_instance_deterministe) — oriente le prompt de l'agent de
    # compréhension sans devoir être re-saisi à chaque tentative.
    secteur_activite: str | None = None


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
    source_id = etat.enregistrer_source(client_id, requete.donnees_brutes, requete.nom, requete.secteur_activite)
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
        "secteur_activite": source.secteur_activite,
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


@router.post("/{source_id}/generer-instance")
def generer_instance(
    source_id: str,
    nom_projet: str | None = None,
    etat: EtatAPI = Depends(obtenir_etat),
    modele: BaseChatModel = Depends(construire_modele_comprehension),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Rejouable à volonté sur la même source : chaque appel ajoute une
    instance à son historique de provenance, il ne remplace jamais les
    précédentes. L'instance produite s'exécute directement par son propre
    `instance_id` — aucune association supplémentaire n'est nécessaire.
    `nom_projet` (query, optionnel) étiquette librement l'instance produite ;
    à défaut, reprend le nom de la source elle-même (`source.nom`).
    `secteur_activite` n'est pas un paramètre ici : il vient de la source
    (`source.secteur_activite`, capturé une fois à sa création) et oriente
    le prompt de l'agent de compréhension à chaque reconversion."""
    try:
        source = etat.recuperer_source(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="source inconnue") from None

    verifier_acces_client(utilisateur, source.client_id)

    try:
        resultat = comprendre_donnees_erp(modele, source.donnees_brutes, secteur_activite=source.secteur_activite)
    except ErreurReponseAgentInvalide as erreur:
        raise HTTPException(status_code=502, detail=f"agent de compréhension : {erreur}") from erreur

    instance = valider_payload_trco(resultat.instance_brute)  # lève déjà un 422 si invalide

    instance_id = etat.enregistrer_instance(
        source.client_id,
        instance,
        source_id=source_id,
        description_metier=resultat.description_metier,
        nom_projet=nom_projet if nom_projet is not None else source.nom,
        secteur_activite=source.secteur_activite,
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
    nom_projet: str | None = None,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Alternative à `generer_instance` sans appel LLM : traduit le texte brut
    déjà enregistré via les adaptateurs déterministes (`adapters.json_import`/
    `adapters.csv_import`) s'il est déjà structuré — gratuit, instantané, mais
    n'aboutit que si ce texte est un JSON canonique ou un export CSV
    Tâches/Ressources/Contraintes reconstituable ; sinon 422, direction
    `generer_instance` (l'agent), qui interprète n'importe quel texte libre.
    `nom_projet` (query, optionnel) suit la même convention que
    `generer_instance` (défaut : `source.nom`)."""
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

    instance_id = etat.enregistrer_instance(
        source.client_id,
        resultat.instance,
        source_id=source_id,
        nom_projet=nom_projet if nom_projet is not None else source.nom,
        secteur_activite=source.secteur_activite,
    )
    return {
        "instance_id": instance_id,
        "structure_contraintes": structure_contraintes(resultat.instance),
        "avertissements": list(resultat.avertissements),
    }
