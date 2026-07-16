"""Couche 1 (§6.1) : `/adapters/greensig/ingerer` fait le pont entre la base
GreenSIG réelle (`db_greensig`, profil `greensig`) et le canal d'ingestion.
Nécessite ce service — skip sinon (voir `greensig_dsn`).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from api.etat import EtatAPI, obtenir_etat


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
