"""Couche 1 (§6.1) : `/adapters/greensig/ingerer` fait le pont entre la base
GreenSIG réelle (`db_greensig`, profil `greensig`) et le canal d'ingestion —
nécessite ce service, skip sinon (voir `greensig_dsn`). `/adapters/comprehension/ingerer`
(agent LLM, `adapters/agent_comprehension/`) n'a besoin d'aucun service
externe ici : `construire_modele_comprehension` est substitué comme
n'importe quelle autre dépendance FastAPI (`app.dependency_overrides`),
jamais un vrai appel LLM.
"""

from __future__ import annotations

import psycopg
import pytest
from fastapi.testclient import TestClient

import api.routes.adapters as routes_adapters
from adapters.agent_comprehension.agent import _SchemaComprehension
from adapters.agent_comprehension.exploration_bdd import ResultatExplorationBDD
from api.app import app
from api.etat import EtatAPI, obtenir_etat
from generation.agents.base import ErreurReponseAgentInvalide
from generation.agents.client_llm import construire_modele_comprehension
from tests.unit.aides_test_agents import ModeleFactice


def test_ingestion_depuis_greensig_signale_le_rejet_du_lot_brut(greensig_dsn: str) -> None:
    """Documente l'état réel actuel (voir tests/integration/test_greensig_extraction.py) :
    228/1007 tâches à planifier n'ont aucune équipe active, donc `traduire()` rejette tout
    le lot — la route doit relayer ce 422 tel quel, jamais masquer le rejet derrière un
    succès partiel."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test

    try:
        client = TestClient(app)
        reponse = client.post("/adapters/greensig/ingerer")

        assert reponse.status_code == 422
        detail = reponse.json()["detail"]
        assert any("sans aucune contrainte de compatibilité" in erreur["msg"] for erreur in detail)
        assert etat_test.instances == {}
    finally:
        app.dependency_overrides.clear()


def test_ingestion_via_comprehension_accepte_une_traduction_valide() -> None:
    etat_test = EtatAPI()
    schema_agent = _SchemaComprehension(
        instance={
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [
                {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}
            ],
            "objectifs": [{"type": "minimiser_makespan"}],
        },
        description_metier="Une tâche T1 exécutée sur la ressource R1.",
        avertissements=["durée estimée, absente des données source"],
    )
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=schema_agent
    )

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/comprehension/ingerer",
            json={"client_id": "nouveau_client", "donnees_brutes": "T1;M1;10min"},
        )

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        assert corps["structure_contraintes"] == "compatibilite_ressource_tache"
        assert corps["description_metier"] == "Une tâche T1 exécutée sur la ressource R1."
        assert corps["avertissements"] == ["durée estimée, absente des données source"]
        assert corps["instance_id"] in etat_test.instances
        assert (
            etat_test.recuperer_description_metier(corps["instance_id"])
            == "Une tâche T1 exécutée sur la ressource R1."
        )
    finally:
        app.dependency_overrides.clear()


def test_ingestion_via_comprehension_relaie_le_rejet_du_garde_fou() -> None:
    """Le garde-fou déterministe (§6.7) tranche pareil, que le payload vienne d'un humain,
    d'un adaptateur écrit à la main ou de l'agent de compréhension : une tâche sans
    compatibilité est rejetée avec un 422, jamais ingérée en silence."""
    etat_test = EtatAPI()
    schema_agent = _SchemaComprehension(
        instance={
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [],
            "objectifs": [{"type": "minimiser_makespan"}],
        },
        description_metier="Une tâche T1, sans ressource compatible identifiée.",
    )
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=schema_agent
    )

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/comprehension/ingerer",
            json={"client_id": "nouveau_client", "donnees_brutes": "???"},
        )

        assert reponse.status_code == 422
        assert etat_test.instances == {}
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_csv_accepte_trois_fichiers_valides() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/csv/client_test",
            files={
                "taches": ("taches.csv", b"id,nom\nT1,Decoupe\nT2,Assemblage\n", "text/csv"),
                "ressources": ("ressources.csv", b"id,nom\nR1,Decoupeuse\n", "text/csv"),
                "contraintes": (
                    "contraintes.csv",
                    b"type,tache_avant,tache_apres,tache,ressource,duree_jours\n"
                    b"precedence,T1,T2,,,\n"
                    b"compatibilite_ressource_tache,,,T1,R1,10\n"
                    b"compatibilite_ressource_tache,,,T2,R1,15\n",
                    "text/csv",
                ),
            },
        )

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        assert corps["structure_contraintes"] == "compatibilite_ressource_tache,precedence"
        assert corps["instance_id"] in etat_test.instances
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_csv_avec_delimiteur_point_virgule() -> None:
    """Export Excel FR typique (`;`) — jamais deviné, le client le déclare
    explicitement via le paramètre de requête `delimiteur`."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/csv/client_test",
            params={"delimiteur": ";"},
            files={
                "taches": ("taches.csv", b"id;nom\nT1;Decoupe\nT2;Assemblage\n", "text/csv"),
                "ressources": ("ressources.csv", b"id;nom\nR1;Decoupeuse\n", "text/csv"),
                "contraintes": (
                    "contraintes.csv",
                    b"type;tache_avant;tache_apres;tache;ressource;duree_jours\n"
                    b"precedence;T1;T2;;;\n"
                    b"compatibilite_ressource_tache;;;T1;R1;10\n"
                    b"compatibilite_ressource_tache;;;T2;R1;15\n",
                    "text/csv",
                ),
            },
        )

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        assert corps["structure_contraintes"] == "compatibilite_ressource_tache,precedence"
        assert corps["instance_id"] in etat_test.instances
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_csv_rejette_un_delimiteur_multi_caracteres() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/csv/client_test",
            params={"delimiteur": "::"},
            files={
                "taches": ("taches.csv", b"id,nom\nT1,Decoupe\n", "text/csv"),
                "ressources": ("ressources.csv", b"id,nom\nR1,Decoupeuse\n", "text/csv"),
                "contraintes": (
                    "contraintes.csv",
                    b"type,tache,ressource,duree_jours\ncompatibilite_ressource_tache,T1,R1,10\n",
                    "text/csv",
                ),
            },
        )

        assert reponse.status_code == 422
        assert etat_test.instances == {}
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_csv_derive_la_compatibilite_par_competence() -> None:
    """Bout en bout (§5.4) : plutôt que de saisir tache/ressource/duree à la
    main, une ressource déclare une compétence et une tâche l'exige — la
    compatibilité (et sa durée) est calculée par l'adaptateur, pas par
    l'utilisateur (`adapters/csv_import/traducteur.py`)."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/csv/client_test",
            files={
                "taches": ("taches.csv", b"id,duree_estimee_jours\nT1,25\n", "text/csv"),
                "ressources": ("ressources.csv", b"id,competences\nR1,decoupe\nR2,assemblage\n", "text/csv"),
                "contraintes": (
                    "contraintes.csv",
                    b"type,tache,competence\ncompetence_requise,T1,decoupe\n",
                    "text/csv",
                ),
            },
        )

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        assert corps["structure_contraintes"] == "compatibilite_ressource_tache,competence_requise"
        instance_id = corps["instance_id"]
        _, instance = etat_test.instances[instance_id]
        compatibilites = [c for c in instance.contraintes if c.type == "compatibilite_ressource_tache"]
        assert [(c.tache, c.ressource, c.duree) for c in compatibilites] == [("T1", "R1", 25)]
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_csv_avec_commandes_derive_une_echeance() -> None:
    """Bout en bout (§5.4) : le quatrième fichier optionnel `commandes` relie
    des tâches à une commande cliente et une date limite — l'adaptateur
    dérive une `Echeance` pour chaque tâche liée (`adapters/commande_derivation.py`)."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/csv/client_test",
            files={
                "taches": ("taches.csv", b"id,nom\nT1,Decoupe\nT2,Assemblage\n", "text/csv"),
                "ressources": ("ressources.csv", b"id,nom\nR1,Decoupeuse\n", "text/csv"),
                "contraintes": (
                    "contraintes.csv",
                    b"type,tache_avant,tache_apres,tache,ressource,duree_jours\n"
                    b"precedence,T1,T2,,,\n"
                    b"compatibilite_ressource_tache,,,T1,R1,10\n"
                    b"compatibilite_ressource_tache,,,T2,R1,15\n",
                    "text/csv",
                ),
                "commandes": (
                    "commandes.csv",
                    b"id,taches,client,date_limite\nCMD1,T1;T2,Client A,30\n",
                    "text/csv",
                ),
            },
        )

        assert reponse.status_code == 200, reponse.json()
        instance_id = reponse.json()["instance_id"]
        _, instance = etat_test.instances[instance_id]
        echeances = {c.tache: c.echeance for c in instance.contraintes if c.type == "echeance"}
        assert echeances == {"T1": 30, "T2": 30}
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_csv_rejette_une_extension_invalide() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/csv/client_test",
            files={
                "taches": ("taches.txt", b"id,nom\nT1,Decoupe\n", "text/plain"),
                "ressources": ("ressources.csv", b"id,nom\nR1,Decoupeuse\n", "text/csv"),
                "contraintes": (
                    "contraintes.csv",
                    b"type,tache_avant,tache_apres,tache,ressource,duree_jours\n",
                    "text/csv",
                ),
            },
        )

        assert reponse.status_code == 422
        assert etat_test.instances == {}
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_csv_relaie_une_colonne_manquante() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/csv/client_test",
            files={
                "taches": ("taches.csv", b"identifiant,nom\nT1,Decoupe\n", "text/csv"),
                "ressources": ("ressources.csv", b"id,nom\nR1,Decoupeuse\n", "text/csv"),
                "contraintes": (
                    "contraintes.csv",
                    b"type,tache_avant,tache_apres,tache,ressource,duree_jours\n",
                    "text/csv",
                ),
            },
        )

        assert reponse.status_code == 422
        assert "colonne" in reponse.json()["detail"]
        assert etat_test.instances == {}
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_json_ingere_une_instance_canonique_sans_transformation() -> None:
    """Sur-ensemble strict du format canonique (§5.4, `adapters/json_import/`) :
    un payload sans compétence ni durée estimée est ingéré tel quel."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/json/client_test",
            json={
                "taches": [{"id": "T1"}],
                "ressources": [{"id": "R1"}],
                "contraintes": [
                    {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}
                ],
            },
        )

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        assert corps["structure_contraintes"] == "compatibilite_ressource_tache"
        assert corps["instance_id"] in etat_test.instances
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_json_derive_la_compatibilite_par_competence() -> None:
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/json/client_test",
            json={
                "taches": [{"id": "T1", "duree_estimee_jours": 25}],
                "ressources": [{"id": "R1", "competences": ["decoupe"]}, {"id": "R2", "competences": []}],
                "contraintes": [{"type": "competence_requise", "tache": "T1", "competence": "decoupe"}],
            },
        )

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        instance_id = corps["instance_id"]
        _, instance = etat_test.instances[instance_id]
        compatibilites = [c for c in instance.contraintes if c.type == "compatibilite_ressource_tache"]
        assert [(c.tache, c.ressource, c.duree) for c in compatibilites] == [("T1", "R1", 25)]
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_json_comble_une_duree_manquante_par_estimation_ml() -> None:
    """`estimation` (scikit-learn) est branché par défaut sur cette route
    (`_estimateur_duree_optionnel`, `api/routes/adapters.py`) — une durée
    manquante n'est donc plus un rejet : elle est comblée par apprentissage
    automatique, signalée par un avertissement explicite (§FC4), jamais
    silencieusement. Voir le test suivant pour le comportement de repli
    quand `estimation` n'est pas installé."""
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/json/client_test",
            json={
                "taches": [{"id": "T1"}],
                "ressources": [{"id": "R1", "competences": ["decoupe"]}],
                "contraintes": [{"type": "competence_requise", "tache": "T1", "competence": "decoupe"}],
            },
        )

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        assert any("estimée par apprentissage automatique" in a for a in corps["avertissements"])
        _, instance = etat_test.instances[corps["instance_id"]]
        compatibilites = [c for c in instance.contraintes if c.type == "compatibilite_ressource_tache"]
        assert len(compatibilites) == 1
        assert compatibilites[0].tache == "T1"
        assert compatibilites[0].duree >= 1
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_json_signale_une_duree_manquante_sans_estimateur(monkeypatch) -> None:
    """Comportement de repli quand `estimation` n'est pas installé
    (`uv sync` sans `--extra estimation`) — `_estimateur_duree_optionnel`
    renvoie alors `None` et une durée manquante reste un rejet explicite,
    exactement comme avant le branchement de l'estimateur."""
    monkeypatch.setattr(routes_adapters, "_estimateur_duree_optionnel", lambda: None)
    etat_test = EtatAPI()
    app.dependency_overrides[obtenir_etat] = lambda: etat_test

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/json/client_test",
            json={
                "taches": [{"id": "T1"}],
                "ressources": [{"id": "R1", "competences": ["decoupe"]}],
                "contraintes": [{"type": "competence_requise", "tache": "T1", "competence": "decoupe"}],
            },
        )

        assert reponse.status_code == 422
        assert "durée estimée manquante" in reponse.json()["detail"]
        assert etat_test.instances == {}
    finally:
        app.dependency_overrides.clear()


