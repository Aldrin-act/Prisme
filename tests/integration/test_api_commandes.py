"""Couche 1 (§6.1) : `POST/GET /ingestion/{instance_id}/commandes` et `GET
/ingestion/commandes/{commande_id}` (`api/routes/ingestion.py`) — une commande référence des
tâches déjà présentes dans l'instance et en dérive une `Echeance`
(`adapters/commande_derivation.py`, même mécanisme que `csv_import`/`json_import`), sans jamais
en créer — contrairement à l'ancienne explosion de gamme (fonctionnalité retirée). State en
mémoire (`EtatAPI`), aucun service externe requis.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from api.etat import EtatAPI, obtenir_etat
from dsl.schema import OperationPlanifiee, Planning
from sandbox.runner import ResultatExecution
from validation_engine.feasibility_checker import ResultatFaisabilite


def _payload_instance_minimale() -> dict:
    return {
        "taches": [{"id": "EXISTANT"}],
        "ressources": [{"id": "R1", "competences": ["soudure"]}],
        "contraintes": [
            {"type": "compatibilite_ressource_tache", "tache": "EXISTANT", "ressource": "R1", "duree": 1}
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def _creer_instance(client: TestClient) -> str:
    reponse = client.post("/ingestion/client_test", json=_payload_instance_minimale())
    assert reponse.status_code == 200, reponse.json()
    return reponse.json()["instance_id"]


def test_ajouter_commande_derive_une_echeance_pour_des_taches_existantes() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)

        reponse = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"], "date_limite": 10}
        )

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        assert corps["commande_id"].startswith("cmd-")

        instance = client.get(f"/ingestion/{instance_id}")
        assert instance.status_code == 200, instance.json()
        instance_json = instance.json()

        # La tâche n'est jamais recréée, juste référencée.
        assert [t["id"] for t in instance_json["taches"]] == ["EXISTANT"]
        assert any(
            c["type"] == "echeance" and c["tache"] == "EXISTANT" and c["echeance"] == 10
            for c in instance_json["contraintes"]
        )
    finally:
        app.dependency_overrides.clear()


def test_ajouter_commande_tache_inconnue_de_l_instance_renvoie_422() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)

        reponse = client.post(f"/ingestion/{instance_id}/commandes", json={"taches": ["FANTOME"]})

        assert reponse.status_code == 422
        assert "FANTOME" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_ajouter_commande_explicite_lemporte_sur_la_derivation() -> None:
    """Même règle que `adapters/commande_derivation.py` : une `Echeance` déjà explicite pour une
    tâche n'est jamais remplacée par celle dérivée de la commande."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        payload = _payload_instance_minimale()
        payload["contraintes"].append({"type": "echeance", "tache": "EXISTANT", "echeance": 3})
        reponse = client.post("/ingestion/client_test", json=payload)
        instance_id = reponse.json()["instance_id"]

        client.post(f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"], "date_limite": 10})

        instance_json = client.get(f"/ingestion/{instance_id}").json()
        echeances = [c for c in instance_json["contraintes"] if c["type"] == "echeance"]
        assert len(echeances) == 1
        assert echeances[0]["echeance"] == 3
    finally:
        app.dependency_overrides.clear()


def test_commande_persistee_consultable_avant_execution() -> None:
    """La commande survit à la réponse HTTP — sans exécution encore lancée, son statut est
    honnête : `planifiee=False`, pas confondu avec "en retard"."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)

        reponse = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"], "date_limite": 10}
        )
        assert reponse.status_code == 200, reponse.json()
        commande_id = reponse.json()["commande_id"]

        reponse = client.get(f"/ingestion/commandes/{commande_id}")

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        assert corps["commande_id"] == commande_id
        assert corps["instance_id"] == instance_id
        assert corps["date_limite"] == 10
        assert corps["taches"] == ["EXISTANT"]
        assert corps["planifiee"] is False
        assert corps["date_fin_prevue"] is None
        assert corps["en_retard"] is None
        assert corps["taches_manquantes"] == ["EXISTANT"]
    finally:
        app.dependency_overrides.clear()


def test_commande_planifiee_dans_les_temps_apres_execution_reussie() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)

        reponse = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"], "date_limite": 10}
        )
        commande_id = reponse.json()["commande_id"]

        # Exécution simulée directement via EtatAPI — aucun solveur réel dans ce test (Couche 1).
        resultat = ResultatExecution(
            planning=Planning(operations=[OperationPlanifiee(tache="EXISTANT", ressource="R1", debut=0)]),
            verdict_faisabilite=ResultatFaisabilite(violations=()),
            erreur=None,
        )
        etat_test.enregistrer_execution("solveur-factice", instance_id, resultat)

        reponse = client.get(f"/ingestion/commandes/{commande_id}")

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        assert corps["planifiee"] is True
        assert corps["date_fin_prevue"] == 1  # duree=1 de la compatibilité EXISTANT|R1
        assert corps["en_retard"] is False
        assert corps["taches_manquantes"] == []
    finally:
        app.dependency_overrides.clear()


def test_commande_en_retard_apres_execution() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)

        reponse = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"], "date_limite": 0}
        )
        commande_id = reponse.json()["commande_id"]

        resultat = ResultatExecution(
            planning=Planning(operations=[OperationPlanifiee(tache="EXISTANT", ressource="R1", debut=0)]),
            verdict_faisabilite=ResultatFaisabilite(violations=()),
            erreur=None,
        )
        etat_test.enregistrer_execution("solveur-factice", instance_id, resultat)

        reponse = client.get(f"/ingestion/commandes/{commande_id}")

        assert reponse.status_code == 200, reponse.json()
        assert reponse.json()["en_retard"] is True
    finally:
        app.dependency_overrides.clear()


def test_commande_sans_date_limite_reste_pure_tracabilite() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)

        reponse = client.post(f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"]})

        assert reponse.status_code == 200, reponse.json()
        instance_json = client.get(f"/ingestion/{instance_id}").json()
        assert not [c for c in instance_json["contraintes"] if c["type"] == "echeance"]
    finally:
        app.dependency_overrides.clear()


def test_obtenir_commande_inconnue_renvoie_404() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        reponse = client.get("/ingestion/commandes/id-inexistant")

        assert reponse.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_lister_commandes_instance_renvoie_leur_statut() -> None:
    """`GET /{instance_id}/commandes` — même statut recalculé à la volée que `GET
    /commandes/{commande_id}`, pour toutes les commandes de l'atelier en un seul appel."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)

        reponse = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"], "date_limite": 10}
        )
        commande_id = reponse.json()["commande_id"]

        resultat = ResultatExecution(
            planning=Planning(operations=[OperationPlanifiee(tache="EXISTANT", ressource="R1", debut=0)]),
            verdict_faisabilite=ResultatFaisabilite(violations=()),
            erreur=None,
        )
        etat_test.enregistrer_execution("solveur-factice", instance_id, resultat)

        reponse = client.get(f"/ingestion/{instance_id}/commandes")

        assert reponse.status_code == 200, reponse.json()
        commandes = reponse.json()
        assert len(commandes) == 1
        assert commandes[0]["commande_id"] == commande_id
        assert commandes[0]["planifiee"] is True
        assert commandes[0]["en_retard"] is False
    finally:
        app.dependency_overrides.clear()


def test_lister_commandes_instance_vide_sans_commande() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)

        reponse = client.get(f"/ingestion/{instance_id}/commandes")

        assert reponse.status_code == 200, reponse.json()
        assert reponse.json() == []
    finally:
        app.dependency_overrides.clear()


def test_lister_commandes_instance_inconnue_renvoie_404() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        reponse = client.get("/ingestion/id-inexistant/commandes")

        assert reponse.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_supprimer_instance_supprime_ses_commandes() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        reponse = client.post(f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"]})
        commande_id = reponse.json()["commande_id"]

        assert client.delete(f"/ingestion/{instance_id}").status_code == 204

        assert client.get(f"/ingestion/commandes/{commande_id}").status_code == 404
    finally:
        app.dependency_overrides.clear()
