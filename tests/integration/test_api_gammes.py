"""Couche 1 (§6.1) : CRUD `GammeProduit` (`api/routes/gammes.py`) et explosion par commande
(`POST /ingestion/{instance_id}/commandes`, `api/routes/ingestion.py`) — state en mémoire
(`EtatAPI`), aucun service externe requis."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from api.etat import EtapeGamme, EtatAPI, obtenir_etat


def _payload_instance_minimale() -> dict:
    return {
        "taches": [{"id": "EXISTANT"}],
        "ressources": [{"id": "R1", "competences": ["soudure"]}],
        "contraintes": [
            {"type": "compatibilite_ressource_tache", "tache": "EXISTANT", "ressource": "R1", "duree": 1}
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def _creer_instance(
    client: TestClient, *, nom_projet: str | None = None, secteur_activite: str | None = None
) -> str:
    reponse = client.post(
        "/ingestion/client_test",
        json=_payload_instance_minimale(),
        params={"nom_projet": nom_projet, "secteur_activite": secteur_activite},
    )
    assert reponse.status_code == 200, reponse.json()
    return reponse.json()["instance_id"]


def _creer_gamme(client: TestClient, **overrides: object) -> str:
    corps = {
        "produit": "Vanne V12",
        "client_id": "client_test",
        "etapes": [{"id": "soudure", "competences": ["soudure"], "duree_nominale": 3}],
        **overrides,
    }
    reponse = client.post("/gammes", json=corps)
    assert reponse.status_code == 200, reponse.json()
    return reponse.json()["gamme_id"]


def test_crud_gamme() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        gamme_id = _creer_gamme(client, nom="Gamme vanne")

        reponse = client.get(f"/gammes/{gamme_id}")
        assert reponse.status_code == 200, reponse.json()
        assert reponse.json()["produit"] == "Vanne V12"
        assert reponse.json()["nom"] == "Gamme vanne"

        reponse = client.get("/gammes")
        assert [g["gamme_id"] for g in reponse.json()] == [gamme_id]

        reponse = client.put(
            f"/gammes/{gamme_id}",
            json={"produit": "Vanne V13", "etapes": [{"id": "soudure", "competences": ["soudure"]}]},
        )
        assert reponse.status_code == 200, reponse.json()
        assert reponse.json()["produit"] == "Vanne V13"

        reponse = client.delete(f"/gammes/{gamme_id}")
        assert reponse.status_code == 204

        assert client.get(f"/gammes/{gamme_id}").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_ajouter_commande_explose_la_gamme_dans_l_instance() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client, nom_projet="Atelier X", secteur_activite="imprimerie")
        gamme_id = _creer_gamme(client)

        reponse = client.post(
            f"/ingestion/{instance_id}/commandes",
            json={"gamme_id": gamme_id, "quantite": 5, "date_limite": 10},
        )

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        commande_id = corps["commande_id"]
        assert corps["avertissements"] == []

        instance = client.get(f"/ingestion/{instance_id}")
        assert instance.status_code == 200, instance.json()
        instance_json = instance.json()

        tache_id = f"{commande_id}_soudure"
        assert any(
            t["id"] == tache_id and t["produit"] == "Vanne V12" and t["quantite"] == 5
            for t in instance_json["taches"]
        )
        assert any(
            c["type"] == "compatibilite_ressource_tache" and c["tache"] == tache_id and c["duree"] == 3
            for c in instance_json["contraintes"]
        )
        assert any(
            c["type"] == "echeance" and c["tache"] == tache_id and c["echeance"] == 10
            for c in instance_json["contraintes"]
        )
        # nom_projet/secteur_activite préservés — même piège que PUT /{instance_id}
        # (modifier_instance les écrase sinon renvoyés explicitement).
        assert instance_json["nom_projet"] == "Atelier X"
        assert instance_json["secteur_activite"] == "imprimerie"
        # La tâche déjà présente avant la commande reste intacte.
        assert any(t["id"] == "EXISTANT" for t in instance_json["taches"])
    finally:
        app.dependency_overrides.clear()


def test_ajouter_commande_gamme_d_un_autre_client_refusee() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        gamme_id_autre_client = etat_test.enregistrer_gamme(
            "autre_client", "P", (EtapeGamme(id="x", competences=("x",), duree_nominale=1),)
        )

        reponse = client.post(f"/ingestion/{instance_id}/commandes", json={"gamme_id": gamme_id_autre_client})

        assert reponse.status_code == 400
        assert "n'appartient pas" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_ajouter_commande_competence_non_couverte_renvoie_422() -> None:
    """Aucune ressource de l'instance ne possède "fraisage" (seule "soudure" est déclarée sur
    R1) — l'estimateur ML (s'il est disponible dans l'environnement de test) ne peut rien
    estimer non plus dans ce cas : `completer_durees_par_estimation` ne comble une durée que si
    au moins une ressource couvre déjà la compétence exigée."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        gamme_id = _creer_gamme(client, etapes=[{"id": "fraisage", "competences": ["fraisage"]}])

        reponse = client.post(f"/ingestion/{instance_id}/commandes", json={"gamme_id": gamme_id})

        assert reponse.status_code == 422
        assert "durée estimée manquante" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()
