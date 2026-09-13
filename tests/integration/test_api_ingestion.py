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
from dsl.schema import OperationPlanifiee, Planning
from sandbox.runner import ResultatExecution
from solver_store.registry import Registre
from validation_engine.feasibility_checker import ResultatFaisabilite


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


def test_ingestion_accepte_unite_temps_heures(client_isole: tuple[TestClient, EtatAPI]) -> None:
    """Chemin manuel : `unite_temps` est un champ `InstanceTRCO` comme un autre (voir
    `dsl/schema/instance.py`) — un payload brut le déclarant est accepté sans aucun changement
    de route, contrairement au JSON import (`InstanceBrute`, `extra="forbid"`)."""
    client, etat_test = client_isole
    payload = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 100}],
        "objectifs": [{"type": "minimiser_makespan"}],
        "unite_temps": "heures",
    }

    reponse = client.post("/ingestion/client_a", json=payload)

    assert reponse.status_code == 200, reponse.json()
    instance_id = reponse.json()["instance_id"]
    _, instance = etat_test.recuperer_instance(instance_id)
    assert instance.unite_temps == "heures"
    assert etat_test.recuperer_unite_duree(instance_id) == "heures"


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


_PAYLOAD_MINIMAL = {
    "taches": [{"id": "T1"}],
    "ressources": [{"id": "R1"}],
    "contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}],
    "objectifs": [{"type": "minimiser_makespan"}],
}


# --- Modification en place (PUT /ingestion/{instance_id}) -----------------

_PAYLOAD_MODIFIE = {
    "taches": [{"id": "T1"}, {"id": "T2"}],
    "ressources": [{"id": "R1"}],
    "contraintes": [
        {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 5},
        {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 5},
    ],
    "objectifs": [{"type": "minimiser_makespan"}],
}


def test_modifier_instance_remplace_le_contenu_meme_instance_id(
    client_isole: tuple[TestClient, EtatAPI],
) -> None:
    client, _ = client_isole
    instance_id = client.post("/ingestion/client_a", json=_PAYLOAD_MINIMAL).json()["instance_id"]

    reponse = client.put(f"/ingestion/{instance_id}", json=_PAYLOAD_MODIFIE)

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["instance_id"] == instance_id
    assert [t["id"] for t in corps["taches"]] == ["T1", "T2"]

    relue = client.get(f"/ingestion/{instance_id}").json()
    assert [t["id"] for t in relue["taches"]] == ["T1", "T2"]


def test_modifier_instance_inconnue_404(client_isole: tuple[TestClient, EtatAPI]) -> None:
    client, _ = client_isole

    reponse = client.put("/ingestion/id-inexistant", json=_PAYLOAD_MODIFIE)

    assert reponse.status_code == 404


def test_modifier_instance_payload_invalide_422(client_isole: tuple[TestClient, EtatAPI]) -> None:
    client, _ = client_isole
    instance_id = client.post("/ingestion/client_a", json=_PAYLOAD_MINIMAL).json()["instance_id"]

    payload_invalide = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [],  # T1 sans compatibilité ressource-tâche — rejeté par le garde-fou §6.7
        "objectifs": [{"type": "minimiser_makespan"}],
    }
    reponse = client.put(f"/ingestion/{instance_id}", json=payload_invalide)

    assert reponse.status_code == 422


# --- Scénarios comparatifs (what-if) --------------------------------------


def test_creer_scenario_ajoute_une_instance_variante(client_isole: tuple[TestClient, EtatAPI]) -> None:
    client, etat_test = client_isole
    instance_id = client.post("/ingestion/client_a", json=_PAYLOAD_MINIMAL).json()["instance_id"]

    reponse = client.post(f"/ingestion/{instance_id}/scenarios", json=_PAYLOAD_MODIFIE)

    assert reponse.status_code == 200
    scenario_id = reponse.json()["instance_id"]
    assert scenario_id != instance_id
    assert scenario_id in etat_test.instances
    assert etat_test.groupes_scenario[scenario_id] == instance_id


def test_creer_scenario_peut_ajouter_une_ressource(client_isole: tuple[TestClient, EtatAPI]) -> None:
    """Un scénario peut ajouter une ressource à celles de l'instance de base (ex. « et si on
    achetait une nouvelle machine ? ») — seul en retirer une déjà présente est rejeté, voir
    test_creer_scenario_retire_une_ressource_de_la_base_422."""
    client, etat_test = client_isole
    instance_id = client.post("/ingestion/client_a", json=_PAYLOAD_MINIMAL).json()["instance_id"]

    payload_avec_nouvelle_ressource = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}, {"id": "R2"}],
        "contraintes": [
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R2", "duree": 10},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }
    reponse = client.post(f"/ingestion/{instance_id}/scenarios", json=payload_avec_nouvelle_ressource)

    assert reponse.status_code == 200, reponse.json()
    scenario_id = reponse.json()["instance_id"]
    assert scenario_id in etat_test.instances


def test_creer_scenario_retire_une_ressource_de_la_base_422(client_isole: tuple[TestClient, EtatAPI]) -> None:
    """Une instance représente un atelier — un scénario compare des variantes du MÊME atelier,
    jamais deux ateliers différents : retirer une ressource de l'instance de base est rejeté."""
    client, _ = client_isole
    instance_id = client.post("/ingestion/client_a", json=_PAYLOAD_MINIMAL).json()["instance_id"]

    payload_sans_r1 = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R2"}],
        "contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R2", "duree": 10}],
        "objectifs": [{"type": "minimiser_makespan"}],
    }
    reponse = client.post(f"/ingestion/{instance_id}/scenarios", json=payload_sans_r1)

    assert reponse.status_code == 422
    assert "R1" in reponse.json()["detail"]


