"""Couche 1 (§6.1) : la route d'ingestion valide et met en attente une
instance (garde-fou amont, §6.7). Placé dans `integration/` parce qu'il
exerce une vraie application FastAPI via `TestClient`, mais ne nécessite pas
Docker (aucune exécution n'a lieu ici) — contrairement à
`test_api_bout_en_bout.py`. Nécessite en revanche PostgreSQL joignable,
car `client_isole` instancie tout de même un `Registre` pour la
dépendance FastAPI (skip sinon, voir `registre_test`).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from solver_store.registry import Registre


@pytest.fixture
def client_isole(registre_test: Registre) -> Iterator[tuple[TestClient, EtatAPI]]:
    """Un client de test avec état et store isolés — jamais le store réel du dépôt."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[obtenir_registre] = lambda: registre_test
    try:
        yield TestClient(app), etat_test
    finally:
        app.dependency_overrides.clear()


def test_ingestion_accepte_un_payload_valide(client_isole: tuple[TestClient, EtatAPI]) -> None:
    client, etat_test = client_isole
    payload = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}],
        "objectifs": [{"type": "minimiser_makespan"}],
    }

    reponse = client.post("/ingestion/client_a", json=payload)

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["instance_id"] in etat_test.instances
    assert corps["structure_contraintes"] == "compatibilite_ressource_tache"


def test_ingestion_rejette_un_payload_invalide(client_isole: tuple[TestClient, EtatAPI]) -> None:
    client, _ = client_isole
    payload = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": -10}],
        "objectifs": [{"type": "minimiser_makespan"}],
    }

    reponse = client.post("/ingestion/client_a", json=payload)

    assert reponse.status_code == 422


def test_obtenir_instance_sans_description_metier_pour_une_ingestion_directe(
    client_isole: tuple[TestClient, EtatAPI],
) -> None:
    """Une instance ingérée par payload T-R-C-O direct (pas via l'agent de
    compréhension) n'a pas de description métier proposée — `None`, pas une
    absence de champ."""
    client, _ = client_isole
    payload = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}],
        "objectifs": [{"type": "minimiser_makespan"}],
    }
    instance_id = client.post("/ingestion/client_a", json=payload).json()["instance_id"]

    reponse = client.get(f"/ingestion/{instance_id}")

    assert reponse.status_code == 200
    assert reponse.json()["description_metier"] is None


def test_ingestion_calcule_la_structure_de_contraintes(client_isole: tuple[TestClient, EtatAPI]) -> None:
    client, _ = client_isole
    payload = {
        "taches": [{"id": "T1"}, {"id": "T2"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 5},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }

    reponse = client.post("/ingestion/client_a", json=payload)

    assert reponse.status_code == 200
    assert reponse.json()["structure_contraintes"] == "compatibilite_ressource_tache,precedence"
