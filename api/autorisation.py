"""Autorisation par client_id : un utilisateur authentifié n'agit et ne voit
que les données de son propre `client_id` (porté par son JWT, `api/routes/auth.py`)
— sauf le rôle `admin`, qui accède à tout. Le `client_id` d'une opération vient
toujours du compte authentifié, jamais d'une valeur fournie par la requête
elle-même (sans quoi un utilisateur pourrait usurper un autre client en la
passant simplement dans l'URL ou le corps de la requête).
"""

from __future__ import annotations

from fastapi import HTTPException


def client_id_pour_filtre(utilisateur: dict) -> str | None:
    """`None` = pas de filtre (admin, voit tout) ; sinon le `client_id` du compte."""
    if utilisateur.get("role") == "admin":
        return None
    return utilisateur.get("client_id")


def verifier_acces_client(utilisateur: dict, client_id_ressource: str | None) -> None:
    """Lève un 403 si un utilisateur non-admin tente d'agir sur un `client_id`
    différent du sien (y compris si son propre compte n'en a aucun)."""
    if utilisateur.get("role") == "admin":
        return
    if utilisateur.get("client_id") is None or utilisateur.get("client_id") != client_id_ressource:
        raise HTTPException(status_code=403, detail="accès refusé pour ce client")
