"""Couche 1 (§6.1) : parties pures de `generation.graph` — les routeurs
(`_route_apres_reviewer`/`_route_apres_validation`, de simples fonctions
d'état → chaîne, sans effet de bord) et `_valider_completement` (aucun appel
LLM, voir la même approche que l'ancien `tests/unit/test_loop.py`). Le
comportement du graphe complet (boucle de réparation réelle, streaming) est
couvert par `tests/integration/test_graph_pipeline.py`."""

from __future__ import annotations

import generation.graph as g
from generation.agents.reviewer import ResultatRevue
from generation.validation_statique import ResultatValidationStatique
from sandbox.runner import RapportTestsSandbox, ResultatTestUnitaire
from validation_engine.cascade import VerdictCascade

CODE_BON = """
from __future__ import annotations

from dsl.schema import Planning


def resoudre(instance):
    return Planning(operations=[])
"""

CODE_INVALIDE_STATIQUEMENT = "import os\n\n\ndef resoudre(instance):\n    return None\n"


def _revue(approuve: bool) -> ResultatRevue:
    return ResultatRevue(reponse_brute="{}", approuve=approuve, problemes=())


def test_valider_completement_transmet_la_tolerance_a_evaluer_cascade(monkeypatch) -> None:
    appels: list[tuple[float, bool]] = []

    def faux_evaluer_cascade(solveur, tolerance_relative=0.0, comparer_affectation=True):
        appels.append((tolerance_relative, comparer_affectation))
        return VerdictCascade(())

    monkeypatch.setattr(g, "evaluer_cascade", faux_evaluer_cascade)

    validation, erreur_exec, verdict = g._valider_completement(CODE_BON, 0.10, False)

    assert appels == [(0.10, False)]
    assert validation.valide is True
    assert erreur_exec is None
    assert verdict is not None
    assert verdict.reussi is True


def test_valider_completement_rejette_avant_cascade_si_validation_statique_echoue(monkeypatch) -> None:
    appele = False

    def faux_evaluer_cascade(solveur, tolerance_relative=0.0, comparer_affectation=True):
        nonlocal appele
        appele = True
        return VerdictCascade(())

    monkeypatch.setattr(g, "evaluer_cascade", faux_evaluer_cascade)

    validation, erreur_exec, verdict = g._valider_completement(CODE_INVALIDE_STATIQUEMENT, 0.10, False)

    assert validation.valide is False
    assert erreur_exec is None
    assert verdict is None
    assert appele is False  # jamais atteint la cascade, arrêté dès la validation statique


def test_route_apres_reviewer_va_a_validation_si_approuve() -> None:
    etat: g.EtatGeneration = {"derniere_revue": _revue(True), "numero_tentative": 1}
    assert g._route_apres_reviewer(etat) == "validation"


def test_route_apres_reviewer_va_au_debugger_si_rejete_et_tentatives_restantes() -> None:
    etat: g.EtatGeneration = {"derniere_revue": _revue(False), "numero_tentative": 5}
    assert g._route_apres_reviewer(etat) == "debugger"


def test_route_apres_reviewer_va_a_fin_boucle_si_rejete_et_tentatives_epuisees() -> None:
    etat: g.EtatGeneration = {
        "derniere_revue": _revue(False),
        "numero_tentative": g.MAX_TENTATIVES_REPARATION,
    }
    assert g._route_apres_reviewer(etat) == "fin_boucle"


def test_route_apres_validation_va_a_documentation_si_reussi() -> None:
    """test_sandbox tourne désormais avant Reviewer/Validation, pas après
    (§6.6bis) — une validation réussie va directement à Documentation."""
    etat: g.EtatGeneration = {"boucle_reussie": True, "numero_tentative": 3}
    assert g._route_apres_validation(etat) == "documentation"


def test_route_apres_validation_va_au_debugger_si_echec_et_tentatives_restantes() -> None:
    etat: g.EtatGeneration = {"boucle_reussie": False, "numero_tentative": 5}
    assert g._route_apres_validation(etat) == "debugger"


_RAPPORT_TESTS_REUSSI = RapportTestsSandbox(tests=(ResultatTestUnitaire("test_x", True, None),), erreur=None)
_RAPPORT_TESTS_ECHEC = RapportTestsSandbox(
    tests=(ResultatTestUnitaire("test_x", False, "AssertionError"),), erreur=None
)


def test_route_apres_test_sandbox_va_a_validation_si_sandbox_indisponible() -> None:
    """`rapport_tests_sandbox is None` (Docker injoignable, image absente...)
    ne doit jamais bloquer — voir `_noeud_test_sandbox`. Le Reviewer est
    désactivé (voir `_construire_graphe`), donc la dégradation va directement
    à Validation."""
    etat: g.EtatGeneration = {"rapport_tests_sandbox": None, "numero_tentative": 3}
    assert g._route_apres_test_sandbox(etat) == "validation"


