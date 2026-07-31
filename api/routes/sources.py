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

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel

from adapters.agent_comprehension import comprendre_donnees_erp
from api.autorisation import client_id_pour_filtre, verifier_acces_client
from api.etat import EtatAPI, obtenir_etat, structure_contraintes
from api.input_validation import valider_payload_trco
from api.routes.auth import obtenir_utilisateur_courant
from generation.agents.base import ErreurReponseAgentInvalide
from generation.agents.client_llm import construire_modele_comprehension

router = APIRouter(prefix="/sources", tags=["sources"])


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


@router.post("/{source_id}/generer-instance")
def generer_instance(
    source_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    modele: BaseChatModel = Depends(construire_modele_comprehension),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Rejouable à volonté sur la même source : chaque appel ajoute une
    instance à son historique de provenance, il ne remplace jamais les
    précédentes. L'instance produite s'exécute directement par son propre
    `instance_id` — aucune association supplémentaire n'est nécessaire."""
    try:
        source = etat.recuperer_source(source_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="source inconnue") from None

    verifier_acces_client(utilisateur, source.client_id)

    try:
        resultat = comprendre_donnees_erp(modele, source.donnees_brutes)
    except ErreurReponseAgentInvalide as erreur:
        raise HTTPException(status_code=502, detail=f"agent de compréhension : {erreur}") from erreur

    instance = valider_payload_trco(resultat.instance_brute)  # lève déjà un 422 si invalide

    instance_id = etat.enregistrer_instance(source.client_id, instance, source_id=source_id)
    return {
        "instance_id": instance_id,
        "structure_contraintes": structure_contraintes(instance),
        "avertissements": list(resultat.avertissements),
        "justifications": [{"contrainte": j.contrainte, "raison": j.raison} for j in resultat.justifications],
    }
