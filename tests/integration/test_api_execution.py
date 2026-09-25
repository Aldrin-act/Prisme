"""Couche 1 (§6.1), Docker + PostgreSQL requis. `POST /execution/{instance_id}?horizon_gele_jours=...`
bout en bout (Phase 2, replanification à horizon glissant) : `client_isole` isole état et store —
même patron que `test_api_planifier.py`/`test_api_ingestion.py` — `image_sandbox` fournit un vrai
conteneur pour un solveur réellement enregistré et exécuté (`scripts/_solveur_minimal.py`, étendu
de façon additive avec `planning_precedent`/`horizon_gele_jours`).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import scripts._solveur_minimal as _module_solveur_minimal
from api.app import app
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from solver_store.registry import Registre
from validation_engine.cascade import VerdictCascade


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


def _enregistrer_solveur_minimal(registre: Registre, instance_id: str) -> None:
    """Enregistre `_solveur_minimal.py` (déjà étendu, Phase 2) — verdict vert « à blanc », comme
    `test_solveur_valide_stocke_puis_execute_en_sandbox` : ce test vérifie le câblage
    route → sandbox → état, pas la cascade elle-même (déjà couverte ailleurs). Un solveur ne
    sert que l'instance qui l'a fait générer — `instance_id` obligatoire, l'instance doit donc
    déjà exister (ingérée) avant cet appel."""
    code_source = Path(_module_solveur_minimal.__file__).read_text(encoding="utf-8")
    registre.enregistrer_solveur(
        code_source=code_source,
        structure_contraintes="compatibilite_ressource_tache",
        verdict_cascade=VerdictCascade(diagnostics=()),
        instance_id=instance_id,
        client_id="client_a",
    )


def test_horizon_gele_sans_historique_solve_normalement(
    image_sandbox: str, client_isole: tuple[TestClient, EtatAPI], registre_test: Registre
) -> None:
    """Première exécution de cette instance : `horizon_gele_jours>0` est demandé mais il n'existe
    encore aucun planning précédent — rien à figer, le solve se déroule normalement."""
    client, etat_test = client_isole
    instance_id = client.post("/ingestion/client_a", json=_payload_valide()).json()["instance_id"]
    _enregistrer_solveur_minimal(registre_test, instance_id)

    reponse = client.post(f"/execution/{instance_id}", params={"horizon_gele_jours": 5})

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["reussi"] is True, corps["erreur"]
    assert corps["horizon_gele_jours"] == 5
    assert corps["planning_precedent_utilise"] is False
    # Ancrage calendaire du Gantt (voir GanttChart côté frontend) — exposé directement à la
    # réponse de déclenchement, pas seulement via un GET /planning/{execution_id} séparé.
    assert corps["date_execution"] == etat_test.recuperer_date_execution(corps["execution_id"])


def test_horizon_gele_avec_historique_reutilise_le_dernier_planning_reussi(
    image_sandbox: str, client_isole: tuple[TestClient, EtatAPI], registre_test: Registre
) -> None:
    """Deuxième exécution de la même instance, après un premier succès : `horizon_gele_jours>0`
    trouve bien un planning précédent à transmettre — transparence humaine, jamais silencieux."""
    client, _ = client_isole
    instance_id = client.post("/ingestion/client_a", json=_payload_valide()).json()["instance_id"]
    _enregistrer_solveur_minimal(registre_test, instance_id)

    premiere = client.post(f"/execution/{instance_id}")
    assert premiere.json()["reussi"] is True, premiere.json()["erreur"]

    deuxieme = client.post(f"/execution/{instance_id}", params={"horizon_gele_jours": 5})

    assert deuxieme.status_code == 200
    corps = deuxieme.json()
    assert corps["reussi"] is True, corps["erreur"]
    assert corps["planning_precedent_utilise"] is True


def test_horizon_gele_negatif_est_rejete(client_isole: tuple[TestClient, EtatAPI]) -> None:
    client, _ = client_isole
    instance_id = client.post("/ingestion/client_a", json=_payload_valide()).json()["instance_id"]

    reponse = client.post(f"/execution/{instance_id}", params={"horizon_gele_jours": -1})

    assert reponse.status_code == 422


def test_scenario_sans_solveur_propre_execute_avec_celui_de_sa_base(
    image_sandbox: str, client_isole: tuple[TestClient, EtatAPI], registre_test: Registre
) -> None:
    """Un scénario (`POST .../scenarios`) n'a jamais son propre solveur enregistré — il doit
    pouvoir s'exécuter quand même, avec le solveur de l'instance de base dont il varie, tant que
    sa structure de contraintes et ses objectifs restent les mêmes (voir
    `api/etat.py::solveurs_pour_instance_ou_scenario_de_base`)."""
    client, etat_test = client_isole
    instance_id = client.post("/ingestion/client_a", json=_payload_valide()).json()["instance_id"]
    _enregistrer_solveur_minimal(registre_test, instance_id)

    # Même structure/objectifs que la base, seule la donnée (durée) change — un vrai « et si ».
    payload_variante = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 5}],
        "objectifs": [{"type": "minimiser_makespan"}],
    }
    scenario_id = client.post(f"/ingestion/{instance_id}/scenarios", json=payload_variante).json()["instance_id"]
    assert scenario_id != instance_id
    # Aucun solveur enregistré pour scenario_id lui-même.
    assert registre_test.rechercher_solveurs(client_id="client_a", instance_id=scenario_id) == []

    reponse = client.post(f"/execution/{scenario_id}")

    assert reponse.status_code == 200, reponse.json()
    corps = reponse.json()
    assert corps["reussi"] is True, corps["erreur"]
    # Le solveur exécuté est bien celui de la base, pas un solveur fantôme du scénario.
    solveur_base = registre_test.rechercher_solveurs(client_id="client_a", instance_id=instance_id)[0]
    _, _, resultat_execution = etat_test.recuperer_execution(corps["execution_id"])
    assert resultat_execution.reussi
    executions_scenario = [e for e in etat_test.executions.values() if e[1] == scenario_id]
    assert len(executions_scenario) == 1
    assert executions_scenario[0][0] == solveur_base.id


def test_scenario_et_base_sans_aucun_solveur_echoue_toujours_409(
    client_isole: tuple[TestClient, EtatAPI],
) -> None:
    """Sans solveur nulle part (ni sur le scénario, ni sur sa base), l'exécution du scénario
    échoue explicitement — le repli sur la base ne fabrique jamais un solveur qui n'existe pas."""
    client, _ = client_isole
    instance_id = client.post("/ingestion/client_a", json=_payload_valide()).json()["instance_id"]
    scenario_id = client.post(f"/ingestion/{instance_id}/scenarios", json=_payload_valide()).json()["instance_id"]

    reponse = client.post(f"/execution/{scenario_id}")

    assert reponse.status_code == 409
