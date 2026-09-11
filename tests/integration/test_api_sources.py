"""Couche 1 (§6.1) : `POST /sources/{id}/generer-instance-deterministe`
(`api/routes/sources.py`) — alternative sans agent LLM à `generer_instance`,
aucun service externe requis ici (state en mémoire, pas de vrai appel LLM ni
de Postgres).
"""

from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from api.app import app
from api.etat import EtatAPI, obtenir_etat
from api.routes.auth import obtenir_utilisateur_courant
from generation.agents.client_llm import construire_modele_comprehension
from tests.unit.aides_test_agents import ModeleFactice


def _creer_source(
    client: TestClient, donnees_brutes: str, nom: str | None = None, unite_duree: str | None = None
) -> str:
    reponse = client.post(
        "/sources",
        json={
            "donnees_brutes": donnees_brutes,
            "client_id": "client_test",
            "nom": nom,
            "unite_duree": unite_duree,
        },
    )
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


def test_generer_instance_deterministe_nom_projet_reprend_le_nom_de_la_source() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        donnees = (
            '{"taches": [{"id": "T1"}], "ressources": [{"id": "R1"}], '
            '"contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", '
            '"ressource": "R1", "duree": 10}]}'
        )
        source_id = _creer_source(client, donnees, nom="Atelier mécanique")

        reponse = client.post(f"/sources/{source_id}/generer-instance-deterministe")

        assert reponse.status_code == 200, reponse.json()
        instance_id = reponse.json()["instance_id"]
        assert etat_test.recuperer_nom_projet(instance_id) == "Atelier mécanique"
    finally:
        app.dependency_overrides.clear()


def test_generer_instance_deterministe_nom_projet_explicite_prime_sur_la_source() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        donnees = (
            '{"taches": [{"id": "T1"}], "ressources": [{"id": "R1"}], '
            '"contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", '
            '"ressource": "R1", "duree": 10}]}'
        )
        source_id = _creer_source(client, donnees, nom="Atelier mécanique")

        reponse = client.post(f"/sources/{source_id}/generer-instance-deterministe?nom_projet=Ligne+B")

        assert reponse.status_code == 200, reponse.json()
        instance_id = reponse.json()["instance_id"]
        assert etat_test.recuperer_nom_projet(instance_id) == "Ligne B"
    finally:
        app.dependency_overrides.clear()


def test_generer_instance_deterministe_sans_nom_de_source_reste_sans_nom_projet() -> None:
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
        instance_id = reponse.json()["instance_id"]
        assert etat_test.recuperer_nom_projet(instance_id) is None
    finally:
        app.dependency_overrides.clear()


def _page_factice(corps: str, code: int = 200) -> httpx.Response:
    return httpx.Response(code, text=corps, request=httpx.Request("GET", "http://exemple.test"))


def test_appeler_api_get_simple_renvoie_le_corps() -> None:
    """`_appeler_api` (fonction pure) — pas de connexion réseau réelle en
    test, même principe que `extraire_payload_api` (`adapters/greensig/
    extraction_api.py`)."""
    from api.routes.sources import RequeteExplorationAPI, _appeler_api

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == "http://exemple.test/taches"
        return httpx.Response(200, text='{"taches": [{"id": 1}]}')

    client = httpx.Client(transport=httpx.MockTransport(handler))
    corps = _appeler_api(RequeteExplorationAPI(url="http://exemple.test/taches"), client=client)

    assert corps == '{"taches": [{"id": 1}]}'


def test_appeler_api_cle_api_ajoute_len_tete() -> None:
    from api.routes.sources import AuthentificationAPI, RequeteExplorationAPI, _appeler_api

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Api-Key"] == "secret123"
        return httpx.Response(200, text="ok")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    requete = RequeteExplorationAPI(
        url="http://exemple.test/taches",
        authentification=AuthentificationAPI(type="cle_api", en_tete="X-Api-Key", valeur="secret123"),
    )
    assert _appeler_api(requete, client=client) == "ok"


