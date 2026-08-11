"""Routes d'authentification pour les maintenants et opérateurs PRISME.

Stockage PostgreSQL avec hachage bcrypt des mots de passe (§5.2, §7).
Même architecture que solver_store/registry.py : table auto-créée, schéma public.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from api.auth_db import RoleUtilisateur, UtilisateursDB
from api.cles_api_db import PREFIXE_CLE_API, ClesApiDB
from api.etat import EtatAPI, obtenir_etat

# Charger les variables d'environnement
load_dotenv()

# Configuration JWT depuis .env
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "VOTRE_CLE_SECRETE_ICI")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "1440"))

# Échappatoire dev uniquement — JAMAIS en production : court-circuite
# entièrement `obtenir_utilisateur_courant` (aucun token requis, aucune
# vérification de client_id nulle part) pour tester l'API sans rejouer un
# flux de login à chaque requête. Défaut : authentification active.
AUTH_DESACTIVEE = os.getenv("PRISME_AUTH_DESACTIVEE", "").strip().lower() in ("1", "true", "yes")
UTILISATEUR_FACTICE_SANS_AUTH = {
    "id": "auth-desactivee",
    "email": "dev@local",
    "nom": "Dev",
    "prenom": "Local",
    "role": "admin",
    "client_id": None,
    "date_creation": "2024-01-01T00:00:00+00:00",
    "dernier_acces": None,
}

router = APIRouter(prefix="/auth", tags=["authentification"])
security = HTTPBearer(auto_error=False)

# Instance globale de la base de données utilisateurs
# Utilise DATABASE_URL (même base que solver_store, etat_postgres, etc.)
utilisateurs_db = UtilisateursDB()

# Même style eager-global que ci-dessus, pour que les deux bases d'identifiants
# (mot de passe, clé API) restent cohérentes entre elles — voir api/cles_api_db.py.
cles_api_db = ClesApiDB()


# ============================================================================
# MODÈLES PYDANTIC (API)
# ============================================================================


class Utilisateur(BaseModel):
    id: str
    email: EmailStr
    nom: str
    prenom: str
    role: str
    client_id: str | None = None
    date_creation: str
    dernier_acces: str | None = None


class SessionAuth(BaseModel):
    utilisateur: Utilisateur
    token: str
    expires_at: str


class ReponseAuth(BaseModel):
    session: SessionAuth
    message: str


class CredentialsLogin(BaseModel):
    email: EmailStr
    password: str


class CredentialsRegister(BaseModel):
    email: EmailStr
    password: str
    nom: str
    prenom: str
    role: RoleUtilisateur = "operateur"
    client_id: str | None = None


class ErreurAuth(BaseModel):
    code: str
    message: str


class ChangePasswordRequest(BaseModel):
    ancien_mot_de_passe: str
    nouveau_mot_de_passe: str


class ResetPasswordRequest(BaseModel):
    token: str
    nouveau_mot_de_passe: str


# ============================================================================
# UTILITAIRES JWT
# ============================================================================


def creer_token_jwt(utilisateur_id: str, role: str, client_id: str | None) -> tuple[str, str]:
    """Crée un JWT token avec expiration."""
    expires_at = datetime.now(UTC) + timedelta(minutes=JWT_EXPIRE_MINUTES)

    payload = {
        "user_id": utilisateur_id,
        "role": role,
        "client_id": client_id,
        "exp": expires_at,
        "iat": datetime.now(UTC),
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token, expires_at.isoformat()


def decoder_token_jwt(token: str) -> dict:
    """Décode et vérifie un JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "TOKEN_EXPIRED", "message": "Token expiré"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Token invalide"},
        )


# ============================================================================
# DÉPENDANCES FASTAPI
# ============================================================================


