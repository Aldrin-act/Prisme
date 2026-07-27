"""Couche 1 (§6.1) : parties pures de `generation.graph` — les routeurs
(`_route_apres_reviewer`/`_route_apres_validation`, de simples fonctions
d'état → chaîne, sans effet de bord) et `_valider_completement` (aucun appel
LLM, voir la même approche que l'ancien `tests/unit/test_loop.py`). Le
comportement du graphe complet (boucle de réparation réelle, streaming) est
couvert par `tests/integration/test_graph_pipeline.py`."""

from __future__ import annotations

import generation.graph as g
from generation.agents.reviewer import ResultatRevue
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
    etat: g.EtatGeneration = {"boucle_reussie": True, "numero_tentative": 3}
    assert g._route_apres_validation(etat) == "documentation"


def test_route_apres_validation_va_au_debugger_si_echec_et_tentatives_restantes() -> None:
    etat: g.EtatGeneration = {"boucle_reussie": False, "numero_tentative": 5}
    assert g._route_apres_validation(etat) == "debugger"


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
