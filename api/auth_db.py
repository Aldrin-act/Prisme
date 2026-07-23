"""Gestion de la base de données d'authentification (utilisateurs) pour PRISME.

Stocke les utilisateurs dans PostgreSQL avec hachage bcrypt des mots de passe.
Architecture similaire à solver_store/registry.py : schéma paramétrable,
création automatique de la table, connexion via DATABASE_URL.
"""

from __future__ import annotations

import os
import uuid
from contextlib import closing
from datetime import UTC, datetime
from typing import Literal

import bcrypt
import psycopg
from dotenv import load_dotenv
from psycopg import sql

from solver_store.registry import SCHEMA_PAR_DEFAUT, dsn_par_defaut

# Charger les variables d'environnement pour DATABASE_URL
load_dotenv()

_NOM_TABLE = "utilisateurs"

RoleUtilisateur = Literal["operateur", "maintenant", "admin"]


class UtilisateurDB:
    """Représentation d'un utilisateur en base de données."""

    def __init__(
        self,
        id: str,
        email: str,
        password_hash: str,
        nom: str,
        prenom: str,
        role: RoleUtilisateur,
        client_id: str | None = None,
        date_creation: str | None = None,
        dernier_acces: str | None = None,
    ):
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.nom = nom
        self.prenom = prenom
        self.role = role
        self.client_id = client_id
        self.date_creation = date_creation or datetime.now(UTC).isoformat()
        self.dernier_acces = dernier_acces

    def to_dict(self) -> dict:
        """Retourne un dict sans le password_hash (pour l'API)."""
        return {
            "id": self.id,
            "email": self.email,
            "nom": self.nom,
            "prenom": self.prenom,
            "role": self.role,
            "client_id": self.client_id,
            "date_creation": self.date_creation,
            "dernier_acces": self.dernier_acces,
        }


def _table(schema: str) -> sql.Composed:
    return sql.Identifier(schema, _NOM_TABLE)


