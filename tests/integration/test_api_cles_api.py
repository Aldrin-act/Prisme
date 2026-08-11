"""Couche 1 (§6.1) : premier test d'intégration à exercer la vraie résolution d'identité
(JWT puis clé API) plutôt que le bypass autouse de `conftest.py::_utilisateur_authentifie_par_defaut`
— nécessite PostgreSQL joignable, comme `test_api_planifier.py`. `UtilisateursDB`/`ClesApiDB` ne
sont pas derrière `Depends` (globals eager, voir `api/routes/auth.py`) : substituées ici par
monkeypatch de module plutôt que par `app.dependency_overrides`."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import api.routes.api_keys as api_keys_module
import api.routes.auth as auth_module
from api.app import app
from api.auth_db import UtilisateursDB
from api.cles_api_db import ClesApiDB
from api.routes.auth import obtenir_utilisateur_courant

_MOT_DE_PASSE = "un-mot-de-passe-suffisamment-long"


@pytest.fixture
def client_avec_vraie_auth(registre_test: object) -> Iterator[tuple[TestClient, UtilisateursDB]]:
    """`registre_test` n'est utilisé ici que pour son garde-fou skip-si-Postgres-injoignable
    (même DSN que `UtilisateursDB`/`ClesApiDB`) — ce test ne touche jamais le registre lui-même."""
    schema = f"test_{uuid.uuid4().hex}"
    utilisateurs_test = UtilisateursDB(schema=schema)
    cles_api_test = ClesApiDB(schema=schema)

    utilisateurs_original = auth_module.utilisateurs_db
    cles_api_original = auth_module.cles_api_db
    auth_desactivee_original = auth_module.AUTH_DESACTIVEE
    auth_module.utilisateurs_db = utilisateurs_test
    auth_module.cles_api_db = cles_api_test
    api_keys_module.cles_api_db = cles_api_test
    # `.env` positionne PRISME_AUTH_DESACTIVEE=1 pour le confort en dev local — ce test exerce
    # justement la vraie résolution d'identité, doit donc la désactiver le temps du test.
    auth_module.AUTH_DESACTIVEE = False

    # Retire le bypass autouse : ce test exerce la vraie résolution d'identité, pas l'utilisateur factice.
    app.dependency_overrides.pop(obtenir_utilisateur_courant, None)

    try:
        yield TestClient(app), utilisateurs_test
    finally:
        auth_module.utilisateurs_db = utilisateurs_original
        auth_module.cles_api_db = cles_api_original
        api_keys_module.cles_api_db = cles_api_original
        auth_module.AUTH_DESACTIVEE = auth_desactivee_original


def _creer_utilisateur_et_connecter(client: TestClient, utilisateurs_db: UtilisateursDB, email: str) -> str:
    utilisateurs_db.creer_utilisateur(email=email, mot_de_passe=_MOT_DE_PASSE, nom="Test", prenom="Utilisateur")
    reponse = client.post("/auth/login", json={"email": email, "password": _MOT_DE_PASSE})
    assert reponse.status_code == 200, reponse.text
    return reponse.json()["session"]["token"]


def test_le_secret_cree_authentifie_les_appels_suivants(
    client_avec_vraie_auth: tuple[TestClient, UtilisateursDB],
) -> None:
    client, utilisateurs_test = client_avec_vraie_auth
    jwt = _creer_utilisateur_et_connecter(client, utilisateurs_test, "alice@example.com")

    creation = client.post("/api-keys", json={"nom": "ci-readonly"}, headers={"Authorization": f"Bearer {jwt}"})
    assert creation.status_code == 201, creation.text
    secret = creation.json()["secret"]
    assert secret.startswith("pk_live_")

    reponse = client.get("/api-keys", headers={"Authorization": f"Bearer {secret}"})

    assert reponse.status_code == 200
    assert [c["nom"] for c in reponse.json()] == ["ci-readonly"]


def test_lister_cles_api_ne_renvoie_jamais_le_secret_ni_le_hash(
    client_avec_vraie_auth: tuple[TestClient, UtilisateursDB],
) -> None:
    client, utilisateurs_test = client_avec_vraie_auth
    jwt = _creer_utilisateur_et_connecter(client, utilisateurs_test, "bob@example.com")
    client.post("/api-keys", json={"nom": "prod-write"}, headers={"Authorization": f"Bearer {jwt}"})

    reponse = client.get("/api-keys", headers={"Authorization": f"Bearer {jwt}"})

    (cle,) = reponse.json()
    assert "secret" not in cle
    assert "hash" not in cle
    assert cle["prefixe"].startswith("pk_live_")


def test_cle_revoquee_echoue_ensuite(client_avec_vraie_auth: tuple[TestClient, UtilisateursDB]) -> None:
    client, utilisateurs_test = client_avec_vraie_auth
    jwt = _creer_utilisateur_et_connecter(client, utilisateurs_test, "carole@example.com")
    creation = client.post("/api-keys", json={"nom": "temp"}, headers={"Authorization": f"Bearer {jwt}"})
    cle_id, secret = creation.json()["cle_id"], creation.json()["secret"]

    revocation = client.delete(f"/api-keys/{cle_id}", headers={"Authorization": f"Bearer {jwt}"})
    assert revocation.status_code == 204

    reponse = client.get("/api-keys", headers={"Authorization": f"Bearer {secret}"})

    assert reponse.status_code == 401


def test_revoquer_la_cle_dun_autre_utilisateur_renvoie_404(
    client_avec_vraie_auth: tuple[TestClient, UtilisateursDB],
) -> None:
    client, utilisateurs_test = client_avec_vraie_auth
    jwt_proprietaire = _creer_utilisateur_et_connecter(client, utilisateurs_test, "dave@example.com")
    jwt_intrus = _creer_utilisateur_et_connecter(client, utilisateurs_test, "eve@example.com")
    creation = client.post(
        "/api-keys", json={"nom": "prod-write"}, headers={"Authorization": f"Bearer {jwt_proprietaire}"}
    )
    cle_id = creation.json()["cle_id"]

    reponse = client.delete(f"/api-keys/{cle_id}", headers={"Authorization": f"Bearer {jwt_intrus}"})

    assert reponse.status_code == 404
