"""Couche 1 (§6.1) : le câblage CLI (`argparse`) est pur et testable sans base réelle — la
création effective du rôle (SQL) n'est testable qu'avec un vrai Postgres, voir
`tests/integration/test_exploration_bdd_greensig.py` pour la frontière de sécurité elle-même.
"""

from __future__ import annotations

import pytest

from scripts.creer_role_lecture_seule_greensig import NOM_BASE, NOM_ROLE, _analyser_arguments, main


def test_zero_argument_reproduit_les_valeurs_greensig() -> None:
    args = _analyser_arguments([])

    assert args.role == NOM_ROLE
    assert args.base == NOM_BASE
    assert args.dsn_admin is None


def test_role_personnalise_sans_dsn_admin_leve(monkeypatch: pytest.MonkeyPatch) -> None:
    def _jamais_appele(*_a: object, **_k: object) -> None:
        raise AssertionError("creer_role ne doit jamais être appelé sans --dsn-admin")

    monkeypatch.setattr("scripts.creer_role_lecture_seule_greensig.creer_role", _jamais_appele)

    with pytest.raises(SystemExit, match="--dsn-admin requis"):
        main(["--role", "acme_lecture_seule"])


def test_base_personnalisee_sans_dsn_admin_leve(monkeypatch: pytest.MonkeyPatch) -> None:
    def _jamais_appele(*_a: object, **_k: object) -> None:
        raise AssertionError("creer_role ne doit jamais être appelé sans --dsn-admin")

    monkeypatch.setattr("scripts.creer_role_lecture_seule_greensig.creer_role", _jamais_appele)

    with pytest.raises(SystemExit, match="--dsn-admin requis"):
        main(["--base", "acme_db"])


def test_role_et_dsn_admin_personnalises_appelle_creer_role_avec_les_bons_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captures: dict[str, object] = {}

    def _capture(**kwargs: object) -> None:
        captures.update(kwargs)

    monkeypatch.setattr("scripts.creer_role_lecture_seule_greensig.creer_role", _capture)

    main(
        [
            "--role",
            "acme_lecture_seule",
            "--base",
            "acme_db",
            "--dsn-admin",
            "postgresql://admin@localhost/acme_db",
            "--schema",
            "vente",
            "--variable-mot-de-passe",
            "ACME_DB_LECTURE_SEULE_PASSWORD",
        ]
    )

    assert captures == {
        "dsn": "postgresql://admin@localhost/acme_db",
        "nom_role": "acme_lecture_seule",
        "nom_base": "acme_db",
        "schema": "vente",
        "variable_mot_de_passe": "ACME_DB_LECTURE_SEULE_PASSWORD",
    }


def test_zero_argument_appelle_creer_role_avec_les_valeurs_greensig(monkeypatch: pytest.MonkeyPatch) -> None:
    captures: dict[str, object] = {}

    def _capture(**kwargs: object) -> None:
        captures.update(kwargs)

    monkeypatch.setattr("scripts.creer_role_lecture_seule_greensig.creer_role", _capture)

    main([])

    assert captures == {
        "dsn": None,
        "nom_role": NOM_ROLE,
        "nom_base": NOM_BASE,
        "schema": "public",
        "variable_mot_de_passe": "GREENSIG_DB_LECTURE_SEULE_PASSWORD",
    }