def test_appeler_api_porteur_ajoute_authorization_bearer() -> None:
    from api.routes.sources import AuthentificationAPI, RequeteExplorationAPI, _appeler_api

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer jeton-abc"
        return httpx.Response(200, text="ok")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    requete = RequeteExplorationAPI(
        url="http://exemple.test/taches",
        authentification=AuthentificationAPI(type="porteur", jeton="jeton-abc"),
    )
    assert _appeler_api(requete, client=client) == "ok"


def test_appeler_api_reponse_en_erreur_leve() -> None:
    from api.routes.sources import RequeteExplorationAPI, _appeler_api

    client = httpx.Client(transport=httpx.MockTransport(lambda _r: httpx.Response(404, text="introuvable")))

    with pytest.raises(httpx.HTTPStatusError):
        _appeler_api(RequeteExplorationAPI(url="http://exemple.test/inconnu"), client=client)


_REQUETE_EXPLORATION_API = {"url": "http://exemple.test/taches"}


def test_explorer_api_retourne_le_corps_de_la_reponse(monkeypatch: pytest.MonkeyPatch) -> None:
    """Couche 1 (§6.1) : la route ne fait que relayer `_appeler_api`
    (déjà testé en isolation ci-dessus) — remplacé ici par un faux résultat,
    aucune vraie connexion réseau."""
    monkeypatch.setattr("api.routes.sources._appeler_api", lambda *_a, **_k: '{"taches": [{"id": 1}]}')
    try:
        client = TestClient(app)
        reponse = client.post("/sources/explorer-api", json=_REQUETE_EXPLORATION_API)

        assert reponse.status_code == 200, reponse.json()
        assert reponse.json()["donnees_brutes"] == '{"taches": [{"id": 1}]}'
    finally:
        app.dependency_overrides.clear()


def test_explorer_api_erreur_http_renvoie_422(monkeypatch: pytest.MonkeyPatch) -> None:
    def _echec(*_a: object, **_k: object) -> None:
        raise httpx.HTTPStatusError(
            "404", request=httpx.Request("GET", "http://exemple.test"), response=_page_factice("introuvable", 404)
        )

    monkeypatch.setattr("api.routes.sources._appeler_api", _echec)
    try:
        client = TestClient(app)
        reponse = client.post("/sources/explorer-api", json=_REQUETE_EXPLORATION_API)

        assert reponse.status_code == 422
        assert "réponse en erreur (404)" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_explorer_api_connexion_impossible_renvoie_422(monkeypatch: pytest.MonkeyPatch) -> None:
    def _echec(*_a: object, **_k: object) -> None:
        raise httpx.ConnectError("connexion refusée")

    monkeypatch.setattr("api.routes.sources._appeler_api", _echec)
    try:
        client = TestClient(app)
        reponse = client.post("/sources/explorer-api", json=_REQUETE_EXPLORATION_API)

        assert reponse.status_code == 422
        assert "appel API impossible" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_unite_duree_declaree_sur_la_source_est_exposee() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        source_id = _creer_source(client, "peu importe", unite_duree="semaines")

        reponse = client.get(f"/sources/{source_id}")

        assert reponse.status_code == 200, reponse.json()
        assert reponse.json()["unite_duree"] == "semaines"
    finally:
        app.dependency_overrides.clear()


def test_unite_duree_se_propage_de_la_source_a_linstance_generee() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        donnees = (
            '{"taches": [{"id": "T1"}], "ressources": [{"id": "R1"}], '
            '"contraintes": [{"type": "compatibilite_ressource_tache", "tache": "T1", '
            '"ressource": "R1", "duree": 10}]}'
        )
        source_id = _creer_source(client, donnees, unite_duree="mois")

        reponse = client.post(f"/sources/{source_id}/generer-instance-deterministe")
        assert reponse.status_code == 200, reponse.json()
        instance_id = reponse.json()["instance_id"]

        reponse_instance = client.get(f"/ingestion/{instance_id}")
        assert reponse_instance.status_code == 200, reponse_instance.json()
        assert reponse_instance.json()["unite_duree"] == "mois"
    finally:
        app.dependency_overrides.clear()


_REQUETE_EXPLORATION_BDD = {"client_id": "acme"}


class _ResultatExplorationBDDFactice:
    def __init__(
        self,
        donnees_json: dict[str, object],
        avertissements: tuple[str, ...] = (),
        requetes_executees: tuple[str, ...] = (),
    ) -> None:
        self.reponse_brute = "{}"
        self.requetes_executees = requetes_executees
        self.donnees_json = donnees_json
        self.avertissements = avertissements


