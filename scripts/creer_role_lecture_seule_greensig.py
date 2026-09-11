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
Généralisable à un autre client (§5.4 bis, `dsn_lecture_seule_pour_client`) via les options
`--role`/--base`/`--schema`/`--dsn-admin`/`--variable-mot-de-passe` — invocation sans argument
inchangée, reproduit exactement le comportement historique GreenSIG.
"""

from __future__ import annotations

import argparse
import os
from contextlib import closing

import psycopg
from psycopg import sql

from adapters.greensig.extraction import dsn_par_defaut

NOM_ROLE = "greensig_lecture_seule"
NOM_BASE = "greensig"
_SCHEMA_PAR_DEFAUT = "public"
_VARIABLE_MOT_DE_PASSE_PAR_DEFAUT = "GREENSIG_DB_LECTURE_SEULE_PASSWORD"


def _mot_de_passe(variable: str = _VARIABLE_MOT_DE_PASSE_PAR_DEFAUT) -> str:
    mot_de_passe = os.environ.get(variable)
    if not mot_de_passe:
        raise RuntimeError(f"{variable} non défini (voir .env.example)")
    return mot_de_passe


def creer_role(
    dsn: str | None = None,
    nom_role: str = NOM_ROLE,
    nom_base: str = NOM_BASE,
    schema: str = _SCHEMA_PAR_DEFAUT,
    variable_mot_de_passe: str = _VARIABLE_MOT_DE_PASSE_PAR_DEFAUT,
) -> None:
    """Crée le rôle lecture seule, ses droits, et impose
    `default_transaction_read_only` de façon persistante sur le rôle —
    en plus du flag mis à chaque connexion (`exploration_bdd.py`), pour ne
    jamais dépendre d'un seul point de contrôle.

    `dsn` reste le DSN *admin* servant à créer le rôle (jamais le DSN du
    rôle lui-même) ; par défaut celui de GreenSIG (`dsn_par_defaut()`) —
    pour un autre client, il n'y a pas d'équivalent générique à deviner,
    voir le garde-fou dans `main` ci-dessous."""
    with closing(psycopg.connect(dsn or dsn_par_defaut(), autocommit=True)) as connexion:
        role_existe = connexion.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (nom_role,)).fetchone()
        if not role_existe:
            connexion.execute(
                sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD {}").format(
                    sql.Identifier(nom_role), sql.Literal(_mot_de_passe(variable_mot_de_passe))
                )
            )

        connexion.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                sql.Identifier(nom_base), sql.Identifier(nom_role)
            )
        )
        connexion.execute(
            sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(schema), sql.Identifier(nom_role))
        )
        connexion.execute(
            sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(
                sql.Identifier(schema), sql.Identifier(nom_role)
            )
        )
        connexion.execute(
            sql.SQL("ALTER DEFAULT PRIVILEGES IN SCHEMA {} GRANT SELECT ON TABLES TO {}").format(
                sql.Identifier(schema), sql.Identifier(nom_role)
            )
        )
        connexion.execute(
            sql.SQL("ALTER ROLE {} SET default_transaction_read_only = on").format(sql.Identifier(nom_role))
        )


def _analyser_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    analyseur = argparse.ArgumentParser(description=__doc__)
    analyseur.add_argument("--role", default=NOM_ROLE, help="nom du rôle lecture seule à créer")
    analyseur.add_argument("--base", default=NOM_BASE, help="base cible")
    analyseur.add_argument("--schema", default=_SCHEMA_PAR_DEFAUT, help="schéma à autoriser en lecture")
    analyseur.add_argument(
        "--dsn-admin",
        default=None,
        help="DSN admin pour créer le rôle — requis dès que --role/--base diffèrent des valeurs GreenSIG",
    )
    analyseur.add_argument(
        "--variable-mot-de-passe",
        default=_VARIABLE_MOT_DE_PASSE_PAR_DEFAUT,
        help="nom de la variable d'environnement portant le mot de passe du rôle",
    )
    return analyseur.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _analyser_arguments(argv)
    personnalise = args.role != NOM_ROLE or args.base != NOM_BASE
    if personnalise and not args.dsn_admin:
        raise SystemExit(
            "--dsn-admin requis : --role/--base diffèrent des valeurs GreenSIG par défaut, "
            "pas de DSN admin générique à deviner"
        )
    creer_role(
        dsn=args.dsn_admin,
        nom_role=args.role,
        nom_base=args.base,
        schema=args.schema,
        variable_mot_de_passe=args.variable_mot_de_passe,
    )
    print(f"rôle lecture seule prêt : {args.role!r} sur la base {args.base!r} (schéma {args.schema!r})")


if __name__ == "__main__":
    main()
