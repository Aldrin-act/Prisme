"""Couche 1 (§6.1) : `generation.graph` exécute réellement du code Python
(comme `test_executer.py`), d'où `integration/` plutôt que
`unit/`. Aucun appel LLM réel — un faux modèle par agent (voir
`tests/unit/aides_test_agents.py`), injecté via `config["configurable"]
["fabrique_modele"]` (voir `generation.graph._modele`), remplace
`construire_modele_pour_agent` sans reconstruire le graphe."""

from __future__ import annotations

from pathlib import Path

import pytest

import generation.graph as g
from generation.agents import (
    analyste,
    architecte,
    benchmarker,
    debugger,
    documentation,
    generateur,
    testeur,
)
from sandbox.runner import ErreurExecutionSandbox, RapportTestsSandbox, ResultatTestUnitaire
from scripts import _solveur_minimal
from tests.unit.aides_test_agents import ModeleFactice

# Respecte l'allowlist AST (generation/validation_statique.py) et résout
# réellement le FJSP (ordonnancement par liste heuristique, `scripts/_solveur_minimal.py`) — un
# stub qui renverrait juste un Planning vide échouerait légitimement la cascade réelle contre le
# banc synthétique.
CODE_BON = Path(_solveur_minimal.__file__).read_text(encoding="utf-8")

CODE_INVALIDE = "import os\n\n\ndef resoudre(instance):\n    return None\n"


