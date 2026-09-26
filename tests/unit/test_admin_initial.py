"""Couche 1 : `api/admin_initial.py` — compte admin créé au démarrage depuis l'environnement.
Base simulée (aucun Postgres) : seul le contrat `email_existe`/`creer_utilisateur` compte."""

from __future__ import annotations

import pytest

from api.admin_initial import creer_admin_initial

_ENV = {"PRISME_ADMIN_EMAIL": "admin@prisme.ma", "PRISME_ADMIN_MOT_DE_PASSE": "un-mot-de-passe-long"}


class _BaseFactice:
    def __init__(self, emails: set[str] | None = None) -> None:
        self.emails = set(emails or ())
        self.crees: list[dict] = []

    def email_existe(self, email: str) -> bool:
        return email in self.emails

    def creer_utilisateur(self, **champs) -> None:
        self.crees.append(champs)
        self.emails.add(champs["email"])


def test_cree_un_admin_sans_client() -> None:
    db = _BaseFactice()

    assert creer_admin_initial(db, _ENV) is True
    assert db.crees == [
        {
            "email": "admin@prisme.ma",
            "mot_de_passe": "un-mot-de-passe-long",
            "nom": "Administrateur",
            "prenom": "PRISME",
            "role": "admin",
            "client_id": None,
        }
    ]


def test_ne_touche_jamais_un_compte_existant() -> None:
    """Redémarrer le serveur ne doit ni recréer le compte ni écraser un mot de passe changé depuis."""
    db = _BaseFactice(emails={"admin@prisme.ma"})

    assert creer_admin_initial(db, _ENV) is False
    assert db.crees == []


def test_idempotent_sur_deux_demarrages() -> None:
    db = _BaseFactice()
    creer_admin_initial(db, _ENV)

    assert creer_admin_initial(db, _ENV) is False
    assert len(db.crees) == 1


def test_sans_variables_aucune_action() -> None:
    db = _BaseFactice()

    assert creer_admin_initial(db, {}) is False
    assert db.crees == []


@pytest.mark.parametrize(
    "env",
    [
        {"PRISME_ADMIN_EMAIL": "admin@prisme.ma"},
        {"PRISME_ADMIN_MOT_DE_PASSE": "un-mot-de-passe-long"},
        {"PRISME_ADMIN_EMAIL": "admin@prisme.ma", "PRISME_ADMIN_MOT_DE_PASSE": "court"},
    ],
)
def test_configuration_incomplete_ou_faible_echoue_explicitement(env: dict[str, str]) -> None:
    db = _BaseFactice()

    with pytest.raises(ValueError):
        creer_admin_initial(db, env)
    assert db.crees == []
