"""Crée (si absent) un rôle Postgres lecture seule sur la base GreenSIG, pour
`adapters/agent_comprehension/exploration_bdd.py` (§5.4 bis, sous-agent
d'exploration de base de données). C'est la vraie frontière de sécurité —
pas le filtre SQL statique de `exploration_bdd.py`, qui n'est qu'un premier
filtre faible (même relation que l'allowlist AST vs. le sandbox, §5.3) :
même si le LLM générait une requête d'écriture qui passait ce filtre, ce
rôle ne pourrait de toute façon rien écrire.

Idempotent (même motif que `enregistrer_solveur_reference.py`) : relançable
sans effet de bord. Connecté avec les creds admin `greensig` existants
(`GREENSIG_DATABASE_URL`/`GREENSIG_DB_*`, voir `adapters/greensig/extraction.py`).

Usage, depuis la racine du dépôt : python -m scripts.creer_role_lecture_seule_greensig
"""

from __future__ import annotations

import os
from contextlib import closing

import psycopg
from psycopg import sql

from adapters.greensig.extraction import dsn_par_defaut

NOM_ROLE = "greensig_lecture_seule"
NOM_BASE = "greensig"


def _mot_de_passe() -> str:
    mot_de_passe = os.environ.get("GREENSIG_DB_LECTURE_SEULE_PASSWORD")
    if not mot_de_passe:
        raise RuntimeError("GREENSIG_DB_LECTURE_SEULE_PASSWORD non défini (voir .env.example)")
    return mot_de_passe


def creer_role(dsn: str | None = None) -> None:
    """Crée le rôle lecture seule, ses droits, et impose
    `default_transaction_read_only` de façon persistante sur le rôle —
    en plus du flag mis à chaque connexion (`exploration_bdd.py`), pour ne
    jamais dépendre d'un seul point de contrôle."""
    with closing(psycopg.connect(dsn or dsn_par_defaut(), autocommit=True)) as connexion:
        role_existe = connexion.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (NOM_ROLE,)).fetchone()
        if not role_existe:
            connexion.execute(
                sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(
                    sql.Identifier(NOM_ROLE), sql.Literal(_mot_de_passe())
                )
            )

        connexion.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(NOM_BASE), sql.Identifier(NOM_ROLE)
            )
        )
        connexion.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(NOM_ROLE)))
        connexion.execute(
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(NOM_ROLE))
        )
        connexion.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {}").format(
                sql.Identifier(NOM_ROLE)
            )
        )
        connexion.execute(
            sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(sql.Identifier(NOM_ROLE))
        )


def main() -> None:
    creer_role()
    print(f"rôle lecture seule prêt : {NOM_ROLE!r} sur la base {NOM_BASE!r}")


if __name__ == "__main__":
    main()
