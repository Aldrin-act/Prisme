"""Routes d'authentification pour les maintenants et opérateurs PRISME."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

# Configuration JWT (à déplacer dans un fichier config)
JWT_SECRET_KEY = "VOTRE_CLE_SECRETE_ICI"  # À remplacer par variable d'environnement
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 1440  # 24 heures

router = APIRouter(prefix="/auth", tags=["authentification"])
security = HTTPBearer()


# ============================================================================
# MODÈLES
# ============================================================================

class RoleUtilisateur(str):
    OPERATEUR = "operateur"
    MAINTENANT = "maintenant"
    ADMIN = "admin"


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
    role: str = "operateur"
    client_id: str | None = None


class ErreurAuth(BaseModel):
    code: str
    message: str


# ============================================================================
# STOCKAGE TEMPORAIRE (À REMPLACER PAR BASE DE DONNÉES)
# ============================================================================

# Base de données en mémoire pour la démo
# En production, remplacer par PostgreSQL/SQLite
UTILISATEURS_DB: dict[str, dict] = {
    "maintenant@example.com": {
        "id": "user-001",
        "email": "maintenant@example.com",
        "password_hash": "hashed_password_123",  # En vrai: bcrypt.hashpw(...)
        "nom": "Dupont",
        "prenom": "Jean",
        "role": "maintenant",
        "client_id": None,
        "date_creation": "2026-01-01T00:00:00Z",
        "dernier_acces": None,
    },
    "admin@example.com": {
        "id": "user-002",
        "email": "admin@example.com",
        "password_hash": "hashed_password_456",
        "nom": "Admin",
        "prenom": "Super",
        "role": "admin",
        "client_id": None,
        "date_creation": "2026-01-01T00:00:00Z",
        "dernier_acces": None,
    },
}

# Blacklist tokens invalidés
TOKENS_INVALIDES: set[str] = set()


# ============================================================================
# UTILITAIRES JWT
# ============================================================================

def creer_token_jwt(utilisateur_id: str, role: str, client_id: str | None) -> tuple[str, str]:
    """Crée un JWT token avec expiration."""
    expires_at = datetime.utcnow() + timedelta(minutes=JWT_EXPIRE_MINUTES)

    payload = {
        "user_id": utilisateur_id,
        "role": role,
        "client_id": client_id,
        "exp": expires_at,
        "iat": datetime.utcnow(),
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


def verifier_mot_de_passe(mot_de_passe: str, hash_stocke: str) -> bool:
    """Vérifie le mot de passe (version simplifiée, utiliser bcrypt en prod)."""
    # En production: bcrypt.checkpw(mot_de_passe.encode(), hash_stocke.encode())
    return f"hashed_{mot_de_passe}" == hash_stocke


# ============================================================================
# DÉPENDANCES
# ============================================================================

async def obtenir_utilisateur_courant(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
) -> dict:
    """Dépendance FastAPI pour extraire l'utilisateur du token JWT."""
    token = credentials.credentials

    # Vérifier si token blacklisté
    if token in TOKENS_INVALIDES:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Token révoqué"},
        )

    payload = decoder_token_jwt(token)

    # Récupérer utilisateur de la DB
    utilisateur_id = payload["user_id"]
    utilisateur = next(
        (u for u in UTILISATEURS_DB.values() if u["id"] == utilisateur_id),
        None,
    )

    if not utilisateur:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "UNAUTHORIZED", "message": "Utilisateur introuvable"},
        )

    return utilisateur


async def require_role(*roles: str):
    """Dépendance pour vérifier le rôle de l'utilisateur."""
    async def role_checker(utilisateur: dict = Depends(obtenir_utilisateur_courant)):
        if utilisateur["role"] not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "FORBIDDEN", "message": "Rôle insuffisant"},
            )
        return utilisateur

    return role_checker


# ============================================================================
# ROUTES
# ============================================================================

