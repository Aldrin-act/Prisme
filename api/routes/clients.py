"""Clients (tenants) — l'unité de cloisonnement des données dans tout le
système (§7) : matching des solveurs (`solver_store/registry.py`), visibilité
des instances/projets (`api/autorisation.py`). Ce module permet de les créer
explicitement, avec un vrai nom, plutôt que de laisser `client_id` être du
texte libre non vérifié créé implicitement au premier usage.

`GET /clients` est délibérément public (aucune authentification requise) :
le formulaire d'inscription en a besoin pour proposer un client existant
à un nouvel utilisateur, avant même qu'il ait un compte."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.etat import EtatAPI, obtenir_etat
from api.routes.auth import require_role

router = APIRouter(prefix="/clients", tags=["clients"])


class RequeteCreationClient(BaseModel):
    client_id: str
    nom: str | None = None


@router.get("")
def lister_clients(etat: EtatAPI = Depends(obtenir_etat)) -> list[dict[str, object]]:
    return etat.lister_clients()


@router.post("", status_code=201)
def creer_client(
    requete: RequeteCreationClient,
    etat: EtatAPI = Depends(obtenir_etat),
    _utilisateur: dict = Depends(require_role("admin")),
) -> dict[str, object]:
    try:
        etat.recuperer_client(requete.client_id)
    except KeyError:
        pass
    else:
        raise HTTPException(status_code=409, detail="ce client_id existe déjà")

    etat.enregistrer_client(requete.client_id, requete.nom)
    return {"client_id": requete.client_id, "nom": requete.nom}
