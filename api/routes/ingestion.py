"""Réception du payload T-R-C-O canonique venant d'un adaptateur ERP (§5.1, §5.5)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError

from api.autorisation import verifier_acces_client
from api.etat import EtatAPI, SecteurActivite, obtenir_etat, structure_contraintes
from api.input_validation import erreurs_serialisables, valider_payload_trco
from api.routes.auth import obtenir_utilisateur_courant
from dsl.schema import Objectif

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class RequeteModificationObjectifs(BaseModel):
    objectifs: list[Objectif] = Field(min_length=1)


@router.post("/{client_id}")
def ingerer_instance(
    client_id: str,
    payload: dict[str, Any],
    nom_projet: str | None = None,
    secteur_activite: SecteurActivite | None = None,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, str]:
    """Valide le payload (garde-fou amont, §6.7) et le met en attente
    d'exécution. `nom_projet`/`secteur_activite` (query, optionnels)
    étiquettent librement l'instance créée. Pour modifier une instance déjà
    ingérée, voir `PUT /{instance_id}` ci-dessous — modification en place,
    jamais une nouvelle instance."""
    verifier_acces_client(utilisateur, client_id)
    instance = valider_payload_trco(payload)
    instance_id = etat.enregistrer_instance(
        client_id, instance, nom_projet=nom_projet, secteur_activite=secteur_activite
    )
    return {"instance_id": instance_id, "structure_contraintes": structure_contraintes(instance)}


@router.get("/{instance_id}")
def obtenir_instance(
    instance_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Contenu T-R-C-O complet d'une instance déjà ingérée — pour l'afficher
    (dashboard), jamais pour la re-générer (le solveur, une fois validé,
    reste figé quelle que soit la relecture qu'on en fait, §7)."""
    try:
        client_id, instance = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)

    return {
        "instance_id": instance_id,
        "client_id": client_id,
        "structure_contraintes": structure_contraintes(instance),
        "description_metier": etat.recuperer_description_metier(instance_id),
        "nom_projet": etat.recuperer_nom_projet(instance_id),
        "secteur_activite": etat.recuperer_secteur_activite(instance_id),
        **instance.model_dump(mode="json"),
    }


@router.patch("/{instance_id}/objectifs")
def modifier_objectifs_instance(
    instance_id: str,
    requete: RequeteModificationObjectifs,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Change l'objectif d'optimisation d'une instance déjà ingérée sans
    devoir tout réingérer — seul champ pour lequel une modification en place
    a du sens (taches/ressources/contraintes définissent le problème,
    l'objectif ne fait qu'orienter le solveur dessus)."""
    try:
        client_id, _ = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)

    try:
        instance = etat.modifier_objectifs(instance_id, requete.objectifs)
    except ValidationError as erreur:
        raise HTTPException(status_code=422, detail=erreurs_serialisables(erreur)) from erreur

    return {
        "instance_id": instance_id,
        "client_id": client_id,
        "structure_contraintes": structure_contraintes(instance),
        **instance.model_dump(mode="json"),
    }


@router.put("/{instance_id}")
def modifier_instance(
    instance_id: str,
    payload: dict[str, Any],
    nom_projet: str | None = None,
    secteur_activite: SecteurActivite | None = None,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict[str, object]:
    """Remplace en place le contenu T-R-C-O complet (tâches/ressources/
    contraintes/objectifs) d'une instance déjà ingérée — même instance_id,
    historique d'exécution intact (rien n'est dupliqué). Repasse par le même
    garde-fou amont (§6.7, `valider_payload_trco`) que la création."""
    try:
        client_id, _ = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)
    instance = valider_payload_trco(payload)
    instance = etat.modifier_instance(
        instance_id, instance, nom_projet=nom_projet, secteur_activite=secteur_activite
    )

    return {
        "instance_id": instance_id,
        "client_id": client_id,
        "structure_contraintes": structure_contraintes(instance),
        **instance.model_dump(mode="json"),
    }


@router.delete("/{instance_id}", status_code=204)
def supprimer_instance(
    instance_id: str,
    etat: EtatAPI = Depends(obtenir_etat),
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> None:
    """Supprime une instance et son historique d'exécution — n'affecte jamais
    les solveurs enregistrés (indépendants, §7)."""
    try:
        client_id, _ = etat.recuperer_instance(instance_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="instance inconnue") from None

    verifier_acces_client(utilisateur, client_id)
    etat.supprimer_instance(instance_id)