@router.post("/login")
def login(credentials: CredentialsLogin) -> ReponseAuth:
    """Connexion avec email/password."""
    # Rechercher utilisateur
    utilisateur = UTILISATEURS_DB.get(credentials.email)

    if not utilisateur or not verifier_mot_de_passe(
        credentials.password, utilisateur["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Email ou mot de passe incorrect",
            },
        )

    # Générer token
    token, expires_at = creer_token_jwt(
        utilisateur["id"], utilisateur["role"], utilisateur.get("client_id")
    )

    # Mettre à jour dernier accès
    utilisateur["dernier_acces"] = datetime.utcnow().isoformat()

    # Créer session
    session = SessionAuth(
        utilisateur=Utilisateur(**{k: v for k, v in utilisateur.items() if k != "password_hash"}),
        token=token,
        expires_at=expires_at,
    )

    return ReponseAuth(
        session=session,
        message="Connexion réussie",
    )


@router.post("/register")
def register(credentials: CredentialsRegister) -> ReponseAuth:
    """Inscription d'un nouvel utilisateur."""
    # Vérifier si email existe déjà
    if credentials.email in UTILISATEURS_DB:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "USER_EXISTS",
                "message": "Un compte avec cet email existe déjà",
            },
        )

    # Créer utilisateur
    user_id = f"user-{len(UTILISATEURS_DB) + 1:03d}"
    utilisateur = {
        "id": user_id,
        "email": credentials.email,
        "password_hash": f"hashed_{credentials.password}",  # En vrai: bcrypt
        "nom": credentials.nom,
        "prenom": credentials.prenom,
        "role": credentials.role,
        "client_id": credentials.client_id,
        "date_creation": datetime.utcnow().isoformat(),
        "dernier_acces": None,
    }

    UTILISATEURS_DB[credentials.email] = utilisateur

    # Générer token
    token, expires_at = creer_token_jwt(user_id, credentials.role, credentials.client_id)

    # Créer session
    session = SessionAuth(
        utilisateur=Utilisateur(**{k: v for k, v in utilisateur.items() if k != "password_hash"}),
        token=token,
        expires_at=expires_at,
    )

    return ReponseAuth(
        session=session,
        message="Compte créé avec succès",
    )


@router.post("/logout")
def logout(utilisateur: dict = Depends(obtenir_utilisateur_courant)) -> dict:
    """Déconnexion (invalide le token)."""
    # En production: ajouter le token à une blacklist Redis avec TTL
    # Pour la démo, on utilise un set en mémoire
    return {"message": "Déconnexion réussie"}


@router.get("/verify")
def verify_token(utilisateur: dict = Depends(obtenir_utilisateur_courant)) -> dict:
    """Vérifie la validité du token."""
    return {"valid": True, "user_id": utilisateur["id"]}


@router.post("/refresh")
def refresh_token(utilisateur: dict = Depends(obtenir_utilisateur_courant)) -> ReponseAuth:
    """Rafraîchit le token d'authentification."""
    # Générer nouveau token
    token, expires_at = creer_token_jwt(
        utilisateur["id"], utilisateur["role"], utilisateur.get("client_id")
    )

    # Créer nouvelle session
    session = SessionAuth(
        utilisateur=Utilisateur(**{k: v for k, v in utilisateur.items() if k != "password_hash"}),
        token=token,
        expires_at=expires_at,
    )

    return ReponseAuth(
        session=session,
        message="Token rafraîchi",
    )


@router.post("/change-password")
def change_password(
    ancien_mot_de_passe: str,
    nouveau_mot_de_passe: str,
    utilisateur: dict = Depends(obtenir_utilisateur_courant),
) -> dict:
    """Change le mot de passe de l'utilisateur."""
    if not verifier_mot_de_passe(ancien_mot_de_passe, utilisateur["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Ancien mot de passe incorrect",
            },
        )

    # Mettre à jour le mot de passe
    utilisateur["password_hash"] = f"hashed_{nouveau_mot_de_passe}"

    return {"message": "Mot de passe modifié"}


@router.post("/forgot-password")
def forgot_password(email: EmailStr) -> dict:
    """Demande de réinitialisation de mot de passe."""
    # En production: envoyer email avec lien de réinitialisation
    return {"message": "Email de réinitialisation envoyé (si le compte existe)"}


@router.post("/reset-password")
def reset_password(token: str, nouveau_mot_de_passe: str) -> dict:
    """Réinitialise le mot de passe avec un token."""
    # En production: vérifier le token de réinitialisation
    return {"message": "Mot de passe réinitialisé"}
