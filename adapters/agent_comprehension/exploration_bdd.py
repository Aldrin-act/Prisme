"""Sous-agent d'exploration de base de données (§5.4 bis) — comprend le
schéma/les relations d'une base quelconque, décide lui-même d'une ou
plusieurs requêtes SQL, les exécute sur une connexion strictement lecture
seule, et convertit le résultat en JSON brut — directement réutilisable
comme `donnees_brutes` de `comprendre_donnees_erp` (`agent.py`), qui fait
ensuite le travail de traduction T-R-C-O, inchangé. Les deux restent deux
fonctions indépendantes, testables séparément.

Exécution autonome, sans validation humaine avant la requête — écart
assumé au principe "humain dans la boucle" (CLAUDE.md), qui vise des
actions à conséquence (déclencher une replanification, agir sur un
diagnostic), pas une simple extraction en lecture seule.

La vraie frontière de sécurité n'est PAS le filtre SQL statique de ce
module (`_valider_requete_lecture_seule`, un premier filtre faible, même
relation que l'allowlist AST vs. le sandbox, §5.3) : c'est le rôle Postgres
lecture seule dédié (`scripts/creer_role_lecture_seule_greensig.py`), plus
`default_transaction_read_only`/`statement_timeout` imposés à la connexion
elle-même — même philosophie de défense en profondeur que le sandbox,
jamais un seul point de contrôle.
"""

from __future__ import annotations

import os
import re
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psycopg
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from generation.agents.base import ErreurReponseAgentInvalide, extraire_texte_brut
from generation.agents.client_llm import _avec_retry, methode_sortie_structuree

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

CHEMIN_PROMPT = Path(__file__).resolve().parent / "prompts" / "exploration_bdd.md"


def dsn_lecture_seule_greensig_par_defaut() -> str:
    """`GREENSIG_LECTURE_SEULE_DATABASE_URL` si défini ; sinon reconstruit
    depuis `GREENSIG_DB_LECTURE_SEULE_PASSWORD` et les mêmes hôte/port que
    `adapters.greensig.extraction.dsn_par_defaut` — rôle créé par
    `scripts/creer_role_lecture_seule_greensig.py`, jamais le rôle admin
    `greensig`."""
    url = os.environ.get("GREENSIG_LECTURE_SEULE_DATABASE_URL")
    if url:
        return url
    mot_de_passe = os.environ.get("GREENSIG_DB_LECTURE_SEULE_PASSWORD", "changeme_lecture_seule")
    hote = os.environ.get("GREENSIG_DB_HOST", "localhost")
    port = os.environ.get("GREENSIG_DB_PORT", "5433")
    return f"postgresql://greensig_lecture_seule:{mot_de_passe}@{hote}:{port}/greensig"


_PROMPT_SYSTEME = (
    "Tu es un analyste de bases de données spécialisé dans l'extraction de données "
    "d'ordonnancement depuis des schémas ERP quelconques. Tu réponds toujours en JSON strict, "
    "jamais en texte libre, et ne proposes jamais rien d'autre qu'une requête SELECT en lecture seule."
)


class _SchemaRequete(BaseModel):
    nom: str = Field(description="Nom court identifiant le besoin (ex: 'taches', 'ressources').")
    sql: str = Field(description="Requête SELECT/WITH en lecture seule, une seule instruction.")


class _SchemaExploration(BaseModel):
    requetes: list[_SchemaRequete] = Field(default_factory=list)
    avertissements: list[str] = Field(
        default_factory=list, description="Incertitudes ou besoins hors de portée du schéma fourni."
    )

_STATEMENT_TIMEOUT_MS = 5000

_MOTS_INTERDITS = (
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "grant",
    "revoke",
    "create",
    "truncate",
    "copy",
    "call",
    "execute",
    "vacuum",
    "pg_terminate_backend",
    "pg_read_file",
    "pg_write_file",
    "pg_read_binary_file",
    "dblink",
    "lo_import",
    "lo_export",
    "pg_sleep",
)
_MOTIF_MOT_INTERDIT = re.compile(r"\b(" + "|".join(_MOTS_INTERDITS) + r")\b", re.IGNORECASE)
_MOTIF_COMMENTAIRE_LIGNE = re.compile(r"--.*$", re.MULTILINE)
_MOTIF_COMMENTAIRE_BLOC = re.compile(r"/\*.*?\*/", re.DOTALL)


class ErreurRequeteNonAutorisee(Exception):
    """Une requête proposée par l'agent n'est pas un SELECT/WITH lecture
    seule unique — rejetée avant d'atteindre la base."""


def _valider_requete_lecture_seule(sql_brut: str) -> str:
    """Premier filtre, faible (voir docstring du module) : rejette tout ce
    qui n'est pas un unique SELECT/WITH, et une liste noire de mots-clés/
    fonctions dangereux même à l'intérieur d'un SELECT par ailleurs valide."""
    sans_commentaires = _MOTIF_COMMENTAIRE_BLOC.sub(" ", _MOTIF_COMMENTAIRE_LIGNE.sub(" ", sql_brut))
    requete = sans_commentaires.strip()
    if requete.endswith(";"):
        requete = requete[:-1].strip()
    if ";" in requete:
        raise ErreurRequeteNonAutorisee("plusieurs instructions détectées (point-virgule interne)")
    if not requete:
        raise ErreurRequeteNonAutorisee("requête vide")
    premier_mot = requete.split(None, 1)[0].lower()
    if premier_mot not in ("select", "with"):
        raise ErreurRequeteNonAutorisee(f"seul SELECT/WITH est autorisé, pas : {premier_mot!r}")
    correspondance = _MOTIF_MOT_INTERDIT.search(sans_commentaires)
    if correspondance is not None:
        raise ErreurRequeteNonAutorisee(f"mot-clé non autorisé dans la requête : {correspondance.group(0)!r}")
    return sql_brut


