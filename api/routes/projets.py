"""Projets (§5.4 bis) : persistent des données brutes (export ERP sans
adaptateur dédié, collé ou déposé par un humain) séparément de leur
conversion — une même donnée brute peut être reconvertie plusieurs fois
via l'agent de compréhension (nouvel essai après un rejet, DSL affiné...)
sans jamais devoir être re-saisie. Chaque conversion réussie ajoute une
instance T-R-C-O de plus à l'historique du projet (`instances`,
`lister_instances_pour_projet`, inchangé) ; le même garde-fou déterministe
(§6.7) juge chaque tentative, comme pour tout autre payload.

Distinct de l'instance *courante* du projet (`instance_id`) : celle contre
laquelle l'exécution se déclenche (`POST /execution/{projet_id}`). Une
instance est un gabarit réutilisable (règles métier d'un secteur donné) —
plusieurs projets peuvent partager la même instance courante, chacun avec
son propre historique d'exécution/planning. `generer-instance` pointe
automatiquement le projet vers la dernière instance générée ;
`POST /{projet_id}/instance` permet de réutiliser une instance existante
sans repasser par l'agent de compréhension.

Distinct de `POST /adapters/comprehension/ingerer` (conversion immédiate,
sans persistance de la donnée brute ni d'historique) — les deux chemins
coexistent, celui-ci est le chemin recommandé depuis le dashboard.

Le `client_id` d'un projet vient toujours du compte authentifié, jamais
d'une valeur fournie par la requête (sauf pour un admin ciblant un autre
client explicitement) — voir `api/autorisation.py`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel

from adapters.agent_comprehension import comprendre_donnees_erp
from api.autorisation import client_id_pour_filtre, verifier_acces_client
from api.etat import ClientIncompatible, EtatAPI, obtenir_etat, structure_contraintes
from api.input_validation import valider_payload_trco
from api.routes.auth import obtenir_utilisateur_courant
from generation.agents.base import ErreurReponseAgentInvalide
from generation.agents.client_llm import construire_modele_comprehension

router = APIRouter(prefix="/projets", tags=["projets"])


class RequeteCreationProjet(BaseModel):
    donnees_brutes: str
    nom: str | None = None
    client_id: str | None = None  # admin uniquement : cible un client autre que le sien


class RequeteAssociationInstance(BaseModel):
    instance_id: str


def _client_id_effectif(requete_client_id: str | None, utilisateur: dict) -> str:
    if utilisateur.get("role") == "admin" and requete_client_id:
        return requete_client_id
    client_id = utilisateur.get("client_id")
    if not client_id:
        raise HTTPException(status_code=400, detail="compte sans client_id associé")
    return client_id


@router.post("")
def creer_projet(
    requete: RequeteCreationProjet,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str]:
    client_id = _client_id_effectif(requete.client_id, utilisateur)
    projet_id = etat.enregistrer_projet(client_id, requete.donnees_brutes, requete.nom)
    return {"projet_id": projet_id}


@router.get("")
def lister_projets(
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> list[dict[str, object]]:
    return etat.lister_projets(client_id=client_id_pour_filtre(utilisateur))


@router.get("/{projet_id}")
def obtenir_projet(
    projet_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    try:
        projet = etat.recuperer_projet(projet_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="projet inconnu") from None

    verifier_acces_client(utilisateur, projet.client_id)

    return {
        "projet_id": projet.id,
        "client_id": projet.client_id,
        "nom": projet.nom,
        "donnees_brutes": projet.donnees_brutes,
        "date_creation": projet.date_creation,
        "instance_id": projet.instance_id,
        "instances": etat.lister_instances_pour_projet(projet_id),
    }


@router.delete("/{projet_id}", status_code=204)
def supprimer_projet(
    projet_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> None:
    """Supprime le projet et son propre historique d'exécution/planning —
    n'affecte jamais les instances (elles restent, réutilisables par
    d'autres projets, seul le lien de provenance disparaît)."""
    try:
        projet = etat.recuperer_projet(projet_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="projet inconnu") from None

    verifier_acces_client(utilisateur, projet.client_id)
    etat.supprimer_projet(projet_id)


@router.post("/{projet_id}/generer-instance")
def generer_instance(
    projet_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    modele: BaseChatModel = Depends(construire_modele_comprehension),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Rejouable à volonté sur le même projet : chaque appel ajoute une
    instance à son historique, il ne remplace jamais les précédentes."""
    try:
        projet = etat.recuperer_projet(projet_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="projet inconnu") from None

    verifier_acces_client(utilisateur, projet.client_id)

    try:
        resultat = comprendre_donnees_erp(modele, projet.donnees_brutes)
    except ErreurReponseAgentInvalide as erreur:
        raise HTTPException(status_code=502, detail=f"agent de compréhension : {erreur}") from erreur

    instance = valider_payload_trco(resultat.instance_brute)  # lève déjà un 422 si invalide

    instance_id = etat.enregistrer_instance(projet.client_id, instance, projet_id=projet_id)
    etat.associer_instance_projet(projet_id, instance_id)  # devient l'instance courante du projet
    return {
        "instance_id": instance_id,
        "structure_contraintes": structure_contraintes(instance),
        "avertissements": list(resultat.avertissements),
        "justifications": [{"contrainte": j.contrainte, "raison": j.raison} for j in resultat.justifications],
    }


@router.post("/{projet_id}/instance")
def associer_instance(
    projet_id: str,
    requete: RequeteAssociationInstance,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str]:
    """Réutilise une instance existante (gabarit sectoriel déjà validé,
    éventuellement celle d'un autre projet) comme instance courante de ce
    projet, sans repasser par l'agent de compréhension — l'alternative à
    `generer-instance` quand l'instance voulue existe déjà."""
    try:
        projet = etat.recuperer_projet(projet_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="projet inconnu") from None

    verifier_acces_client(utilisateur, projet.client_id)

    try:
        etat.associer_instance_projet(projet_id, requete.instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None
    except ClientIncompatible as erreur:
        raise HTTPException(status_code=403, detail=str(erreur)) from erreur

    return {"projet_id": projet_id, "instance_id": requete.instance_id}
