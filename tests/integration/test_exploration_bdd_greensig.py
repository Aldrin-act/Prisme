"""Couche 1 (§6.1), Docker/Postgres requis (`db_greensig`, rôle lecture
seule créé par `scripts/creer_role_lecture_seule_greensig.py`) : bout en
bout réel du sous-agent d'exploration de base de données
(`adapters/agent_comprehension/exploration_bdd.py`) contre le vrai dump
GreenSIG. Saute si le rôle lecture seule n'existe pas encore, même
convention que le reste de `tests/integration/`.

Le dernier test (`test_ecriture_bloquee_meme_hors_filtre_python`) contourne
volontairement le filtre SQL statique du module — comme
`test_sandbox_securite.py` contourne l'allowlist AST — pour prouver que la
vraie frontière (le rôle Postgres lui-même) tient indépendamment du filtre
côté Python, qui n'est jamais la garantie réelle (voir docstring du module).
"""

from __future__ import annotations

from contextlib import closing

import psycopg
import pytest

from adapters.agent_comprehension.exploration_bdd import (
    ErreurRequeteNonAutorisee,
    _SchemaExploration,
    _SchemaRequete,
    explorer_base_de_donnees,
    introspecter_schema,
)
from tests.unit.aides_test_agents import ModeleFactice


def test_exploration_execute_une_requete_sure_et_retourne_du_json(greensig_dsn_lecture_seule: str) -> None:
    schema = _SchemaExploration(
        requetes=[
            _SchemaRequete(
                nom="types_tache",
                sql="SELECT id, nom_tache FROM api_planification_typetache ORDER BY id LIMIT 3",
            )
        ],
    )
    modele = ModeleFactice(raw_content="{}", parsed=schema)

    resultat = explorer_base_de_donnees(modele, greensig_dsn_lecture_seule)

    assert resultat.requetes_executees
    assert "types_tache" in resultat.donnees_json
    lignes = resultat.donnees_json["types_tache"]
    assert len(lignes) == 3
    assert set(lignes[0].keys()) == {"id", "nom_tache"}


def test_exploration_rejette_une_requete_decriture_avant_la_base(greensig_dsn_lecture_seule: str) -> None:
    schema = _SchemaExploration(
        requetes=[_SchemaRequete(nom="x", sql="DELETE FROM api_planification_tache")],
    )
    modele = ModeleFactice(raw_content="{}", parsed=schema)

    with pytest.raises(ErreurRequeteNonAutorisee):
        explorer_base_de_donnees(modele, greensig_dsn_lecture_seule)


def test_introspection_detecte_les_tables_reelles(greensig_dsn_lecture_seule: str) -> None:
    """Constat sur données réelles, pas un bug d'introspection : le dump GreenSIG ne déclare
    aucune contrainte FOREIGN KEY au niveau base (vérifié directement en psql) — les relations
    logiques (ex. `api_planification_tache.id_type_tache_id` -> `api_planification_typetache.id`)
    existent mais ne sont pas formalisées. `schema.relations` est donc vide sur cette base
    précise ; `introspecter_schema` reste correct, il n'y a simplement rien à y trouver ici."""
    with closing(psycopg.connect(greensig_dsn_lecture_seule)) as connexion:
        schema = introspecter_schema(connexion)

    noms_tables = {t.nom for t in schema.tables}
    assert "api_planification_tache" in noms_tables
    assert schema.relations == ()


def test_ecriture_bloquee_meme_hors_filtre_python(greensig_dsn_lecture_seule: str) -> None:
    """Contourne volontairement `_valider_requete_lecture_seule` (comme
    `test_sandbox_securite.py` contourne l'allowlist AST) pour prouver que
    le rôle Postgres lecture seule bloque l'écriture indépendamment du
    filtre côté Python — la vraie frontière, pas une commodité."""
    with closing(psycopg.connect(greensig_dsn_lecture_seule)) as connexion:
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            connexion.execute("DELETE FROM api_planification_tache WHERE id = -1")
