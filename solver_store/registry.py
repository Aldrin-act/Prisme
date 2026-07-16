"""Store de code persistant (§5.2, §7) : indexation et récupération des
solveurs validés, par client / structure de contraintes.

Backend PostgreSQL (service `db` de `docker-compose.yml`), connexion via
`DATABASE_URL` (voir `.env.example`) — même interface (`Registre`) qu'avant
la migration depuis SQLite, ce module restant le seul point de contact avec
le stockage. Chaque instance peut cibler un schéma Postgres distinct
(`schema`, `public` par défaut) : les tests s'isolent ainsi les uns des
autres sans fichier séparé, à la manière d'un fichier `.sqlite3` par test.

Le code source n'est jamais dupliqué en base : seul son chemin sur disque
(`artifacts/<id>/solveur.py`) et son empreinte SHA-256 le sont, pour détecter
toute altération du fichier « figé » après coup — le principe fondateur
veut que le code persiste tel quel, jamais réécrit une fois validé.
"""

from __future__ import annotations

import hashlib
import os
import uuid
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import psycopg
from psycopg import sql

from validation_engine.cascade import VerdictCascade

DOSSIER_STORE = Path(__file__).resolve().parent
DOSSIER_ARTEFACTS = DOSSIER_STORE / "artifacts"

SCHEMA_PAR_DEFAUT = "public"
_NOM_TABLE = "solveurs"


def dsn_par_defaut() -> str:
    """`DATABASE_URL` si défini (voir `.env.example`, injecté dans le
    conteneur `dev`/`api` via `env_file`) ; sinon reconstruit depuis les
    variables `POSTGRES_*` individuelles, hôte `localhost` par défaut pour
    un usage hors conteneur."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    utilisateur = os.environ.get("POSTGRES_USER", "prisme")
    mot_de_passe = os.environ.get("POSTGRES_PASSWORD", "changeme")
    hote = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    base = os.environ.get("POSTGRES_DB", "prisme")
    return f"postgresql://{utilisateur}:{mot_de_passe}@{hote}:{port}/{base}"


class ErreurIntegriteSolveur(Exception):
    """Le code sur disque ne correspond plus à l'empreinte enregistrée —
    le principe « code figé » est possiblement violé."""


@dataclass(frozen=True)
class ArtefactSolveur:
    id: str
    client_id: str | None
    structure_contraintes: str
    chemin_code: Path
    empreinte_sha256: str
    date_validation: str
    code_source: str


def _empreinte(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()


def _table(schema: str) -> sql.Composed:
    return sql.Identifier(schema, _NOM_TABLE)


class Registre:
    """Un registre Postgres de solveurs validés.

    Chaque instance cible une base (`dsn`) et un schéma (`schema`) au sein de
    cette base, plus un dossier d'artefacts (`dossier_artefacts`) ; ceux-ci
    valent par défaut la base `DATABASE_URL`/schéma `public`/dossier de
    `solver_store/`, mais des valeurs dédiées (schéma unique + `tmp_path` en
    test) évitent de polluer le store réel.
    """

    def __init__(
        self,
        dsn: str | None = None,
        schema: str = SCHEMA_PAR_DEFAUT,
        dossier_artefacts: Path = DOSSIER_ARTEFACTS,
    ) -> None:
        self._dsn = dsn or dsn_par_defaut()
        self._schema = schema
        self._dossier_artefacts = dossier_artefacts
        self._dossier_artefacts.mkdir(parents=True, exist_ok=True)
        with closing(self._connexion()) as connexion:
            if self._schema != SCHEMA_PAR_DEFAUT:
                connexion.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self._schema)))
            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "client_id TEXT, "
                    "structure_contraintes TEXT NOT NULL, "
                    "chemin_code TEXT NOT NULL, "
                    "empreinte_sha256 TEXT NOT NULL, "
                    "date_validation TEXT NOT NULL"
                    ")"
                ).format(table=_table(self._schema))
            )
            connexion.commit()

    def _connexion(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn)

    def enregistrer_solveur(
        self,
        code_source: str,
        structure_contraintes: str,
        verdict_cascade: VerdictCascade,
        client_id: str | None = None,
    ) -> str:
        """N'enregistre que du code déjà passé au vert par la cascade
        (Étape 5) — le store ne persiste jamais un solveur non validé
        (principe fondateur, §5.2)."""
        if not verdict_cascade.reussi:
            raise ValueError("refus d'enregistrer un solveur dont la cascade de validation n'est pas au vert")

        id_solveur = str(uuid.uuid4())
        dossier = self._dossier_artefacts / id_solveur
        dossier.mkdir(parents=True, exist_ok=False)
        chemin_code = dossier / "solveur.py"
        chemin_code.write_text(code_source, encoding="utf-8")

        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL(
                    "INSERT INTO {table} "
                    "(id, client_id, structure_contraintes, chemin_code, empreinte_sha256, date_validation) "
                    "VALUES (%s, %s, %s, %s, %s, %s)"
                ).format(table=_table(self._schema)),
                (
                    id_solveur,
                    client_id,
                    structure_contraintes,
                    str(chemin_code),
                    _empreinte(code_source),
                    datetime.now(UTC).isoformat(),
                ),
            )
            connexion.commit()

        return id_solveur

    def recuperer_solveur(self, id_solveur: str) -> ArtefactSolveur:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL(
                    "SELECT id, client_id, structure_contraintes, chemin_code, empreinte_sha256, date_validation "
                    "FROM {table} WHERE id = %s"
                ).format(table=_table(self._schema)),
                (id_solveur,),
            ).fetchone()

        if ligne is None:
            raise KeyError(f"aucun solveur enregistré avec l'id {id_solveur!r}")

        id_, client_id, structure, chemin_code, empreinte, date_validation = ligne
        code_source = Path(chemin_code).read_text(encoding="utf-8")
        if _empreinte(code_source) != empreinte:
            raise ErreurIntegriteSolveur(
                f"le code de {id_solveur!r} sur disque ne correspond plus à l'empreinte enregistrée"
            )

        return ArtefactSolveur(
            id=id_,
            client_id=client_id,
            structure_contraintes=structure,
            chemin_code=Path(chemin_code),
            empreinte_sha256=empreinte,
            date_validation=date_validation,
            code_source=code_source,
        )

    def rechercher_solveurs(
        self, client_id: str | None = None, structure_contraintes: str | None = None
    ) -> list[ArtefactSolveur]:
        requete = sql.SQL("SELECT id FROM {table} WHERE 1 = 1").format(table=_table(self._schema))
        parametres: list[str] = []
        if client_id is not None:
            requete += sql.SQL(" AND client_id = %s")
            parametres.append(client_id)
        if structure_contraintes is not None:
            requete += sql.SQL(" AND structure_contraintes = %s")
            parametres.append(structure_contraintes)

        with closing(self._connexion()) as connexion:
            ids = [ligne[0] for ligne in connexion.execute(requete, parametres).fetchall()]

        return [self.recuperer_solveur(id_solveur) for id_solveur in ids]