def test_creer_scenario_instance_de_base_inconnue_404(client_isole: tuple[TestClient, EtatAPI]) -> None:
    client, _ = client_isole
    reponse = client.post("/ingestion/id-inexistant/scenarios", json=_PAYLOAD_MODIFIE)
    assert reponse.status_code == 404


def test_creer_scenario_payload_invalide_422(client_isole: tuple[TestClient, EtatAPI]) -> None:
    client, _ = client_isole
    instance_id = client.post("/ingestion/client_a", json=_PAYLOAD_MINIMAL).json()["instance_id"]

    payload_invalide = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [],
        "objectifs": [{"type": "minimiser_makespan"}],
    }
    reponse = client.post(f"/ingestion/{instance_id}/scenarios", json=payload_invalide)

    assert reponse.status_code == 422


def test_comparer_scenarios_sans_execution_donne_des_metriques_nulles(
    client_isole: tuple[TestClient, EtatAPI],
) -> None:
    client, _ = client_isole
    instance_id = client.post("/ingestion/client_a", json=_PAYLOAD_MINIMAL).json()["instance_id"]
    scenario_id = client.post(f"/ingestion/{instance_id}/scenarios", json=_PAYLOAD_MODIFIE).json()["instance_id"]

    reponse = client.get(f"/ingestion/{instance_id}/scenarios/comparaison")

    assert reponse.status_code == 200
    corps = reponse.json()
    scenarios_par_id = {s["instance_id"]: s for s in corps["scenarios"]}
    assert set(scenarios_par_id) == {instance_id, scenario_id}
    assert all(s["metriques"] is None for s in scenarios_par_id.values())
    assert scenarios_par_id[instance_id]["est_instance_de_base"] is True
    assert scenarios_par_id[scenario_id]["est_instance_de_base"] is False


def test_comparer_scenarios_depuis_une_variante_designe_quand_meme_la_vraie_base(
    client_isole: tuple[TestClient, EtatAPI],
) -> None:
    """Consulter la comparaison depuis l'`instance_id` d'un scénario (pas depuis l'instance
    d'origine) doit quand même désigner l'instance d'origine comme base — jamais le scénario
    consulté, même si c'est lui que l'appelant a passé dans l'URL."""
    client, _ = client_isole
    instance_id = client.post("/ingestion/client_a", json=_PAYLOAD_MINIMAL).json()["instance_id"]
    scenario_id = client.post(f"/ingestion/{instance_id}/scenarios", json=_PAYLOAD_MODIFIE).json()["instance_id"]

    reponse = client.get(f"/ingestion/{scenario_id}/scenarios/comparaison")

    assert reponse.status_code == 200
    scenarios_par_id = {s["instance_id"]: s for s in reponse.json()["scenarios"]}
    assert scenarios_par_id[instance_id]["est_instance_de_base"] is True
    assert scenarios_par_id[scenario_id]["est_instance_de_base"] is False


def test_comparer_scenarios_instance_inconnue_404(client_isole: tuple[TestClient, EtatAPI]) -> None:
    client, _ = client_isole
    reponse = client.get("/ingestion/id-inexistant/scenarios/comparaison")
    assert reponse.status_code == 404


def test_instance_sans_scenario_se_compare_a_elle_meme(client_isole: tuple[TestClient, EtatAPI]) -> None:
    """Une instance qui n'a jamais eu de variante créée reste un groupe d'un
    seul membre — elle-même — jamais une erreur."""
    client, _ = client_isole
    instance_id = client.post("/ingestion/client_a", json=_PAYLOAD_MINIMAL).json()["instance_id"]

    reponse = client.get(f"/ingestion/{instance_id}/scenarios/comparaison")

    assert reponse.status_code == 200
    corps = reponse.json()
    assert [s["instance_id"] for s in corps["scenarios"]] == [instance_id]


def test_comparer_scenarios_calcule_les_metriques_de_la_derniere_execution(
    client_isole: tuple[TestClient, EtatAPI],
) -> None:
    """Injecte directement un résultat d'exécution (pas de vrai sandbox ici,
    couvert par les tests bout-en-bout Docker ailleurs) pour vérifier que la
    comparaison calcule bien les métriques dessus, sans jamais ré-exécuter."""
    client, etat_test = client_isole
    instance_id = client.post("/ingestion/client_a", json=_PAYLOAD_MINIMAL).json()["instance_id"]

    planning = Planning(operations=[OperationPlanifiee(tache="T1", ressource="R1", debut=0)])
    resultat = ResultatExecution(
        planning=planning, verdict_faisabilite=ResultatFaisabilite(violations=()), erreur=None
    )
    etat_test.enregistrer_execution("solveur-factice", instance_id, resultat)

    reponse = client.get(f"/ingestion/{instance_id}/scenarios/comparaison")

    assert reponse.status_code == 200
    scenario = reponse.json()["scenarios"][0]
    assert scenario["metriques"] == {
        "makespan": 10,
        "taux_utilisation_par_ressource": {"R1": 100.0},
        "taches_en_retard": [],
    }
    assert scenario["execution_id"] is not None