def _utilisateur_depuis_cle_api(cle: str) -> dict:
    """Résout une clé API (`Authorization: Bearer pk_live_...`) vers le même dict
    qu'un JWT — une clé n'est jamais un instantané figé du rôle/client_id de son
    propriétaire, toujours relu en base à chaque appel (voir `api/cles_api_db.py`)."""
    ligne = cles_api_db.recuperer_par_hash(hashlib.sha256(cle.encode("utf-8")).hexdigest())
    if ligne is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Clé API invalide"},
        )

    utilisateur_db = utilisateurs_db.recuperer_par_id(ligne.utilisateur_id)
    if not utilisateur_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Clé API invalide"},
        )

    cles_api_db.mettre_a_jour_derniere_utilisation(ligne.id)
    return utilisateur_db.to_dict()


async def obtenir_utilisateur_courant(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)] = None,
) -> dict:
    """Dépendance FastAPI pour extraire l'utilisateur du token JWT ou d'une clé API
    (`pk_live_...`, voir `_utilisateur_depuis_cle_api`) — mêmes droits, même dict renvoyé,
    peu importe le type de credential.

    `PRISME_AUTH_DESACTIVEE=1` (dev uniquement) court-circuite entièrement
    cette vérification et renvoie un admin factice, sans exiger de token."""
    if AUTH_DESACTIVEE:
        return UTILISATEUR_FACTICE_SANS_AUTH

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Authentification requise"},
        )

    token = credentials.credentials

    if token.startswith(PREFIXE_CLE_API):
        return _utilisateur_depuis_cle_api(token)

    payload = decoder_token_jwt(token)

    # Récupérer utilisateur de la base de données PostgreSQL
    utilisateur_id = payload["user_id"]
    utilisateur_db = utilisateurs_db.recuperer_par_id(utilisateur_id)

    if not utilisateur_db:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Utilisateur introuvable"},
        )

    return utilisateur_db.to_dict()


def require_role(*roles: str):
    """Dépendance paramétrée pour vérifier le rôle de l'utilisateur — usage :
    `Depends(require_role("admin"))`. Factory volontairement synchrone : elle
    ne fait que construire et renvoyer `role_checker`, seul ce dernier est
    exécuté par FastAPI comme dépendance (async)."""

    async def role_checker(utilisateur: dict = Depends(obtenir_utilisateur_courant)):
        if utilisateur["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Rôle insuffisant"},
            )
        return utilisateur

    return role_checker


# ============================================================================
# ROUTES D'AUTHENTIFICATION
# ============================================================================


@router.post("/login")
def login(credentials: CredentialsLogin) -> ReponseAuth:
    """Connexion avec email/password (stockage PostgreSQL + bcrypt)."""
    # Rechercher utilisateur dans PostgreSQL
    utilisateur_db = utilisateurs_db.recuperer_par_email(credentials.email)

    if not utilisateur_db or not utilisateurs_db.verifier_mot_de_passe(
        credentials.password, utilisateur_db.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Email ou mot de passe incorrect",
            },
        )

    # Générer token JWT
    token, expires_at = creer_token_jwt(utilisateur_db.id, utilisateur_db.role, utilisateur_db.client_id)

    # Mettre à jour dernier accès dans PostgreSQL
    utilisateurs_db.mettre_a_jour_dernier_acces(utilisateur_db.id)

    # Créer session
    utilisateur_dict = utilisateur_db.to_dict()
    utilisateur_dict["dernier_acces"] = datetime.now(UTC).isoformat()

    session = SessionAuth(
        utilisateur=Utilisateur(**utilisateur_dict),
        token=token,
        expires_at=expires_at,
    )

    return ReponseAuth(
        session=session,
        message="Connexion réussie",
    )


