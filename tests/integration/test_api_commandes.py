"""Couche 1 (§6.1) : `POST/GET /ingestion/{instance_id}/commandes` et `GET
/ingestion/commandes/{commande_id}` (`api/routes/ingestion.py`) — une commande référence des
tâches déjà présentes dans l'instance et en dérive une `Echeance`
(`adapters/commande_derivation.py`, même mécanisme que `csv_import`/`json_import`), sans jamais
en créer — contrairement à l'ancienne explosion de gamme (fonctionnalité retirée). State en
mémoire (`EtatAPI`), aucun service externe requis.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.etat import EtatAPI, obtenir_etat
from api.routes.auth import obtenir_utilisateur_courant
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


def _creer_instance(client: TestClient, client_id: str = "client_test") -> str:
    reponse = client.post(f"/ingestion/{client_id}", json=_payload_instance_minimale())
    assert reponse.status_code == 200, reponse.json()
    return reponse.json()["instance_id"]


def _utilisateur_scope(client_id: str, role: str = "operateur") -> dict:
    """Même patron que `test_api_sources.py` : écrase le fixture admin par défaut
    (`conftest.py::_utilisateur_authentifie_par_defaut`) pour vérifier un filtrage par client_id réel."""
    return {
        "id": "u1",
        "email": "op@client.test",
        "nom": "Op",
        "prenom": "Erateur",
        "role": role,
        "client_id": client_id,
        "date_creation": "2024-01-01T00:00:00+00:00",
        "dernier_acces": None,
    }


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


def _payload_deux_taches_multi_ressources() -> dict:
    return {
        "unite_temps": "heures",
        "taches": [{"id": "T1"}, {"id": "T2"}],
        "ressources": [{"id": "R1"}, {"id": "R2"}],
        "contraintes": [
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 48},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R2", "duree": 60},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 8},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def test_ajouter_commande_applique_une_duree_propre_a_chaque_tache() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        creation = client.post("/ingestion/client_test", json=_payload_deux_taches_multi_ressources())
        assert creation.status_code == 200, creation.json()
        instance_id = creation.json()["instance_id"]

        reponse = client.post(
            f"/ingestion/{instance_id}/commandes",
            json={"taches": ["T1", "T2"], "durees_taches": {"T1": 25, "T2": 12}, "date_limite": 100},
        )
        assert reponse.status_code == 200, reponse.json()

        contraintes = client.get(f"/ingestion/{instance_id}").json()["contraintes"]
        durees = {
            (c["tache"], c["ressource"]): c["duree"]
            for c in contraintes
            if c["type"] == "compatibilite_ressource_tache"
        }
        # T1 prend 25 sur ses deux ressources, T2 prend 12 : chaque tâche a sa propre durée.
        assert durees == {("T1", "R1"): 25, ("T1", "R2"): 25, ("T2", "R1"): 12}
    finally:
        app.dependency_overrides.clear()


def test_ajouter_commande_sans_duree_garde_les_durees_de_l_atelier() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        creation = client.post("/ingestion/client_test", json=_payload_deux_taches_multi_ressources())
        instance_id = creation.json()["instance_id"]

        reponse = client.post(
            f"/ingestion/{instance_id}/commandes",
            json={"taches": ["T1", "T2"], "durees_taches": {"T2": 12}, "date_limite": 100},
        )
        assert reponse.status_code == 200, reponse.json()

        contraintes = client.get(f"/ingestion/{instance_id}").json()["contraintes"]
        durees_t1 = sorted(
            c["duree"] for c in contraintes if c["type"] == "compatibilite_ressource_tache" and c["tache"] == "T1"
        )
        assert durees_t1 == [48, 60]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("durees", "extrait_erreur"),
    [
        ({"T2": 5}, "absentes de la commande"),
        ({"T1": 0}, "durée invalide"),
    ],
)
def test_ajouter_commande_durees_taches_invalides_renvoient_422(durees: dict, extrait_erreur: str) -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        creation = client.post("/ingestion/client_test", json=_payload_deux_taches_multi_ressources())
        instance_id = creation.json()["instance_id"]

        reponse = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["T1"], "durees_taches": durees}
        )

        assert reponse.status_code == 422
        assert extrait_erreur in reponse.json()["detail"]
        assert etat_test.lister_commandes(instance_id) == []
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
        # Rien à ancrer calendairement sans exécution réussie — voir
        # EtatAPI.date_derniere_execution_reussie.
        assert corps["date_execution"] is None
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
        # Ancrage calendaire de l'exécution qui a produit ce statut — voir
        # EtatAPI.date_derniere_execution_reussie.
        assert corps["date_execution"] is not None
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
        assert commandes[0]["date_execution"] is not None
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


# --- GET /ingestion/commandes (liste globale, tous ateliers) ----------------


def test_lister_toutes_commandes_agrege_plusieurs_ateliers() -> None:
    """Une commande par instance, deux instances distinctes — les deux ressortent,
    chacune avec le bon instance_id/client_id (l'« atelier associé »)."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_a = _creer_instance(client, client_id="client_a")
        instance_b = _creer_instance(client, client_id="client_b")
        cmd_a = client.post(
            f"/ingestion/{instance_a}/commandes", json={"taches": ["EXISTANT"], "date_limite": 5}
        ).json()["commande_id"]
        cmd_b = client.post(
            f"/ingestion/{instance_b}/commandes", json={"taches": ["EXISTANT"], "date_limite": 10}
        ).json()["commande_id"]

        reponse = client.get("/ingestion/commandes")

        assert reponse.status_code == 200, reponse.json()
        par_id = {c["commande_id"]: c for c in reponse.json()}
        assert set(par_id) == {cmd_a, cmd_b}
        assert par_id[cmd_a]["instance_id"] == instance_a
        assert par_id[cmd_a]["client_id"] == "client_a"
        assert par_id[cmd_b]["instance_id"] == instance_b
        assert par_id[cmd_b]["client_id"] == "client_b"
    finally:
        app.dependency_overrides.clear()


def test_lister_toutes_commandes_calcule_le_statut_par_atelier() -> None:
    """Même statut (planifiee/en_retard/date_execution) que GET /{instance_id}/commandes —
    la version agrégée ne doit rien perdre du calcul par atelier."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        commande_id = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"], "date_limite": 10}
        ).json()["commande_id"]

        resultat = ResultatExecution(
            planning=Planning(operations=[OperationPlanifiee(tache="EXISTANT", ressource="R1", debut=0)]),
            verdict_faisabilite=ResultatFaisabilite(violations=()),
            erreur=None,
        )
        etat_test.enregistrer_execution("solveur-factice", instance_id, resultat)

        reponse = client.get("/ingestion/commandes")

        assert reponse.status_code == 200, reponse.json()
        commandes = reponse.json()
        assert len(commandes) == 1
        assert commandes[0]["commande_id"] == commande_id
        assert commandes[0]["planifiee"] is True
        assert commandes[0]["en_retard"] is False
        assert commandes[0]["date_execution"] is not None
        assert commandes[0]["operations"] == [{"tache": "EXISTANT", "debut": 0, "fin": 1}]
    finally:
        app.dependency_overrides.clear()


def test_lister_toutes_commandes_scopee_par_client_pour_un_non_admin() -> None:
    """Un utilisateur non-admin ne voit que les commandes de son propre client_id —
    même filtrage que supervision.py::lister_instances (client_id_pour_filtre)."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_mon_client = _creer_instance(client, client_id="mon_client")
        instance_autre_client = _creer_instance(client, client_id="autre_client")
        client.post(f"/ingestion/{instance_mon_client}/commandes", json={"taches": ["EXISTANT"]})
        client.post(f"/ingestion/{instance_autre_client}/commandes", json={"taches": ["EXISTANT"]})

        app.dependency_overrides[obtenir_utilisateur_courant] = lambda: _utilisateur_scope("mon_client")

        reponse = client.get("/ingestion/commandes")

        assert reponse.status_code == 200, reponse.json()
        commandes = reponse.json()
        assert len(commandes) == 1
        assert commandes[0]["instance_id"] == instance_mon_client
        assert commandes[0]["client_id"] == "mon_client"
    finally:
        app.dependency_overrides.clear()


def test_lister_toutes_commandes_vide_sans_aucune_commande() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        reponse = client.get("/ingestion/commandes")

        assert reponse.status_code == 200, reponse.json()
        assert reponse.json() == []
    finally:
        app.dependency_overrides.clear()


def test_commande_demarre_non_debutee() -> None:
    """Une commande fraîchement créée n'est jamais supposée avoir commencé — l'avancement réel
    ne peut venir que d'une déclaration humaine (voir `PATCH .../statut`)."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)

        commande_id = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"], "date_limite": 10}
        ).json()["commande_id"]

        reponse = client.get(f"/ingestion/commandes/{commande_id}")

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        assert corps["statut_realisation"] == "non_debutee"
        assert corps["date_realisation"] is None
    finally:
        app.dependency_overrides.clear()


def test_changer_statut_commande_en_cours_puis_realisee() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        commande_id = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"], "date_limite": 10}
        ).json()["commande_id"]

        en_cours = client.patch(f"/ingestion/commandes/{commande_id}/statut", json={"statut": "en_cours"})
        assert en_cours.status_code == 200, en_cours.json()
        assert en_cours.json()["statut_realisation"] == "en_cours"
        # Horodatage réservé à la réalisation : rien à dater tant que le travail n'est pas fini.
        assert en_cours.json()["date_realisation"] is None

        realisee = client.patch(f"/ingestion/commandes/{commande_id}/statut", json={"statut": "realisee"})
        assert realisee.status_code == 200, realisee.json()
        assert realisee.json()["statut_realisation"] == "realisee"
        assert realisee.json()["date_realisation"] is not None

        # Le statut déclaré survit à la relecture, et voisine le statut prévisionnel sans
        # jamais l'écraser (voir `_commande_en_dict`).
        relu = client.get(f"/ingestion/commandes/{commande_id}").json()
        assert relu["statut_realisation"] == "realisee"
        assert relu["planifiee"] is False  # aucune exécution : la prévision reste indépendante
    finally:
        app.dependency_overrides.clear()


def test_changer_statut_commande_accepte_une_date_de_realisation_retroactive() -> None:
    """« Elle a été finie mardi dernier » — la date déclarée prime sur l'instant de la saisie,
    sinon tout taux de service calculé après coup serait faux."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        commande_id = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"], "date_limite": 10}
        ).json()["commande_id"]

        reponse = client.patch(
            f"/ingestion/commandes/{commande_id}/statut",
            json={"statut": "realisee", "date_realisation": "2026-09-15T08:00:00+00:00"},
        )

        assert reponse.status_code == 200, reponse.json()
        assert reponse.json()["date_realisation"] == "2026-09-15T08:00:00+00:00"
    finally:
        app.dependency_overrides.clear()


