"""Couche 1 (§6.1) : extraction depuis la base GreenSIG réelle (`db_greensig`,
profil `greensig`) vers `InstanceTRCO`, bout en bout. Nécessite ce service —
skip sinon (voir `greensig_dsn`), même convention que les tests Docker/
Postgres du reste de la suite.
"""

from __future__ import annotations

import pytest

from adapters.greensig import extraire_payload, traduire


def test_extraction_produit_un_payload_non_vide(greensig_dsn: str) -> None:
    payload = extraire_payload(greensig_dsn)

    assert payload.taches, "aucune tâche extraite — le dump backup_20260503.sql est-il restauré ?"
    assert payload.equipes
    assert payload.types_tache


def test_traduction_du_brut_signale_les_taches_sans_equipe_active(greensig_dsn: str) -> None:
    """Constat sur données réelles, pas un bug d'adaptateur : ~23 % des tâches encore à
    planifier (228/1007 sur `backup_20260503.sql`) n'ont aucune équipe active affectée.
    `traduire` refuse d'inventer une compatibilité (regles.md, limite 3) — donc `InstanceTRCO`
    rejette tout le lot plutôt qu'un sous-ensemble silencieusement tronqué. Ce test documente
    ce comportement volontaire ; s'il se met à passer, c'est que le trou de données côté
    GreenSIG a été comblé (ou que la logique de rejet a changé), pas juste un test à supprimer."""
    payload = extraire_payload(greensig_dsn)

    with pytest.raises(ValueError, match="sans aucune contrainte de compatibilité"):
        traduire(payload)
