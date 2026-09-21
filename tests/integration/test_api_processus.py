"""Couche 1 (§6.1) : processus unique d'un atelier (`GET/PUT /ingestion/{instance_id}/processus`)
et création de commande qui l'éclate (`POST /ingestion/{instance_id}/commandes` sans `taches`).
État en mémoire (`EtatAPI`), aucun service externe requis."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.etat import EtatAPI, obtenir_etat
from api.routes.auth import obtenir_utilisateur_courant

PROCESSUS = {
    "etapes": [
        {"id": "TOURNAGE", "nom": "Tournage", "competences": ["TOUR"], "duree_par_piece": 2},
        {
            "id": "FRAISAGE",
            "nom": "Fraisage",
            "competences": ["FRAISE"],
            "duree_par_piece": 1,
            "predecesseurs": ["TOURNAGE"],
        },
    ]
}


@pytest.fixture
def etat_test() -> Iterator[EtatAPI]:
    etat = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat
    yield etat
    app.dependency_overrides.clear()


def _creer_atelier(client: TestClient, client_id: str = "client_test") -> str:
    reponse = client.post(
        f"/ingestion/{client_id}",
        json={
            "taches": [{"id": "EXISTANTE"}],
            "ressources": [
                {"id": "NADIA", "competences": ["TOUR", "FRAISE"]},
                {"id": "JULIEN", "competences": ["TOUR"]},
            ],
            "contraintes": [
                {"type": "compatibilite_ressource_tache", "tache": "EXISTANTE", "ressource": "JULIEN", "duree": 1}
            ],
            "objectifs": [{"type": "minimiser_makespan"}],
        },
    )
    assert reponse.status_code == 200, reponse.json()
    return reponse.json()["instance_id"]


def test_atelier_neuf_sans_processus(etat_test: EtatAPI) -> None:
    client = TestClient(app)
    instance_id = _creer_atelier(client)

    reponse = client.get(f"/ingestion/{instance_id}/processus")

    assert reponse.status_code == 200
    assert reponse.json() == {"etapes": []}


def test_definir_puis_relire_le_processus(etat_test: EtatAPI) -> None:
    client = TestClient(app)
    instance_id = _creer_atelier(client)

    ecrit = client.put(f"/ingestion/{instance_id}/processus", json=PROCESSUS)
    relu = client.get(f"/ingestion/{instance_id}/processus")

    assert ecrit.status_code == 200, ecrit.json()
    assert relu.json()["etapes"][1] == {
        "id": "FRAISAGE",
        "nom": "Fraisage",
        "competences": ["FRAISE"],
        "predecesseurs": ["TOURNAGE"],
        "duree_par_piece": 1,
    }


def test_processus_avec_cycle_refuse(etat_test: EtatAPI) -> None:
    client = TestClient(app)
    instance_id = _creer_atelier(client)
    cycle = {
        "etapes": [
            {"id": "A", "competences": ["TOUR"], "duree_par_piece": 1, "predecesseurs": ["B"]},
            {"id": "B", "competences": ["TOUR"], "duree_par_piece": 1, "predecesseurs": ["A"]},
        ]
    }

    reponse = client.put(f"/ingestion/{instance_id}/processus", json=cycle)

    assert reponse.status_code == 422
    assert "cycle" in reponse.json()["detail"]
    assert client.get(f"/ingestion/{instance_id}/processus").json() == {"etapes": []}


def test_processus_sans_duree_refuse(etat_test: EtatAPI) -> None:
    client = TestClient(app)
    instance_id = _creer_atelier(client)

    reponse = client.put(
        f"/ingestion/{instance_id}/processus", json={"etapes": [{"id": "A", "competences": ["TOUR"]}]}
    )

    assert reponse.status_code == 422


def test_commande_sans_processus_refusee(etat_test: EtatAPI) -> None:
    client = TestClient(app)
    instance_id = _creer_atelier(client)

    reponse = client.post(f"/ingestion/{instance_id}/commandes", json={"quantite": 2, "date_limite": 20})

    assert reponse.status_code == 422
    assert "processus" in reponse.json()["detail"]


def test_commande_eclate_le_processus_avec_duree_fois_quantite(etat_test: EtatAPI) -> None:
    client = TestClient(app)
    instance_id = _creer_atelier(client)
    client.put(f"/ingestion/{instance_id}/processus", json=PROCESSUS)

    reponse = client.post(
        f"/ingestion/{instance_id}/commandes", json={"quantite": 3, "date_limite": 20, "numero": "P1"}
    )

    assert reponse.status_code == 200, reponse.json()
    corps = reponse.json()
    commande_id = corps["commande_id"]
    assert corps["taches"] == [f"{commande_id}_TOURNAGE", f"{commande_id}_FRAISAGE"]

    _, instance = etat_test.recuperer_instance(instance_id)
    durees = {
        (c.tache, c.ressource): c.duree
        for c in instance.contraintes
        if c.type == "compatibilite_ressource_tache" and c.tache.startswith(commande_id)
    }
    assert durees == {
        (f"{commande_id}_TOURNAGE", "NADIA"): 6,
        (f"{commande_id}_TOURNAGE", "JULIEN"): 6,
        (f"{commande_id}_FRAISAGE", "NADIA"): 3,
    }
    echeances = {c.tache: c.echeance for c in instance.contraintes if c.type == "echeance"}
    assert echeances == {f"{commande_id}_TOURNAGE": 20, f"{commande_id}_FRAISAGE": 20}

    commande = client.get(f"/ingestion/commandes/{commande_id}").json()
    assert commande["quantite"] == 3
    assert commande["numero"] == "P1"


def test_commande_sur_taches_existantes_reste_possible(etat_test: EtatAPI) -> None:
    """Le chemin « tâches déjà dans l'atelier » sert l'import de données existantes et l'API : il
    reste valable, même quand un processus est défini, et ne crée aucune tâche."""
    client = TestClient(app)
    instance_id = _creer_atelier(client)
    client.put(f"/ingestion/{instance_id}/processus", json=PROCESSUS)

    reponse = client.post(f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANTE"], "date_limite": 5})

    assert reponse.status_code == 200, reponse.json()
    assert reponse.json()["taches"] == ["EXISTANTE"]
    _, instance = etat_test.recuperer_instance(instance_id)
    assert [t.id for t in instance.taches] == ["EXISTANTE"]
    assert client.get(f"/ingestion/commandes/{reponse.json()['commande_id']}").json()["quantite"] is None


def test_processus_modifie_ne_reecrit_pas_les_commandes_passees(etat_test: EtatAPI) -> None:
    client = TestClient(app)
    instance_id = _creer_atelier(client)
    client.put(f"/ingestion/{instance_id}/processus", json=PROCESSUS)
    premiere = client.post(f"/ingestion/{instance_id}/commandes", json={"quantite": 1}).json()["commande_id"]

    client.put(
        f"/ingestion/{instance_id}/processus",
        json={"etapes": [{"id": "CONTROLE", "competences": ["TOUR"], "duree_par_piece": 1}]},
    )
    seconde = client.post(f"/ingestion/{instance_id}/commandes", json={"quantite": 1}).json()

    _, instance = etat_test.recuperer_instance(instance_id)
    ids = {t.id for t in instance.taches}
    assert {f"{premiere}_TOURNAGE", f"{premiere}_FRAISAGE"} <= ids
    assert seconde["taches"] == [f"{seconde['commande_id']}_CONTROLE"]


def test_processus_atelier_inconnu_404(etat_test: EtatAPI) -> None:
    client = TestClient(app)

    assert client.get("/ingestion/inexistant/processus").status_code == 404
    assert client.put("/ingestion/inexistant/processus", json=PROCESSUS).status_code == 404


def test_processus_refuse_un_client_etranger(etat_test: EtatAPI) -> None:
    client = TestClient(app)
    instance_id = _creer_atelier(client, client_id="client_a")
    app.dependency_overrides[obtenir_utilisateur_courant] = lambda: {
        "id": "u1",
        "email": "op@client.test",
        "nom": "Op",
        "prenom": "Erateur",
        "role": "operateur",
        "client_id": "client_b",
        "date_creation": "2024-01-01T00:00:00+00:00",
        "dernier_acces": None,
    }

    assert client.put(f"/ingestion/{instance_id}/processus", json=PROCESSUS).status_code == 403
    assert client.get(f"/ingestion/{instance_id}/processus").status_code == 403


def test_supprimer_l_atelier_supprime_son_processus(etat_test: EtatAPI) -> None:
    client = TestClient(app)
    instance_id = _creer_atelier(client)
    client.put(f"/ingestion/{instance_id}/processus", json=PROCESSUS)

    client.delete(f"/ingestion/{instance_id}")

    assert instance_id not in etat_test.processus