@dataclass(frozen=True)
class TableSchema:
    nom: str
    colonnes: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class RelationCle:
    table: str
    colonne: str
    table_referencee: str
    colonne_referencee: str


@dataclass(frozen=True)
class SchemaBaseDeDonnees:
    tables: tuple[TableSchema, ...]
    relations: tuple[RelationCle, ...]

    def formatte(self) -> str:
        lignes: list[str] = []
        for table in self.tables:
            colonnes = ", ".join(f"{nom} ({type_})" for nom, type_ in table.colonnes)
            lignes.append(f"- {table.nom} : {colonnes}")
        if self.relations:
            lignes.append("")
            lignes.append("Clés étrangères :")
            for relation in self.relations:
                lignes.append(
                    f"- {relation.table}.{relation.colonne} -> "
                    f"{relation.table_referencee}.{relation.colonne_referencee}"
                )
        return "\n".join(lignes)


def introspecter_schema(
    connexion: psycopg.Connection, schemas: tuple[str, ...] = ("public",)
) -> SchemaBaseDeDonnees:
    """Décrit le schéma réellement présent — déterministe, jamais confié au
    LLM (plus sûr et moins cher qu'une exploration en plusieurs
    allers-retours)."""
    colonnes_par_table: dict[str, list[tuple[str, str]]] = {}
    for nom_table, nom_colonne, type_colonne in connexion.execute(
        "SELECT table_name, column_name, data_type FROM information_schema.columns "
        "WHERE table_schema = ANY(%s) ORDER BY table_name, ordinal_position",
        (list(schemas),),
    ).fetchall():
        colonnes_par_table.setdefault(nom_table, []).append((nom_colonne, type_colonne))

    tables = tuple(TableSchema(nom=nom, colonnes=tuple(cols)) for nom, cols in colonnes_par_table.items())

    relations = tuple(
        RelationCle(table=table, colonne=colonne, table_referencee=table_ref, colonne_referencee=colonne_ref)
        for table, colonne, table_ref, colonne_ref in connexion.execute(
            """
            SELECT tc.table_name, kcu.column_name, ccu.table_name, ccu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = ANY(%s)
            """,
            (list(schemas),),
        ).fetchall()
    )

    return SchemaBaseDeDonnees(tables=tables, relations=relations)


@dataclass(frozen=True)
class ResultatExplorationBDD:
    reponse_brute: str
    requetes_executees: tuple[str, ...]
    donnees_json: dict[str, Any]
    avertissements: tuple[str, ...]


def _executer(connexion: psycopg.Connection, requete_sql: str) -> list[dict[str, Any]]:
    curseur = connexion.execute(requete_sql)
    colonnes = [description.name for description in curseur.description]
    return [dict(zip(colonnes, ligne, strict=True)) for ligne in curseur.fetchall()]


def explorer_base_de_donnees(
    modele: BaseChatModel, dsn_lecture_seule: str, schemas: tuple[str, ...] = ("public",)
) -> ResultatExplorationBDD:
    """Le sous-agent complet : introspection déterministe, un seul appel LLM
    pour décider des requêtes, validation puis exécution sur une connexion
    strictement lecture seule (voir docstring du module pour la frontière
    de sécurité réelle)."""
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")

    with closing(
        psycopg.connect(
            dsn_lecture_seule,
            options=f"-c default_transaction_read_only=on -c statement_timeout={_STATEMENT_TIMEOUT_MS}",
        )
    ) as connexion:
        schema = introspecter_schema(connexion, schemas=schemas)
        prompt = gabarit.format(schema_description=schema.formatte())

        structure = modele.with_structured_output(
            _SchemaExploration, include_raw=True, method=methode_sortie_structuree(modele)
        )
        sortie = _avec_retry(structure.invoke)(
            [SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)]
        )
        reponse_brute = extraire_texte_brut(sortie["raw"])
        if sortie["parsing_error"] is not None:
            raise ErreurReponseAgentInvalide(
                f"réponse non conforme au schéma reçue de l'agent : {reponse_brute[:200]!r}"
            ) from sortie["parsing_error"]

        donnees = sortie["parsed"]
        requetes_executees: list[str] = []
        donnees_json: dict[str, Any] = {}
        for requete in donnees.requetes:
            sql_valide = _valider_requete_lecture_seule(requete.sql)
            requetes_executees.append(sql_valide)
            donnees_json[requete.nom] = _executer(connexion, sql_valide)

    return ResultatExplorationBDD(
        reponse_brute=reponse_brute,
        requetes_executees=tuple(requetes_executees),
        donnees_json=donnees_json,
        avertissements=tuple(donnees.avertissements),
    )
