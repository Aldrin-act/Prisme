"""Couche 1 (§6.1) : `/adapters/greensig/ingerer` fait le pont entre la base
GreenSIG réelle (`db_greensig`, profil `greensig`) et le canal d'ingestion —
nécessite ce service, skip sinon (voir `greensig_dsn`). `/adapters/comprehension/ingerer`
(agent LLM, `adapters/agent_comprehension/`) n'a besoin d'aucun service
externe ici : `construire_modele_comprehension` est substitué comme
n'importe quelle autre dépendance FastAPI (`app.dependency_overrides`),
jamais un vrai appel LLM.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from adapters.agent_comprehension.agent import _SchemaComprehension
from api.app import app
from api.etat import EtatAPI, obtenir_etat
from generation.agents.client_llm import construire_modele_comprehension
from tests.unit.aides_test_agents import ModeleFactice


def test_ingestion_depuis_greensig_signale_le_rejet_du_lot_brut(greensig_dsn: str) -> None:
    """Documente l'état réel actuel (voir tests/integration/test_greensig_extraction.py) :
    228/1007 tâches à planifier n'ont aucune équipe active, donc `traduire()` rejette tout
    le lot — la route doit relayer ce 422 tel quel, jamais masquer le rejet derrière un
    succès partiel."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test

    try:
        client = TestClient(app)
        reponse = client.post("/adapters/greensig/ingerer")

        assert reponse.status_code == 422
        detail = reponse.json()["detail"]
        assert any("sans aucune contrainte de compatibilité" in erreur["msg"] for erreur in detail)
        assert etat_test.instances == {}
    finally:
        app.dependency_overrides.clear()


def test_ingestion_via_comprehension_accepte_une_traduction_valide() -> None:
    etat_test = EtatAPI()
    schema_agent = _SchemaComprehension(
        instance={
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [
                {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}
            ],
            "objectifs": [{"type": "minimiser_makespan"}],
        },
        avertissements=["durée estimée, absente des données source"],
    )
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=schema_agent
    )

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/comprehension/ingerer",
            json={"client_id": "nouveau_client", "donnees_brutes": "T1;M1;10min"},
        )

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        assert corps["structure_contraintes"] == "compatibilite_ressource_tache"
        assert corps["avertissements"] == ["durée estimée, absente des données source"]
        assert corps["instance_id"] in etat_test.instances
    finally:
        app.dependency_overrides.clear()


def test_ingestion_via_comprehension_relaie_le_rejet_du_garde_fou() -> None:
    """Le garde-fou déterministe (§6.7) tranche pareil, que le payload vienne d'un humain,
    d'un adaptateur écrit à la main ou de l'agent de compréhension : une tâche sans
    compatibilité est rejetée avec un 422, jamais ingérée en silence."""
    etat_test = EtatAPI()
    schema_agent = _SchemaComprehension(
        instance={
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [],
            "objectifs": [{"type": "minimiser_makespan"}],
        }
    )
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=schema_agent
    )

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/comprehension/ingerer",
            json={"client_id": "nouveau_client", "donnees_brutes": "???"},
        )

        assert reponse.status_code == 422
        assert etat_test.instances == {}
    finally:
        app.dependency_overrides.clear()


def test_ingestion_via_comprehension_signale_une_reponse_llm_non_conforme() -> None:
    app.dependency_overrides[obtenir_etat] = lambda: EtatAPI()
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="désolé, je ne peux pas faire ça.", parsed=None, parsing_error=ValueError("mal formé")
    )

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/comprehension/ingerer",
            json={"client_id": "nouveau_client", "donnees_brutes": "???"},
        )

        assert reponse.status_code == 502
    finally:
        app.dependency_overrides.clear()
