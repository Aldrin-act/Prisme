"""Couche 1 (§6.1) : `POST /sources/{id}/generer-instance-deterministe`
(`api/routes/sources.py`) — alternative sans agent LLM à `generer_instance`,
aucun service externe requis ici (state en mémoire, pas de vrai appel LLM ni
de Postgres).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from api.etat import EtatAPI, obtenir_etat


def _creer_source(client: TestClient, donnees_brutes: str) -> str:
    reponse = client.post("/sources", json={"donnees_brutes": donnees_brutes, "client_id": "client_test"})
    assert reponse.status_code == 200, reponse.json()
    return reponse.json()["source_id"]


def test_generer_instance_deterministe_reconnait_un_json_canonique() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        donnees = (
            '{"taches": [{"id": "T1"}], "ressources": [{"id": "R1"}], '
            '"contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", '
            '"ressource": "R1", "duree": 10}]}'
        )
        source_id = _creer_source(client, donnees)

        reponse = client.post(f"/sources/{source_id}/generer-instance-deterministe")

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        assert corps["structure_contraintes"] == "compatibilite_ressource_tache"
        assert corps["instance_id"] in etat_test.instances
        instances_source = etat_test.lister_instances_pour_source(source_id)
        assert [i["instance_id"] for i in instances_source] == [corps["instance_id"]]
    finally:
        app.dependency_overrides.clear()


def test_generer_instance_deterministe_reconnait_un_csv_multi_blocs() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        donnees = (
            "--- taches.csv ---\nid\nT1\n\n"
            "--- ressources.csv ---\nid\nR1\n\n"
            "--- contraintes.csv ---\ntype,tache,ressource,duree_jours\n"
            "compatibilite_ressource_tache,T1,R1,10"
        )
        source_id = _creer_source(client, donnees)

        reponse = client.post(f"/sources/{source_id}/generer-instance-deterministe")

        assert reponse.status_code == 200, reponse.json()
        assert reponse.json()["structure_contraintes"] == "compatibilite_ressource_tache"
    finally:
        app.dependency_overrides.clear()


def test_generer_instance_deterministe_rejette_un_texte_non_structure() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        source_id = _creer_source(client, "precedence,CALAGE_PRESSE,IMPRESSION_RECTO,,,\n")

        reponse = client.post(f"/sources/{source_id}/generer-instance-deterministe")

        assert reponse.status_code == 422
        assert "conversion déterministe impossible" in reponse.json()["detail"]
        assert etat_test.instances == {}
    finally:
        app.dependency_overrides.clear()


def test_generer_instance_deterministe_relaie_le_rejet_du_garde_fou() -> None:
    """Structure identifiée (JSON canonique) mais instance invalide au sens du
    DSL (tâche sans compatibilité) — même garde-fou (§6.7) que tout autre
    canal, pas une erreur de structure."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        donnees = '{"taches": [{"id": "T1"}], "ressources": [{"id": "R1"}], "contraintes": []}'
        source_id = _creer_source(client, donnees)

        reponse = client.post(f"/sources/{source_id}/generer-instance-deterministe")

        assert reponse.status_code == 422
        assert etat_test.instances == {}
    finally:
        app.dependency_overrides.clear()


def test_generer_instance_deterministe_source_inconnue() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        reponse = client.post("/sources/id-inexistant/generer-instance-deterministe")
        assert reponse.status_code == 404
    finally:
        app.dependency_overrides.clear()