@router.post("/register")
def register(credentials: CredentialsRegister, etat: EtatAPI = Depends(obtenir_etat)) -> ReponseAuth:
    """Inscription d'un nouvel utilisateur (stockage PostgreSQL + bcrypt).

    `client_id` requis pour tout rôle autre qu'admin (sinon le compte ne
    pourrait rien créer, voir `api/autorisation.py`), et doit référencer un
    client déjà enregistré (`api/routes/clients.py`) — jamais une valeur
    inventée à la volée."""
    # Vérifier si email existe déjà
    if utilisateurs_db.email_existe(credentials.email):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "USER_EXISTS",
                "message": "Un compte avec cet email existe déjà",
            },
        )

    if credentials.role != "admin":
        if not credentials.client_id:
            raise HTTPException(status_code=400, detail="client_id requis pour ce rôle")
        try:
            etat.recuperer_client(credentials.client_id)
        except KeyError:
            raise HTTPException(status_code=400, detail="client_id inconnu") from None

    # Créer utilisateur dans PostgreSQL (hachage bcrypt automatique)
    utilisateur_db = utilisateurs_db.creer_utilisateur(
        email=credentials.email,
        mot_de_passe=credentials.password,
        nom=credentials.nom,
        prenom=credentials.prenom,
        role=credentials.role,
        client_id=credentials.client_id,
    )

    # Générer token JWT
    token, expires_at = creer_token_jwt(utilisateur_db.id, utilisateur_db.role, utilisateur_db.client_id)

    # Créer session
    session = SessionAuth(
        utilisateur=Utilisateur(**utilisateur_db.to_dict()),
        token=token,
        expires_at=expires_at,
    )

    return ReponseAuth(
        session=session,
        message="Compte créé avec succès",
    )


@router.post("/logout")
def logout(utilisateur: dict = Depends(obtenir_utilisateur_courant)) -> dict:
    """Déconnexion (le client doit supprimer son token côté frontend)."""
    # Note: Pour une vraie blacklist de tokens, utiliser Redis avec TTL
    # Pour cette implémentation, on se fie au client pour supprimer le token
    return {"message": "Déconnexion réussie"}


@router.get("/verify")
def verify_token(utilisateur: dict = Depends(obtenir_utilisateur_courant)) -> dict:
    """Vérifie la validité du token JWT."""
    return {"valid": True, "user_id": utilisateur["id"]}


@router.post("/refresh")
def refresh_token(utilisateur: dict = Depends(obtenir_utilisateur_courant)) -> ReponseAuth:
    """Rafraîchit le token d'authentification."""
    # Générer nouveau token
    token, expires_at = creer_token_jwt(utilisateur["id"], utilisateur["role"], utilisateur.get("client_id"))

    # Créer nouvelle session
    session = SessionAuth(
        utilisateur=Utilisateur(**utilisateur),
        token=token,
        expires_at=expires_at,
    )

    return ReponseAuth(
        session=session,
        message="Token rafraîchi",
    )


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict:
    """Change le mot de passe de l'utilisateur."""
    # Récupérer utilisateur complet depuis PostgreSQL
    utilisateur_db = utilisateurs_db.recuperer_par_id(utilisateur["id"])

    if not utilisateur_db:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "NOT_FOUND", "message": "Utilisateur introuvable"},
        )

    # Vérifier ancien mot de passe
    if not utilisateurs_db.verifier_mot_de_passe(request.ancien_mot_de_passe, utilisateur_db.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Ancien mot de passe incorrect",
            },
        )

    # Mettre à jour le mot de passe (hachage bcrypt automatique)
    utilisateurs_db.changer_mot_de_passe(utilisateur["id"], request.nouveau_mot_de_passe)

    return {"message": "Mot de passe modifié"}


@router.post("/forgot-password")
def forgot_password(email: EmailStr) -> dict:
    """Demande de réinitialisation de mot de passe."""
    # En production: générer token unique, envoyer email avec lien de réinitialisation
    # Pour cette implémentation, on retourne un message générique
    return {"message": "Email de réinitialisation envoyé (si le compte existe)"}


@router.post("/reset-password")
def reset_password(request: ResetPasswordRequest) -> dict:
    """Réinitialise le mot de passe avec un token."""
    # En production: vérifier le token de réinitialisation (stocké en Redis/PostgreSQL avec expiration)
    # Pour cette implémentation, endpoint placeholder
    return {"message": "Mot de passe réinitialisé"}