def test_explorer_bdd_retourne_les_donnees_json_serialisees(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=None
    )
    monkeypatch.setattr("api.routes.sources.dsn_lecture_seule_pour_client", lambda _client_id: "postgresql://x")
    monkeypatch.setattr(
        "api.routes.sources.explorer_base_de_donnees",
        lambda *_a, **_k: _ResultatExplorationBDDFactice(
            donnees_json={"taches": [{"id": 1}]},
            avertissements=("x",),
            requetes_executees=("SELECT 1",),
        ),
    )
    try:
        client = TestClient(app)
        reponse = client.post("/sources/explorer-bdd", json=_REQUETE_EXPLORATION_BDD)

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        import json as _json

        assert _json.loads(corps["donnees_brutes"]) == {"taches": [{"id": 1}]}
        assert corps["avertissements"] == ["x"]
        assert corps["requetes_executees"] == ["SELECT 1"]
    finally:
        app.dependency_overrides.clear()


def test_explorer_bdd_client_sans_dsn_configure_renvoie_404(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=None
    )
    monkeypatch.setattr("api.routes.sources.dsn_lecture_seule_pour_client", lambda _client_id: None)
    try:
        client = TestClient(app)
        reponse = client.post("/sources/explorer-bdd", json=_REQUETE_EXPLORATION_BDD)

        assert reponse.status_code == 404
        assert "non configurée" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_explorer_bdd_connexion_impossible_renvoie_503(monkeypatch: pytest.MonkeyPatch) -> None:
    import psycopg

    def _echec(*_a: object, **_k: object) -> None:
        raise psycopg.OperationalError("connexion refusée")

    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=None
    )
    monkeypatch.setattr("api.routes.sources.dsn_lecture_seule_pour_client", lambda _client_id: "postgresql://x")
    monkeypatch.setattr("api.routes.sources.explorer_base_de_donnees", _echec)
    try:
        client = TestClient(app)
        reponse = client.post("/sources/explorer-bdd", json=_REQUETE_EXPLORATION_BDD)

        assert reponse.status_code == 503
        assert "injoignable" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_explorer_bdd_requete_echoue_renvoie_502(monkeypatch: pytest.MonkeyPatch) -> None:
    import psycopg

    def _echec(*_a: object, **_k: object) -> None:
        raise psycopg.Error("relation inconnue")

    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=None
    )
    monkeypatch.setattr("api.routes.sources.dsn_lecture_seule_pour_client", lambda _client_id: "postgresql://x")
    monkeypatch.setattr("api.routes.sources.explorer_base_de_donnees", _echec)
    try:
        client = TestClient(app)
        reponse = client.post("/sources/explorer-bdd", json=_REQUETE_EXPLORATION_BDD)

        assert reponse.status_code == 502
        assert "requête d'exploration a échoué" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_explorer_bdd_reponse_llm_non_conforme_renvoie_502(monkeypatch: pytest.MonkeyPatch) -> None:
    from generation.agents.base import ErreurReponseAgentInvalide

    def _echec(*_a: object, **_k: object) -> None:
        raise ErreurReponseAgentInvalide("mal formé")

    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=None
    )
    monkeypatch.setattr("api.routes.sources.dsn_lecture_seule_pour_client", lambda _client_id: "postgresql://x")
    monkeypatch.setattr("api.routes.sources.explorer_base_de_donnees", _echec)
    try:
        client = TestClient(app)
        reponse = client.post("/sources/explorer-bdd", json=_REQUETE_EXPLORATION_BDD)

        assert reponse.status_code == 502
        assert "agent d'exploration" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_explorer_bdd_schemas_par_defaut_est_public(monkeypatch: pytest.MonkeyPatch) -> None:
    captures: dict[str, object] = {}

    def _capture(_modele: object, _dsn: str, schemas: tuple[str, ...]) -> _ResultatExplorationBDDFactice:
        captures["schemas"] = schemas
        return _ResultatExplorationBDDFactice(donnees_json={})

    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=None
    )
    monkeypatch.setattr("api.routes.sources.dsn_lecture_seule_pour_client", lambda _client_id: "postgresql://x")
    monkeypatch.setattr("api.routes.sources.explorer_base_de_donnees", _capture)
    try:
        client = TestClient(app)
        reponse = client.post("/sources/explorer-bdd", json={"client_id": "acme"})

        assert reponse.status_code == 200, reponse.json()
        assert captures["schemas"] == ("public",)
    finally:
        app.dependency_overrides.clear()