class UtilisateursDB:
    """Registre PostgreSQL des utilisateurs PRISME.

    Même pattern que solver_store.Registre : schéma paramétrable (test vs prod),
    création automatique de la table, isolation par schéma.
    """

    def __init__(self, dsn: str | None = None, schema: str = SCHEMA_PAR_DEFAUT) -> None:
        self._dsn = dsn or dsn_par_defaut()
        self._schema = schema
        with closing(self._connexion()) as connexion:
            if self._schema != SCHEMA_PAR_DEFAUT:
                connexion.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self._schema)))

            # Créer la table utilisateurs
            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "email TEXT UNIQUE NOT NULL, "
                    "password_hash TEXT NOT NULL, "
                    "nom TEXT NOT NULL, "
                    "prenom TEXT NOT NULL, "
                    "role TEXT NOT NULL, "
                    "client_id TEXT, "
                    "date_creation TEXT NOT NULL, "
                    "dernier_acces TEXT"
                    ")"
                ).format(table=_table(self._schema))
            )

            # Index sur email pour les recherches rapides
            connexion.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {index} ON {table} (email)").format(
                    index=sql.Identifier(f"{_NOM_TABLE}_email_idx"), table=_table(self._schema)
                )
            )

            connexion.commit()

    def _connexion(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn)

    # ============================================================================
    # GESTION DES MOTS DE PASSE
    # ============================================================================

    @staticmethod
    def hacher_mot_de_passe(mot_de_passe: str) -> str:
        """Hache un mot de passe avec bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(mot_de_passe.encode("utf-8"), salt).decode("utf-8")

    @staticmethod
    def verifier_mot_de_passe(mot_de_passe: str, hash_stocke: str) -> bool:
        """Vérifie qu'un mot de passe correspond au hash stocké."""
        return bcrypt.checkpw(mot_de_passe.encode("utf-8"), hash_stocke.encode("utf-8"))

    # ============================================================================
    # CRUD UTILISATEURS
    # ============================================================================

    def creer_utilisateur(
        self,
        email: str,
        mot_de_passe: str,
        nom: str,
        prenom: str,
        role: RoleUtilisateur = "operateur",
        client_id: str | None = None,
    ) -> UtilisateurDB:
        """Crée un nouvel utilisateur avec hachage bcrypt du mot de passe."""
        user_id = str(uuid.uuid4())
        password_hash = self.hacher_mot_de_passe(mot_de_passe)
        date_creation = datetime.now(UTC).isoformat()

        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL(
                    "INSERT INTO {table} "
                    "(id, email, password_hash, nom, prenom, role, client_id, date_creation, dernier_acces) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
                ).format(table=_table(self._schema)),
                (user_id, email, password_hash, nom, prenom, role, client_id, date_creation, None),
            )
            connexion.commit()

        return UtilisateurDB(
            id=user_id,
            email=email,
            password_hash=password_hash,
            nom=nom,
            prenom=prenom,
            role=role,
            client_id=client_id,
            date_creation=date_creation,
            dernier_acces=None,
        )

    def recuperer_par_email(self, email: str) -> UtilisateurDB | None:
        """Récupère un utilisateur par son email."""
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL(
                    "SELECT id, email, password_hash, nom, prenom, role, client_id, date_creation, dernier_acces "
                    "FROM {table} WHERE email = %s"
                ).format(table=_table(self._schema)),
                (email,),
            ).fetchone()

        if ligne is None:
            return None

        id_, email, password_hash, nom, prenom, role, client_id, date_creation, dernier_acces = ligne
        return UtilisateurDB(
            id=id_,
            email=email,
            password_hash=password_hash,
            nom=nom,
            prenom=prenom,
            role=role,
            client_id=client_id,
            date_creation=date_creation,
            dernier_acces=dernier_acces,
        )

    def recuperer_par_id(self, user_id: str) -> UtilisateurDB | None:
        """Récupère un utilisateur par son ID."""
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL(
                    "SELECT id, email, password_hash, nom, prenom, role, client_id, date_creation, dernier_acces "
                    "FROM {table} WHERE id = %s"
                ).format(table=_table(self._schema)),
                (user_id,),
            ).fetchone()

        if ligne is None:
            return None

        id_, email, password_hash, nom, prenom, role, client_id, date_creation, dernier_acces = ligne
        return UtilisateurDB(
            id=id_,
            email=email,
            password_hash=password_hash,
            nom=nom,
            prenom=prenom,
            role=role,
            client_id=client_id,
            date_creation=date_creation,
            dernier_acces=dernier_acces,
        )

    def mettre_a_jour_dernier_acces(self, user_id: str) -> None:
        """Met à jour la date du dernier accès."""
        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL("UPDATE {table} SET dernier_acces = %s WHERE id = %s").format(table=_table(self._schema)),
                (datetime.now(UTC).isoformat(), user_id),
            )
            connexion.commit()

    def changer_mot_de_passe(self, user_id: str, nouveau_mot_de_passe: str) -> None:
        """Change le mot de passe d'un utilisateur."""
        password_hash = self.hacher_mot_de_passe(nouveau_mot_de_passe)
        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL("UPDATE {table} SET password_hash = %s WHERE id = %s").format(table=_table(self._schema)),
                (password_hash, user_id),
            )
            connexion.commit()

    def email_existe(self, email: str) -> bool:
        """Vérifie si un email existe déjà."""
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT COUNT(*) FROM {table} WHERE email = %s").format(table=_table(self._schema)),
                (email,),
            ).fetchone()
        return ligne[0] > 0 if ligne else False

    def lister_utilisateurs(self) -> list[UtilisateurDB]:
        """Liste tous les utilisateurs (admin uniquement)."""
        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(
                sql.SQL(
                    "SELECT id, email, password_hash, nom, prenom, role, client_id, date_creation, dernier_acces "
                    "FROM {table} ORDER BY date_creation DESC"
                ).format(table=_table(self._schema))
            ).fetchall()

        return [
            UtilisateurDB(
                id=id_,
                email=email,
                password_hash=password_hash,
                nom=nom,
                prenom=prenom,
                role=role,
                client_id=client_id,
                date_creation=date_creation,
                dernier_acces=dernier_acces,
            )
            for id_, email, password_hash, nom, prenom, role, client_id, date_creation, dernier_acces in lignes
        ]
