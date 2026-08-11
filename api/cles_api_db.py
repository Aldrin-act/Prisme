"""Gestion des clés API pour PRISME — un second identifiant révocable pour un compte déjà
authentifié (`api/auth_db.py::UtilisateursDB`), utilisable en `Authorization: Bearer <clé>` sans
rejouer un login JWT à chaque appel (usage typique CI/scripts). Même architecture que
`UtilisateursDB` : schéma paramétrable, création automatique de la table, connexion via
`DATABASE_URL` — les deux classes restent cohérentes entre elles plutôt qu'avec le style
`Depends`-paresseux de `api/dependencies.py`, puisque `obtenir_utilisateur_courant`
(`api/routes/auth.py`) doit déjà appeler `utilisateurs_db` de façon synchrone hors `Depends`.

Une clé n'est jamais un instantané figé du rôle/`client_id` de son propriétaire : elle porte
uniquement `utilisateur_id`, et `obtenir_utilisateur_courant` relit toujours l'utilisateur
propriétaire en base à la résolution — un changement de rôle s'applique donc immédiatement à ses
clés aussi, sans les invalider ni les resynchroniser.

Hachage `sha256` (pas `bcrypt` comme pour les mots de passe) : un secret aléatoire de 256 bits n'a
pas besoin d'un hachage volontairement lent, et seul un hachage déterministe permet un lookup
direct (`WHERE hash = %s`) — `bcrypt` ne le permet pas (sel différent à chaque hachage, il faudrait
comparer contre chaque ligne existante)."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from contextlib import closing
from datetime import UTC, datetime

import psycopg
from psycopg import sql

from solver_store.registry import SCHEMA_PAR_DEFAUT, dsn_par_defaut

_NOM_TABLE = "cles_api"
PREFIXE_CLE_API = "pk_live_"
_LONGUEUR_PREFIXE_AFFICHE = 4  # nombre de caractères du secret montrés après PREFIXE_CLE_API


class CleApiDB:
    """Représentation d'une clé API en base de données — ne porte jamais le secret en clair."""

    def __init__(
        self,
        id: str,
        utilisateur_id: str,
        nom: str,
        hash: str,
        prefixe: str,
        date_creation: str | None = None,
        derniere_utilisation: str | None = None,
    ):
        self.id = id
        self.utilisateur_id = utilisateur_id
        self.nom = nom
        self.hash = hash
        self.prefixe = prefixe
        self.date_creation = date_creation or datetime.now(UTC).isoformat()
        self.derniere_utilisation = derniere_utilisation

    def to_dict(self) -> dict:
        """Retourne un dict sans `hash` ni `utilisateur_id` (pour l'API — jamais assez pour
        s'authentifier, jamais l'identité d'un tiers)."""
        return {
            "cle_id": self.id,
            "nom": self.nom,
            "prefixe": self.prefixe,
            "date_creation": self.date_creation,
            "derniere_utilisation": self.derniere_utilisation,
        }


def _table(schema: str) -> sql.Composed:
    return sql.Identifier(schema, _NOM_TABLE)


