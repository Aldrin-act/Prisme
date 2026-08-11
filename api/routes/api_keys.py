"""CRUD des clés API personnelles — une clé vaut exactement les mêmes droits que le compte qui l'a
créée (voir docstring de `api/cles_api_db.py`), jamais un sous-ensemble de permissions distinct.
Portée par `utilisateur_id`, jamais par `client_id` : une clé est personnelle (comme un token
GitHub), deux comptes d'un même client ne voient pas les clés l'un de l'autre.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.routes.auth import cles_api_db, obtenir_utilisateur_courant

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


class RequeteCreationCleApi(BaseModel):
    nom: str = Field(min_length=1)


@router.post("", status_code=201)
def creer_cle_api(
    requete: RequeteCreationCleApi, utilisateur: dict = Depends(obtenir_utilisateur_courant)
) -> dict[str, str | None]:
    """Le `secret` renvoyé n'est jamais reconstructible après cet appel — seul son hachage
    persiste (voir `ClesApiDB.creer`). L'appelant doit le copier immédiatement."""
    ligne, secret = cles_api_db.creer(utilisateur["id"], requete.nom)
    return {**ligne.to_dict(), "secret": secret}


@router.get("")
def lister_cles_api(utilisateur: dict = Depends(obtenir_utilisateur_courant)) -> list[dict[str, str | None]]:
    """Ne renvoie jamais le secret ni son hachage (voir `CleApiDB.to_dict`) — seulement de quoi
    reconnaître une clé (nom, préfixe, dates)."""
    return [ligne.to_dict() for ligne in cles_api_db.lister_pour_utilisateur(utilisateur["id"])]


@router.delete("/{cle_id}", status_code=204)
def revoquer_cle_api(cle_id: str, utilisateur: dict = Depends(obtenir_utilisateur_courant)) -> None:
    """404 (jamais 403) si la clé n'existe pas ou appartient à quelqu'un d'autre — ne confirme
    jamais l'existence d'une clé qui n'est pas la sienne."""
    ligne = cles_api_db.recuperer(cle_id)
    if ligne is None or ligne.utilisateur_id != utilisateur["id"]:
        raise HTTPException(status_code=404, detail="clé introuvable")
    cles_api_db.supprimer(cle_id)