def test_explorer_bdd_schemas_personnalises_sont_transmis(monkeypatch: pytest.MonkeyPatch) -> None:
    captures: dict[str, object] = {}

    def _capture(_modele: object, _dsn: str, schemas: tuple[str, ...]) -> _ResultatExplorationBDDFactice:
        captures["schemas"] = schemas
        return _ResultatExplorationBDDFactice(donnees_json={})

    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=None
    )
    monkeypatch.setattr("api.routes.sources.dsn_lecture_seule_pour_client", lambda _client_id: "postgresql://x")
    monkeypatch.setattr("api.routes.sources.explorer_base_de_donnees", _capture)
    try:
        client = TestClient(app)
        reponse = client.post("/sources/explorer-bdd", json={"client_id": "acme", "schemas": ["public", "vente"]})

        assert reponse.status_code == 200, reponse.json()
        assert captures["schemas"] == ("public", "vente")
    finally:
        app.dependency_overrides.clear()


def test_explorer_bdd_resultat_trop_volumineux_renvoie_422(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=None
    )
    monkeypatch.setattr("api.routes.sources.dsn_lecture_seule_pour_client", lambda _client_id: "postgresql://x")
    monkeypatch.setattr(
        "api.routes.sources.explorer_base_de_donnees",
        lambda *_a, **_k: _ResultatExplorationBDDFactice(donnees_json={"x": "y" * 6_000_000}),
    )
    try:
        client = TestClient(app)
        reponse = client.post("/sources/explorer-bdd", json=_REQUETE_EXPLORATION_BDD)

        assert reponse.status_code == 422
        assert "trop volumineux" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_explorer_bdd_admin_peut_cibler_un_autre_client(monkeypatch: pytest.MonkeyPatch) -> None:
    captures: dict[str, object] = {}

    def _capture_client_id(client_id: str) -> str | None:
        captures["client_id"] = client_id
        return None  # 404 ensuite, peu importe ici : on ne vérifie que le client_id résolu

    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=None
    )
    monkeypatch.setattr("api.routes.sources.dsn_lecture_seule_pour_client", _capture_client_id)
    try:
        client = TestClient(app)
        client.post("/sources/explorer-bdd", json={"client_id": "acme"})

        assert captures["client_id"] == "acme"
    finally:
        app.dependency_overrides.clear()


def test_explorer_bdd_non_admin_est_contraint_a_son_propre_client(monkeypatch: pytest.MonkeyPatch) -> None:
    captures: dict[str, object] = {}

    def _capture_client_id(client_id: str) -> str | None:
        captures["client_id"] = client_id
        return None

    app.dependency_overrides[obtenir_utilisateur_courant] = lambda: {
        "id": "u1",
        "email": "op@client.test",
        "nom": "Op",
        "prenom": "Erateur",
        "role": "operateur",
        "client_id": "mon_client",
        "date_creation": "2024-01-01T00:00:00+00:00",
        "dernier_acces": None,
    }
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=None
    )
    monkeypatch.setattr("api.routes.sources.dsn_lecture_seule_pour_client", _capture_client_id)
    try:
        client = TestClient(app)
        client.post("/sources/explorer-bdd", json={"client_id": "acme"})

        assert captures["client_id"] == "mon_client"
    finally:
        app.dependency_overrides.clear()


def test_source_sans_unite_duree_declaree_reste_none() -> None:
    """Défaut implicite "jours" côté affichage — jamais une chaîne littérale
    "jours" stockée, `None` partout où l'unité n'a jamais été précisée."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    try:
        client = TestClient(app)
        source_id = _creer_source(client, "peu importe")

        reponse = client.get(f"/sources/{source_id}")

        assert reponse.status_code == 200, reponse.json()
        assert reponse.json()["unite_duree"] is None
    finally:
        app.dependency_overrides.clear()
