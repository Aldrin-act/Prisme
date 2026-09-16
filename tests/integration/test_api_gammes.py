"""Couche 1 (§6.1) : CRUD `GammeProduit` (`api/routes/gammes.py`) et explosion par commande
(`POST /ingestion/{instance_id}/commandes`, `api/routes/ingestion.py`) — une commande peut
référencer plusieurs gammes (plusieurs produits) en plus de tâches choisies directement. State en
mémoire (`EtatAPI`), aucun service externe requis."""

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


def _creer_instance(client: TestClient, client_id: str = "client_test") -> str:
    reponse = client.post(f"/ingestion/{client_id}", json=_payload_instance_minimale())
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
        instance_id = _creer_instance(client)
        gamme_id = _creer_gamme(client)

        reponse = client.post(
            f"/ingestion/{instance_id}/commandes",
            json={"gammes": [{"gamme_id": gamme_id, "quantite": 5}], "date_limite": 10},
        )

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        commande_id = corps["commande_id"]
        assert corps["avertissements"] == []

        instance = client.get(f"/ingestion/{instance_id}")
        assert instance.status_code == 200, instance.json()
        instance_json = instance.json()

        tache_id = f"{commande_id}_0_soudure"
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
        # La tâche déjà présente avant la commande reste intacte.
        assert any(t["id"] == "EXISTANT" for t in instance_json["taches"])
    finally:
        app.dependency_overrides.clear()


def test_ajouter_commande_persiste_et_affiche_les_gammes_referencees() -> None:
    """Le lien vers les gammes utilisées survit à la création — visible dans les trois lectures
    (liste par instance, liste transverse, détail d'une commande), en copie figée (produit/nom au
    moment de la création, indépendante d'une modification ultérieure de la gamme elle-même)."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        gamme_id = _creer_gamme(client, nom="Gamme vanne")

        reponse = client.post(
            f"/ingestion/{instance_id}/commandes",
            json={"gammes": [{"gamme_id": gamme_id, "quantite": 5}], "date_limite": 10},
        )
        assert reponse.status_code == 200, reponse.json()
        commande_id = reponse.json()["commande_id"]

        gamme_attendue = {"gamme_id": gamme_id, "produit": "Vanne V12", "nom": "Gamme vanne", "quantite": 5}

        par_instance = client.get(f"/ingestion/{instance_id}/commandes").json()
        commande_par_instance = next(c for c in par_instance if c["commande_id"] == commande_id)
        assert commande_par_instance["gammes"] == [gamme_attendue]

        toutes = client.get("/ingestion/commandes").json()
        commande_globale = next(c for c in toutes if c["commande_id"] == commande_id)
        assert commande_globale["gammes"] == [gamme_attendue]

        detail = client.get(f"/ingestion/commandes/{commande_id}").json()
        assert detail["gammes"] == [gamme_attendue]

        # Modifier la gamme après coup ne réécrit pas la traçabilité déjà persistée.
        client.put(
            f"/gammes/{gamme_id}",
            json={"produit": "Vanne V13", "etapes": [{"id": "soudure", "competences": ["soudure"]}]},
        )
        detail_apres_modif = client.get(f"/ingestion/commandes/{commande_id}").json()
        assert detail_apres_modif["gammes"] == [gamme_attendue]
    finally:
        app.dependency_overrides.clear()


def test_ajouter_commande_deux_gammes_fusionne_les_deux_produits() -> None:
    """Une commande peut référencer plusieurs gammes (plusieurs produits) dans la même requête —
    nouveau comportement par rapport à l'ancienne version (une seule gamme par commande)."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        gamme_a = _creer_gamme(client, produit="Vanne V12")
        gamme_b = _creer_gamme(client, produit="Bride B7", etapes=[{"id": "peinture", "competences": ["soudure"]}])

        reponse = client.post(
            f"/ingestion/{instance_id}/commandes",
            json={
                "gammes": [{"gamme_id": gamme_a}, {"gamme_id": gamme_b}],
                "date_limite": 10,
            },
        )

        assert reponse.status_code == 200, reponse.json()
        commande_id = reponse.json()["commande_id"]

        instance_json = client.get(f"/ingestion/{instance_id}").json()
        taches_ids = {t["id"] for t in instance_json["taches"]}
        assert f"{commande_id}_0_soudure" in taches_ids
        assert f"{commande_id}_1_peinture" in taches_ids
    finally:
        app.dependency_overrides.clear()