def test_route_apres_test_sandbox_va_a_validation_si_tests_reussis() -> None:
    etat: g.EtatGeneration = {"rapport_tests_sandbox": _RAPPORT_TESTS_REUSSI, "numero_tentative": 3}
    assert g._route_apres_test_sandbox(etat) == "validation"


def test_route_apres_test_sandbox_va_au_debugger_si_tests_en_echec_et_tentatives_restantes() -> None:
    etat: g.EtatGeneration = {"rapport_tests_sandbox": _RAPPORT_TESTS_ECHEC, "numero_tentative": 5}
    assert g._route_apres_test_sandbox(etat) == "debugger"


def test_route_apres_test_sandbox_va_a_fin_boucle_si_tests_en_echec_et_tentatives_epuisees() -> None:
    etat: g.EtatGeneration = {
        "rapport_tests_sandbox": _RAPPORT_TESTS_ECHEC,
        "numero_tentative": g.MAX_TENTATIVES_REPARATION,
    }
    assert g._route_apres_test_sandbox(etat) == "fin_boucle"


def _resultat_pipeline_minimal(**overrides: object) -> g.ResultatPipelineAvecBoucle:
    validation_ok = ResultatValidationStatique(valide=True, violations=())
    boucle = g.ResultatBoucleReparation(
        code_initial=CODE_BON,
        tentatives=(),
        code_final=CODE_BON,
        reussi=True,
        nombre_tentatives=1,
        derniere_revue=_revue(True),
        derniere_validation_statique=validation_ok,
        derniere_erreur_execution=None,
        dernier_verdict_cascade=VerdictCascade(()),
    )
    champs: dict[str, object] = {
        "specification": "s",
        "plan_technique": "p",
        "algorithme_recommande": "tabu_search",
        "justification_algorithme": "petite instance",
        "parametres_algorithme": {},
        "code_genere": CODE_BON,
        "tests_generes": "def test_x(): assert True",
        "boucle_reparation": boucle,
        "code_final": CODE_BON,
        "validation_statique": validation_ok,
        "erreur_execution": None,
        "verdict_cascade": VerdictCascade(()),
        "rapport_tests_sandbox": None,
        "documentation": None,
    }
    champs.update(overrides)
    return g.ResultatPipelineAvecBoucle(**champs)


def test_reussi_est_vrai_si_rapport_tests_sandbox_absent() -> None:
    """Sandbox indisponible : n'empêche jamais le succès global (meilleur-effort)."""
    resultat = _resultat_pipeline_minimal(rapport_tests_sandbox=None)
    assert resultat.reussi is True


def test_reussi_est_vrai_si_tests_sandbox_reussis() -> None:
    resultat = _resultat_pipeline_minimal(rapport_tests_sandbox=_RAPPORT_TESTS_REUSSI)
    assert resultat.reussi is True


def test_reussi_est_faux_si_tests_sandbox_en_echec_malgre_cascade_au_vert() -> None:
    """Régression : avant §6.6bis, `reussi` ignorait `rapport_tests_sandbox` —
    un solveur pouvait être enregistré malgré des tests générés jamais
    corrigés après épuisement des tentatives."""
    resultat = _resultat_pipeline_minimal(rapport_tests_sandbox=_RAPPORT_TESTS_ECHEC)
    assert resultat.reussi is False


def test_route_apres_validation_va_a_fin_boucle_si_echec_et_tentatives_epuisees() -> None:
    etat: g.EtatGeneration = {
        "boucle_reussie": False,
        "numero_tentative": g.MAX_TENTATIVES_REPARATION,
    }
    assert g._route_apres_validation(etat) == "fin_boucle"


def test_message_echec_validation_priorise_la_validation_statique() -> None:
    from generation.validation_statique import ResultatValidationStatique

    validation = ResultatValidationStatique(valide=False, violations=("import interdit: os",))
    message = g._message_echec_validation(validation, "erreur ignorée", VerdictCascade(()))
    assert "Validation statique échouée" in message
    assert "import interdit: os" in message


def test_message_echec_validation_signale_erreur_execution() -> None:
    from generation.validation_statique import ResultatValidationStatique

    validation = ResultatValidationStatique(valide=True, violations=())
    message = g._message_echec_validation(validation, "boom", None)
    assert "Erreur d'exécution" in message
    assert "boom" in message


def test_reviewer_est_absent_du_graphe_compile() -> None:
    """Reviewer désactivé : son nœud ne doit pas apparaître dans le graphe
    réellement exécuté, même si `_noeud_reviewer`/`_route_apres_reviewer`
    restent définis dans le module (réactivation possible plus tard)."""
    noeuds = g._construire_graphe().compile().get_graph().nodes
    assert "reviewer" not in noeuds
    assert "test_sandbox" in noeuds
    assert "validation" in noeuds