class ClesApiDB:
    """Registre PostgreSQL des clés API PRISME — même pattern que `UtilisateursDB` :
    schéma paramétrable (test vs prod), création automatique de la table, isolation par schéma."""

    def __init__(self, dsn: str | None = None, schema: str = SCHEMA_PAR_DEFAUT) -> None:
        self._dsn = dsn or dsn_par_defaut()
        self._schema = schema
        with closing(self._connexion()) as connexion:
            if self._schema != SCHEMA_PAR_DEFAUT:
                connexion.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self._schema)))

            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "utilisateur_id TEXT NOT NULL, "
                    "nom TEXT NOT NULL, "
                    "hash TEXT UNIQUE NOT NULL, "
                    "prefixe TEXT NOT NULL, "
                    "date_creation TEXT NOT NULL, "
                    "derniere_utilisation TEXT"
                    ")"
                ).format(table=_table(self._schema))
            )

            connexion.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {index} ON {table} (hash)").format(
                    index=sql.Identifier(f"{_NOM_TABLE}_hash_idx"), table=_table(self._schema)
                )
            )
            connexion.execute(
                sql.SQL("CREATE INDEX IF NOT EXISTS {index} ON {table} (utilisateur_id)").format(
                    index=sql.Identifier(f"{_NOM_TABLE}_utilisateur_id_idx"), table=_table(self._schema)
                )
            )

            connexion.commit()

    def _connexion(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn)

    def creer(self, utilisateur_id: str, nom: str) -> tuple[CleApiDB, str]:
        """Génère un secret aléatoire (`pk_live_<32 octets url-safe>`), stocke son hachage,
        renvoie `(ligne, secret_en_clair)` — le secret n'est jamais reconstructible après cet
        appel, seul son hachage persiste."""
        cle_id = str(uuid.uuid4())
        secret = PREFIXE_CLE_API + secrets.token_urlsafe(32)
        hash_ = hashlib.sha256(secret.encode("utf-8")).hexdigest()
        prefixe = secret[: len(PREFIXE_CLE_API) + _LONGUEUR_PREFIXE_AFFICHE]
        date_creation = datetime.now(UTC).isoformat()

        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL(
                    "INSERT INTO {table} "
                    "(id, utilisateur_id, nom, hash, prefixe, date_creation, derniere_utilisation) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)"
                ).format(table=_table(self._schema)),
                (cle_id, utilisateur_id, nom, hash_, prefixe, date_creation, None),
            )
            connexion.commit()

        ligne = CleApiDB(
            id=cle_id,
            utilisateur_id=utilisateur_id,
            nom=nom,
            hash=hash_,
            prefixe=prefixe,
            date_creation=date_creation,
            derniere_utilisation=None,
        )
        return ligne, secret

    def recuperer_par_hash(self, hash_: str) -> CleApiDB | None:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL(
                    "SELECT id, utilisateur_id, nom, hash, prefixe, date_creation, derniere_utilisation "
                    "FROM {table} WHERE hash = %s"
                ).format(table=_table(self._schema)),
                (hash_,),
            ).fetchone()
        return self._depuis_ligne(ligne) if ligne else None

    def recuperer(self, cle_id: str) -> CleApiDB | None:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL(
                    "SELECT id, utilisateur_id, nom, hash, prefixe, date_creation, derniere_utilisation "
                    "FROM {table} WHERE id = %s"
                ).format(table=_table(self._schema)),
                (cle_id,),
            ).fetchone()
        return self._depuis_ligne(ligne) if ligne else None

    def lister_pour_utilisateur(self, utilisateur_id: str) -> list[CleApiDB]:
        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(
                sql.SQL(
                    "SELECT id, utilisateur_id, nom, hash, prefixe, date_creation, derniere_utilisation "
                    "FROM {table} WHERE utilisateur_id = %s ORDER BY date_creation DESC"
                ).format(table=_table(self._schema)),
                (utilisateur_id,),
            ).fetchall()
        return [self._depuis_ligne(ligne) for ligne in lignes]

    def mettre_a_jour_derniere_utilisation(self, cle_id: str) -> None:
        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL("UPDATE {table} SET derniere_utilisation = %s WHERE id = %s").format(
                    table=_table(self._schema)
                ),
                (datetime.now(UTC).isoformat(), cle_id),
            )
            connexion.commit()

    def supprimer(self, cle_id: str) -> None:
        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL("DELETE FROM {table} WHERE id = %s").format(table=_table(self._schema)), (cle_id,)
            )
            connexion.commit()

    @staticmethod
    def _depuis_ligne(ligne: tuple) -> CleApiDB:
        id_, utilisateur_id, nom, hash_, prefixe, date_creation, derniere_utilisation = ligne
        return CleApiDB(
            id=id_,
            utilisateur_id=utilisateur_id,
            nom=nom,
            hash=hash_,
            prefixe=prefixe,
            date_creation=date_creation,
            derniere_utilisation=derniere_utilisation,
        )
