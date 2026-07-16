"""Fixtures partagées pour les tests d'intégration qui nécessitent Docker
(§7), PostgreSQL (§7.2, `solver_store/registry.py`), ou la base de référence
GreenSIG (`db_greensig`, profil `greensig`, `adapters/greensig/extraction.py`).
Ces tests sont ignorés (skip), pas en échec, si la dépendance externe n'est
pas disponible dans l'environnement d'exécution.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import psycopg
import pytest
from psycopg import sql

from solver_store.registry import Registre, dsn_par_defaut

RACINE_DEPOT = Path(__file__).resolve().parents[2]


def _docker_disponible() -> bool:
    try:
        import docker

        docker.from_env().ping()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def image_sandbox() -> str:
    """Construit (si besoin) l'image du sandbox ; saute les tests si Docker
    est indisponible plutôt que de les faire échouer."""
    if not _docker_disponible():
        pytest.skip("Docker indisponible dans cet environnement")

    import docker

    from sandbox.runner import IMAGE_SANDBOX

    client = docker.from_env()
    client.images.build(
        path=str(RACINE_DEPOT),
        dockerfile=str(RACINE_DEPOT / "sandbox" / "container" / "Dockerfile"),
        tag=IMAGE_SANDBOX,
    )
    return IMAGE_SANDBOX


def _postgres_disponible() -> bool:
    try:
        with closing(psycopg.connect(dsn_par_defaut(), connect_timeout=2)):
            return True
    except Exception:
        return False


@pytest.fixture
def registre_test(tmp_path: Path) -> Iterator[Registre]:
    """Un registre Postgres isolé dans un schéma unique (plutôt qu'un fichier
    `.sqlite3` dédié, comme avant la migration §7.2) ; le schéma est
    supprimé après le test. Saute plutôt que d'échouer si Postgres est
    injoignable — même convention que `image_sandbox` pour Docker."""
    if not _postgres_disponible():
        pytest.skip("PostgreSQL indisponible dans cet environnement")

    schema = f"test_{uuid.uuid4().hex}"
    registre = Registre(schema=schema, dossier_artefacts=tmp_path / "artifacts")
    try:
        yield registre
    finally:
        with closing(psycopg.connect(dsn_par_defaut())) as connexion:
            connexion.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
            connexion.commit()


def _greensig_dsn_par_defaut() -> str:
    from adapters.greensig.extraction import dsn_par_defaut as greensig_dsn_par_defaut

    return greensig_dsn_par_defaut()


def _greensig_disponible() -> bool:
    try:
        with closing(psycopg.connect(_greensig_dsn_par_defaut(), connect_timeout=2)):
            return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def greensig_dsn() -> str:
    """Le DSN de `db_greensig` (profil `greensig`, hors périmètre par défaut) — saute si
    injoignable, même convention que `image_sandbox`/`registre_test`. Lecture seule : ce dump
    réel n'est jamais modifié par les tests, pas besoin d'isolation par schéma."""
    if not _greensig_disponible():
        pytest.skip("Base GreenSIG (db_greensig) indisponible dans cet environnement")
    return _greensig_dsn_par_defaut()