@pytest.fixture(autouse=True)
def _registre_analyste_indisponible(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ce fichier ne teste que le câblage du graphe et l'exécution
    heuristique réelle (voir docstring de module) — jamais la persistance. Sans ce
    fixture, l'outil `rechercher_instances_similaires` de l'Analyste (voir
    `generation/agents/analyste.py`) toucherait pour de vrai le schéma
    `public` de Postgres dès qu'il est joignable sur la machine de test ;
    `registre_test` (`conftest.py`, schéma isolé + nettoyage) est réservé
    aux tests qui testent le registre lui-même."""
    import solver_store.registry as registry_module

    def _leve(*args: object, **kwargs: object) -> None:
        raise ConnectionError("registre non disponible dans ce fichier de test (intentionnel)")

    monkeypatch.setattr(registry_module, "Registre", _leve)


def _reponses_communes() -> dict[str, object]:
    """Une réponse par agent, suffisante pour amener le pipeline jusqu'à la
    Validation sans jamais échouer avant (Reviewer désactivé, voir
    `generation/graph.py::_construire_graphe`) — chaque test surcharge
    ensuite `generateur`/`debugger` selon le scénario."""
    return {
        "analyste": ModeleFactice(
            raw_content="{}",
            parsed=analyste._SchemaAnalyse(entrees="I", sorties="P", contraintes_a_couvrir=["c1"]),
        ),
        "benchmarker": ModeleFactice(
            raw_content="{}",
            parsed=benchmarker._SchemaBenchmark(
                recommandation=benchmarker._SchemaRecommandation(
                    algorithme="tabu_search", raison="petite instance"
                )
            ),
        ),
        "architecte": ModeleFactice(
            raw_content="{}",
            parsed=architecte._SchemaConception(variables="v", contraintes_modele="c", objectif="o"),
        ),
        "generateur": ModeleFactice(raw_content="{}", parsed=generateur._SchemaGenerationCode(code=CODE_BON)),
        "testeur": ModeleFactice(
            raw_content="{}", parsed=testeur._SchemaTests(code_tests="def test_x(): assert True")
        ),
        "documentation": ModeleFactice(
            raw_content="{}",
            parsed=documentation._SchemaDocumentation(resume="r", limites_connues="l"),
        ),
    }


def _fabrique(specs: dict[str, object | list[object]]):
    files = {nom: iter(v if isinstance(v, list) else [v] * 100) for nom, v in specs.items()}

    def fabrique_modele(nom_agent: str):
        return next(files[nom_agent])

    return fabrique_modele


def _sandbox_indisponible(code_source: str, code_tests: str, limites=None):
    """Stub par défaut pour `executer_tests_dans_sandbox` — ce fichier teste
    l'orchestration LangGraph avec de faux modèles (voir docstring module),
    jamais un appel réel (LLM ou Docker) : sans ce monkeypatch, le
    comportement de ces tests dépendrait de si `prisme-sandbox:latest` est
    construite sur la machine qui les lance, non déterministe. Simule le cas
    « sandbox indisponible » — le nœud test_sandbox doit dégrader en silence
    (voir `generation/graph.py::_noeud_test_sandbox`)."""
    raise ErreurExecutionSandbox("stub : sandbox non disponible dans ce test")


def _invoquer(
    specs: dict[str, object | list[object]],
    *,
    executer_tests_sandbox_stub=_sandbox_indisponible,
) -> g.ResultatPipelineAvecBoucle:
    graphe = g._construire_graphe().compile()
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(g, "executer_tests_dans_sandbox", executer_tests_sandbox_stub)
        etat_final = graphe.invoke(
            {"instance_exemple": None},
            config={"configurable": {"fabrique_modele": _fabrique(specs)}, "recursion_limit": 60},
        )
    resultat = etat_final["resultat_final"]
    assert resultat is not None
    return resultat


def test_pipeline_reussi_directement() -> None:
    """Reviewer désactivé (voir `generation/graph.py::_construire_graphe`) :
    un succès de Validation dès la première tentative suffit, sans détour."""
    specs = _reponses_communes()

    resultat = _invoquer(specs)

    assert resultat.reussi is True
    assert resultat.code_final.strip() == CODE_BON.strip()
    assert resultat.boucle_reparation.nombre_tentatives == 1
    assert len(resultat.boucle_reparation.tentatives) == 1
    assert resultat.boucle_reparation.tentatives[0].reussi is True
    assert resultat.documentation is not None
    # `_sandbox_indisponible` (stub par défaut de `_invoquer`) simule un sandbox
    # injoignable — dégradation silencieuse attendue du nœud test_sandbox
    # (meilleur-effort, voir generation/graph.py::_noeud_test_sandbox).
    assert resultat.rapport_tests_sandbox is None


def test_pipeline_renvoie_au_debugger_si_tests_sandbox_echouent_puis_reussissent() -> None:
    """§6.6bis : un échec des tests générés en sandbox est traité comme un
    échec de cascade — renvoie directement au Debugger (Reviewer désactivé),
    puis revalide ; succès si la seconde tentative des tests sandbox passe."""
    specs = _reponses_communes()
    specs["debugger"] = ModeleFactice(
        raw_content="{}",
        parsed=debugger._SchemaCorrectionTestsSandbox(
            cible="solveur", code=CODE_BON, tests="def test_x(): assert True", cause="tests sandbox en échec"
        ),
    )

    appels = {"n": 0}

    def stub_echoue_puis_reussit(code_source: str, code_tests: str, limites=None) -> RapportTestsSandbox:
        appels["n"] += 1
        if appels["n"] == 1:
            return RapportTestsSandbox(
                tests=(ResultatTestUnitaire("test_x", False, "AssertionError"),), erreur=None
            )
        return RapportTestsSandbox(tests=(ResultatTestUnitaire("test_x", True, None),), erreur=None)

    resultat = _invoquer(specs, executer_tests_sandbox_stub=stub_echoue_puis_reussit)

    assert appels["n"] == 2
    assert resultat.reussi is True
    assert resultat.rapport_tests_sandbox is not None
    assert resultat.rapport_tests_sandbox.reussi is True
    assert resultat.boucle_reparation.nombre_tentatives == 2


def test_pipeline_corrige_le_test_genere_plutot_que_le_solveur_si_designe_fautif() -> None:
    """Le Debugger peut désigner le test généré comme fautif plutôt que le
    solveur (voir generation/agents/debugger.py::corriger_solveur_ou_tests) —
    `tests_generes` doit alors refléter le test corrigé, `code_final` rester
    inchangé."""
    tests_corriges = "from solveur_candidat import resoudre\n\n\ndef test_x_corrige():\n    assert True\n"
    specs = _reponses_communes()
    specs["debugger"] = ModeleFactice(
        raw_content="{}",
        parsed=debugger._SchemaCorrectionTestsSandbox(
            cible="tests", code=CODE_BON, tests=tests_corriges, cause="le test attendait une valeur erronée"
        ),
    )

    appels = {"n": 0}

    def stub_echoue_puis_reussit(code_source: str, code_tests: str, limites=None) -> RapportTestsSandbox:
        appels["n"] += 1
        if appels["n"] == 1:
            return RapportTestsSandbox(
                tests=(ResultatTestUnitaire("test_x", False, "AssertionError"),), erreur=None
            )
        return RapportTestsSandbox(tests=(ResultatTestUnitaire("test_x_corrige", True, None),), erreur=None)

    resultat = _invoquer(specs, executer_tests_sandbox_stub=stub_echoue_puis_reussit)

    assert resultat.reussi is True
    assert resultat.code_final.strip() == CODE_BON.strip()  # solveur jamais touché
    assert resultat.tests_generes == tests_corriges  # le test corrigé remplace l'original


def test_pipeline_echoue_si_tests_sandbox_echouent_apres_epuisement_des_tentatives() -> None:
    """Cascade toujours au vert, mais les tests générés ne passent jamais en
    sandbox : le pipeline doit finir par un échec honnête (fin_boucle),
    jamais enregistrer un solveur dont les tests générés échouent encore."""
    specs = _reponses_communes()
    specs["debugger"] = ModeleFactice(
        raw_content="{}",
        parsed=debugger._SchemaCorrectionTestsSandbox(
            cible="solveur", code=CODE_BON, tests="def test_x(): assert True", cause="tests sandbox en échec"
        ),
    )

    def stub_toujours_en_echec(code_source: str, code_tests: str, limites=None) -> RapportTestsSandbox:
        return RapportTestsSandbox(tests=(ResultatTestUnitaire("test_x", False, "AssertionError"),), erreur=None)

    resultat = _invoquer(specs, executer_tests_sandbox_stub=stub_toujours_en_echec)

    assert resultat.reussi is False
    assert resultat.rapport_tests_sandbox is not None
    assert resultat.rapport_tests_sandbox.reussi is False
    assert resultat.boucle_reparation.nombre_tentatives == g.MAX_TENTATIVES_REPARATION


def test_pipeline_echoue_apres_epuisement_des_tentatives() -> None:
    specs = _reponses_communes()
    specs["generateur"] = ModeleFactice(
        raw_content="{}", parsed=generateur._SchemaGenerationCode(code=CODE_INVALIDE)
    )
    # Le code reste invalide (import os) — la validation échoue à chaque
    # tentative, le Debugger ne corrige jamais vraiment (renvoie le même
    # code invalide).
    specs["debugger"] = ModeleFactice(
        raw_content="{}", parsed=debugger._SchemaCorrection(code=CODE_INVALIDE, cause="tentative infructueuse")
    )

    resultat = _invoquer(specs)

    assert resultat.reussi is False
    assert resultat.boucle_reparation.reussi is False
    assert resultat.boucle_reparation.nombre_tentatives == g.MAX_TENTATIVES_REPARATION
    assert len(resultat.boucle_reparation.tentatives) == g.MAX_TENTATIVES_REPARATION
    assert resultat.documentation is None  # sautée en cas d'échec


class _ModeleFacticeCapturantSequence(ModeleFactice):
    """Contrairement à `_ModeleFacticeCapturant` (plus bas dans ce fichier),
    qui n'écrase qu'un seul `dernier_prompt`, celui-ci accumule le prompt de
    chaque appel — nécessaire pour vérifier qu'un historique grandit d'un
    appel à l'autre plutôt que de rejouer le même contenu."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.prompts: list[str] = []

    def with_structured_output(self, schema: type, include_raw: bool = True, method: str | None = None):
        runnable = super().with_structured_output(schema, include_raw, method)
        invoke_original = runnable.invoke

        def invoke_capturant(messages):
            self.prompts.append(messages[-1].content)
            return invoke_original(messages)

        runnable.invoke = invoke_capturant
        return runnable


def test_debugger_recoit_l_historique_des_tentatives_precedentes_de_cette_generation() -> None:
    """L'historique intra-boucle du Debugger (voir
    `generation/agents/debugger.py::corriger_code`,
    `generation/graph.py::_noeud_debugger`) doit grandir d'une tentative à
    l'autre, jamais rejouer le même contenu deux fois — et ne jamais
    contenir la tentative en cours, qui n'est pas encore connue."""
    specs = _reponses_communes()
    specs["generateur"] = ModeleFactice(
        raw_content="{}", parsed=generateur._SchemaGenerationCode(code=CODE_INVALIDE)
    )
    modele_debugger = _ModeleFacticeCapturantSequence(
        raw_content="{}", parsed=debugger._SchemaCorrection(code=CODE_INVALIDE, cause="tentative infructueuse")
    )
    specs["debugger"] = modele_debugger

    _invoquer(specs)

    assert len(modele_debugger.prompts) == g.MAX_TENTATIVES_REPARATION - 1
    assert "Aucune tentative précédente dans cette génération." in modele_debugger.prompts[0]
    for indice, prompt in enumerate(modele_debugger.prompts):
        for numero_deja_vu in range(1, indice + 1):
            assert f"Tentative {numero_deja_vu} :" in prompt
        assert f"Tentative {indice + 1} :" not in prompt


def test_debugger_jamais_appele_sur_la_derniere_tentative_epuisee() -> None:
    """Le Debugger ne doit jamais être invoqué pour une 11e tentative — le
    contrôle de la borne se fait dans le routeur, avant l'arête vers lui."""
    specs = _reponses_communes()
    specs["generateur"] = ModeleFactice(
        raw_content="{}", parsed=generateur._SchemaGenerationCode(code=CODE_INVALIDE)
    )

    appels_debugger = 0
    modele_debugger = ModeleFactice(
        raw_content="{}", parsed=debugger._SchemaCorrection(code=CODE_INVALIDE, cause="c")
    )
    original_invoke = modele_debugger.with_structured_output

    def with_structured_output_compte(*args, **kwargs):
        nonlocal appels_debugger
        appels_debugger += 1
        return original_invoke(*args, **kwargs)

    modele_debugger.with_structured_output = with_structured_output_compte
    specs["debugger"] = modele_debugger

    resultat = _invoquer(specs)

    assert resultat.boucle_reparation.nombre_tentatives == g.MAX_TENTATIVES_REPARATION
    # Le Debugger corrige après les tentatives 1..9 (jamais après la 10e).
    assert appels_debugger == g.MAX_TENTATIVES_REPARATION - 1


def test_boucle_epuisee_ne_leve_pas_graphrecursionerror() -> None:
    """Couvre le risque de limite de récursion : 5 nœuds de mise en place +
    10 × (test_sandbox + validation + debugger) doit rester sous la limite
    passée à `.invoke()` (voir `generation.graph._LIMITE_RECURSION`)."""
    specs = _reponses_communes()
    specs["generateur"] = ModeleFactice(
        raw_content="{}", parsed=generateur._SchemaGenerationCode(code=CODE_INVALIDE)
    )
    specs["debugger"] = ModeleFactice(
        raw_content="{}", parsed=debugger._SchemaCorrection(code=CODE_INVALIDE, cause="c")
    )

    resultat = _invoquer(specs)  # ne doit lever aucune exception

    assert resultat.boucle_reparation.nombre_tentatives == g.MAX_TENTATIVES_REPARATION


def test_stream_produit_des_evenements_etape_puis_le_resultat_final() -> None:
    specs = _reponses_communes()

    graphe = g._construire_graphe().compile()
    elements: list = []
    for mode, payload in graphe.stream(
        {"instance_exemple": None},
        stream_mode=["custom", "values"],
        config={"configurable": {"fabrique_modele": _fabrique(specs)}, "recursion_limit": 60},
    ):
        if mode == "custom":
            elements.append(payload)

    noms_agents = [e["agent"] for e in elements]
    assert "benchmarker" in noms_agents
    assert "documentation" in noms_agents
    assert all(e["statut"] in ("en_cours", "termine", "echec") for e in elements)


def _fabrique_qui_explose_sur(agent_cible: str, specs: dict[str, object | list[object]]):
    """Comme `_fabrique`, mais lève pour `agent_cible` — simule une panne en cours de
    pipeline (§6.6), pour vérifier que `tenter_generation_avec_boucle_stream` a bien
    yield les `ResultatPartiel` des agents précédents avant que l'exception ne remonte."""
    fabrique_normale = _fabrique(specs)

    def fabrique_modele(nom_agent: str):
        if nom_agent == agent_cible:
            raise RuntimeError(f"panne simulée sur {agent_cible}")
        return fabrique_normale(nom_agent)

    return fabrique_modele


def test_stream_persiste_les_champs_deja_produits_avant_un_plantage(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un plantage en cours de pipeline (pas l'échec « propre » après épuisement des
    tentatives) ne doit pas faire perdre ce que les agents précédents ont déjà produit
    (§6.6) — voir `generation/graph.py::_partiels_nouveaux`. Le Testeur explose, donc
    Analyste/Benchmarker/Architecte/Développeur ont déjà tourné, jamais le Testeur."""
    specs = _reponses_communes()
    monkeypatch.setattr(g, "construire_modele_pour_agent", _fabrique_qui_explose_sur("testeur", specs))

    elements: list = []
    with pytest.raises(RuntimeError, match="panne simulée sur testeur"):
        for item in g.tenter_generation_avec_boucle_stream(None):
            elements.append(item)

    champs = {e.champ: e.valeur for e in elements if isinstance(e, g.ResultatPartiel)}
    assert champs["specification"]
    assert champs["algorithme"] == "tabu_search"
    assert champs["plan_technique"]
    assert champs["code_genere"].strip() == CODE_BON.strip()
    assert "tests_generes" not in champs  # le testeur n'a jamais eu la chance de produire ça


def test_stream_persiste_les_tentatives_deja_accumulees_avant_un_plantage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Une tentative déjà en échec (via Validation — Reviewer désactivé, donc
    déjà accumulée dans l'état LangGraph) ne doit pas être perdue si le
    Debugger plante juste après."""
    specs = _reponses_communes()
    specs["generateur"] = ModeleFactice(
        raw_content="{}", parsed=generateur._SchemaGenerationCode(code=CODE_INVALIDE)
    )
    monkeypatch.setattr(g, "construire_modele_pour_agent", _fabrique_qui_explose_sur("debugger", specs))

    elements: list = []
    with pytest.raises(RuntimeError, match="panne simulée sur debugger"):
        for item in g.tenter_generation_avec_boucle_stream(None):
            elements.append(item)

    tentatives = [e.valeur for e in elements if isinstance(e, g.ResultatPartiel) and e.champ == "tentative"]
    assert len(tentatives) == 1
    assert tentatives[0].reussi is False


class _ModeleFacticeCapturant(ModeleFactice):
    """Capture le dernier prompt envoyé — vérifie que `_noeud_analyste` transmet bien la
    structure de l'instance reçue par le graphe jusqu'au prompt de l'agent, sans dépendre
    d'un vrai appel LLM."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.dernier_prompt: str | None = None

    def with_structured_output(self, schema: type, include_raw: bool = True, method: str | None = None):
        runnable = super().with_structured_output(schema, include_raw, method)
        invoke_original = runnable.invoke

        def invoke_capturant(messages):
            self.dernier_prompt = messages[-1].content
            return invoke_original(messages)

        runnable.invoke = invoke_capturant
        return runnable


def test_noeud_analyste_recoit_la_structure_de_linstance_du_graphe() -> None:
    specs = _reponses_communes()
    modele_analyste = _ModeleFacticeCapturant(
        raw_content="{}", parsed=analyste._SchemaAnalyse(entrees="e", sorties="s", contraintes_a_couvrir=["c"])
    )
    specs["analyste"] = modele_analyste

    instance_avec_echeance = {
        "taches": [{"id": "T1"}],
        "ressources": [{"id": "R1"}],
        "contraintes": [
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 1},
            {"type": "echeance", "tache": "T1", "echeance": 5},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }

    graphe = g._construire_graphe().compile()
    graphe.invoke(
        {"instance_exemple": instance_avec_echeance},
        config={"configurable": {"fabrique_modele": _fabrique(specs)}, "recursion_limit": 60},
    )

    assert modele_analyste.dernier_prompt is not None
    assert "echeance" in modele_analyste.dernier_prompt
    assert "compatibilite_ressource_tache" in modele_analyste.dernier_prompt