def test_ingestion_via_comprehension_signale_une_reponse_llm_non_conforme() -> None:
    app.dependency_overrides[obtenir_etat] = lambda: EtatAPI()
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="désolé, je ne peux pas faire ça.", parsed=None, parsing_error=ValueError("mal formé")
    )

    try:
        client = TestClient(app)
        reponse = client.post(
            "/adapters/comprehension/ingerer",
            json={"client_id": "nouveau_client", "donnees_brutes": "???"},
        )

        assert reponse.status_code == 502
    finally:
        app.dependency_overrides.clear()


_REQUETE_INGESTION_BDD = {"client_id": "acme"}


def test_ingestion_depuis_bdd_accepte_une_traduction_valide(monkeypatch: pytest.MonkeyPatch) -> None:
    etat_test = EtatAPI()
    schema_agent = _SchemaComprehension(
        instance={
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [
                {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}
            ],
            "objectifs": [{"type": "minimiser_makespan"}],
        },
        description_metier="Une tâche T1 exécutée sur la ressource R1.",
        avertissements=["avertissement de l'agent de compréhension"],
    )
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=schema_agent
    )
    monkeypatch.setattr(routes_adapters, "dsn_lecture_seule_pour_client", lambda _client_id: "postgresql://x")
    monkeypatch.setattr(
        routes_adapters,
        "explorer_base_de_donnees",
        lambda *_a, **_k: ResultatExplorationBDD(
            reponse_brute="{}",
            requetes_executees=("SELECT * FROM taches",),
            donnees_json={"taches": [{"id": "T1"}]},
            avertissements=("avertissement de l'exploration",),
        ),
    )

    try:
        client = TestClient(app)
        reponse = client.post("/adapters/bdd/ingerer", json=_REQUETE_INGESTION_BDD)

        assert reponse.status_code == 200, reponse.json()
        corps = reponse.json()
        assert corps["structure_contraintes"] == "compatibilite_ressource_tache"
        assert corps["instance_id"] in etat_test.instances
        assert corps["avertissements"] == [
            "avertissement de l'exploration",
            "avertissement de l'agent de compréhension",
        ]
        assert corps["requetes_executees"] == ["SELECT * FROM taches"]
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_bdd_client_sans_dsn_configure_renvoie_404(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[obtenir_etat] = lambda: EtatAPI()
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=None
    )
    monkeypatch.setattr(routes_adapters, "dsn_lecture_seule_pour_client", lambda _client_id: None)

    try:
        client = TestClient(app)
        reponse = client.post("/adapters/bdd/ingerer", json=_REQUETE_INGESTION_BDD)

        assert reponse.status_code == 404
        assert "non configurée" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_bdd_connexion_impossible_renvoie_503(monkeypatch: pytest.MonkeyPatch) -> None:
    def _echec(*_a: object, **_k: object) -> None:
        raise psycopg.OperationalError("connexion refusée")

    app.dependency_overrides[obtenir_etat] = lambda: EtatAPI()
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=None
    )
    monkeypatch.setattr(routes_adapters, "dsn_lecture_seule_pour_client", lambda _client_id: "postgresql://x")
    monkeypatch.setattr(routes_adapters, "explorer_base_de_donnees", _echec)

    try:
        client = TestClient(app)
        reponse = client.post("/adapters/bdd/ingerer", json=_REQUETE_INGESTION_BDD)

        assert reponse.status_code == 503
        assert "injoignable" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_bdd_requete_exploration_echoue_renvoie_502(monkeypatch: pytest.MonkeyPatch) -> None:
    def _echec(*_a: object, **_k: object) -> None:
        raise psycopg.Error("relation inconnue")

    app.dependency_overrides[obtenir_etat] = lambda: EtatAPI()
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=None
    )
    monkeypatch.setattr(routes_adapters, "dsn_lecture_seule_pour_client", lambda _client_id: "postgresql://x")
    monkeypatch.setattr(routes_adapters, "explorer_base_de_donnees", _echec)

    try:
        client = TestClient(app)
        reponse = client.post("/adapters/bdd/ingerer", json=_REQUETE_INGESTION_BDD)

        assert reponse.status_code == 502
        assert "requête d'exploration a échoué" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_bdd_agent_exploration_non_conforme_renvoie_502(monkeypatch: pytest.MonkeyPatch) -> None:
    def _echec(*_a: object, **_k: object) -> None:
        raise ErreurReponseAgentInvalide("mal formé")

    app.dependency_overrides[obtenir_etat] = lambda: EtatAPI()
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=None
    )
    monkeypatch.setattr(routes_adapters, "dsn_lecture_seule_pour_client", lambda _client_id: "postgresql://x")
    monkeypatch.setattr(routes_adapters, "explorer_base_de_donnees", _echec)

    try:
        client = TestClient(app)
        reponse = client.post("/adapters/bdd/ingerer", json=_REQUETE_INGESTION_BDD)

        assert reponse.status_code == 502
        assert "agent d'exploration" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_bdd_agent_comprehension_non_conforme_renvoie_502(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app.dependency_overrides[obtenir_etat] = lambda: EtatAPI()
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="désolé, je ne peux pas faire ça.", parsed=None, parsing_error=ValueError("mal formé")
    )
    monkeypatch.setattr(routes_adapters, "dsn_lecture_seule_pour_client", lambda _client_id: "postgresql://x")
    monkeypatch.setattr(
        routes_adapters,
        "explorer_base_de_donnees",
        lambda *_a, **_k: ResultatExplorationBDD(
            reponse_brute="{}", requetes_executees=(), donnees_json={"taches": []}, avertissements=()
        ),
    )

    try:
        client = TestClient(app)
        reponse = client.post("/adapters/bdd/ingerer", json=_REQUETE_INGESTION_BDD)

        assert reponse.status_code == 502
        assert "agent de compréhension" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_bdd_relaie_le_rejet_du_garde_fou(monkeypatch: pytest.MonkeyPatch) -> None:
    etat_test = EtatAPI()
    schema_agent = _SchemaComprehension(
        instance={
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [],
            "objectifs": [{"type": "minimiser_makespan"}],
        },
        description_metier="Une tâche T1, sans ressource compatible identifiée.",
    )
    app.dependency_overrides[obtenir_etat] = lambda: etat_test
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=schema_agent
    )
    monkeypatch.setattr(routes_adapters, "dsn_lecture_seule_pour_client", lambda _client_id: "postgresql://x")
    monkeypatch.setattr(
        routes_adapters,
        "explorer_base_de_donnees",
        lambda *_a, **_k: ResultatExplorationBDD(
            reponse_brute="{}", requetes_executees=(), donnees_json={"taches": []}, avertissements=()
        ),
    )

    try:
        client = TestClient(app)
        reponse = client.post("/adapters/bdd/ingerer", json=_REQUETE_INGESTION_BDD)

        assert reponse.status_code == 422
        assert etat_test.instances == {}
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_bdd_resultat_trop_volumineux_renvoie_422(monkeypatch: pytest.MonkeyPatch) -> None:
    app.dependency_overrides[obtenir_etat] = lambda: EtatAPI()
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=None
    )
    monkeypatch.setattr(routes_adapters, "dsn_lecture_seule_pour_client", lambda _client_id: "postgresql://x")
    monkeypatch.setattr(
        routes_adapters,
        "explorer_base_de_donnees",
        lambda *_a, **_k: ResultatExplorationBDD(
            reponse_brute="{}", requetes_executees=(), donnees_json={"x": "y" * 6_000_000}, avertissements=()
        ),
    )

    try:
        client = TestClient(app)
        reponse = client.post("/adapters/bdd/ingerer", json=_REQUETE_INGESTION_BDD)

        assert reponse.status_code == 422
        assert "trop volumineux" in reponse.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_ingestion_depuis_bdd_schemas_personnalises_sont_transmis(monkeypatch: pytest.MonkeyPatch) -> None:
    captures: dict[str, object] = {}

    def _capture(_modele: object, _dsn: str, schemas: tuple[str, ...]) -> ResultatExplorationBDD:
        captures["schemas"] = schemas
        return ResultatExplorationBDD(
            reponse_brute="{}", requetes_executees=(), donnees_json={"taches": []}, avertissements=()
        )

    schema_agent = _SchemaComprehension(
        instance={
            "taches": [{"id": "T1"}],
            "ressources": [{"id": "R1"}],
            "contraintes": [
                {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 10}
            ],
            "objectifs": [{"type": "minimiser_makespan"}],
        },
        description_metier="peu importe",
    )
    app.dependency_overrides[obtenir_etat] = lambda: EtatAPI()
    app.dependency_overrides[construire_modele_comprehension] = lambda: ModeleFactice(
        raw_content="{}", parsed=schema_agent
    )
    monkeypatch.setattr(routes_adapters, "dsn_lecture_seule_pour_client", lambda _client_id: "postgresql://x")
    monkeypatch.setattr(routes_adapters, "explorer_base_de_donnees", _capture)

    try:
        client = TestClient(app)
        client.post("/adapters/bdd/ingerer", json={"client_id": "acme", "schemas": ["public", "vente"]})

        assert captures["schemas"] == ("public", "vente")
    finally:
        app.dependency_overrides.clear()