def test_ajouter_commande_melange_gamme_et_taches_directes() -> None:
    """Les deux mécanismes coexistent pour la même commande : une gamme explosée et une tâche déjà
    existante choisie directement partagent la même échéance dérivée."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        gamme_id = _creer_gamme(client)

        reponse = client.post(
            f"/ingestion/{instance_id}/commandes",
            json={"taches": ["EXISTANT"], "gammes": [{"gamme_id": gamme_id}], "date_limite": 7},
        )

        assert reponse.status_code == 200, reponse.json()
        commande_id = reponse.json()["commande_id"]

        instance_json = client.get(f"/ingestion/{instance_id}").json()
        echeances = {c["tache"]: c["echeance"] for c in instance_json["contraintes"] if c["type"] == "echeance"}
        assert echeances == {"EXISTANT": 7, f"{commande_id}_0_soudure": 7}
    finally:
        app.dependency_overrides.clear()


def test_ajouter_commande_sans_tache_ni_gamme_refusee() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)

        reponse = client.post(f"/ingestion/{instance_id}/commandes", json={"date_limite": 10})

        assert reponse.status_code == 422
        assert "tâche" in reponse.json()["detail"] or "gamme" in reponse.json()["detail"]
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

        reponse = client.post(
            f"/ingestion/{instance_id}/commandes", json={"gammes": [{"gamme_id": gamme_id_autre_client}]}
        )

        assert reponse.status_code == 400
        assert "n'appartient pas" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_ajouter_commande_gamme_inconnue_renvoie_404() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)

        reponse = client.post(f"/ingestion/{instance_id}/commandes", json={"gammes": [{"gamme_id": "fantome"}]})

        assert reponse.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_ajouter_commande_gamme_non_realisable_dans_l_atelier_renvoie_422() -> None:
    """Aucune ressource de l'instance ne possède "fraisage" (seule "soudure" est déclarée sur
    R1) — l'unique étape de la gamme est donc filtrée comme non réalisable dans cet atelier
    (`adapters/gamme_derivation.py::_etape_realisable`) avant même toute tentative de dérivation
    de durée, et l'explosion entière échoue explicitement plutôt que de créer une commande sans
    aucune tâche."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        gamme_id = _creer_gamme(client, etapes=[{"id": "fraisage", "competences": ["fraisage"]}])

        reponse = client.post(f"/ingestion/{instance_id}/commandes", json={"gammes": [{"gamme_id": gamme_id}]})

        assert reponse.status_code == 422
        assert "réalisable" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_ajouter_commande_etape_non_couverte_ignoree_avec_avertissement() -> None:
    """Une gamme à deux étapes dont une seule est couverte par les ressources de l'atelier
    explose quand même — l'étape non couverte est ignorée, signalée par un avertissement dans la
    réponse, la commande n'échoue pas (§FC4, décision humaine préservée)."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        gamme_id = _creer_gamme(
            client,
            etapes=[
                {"id": "soudure", "competences": ["soudure"], "duree_nominale": 3},
                {"id": "fraisage", "competences": ["fraisage"], "duree_nominale": 2},
            ],
        )

        reponse = client.post(
            f"/ingestion/{instance_id}/commandes",
            json={"gammes": [{"gamme_id": gamme_id, "quantite": 5}], "date_limite": 10},
        )

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        commande_id = corps["commande_id"]
        assert len(corps["avertissements"]) == 1
        assert "fraisage" in corps["avertissements"][0]

        instance_json = client.get(f"/ingestion/{instance_id}").json()
        taches_ids = {t["id"] for t in instance_json["taches"]}
        assert f"{commande_id}_0_soudure" in taches_ids
        assert f"{commande_id}_0_fraisage" not in taches_ids
    finally:
        app.dependency_overrides.clear()


# --- Ajout d'un produit à une commande déjà créée (POST /commandes/{commande_id}/produits) ------


def test_ajouter_produit_a_commande_explose_dans_l_instance_et_complete_la_commande() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        gamme_id = _creer_gamme(client, nom="Gamme vanne")

        reponse_creation = client.post(
            f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"], "date_limite": 10}
        )
        assert reponse_creation.status_code == 200, reponse_creation.json()
        commande_id = reponse_creation.json()["commande_id"]
        date_creation_avant = client.get(f"/ingestion/commandes/{commande_id}").json()["date_creation"]

        reponse = client.post(
            f"/ingestion/commandes/{commande_id}/produits", json={"gamme_id": gamme_id, "quantite": 5}
        )

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        tache_id = f"{commande_id}_0_soudure"
        assert corps["taches"] == ["EXISTANT", tache_id]
        assert corps["gammes"] == [
            {"gamme_id": gamme_id, "produit": "Vanne V12", "nom": "Gamme vanne", "quantite": 5}
        ]

        instance_json = client.get(f"/ingestion/{instance_id}").json()
        assert any(t["id"] == tache_id and t["quantite"] == 5 for t in instance_json["taches"])
        # L'échéance de la commande (10) s'applique aussi à la tâche fraîchement explosée.
        echeances = {c["tache"]: c["echeance"] for c in instance_json["contraintes"] if c["type"] == "echeance"}
        assert echeances == {"EXISTANT": 10, tache_id: 10}

        detail = client.get(f"/ingestion/commandes/{commande_id}").json()
        assert detail["taches"] == ["EXISTANT", tache_id]
        assert detail["date_creation"] == date_creation_avant
    finally:
        app.dependency_overrides.clear()


def test_ajouter_produit_a_commande_deux_fois_n_entre_pas_en_collision() -> None:
    """Deux produits ajoutés l'un après l'autre à la même commande, réutilisant le même id
    d'étape ("soudure") — le préfixe de gamme doit continuer à progresser (0 puis 1) plutôt que
    repartir de 0 à chaque appel, sous peine de collision d'id de tâche."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        gamme_id = _creer_gamme(client)

        commande_id = client.post(
            f"/ingestion/{instance_id}/commandes", json={"gammes": [{"gamme_id": gamme_id}], "date_limite": 10}
        ).json()["commande_id"]

        reponse = client.post(f"/ingestion/commandes/{commande_id}/produits", json={"gamme_id": gamme_id})

        assert reponse.status_code == 200, reponse.json()
        instance_json = client.get(f"/ingestion/{instance_id}").json()
        taches_ids = {t["id"] for t in instance_json["taches"]}
        assert f"{commande_id}_0_soudure" in taches_ids
        assert f"{commande_id}_1_soudure" in taches_ids
    finally:
        app.dependency_overrides.clear()


def test_ajouter_produit_a_commande_inconnue_renvoie_404() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        gamme_id = _creer_gamme(client)

        reponse = client.post("/ingestion/commandes/fantome/produits", json={"gamme_id": gamme_id})

        assert reponse.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_ajouter_produit_a_commande_gamme_inconnue_renvoie_404() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        instance_id = _creer_instance(client)
        commande_id = client.post(f"/ingestion/{instance_id}/commandes", json={"taches": ["EXISTANT"]}).json()[
            "commande_id"
        ]

        reponse = client.post(f"/ingestion/commandes/{commande_id}/produits", json={"gamme_id": "fantome"})

        assert reponse.status_code == 404
    finally:
        app.dependency_overrides.clear()
