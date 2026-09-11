"""Couche 1 (§6.1) : `/planifier/*` compose ingestion + exécution en un seul
appel — mêmes garde-fous que les routes qu'il compose (`/ingestion`,
`/adapters/*/ingerer`, `/execution/{instance_id}`), voir docstring de
`api/routes/planifier.py`. Nécessite PostgreSQL joignable (comme
`test_api_ingestion.py`) : `client_isole` instancie un `Registre` réel pour
la dépendance FastAPI, même sans solveur enregistré.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from adapters.agent_comprehension.agent import _SchemaComprehension
from api.app import app
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from generation.agents.client_llm import construire_modele_comprehension
from solver_store.registry import Registre
from tests.unit.aides_test_agents import ModeleFactice


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


def _payload_valide() -> dict:
    return {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def test_planifier_ingere_puis_echoue_proprement_sans_solveur(
    client_isole: tuple[TestClient, EtatAPI],
) -> None:
    """Aucun solveur validé n'existe encore pour cette structure — l'appel
    ingère quand même l'instance (elle reste consultable) et remonte le 409
    d'`executer_pour_instance` tel quel, jamais une génération à la volée."""
    client, etat_test = client_isole

    reponse = client.post("/planifier/client_a", json=_payload_valide())

    assert reponse.status_code == 409
    assert len(etat_test.instances) == 1  # l'ingestion a bien eu lieu avant l'échec d'exécution


def test_planifier_via_comprehension_traduit_puis_echoue_proprement_sans_solveur(
    client_isole: tuple[TestClient, EtatAPI],
) -> None:
    client, etat_test = client_isole
    schema_agent = _SchemaComprehension(
        instance={
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [
                {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}
            ],
            "objectifs": [{"type": "minimiser_makespan"}],
        },
        description_metier="Une tâche T1 exécutée sur la ressource R1.",
        avertissements=["durée estimée, absente des données source"],
    )
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=schema_agent
    )

    reponse = client.post(
        "/planifier/client_a/comprehension",
        json={"donnees_brutes": "T1;R1;10j"},
    )

    assert reponse.status_code == 409  # même limite que le test précédent — pas de solveur encore
    (instance_id,) = etat_test.instances.keys()
    assert etat_test.recuperer_description_metier(instance_id) == "Une tâche T1 exécutée sur la ressource R1."


def test_planifier_via_comprehension_relaie_le_rejet_du_garde_fou(
    client_isole: tuple[TestClient, EtatAPI],
) -> None:
    """Même garde-fou déterministe (§6.7) que `/adapters/comprehension/ingerer` :
    une tâche sans compatibilité proposée par l'agent est rejetée, jamais
    ingérée en silence."""
    client, etat_test = client_isole
    schema_agent = _SchemaComprehension(
        instance={
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [],
            "objectifs": [{"type": "minimiser_makespan"}],
        },
        description_metier="Une tâche T1, sans ressource compatible identifiée.",
    )
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=schema_agent
    )

    reponse = client.post("/planifier/client_a/comprehension", json={"donnees_brutes": "T1 seule"})

    assert reponse.status_code == 422
    assert etat_test.instances == {}


def test_planifier_greensig_est_bien_route_vers_greensig_pas_vers_client_id(
    client_isole: tuple[TestClient, EtatAPI], greensig_dsn: str
) -> None:
    """Garde-fou de non-régression : `/planifier/{client_id}` est enregistrée
    après `/planifier/greensig` précisément pour que ce test passe — si
    l'ordre s'inversait, Starlette matcherait `/planifier/greensig` comme
    `client_id="greensig"` sur la route générique, qui répondrait 422 sur le
    corps manquant (`payload` requis) plutôt que sur le rejet réel du lot
    GreenSIG (voir `test_ingestion_depuis_greensig_signale_le_rejet_du_lot_brut`,
    `test_api_adapters.py`)."""
    client, etat_test = client_isole

    reponse = client.post("/planifier/greensig")

    assert reponse.status_code == 422
    detail = reponse.json()["detail"]
    assert any("sans aucune contrainte de compatibilité" in erreur["msg"] for erreur in detail)
    assert etat_test.instances == {}