def test_revenir_en_arriere_efface_la_date_de_realisation() -> None:
    """Correction d'une fausse manipulation : une commande qui n'est plus réalisée ne doit pas
    garder une date de réalisation qui la ferait compter comme livrée."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        commande_id = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"], "date_limite": 10}
        ).json()["commande_id"]
        client.patch(f"/ingestion/commandes/{commande_id}/statut", json={"statut": "realisee"})

        reponse = client.patch(f"/ingestion/commandes/{commande_id}/statut", json={"statut": "en_cours"})

        assert reponse.status_code == 200, reponse.json()
        assert reponse.json()["statut_realisation"] == "en_cours"
        assert reponse.json()["date_realisation"] is None
    finally:
        app.dependency_overrides.clear()


def test_changer_statut_refuse_un_statut_inconnu() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        commande_id = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"], "date_limite": 10}
        ).json()["commande_id"]

        reponse = client.patch(f"/ingestion/commandes/{commande_id}/statut", json={"statut": "livree"})

        assert reponse.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_changer_statut_commande_inconnue_renvoie_404() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        reponse = client.patch("/ingestion/commandes/inexistante/statut", json={"statut": "en_cours"})

        assert reponse.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_changer_statut_refuse_un_client_etranger() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client, client_id="client_a")
        commande_id = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"], "date_limite": 10}
        ).json()["commande_id"]

        app.dependency_overrides[obtenir_utilisateur_courant] = lambda: _utilisateur_scope("client_b")
        reponse = client.patch(f"/ingestion/commandes/{commande_id}/statut", json={"statut": "realisee"})

        assert reponse.status_code == 403
    finally:
        app.dependency_overrides.clear()
