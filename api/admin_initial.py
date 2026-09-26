"""Compte administrateur initial, créé au démarrage de l'API à partir de variables d'environnement.

Sur un déploiement (ex. Railway, `docs/deploiement_railway.md`), la base n'est joignable que depuis
le réseau privé de la plateforme : aucun script ne peut y créer le premier compte depuis un poste.
`PRISME_ADMIN_EMAIL` + `PRISME_ADMIN_MOT_DE_PASSE` le créent donc au lancement du serveur.

Idempotent : si l'email existe déjà, rien n'est touché — ni son rôle, ni son mot de passe (changé
ensuite depuis l'interface, `POST /auth/change-password`, il ne doit jamais être écrasé par la
valeur de départ à chaque redémarrage). Variables absentes : aucune action.
"""

from __future__ import annotations

import logging
import os
from typing import Protocol

_LOGGER = logging.getLogger(__name__)

LONGUEUR_MIN_MOT_DE_PASSE = 12


class _BaseUtilisateurs(Protocol):
    def email_existe(self, email: str) -> bool: ...

    def creer_utilisateur(
        self, email: str, mot_de_passe: str, nom: str, prenom: str, role: str = ..., client_id: str | None = ...
    ) -> object: ...


def creer_admin_initial(db: _BaseUtilisateurs, environ: dict[str, str] | None = None) -> bool:
    """Crée le compte admin décrit par l'environnement s'il n'existe pas encore. Renvoie `True` si
    un compte a été créé. Lève `ValueError` si une seule des deux variables est définie ou si le mot
    de passe est trop court : une configuration à moitié faite doit se voir, pas être ignorée."""
    environ = os.environ if environ is None else environ
    email = environ.get("PRISME_ADMIN_EMAIL", "").strip()
    mot_de_passe = environ.get("PRISME_ADMIN_MOT_DE_PASSE", "")
    if not email and not mot_de_passe:
        return False
    if not email or not mot_de_passe:
        raise ValueError("PRISME_ADMIN_EMAIL et PRISME_ADMIN_MOT_DE_PASSE doivent être définies ensemble")
    if len(mot_de_passe) < LONGUEUR_MIN_MOT_DE_PASSE:
        raise ValueError(f"PRISME_ADMIN_MOT_DE_PASSE doit faire au moins {LONGUEUR_MIN_MOT_DE_PASSE} caractères")

    if db.email_existe(email):
        return False
    db.creer_utilisateur(
        email=email,
        mot_de_passe=mot_de_passe,
        nom=environ.get("PRISME_ADMIN_NOM", "Administrateur"),
        prenom=environ.get("PRISME_ADMIN_PRENOM", "PRISME"),
        role="admin",
        client_id=None,
    )
    _LOGGER.warning("Compte administrateur initial créé : %s", email)
    return True
