"""Couche 1 (§6.1), Docker requis. Critère de validation de PH10-T3 en
conditions réelles : `construire_solveur_sandbox` enveloppe le solveur
réellement enregistré dans le store, et `/diagnostics/{execution_id}` rejoue
la boucle code→données→spécification DSL en direct, via le sandbox — pas
seulement avec des fonctions Python en mémoire (voir
`tests/unit/test_attribution.py` et `tests/integration/test_attribution_solveur_sain.py`
pour la logique de `diagnostiquer` elle-même, déjà couverte sans passer par
l'API)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api.app import app
from api.dependencies import obtenir_registre
from api.etat import EtatAPI, obtenir_etat
from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, MinimiserMakespan, Precedence, Ressource, Tache
from scripts.enregistrer_solveur_reference import enregistrer
from solver_store.registry import Registre


def test_diagnostic_via_l_api_ne_trouve_aucune_cause_pour_un_solveur_sain(
    image_sandbox: str, registre_test: Registre
) -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[obtenir_registre] = lambda: registre_test

    try:
        enregistrer(registre_test, client_id="client_test")
        client = TestClient(app)

        instance = InstanceTRCO(
            taches=[Tache(id="T1"), Tache(id="T2")],
            ressources=[Ressource(id="R1")],
            contraintes=[
                Precedence(avant="T1", apres="T2"),
                CompatibiliteRessourceTache(tache="T1", ressource="R1", duree=10),
                CompatibiliteRessourceTache(tache="T2", ressource="R1", duree=5),
            ],
            objectifs=[MinimiserMakespan()],
        )
        instance_id = client.post("/ingestion/client_test", json=instance.model_dump(mode="json")).json()[
            "instance_id"
        ]
        reponse = client.post(f"/execution/{instance_id}", params={"client_id": "client_test"})
        assert reponse.status_code == 200, reponse.json()
        execution_id = reponse.json()["execution_id"]

        # Le solveur de référence est réellement sain : rejoué en direct via le
        # sandbox sur tout le banc + tous les cas de référence, aucune cause
        # ne doit être trouvée par élimination.
        reponse = client.post(
            f"/diagnostics/{execution_id}",
            json={"motif_declenchement": "signalement humain : test de la boucle diagnostique en direct"},
        )
        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        assert corps["cause"] == "aucune"
        assert corps["details"] == []
        assert corps["humain_decide"] is True
    finally:
        app.dependency_overrides.clear()


def test_diagnostic_sur_execution_inconnue_rejete() -> None:
    client = TestClient(app)
    reponse = client.post("/diagnostics/inconnue", json={"motif_declenchement": "test"})
    assert reponse.status_code == 404
