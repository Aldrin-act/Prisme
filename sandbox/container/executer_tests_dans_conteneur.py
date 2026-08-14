"""Harnais exécuté À L'INTÉRIEUR du conteneur jetable — mode audit des tests
générés par l'agent Testeur (canal d'audit uniquement, voir
`generation/agents/testeur.py` : ne fait jamais gagner ni perdre
l'acceptation du solveur, seule la cascade de validation en décide).

Distinct de `executer_dans_conteneur.py` (mode solveur, inchangé) : même
image, invoqué avec un `entrypoint=` docker-py explicite plutôt que
l'ENTRYPOINT par défaut de l'image (voir `sandbox/runner.py::
executer_tests_dans_sandbox`) — pour ne jamais toucher au contrat du mode
solveur, sécurité-sensible (§5.3/§7).

Charge le solveur candidat monté en lecture seule sous le nom de module fixe
`solveur_candidat` (contrat avec les tests générés : `from solveur_candidat
import resoudre`, voir `generation/prompts/testeur.md`), exécute pytest EN
PROCESS sur le module de tests également monté en lecture seule, et écrit un
unique objet JSON sur la sortie standard — pas le format texte de pytest —
pour que l'hôte le parse sans plugin tiers (aucune dépendance pip au-delà de
`pytest` lui-même, voir Dockerfile : ni pytest-json-report ni équivalent).

Usage : executer_tests_dans_conteneur.py <chemin_solveur> <chemin_tests>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


class _CollecteurResultats:
    """Plugin pytest en process (pas de dépendance pip supplémentaire, voir
    docstring module) : un seul hook. On ne garde que la phase `call`
    (le corps du test s'est exécuté) et la phase `setup` quand elle échoue
    (erreur de fixture avant même d'atteindre le corps) — sinon un test cassé
    à la préparation n'apparaîtrait jamais dans `tests`. `teardown` est
    délibérément ignoré (erreurs de nettoyage de fixture, hors du périmètre
    d'un canal d'audit informationnel)."""

    def __init__(self) -> None:
        self.resultats: list[dict[str, object]] = []

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
            self.resultats.append(
                {
                    "nom": report.nodeid,
                    # Simplification assumée : un test "skipped" est reporté ici comme
                    # `reussi=False` (le contrat JSON est binaire, un audit informationnel
                    # n'a pas besoin d'un troisième état).
                    "reussi": report.outcome == "passed",
                    "message": None if report.outcome == "passed" else str(report.longrepr)[:2000],
                }
            )


def main() -> None:
    chemin_solveur, chemin_tests = sys.argv[1], sys.argv[2]

    # `solveur_candidat` doit être importable PAR CE NOM (contrat avec les tests
    # générés) — d'où l'ajout au sys.path plutôt qu'un chargement importlib.util
    # anonyme comme dans executer_dans_conteneur.py (qui n'a pas ce besoin : rien
    # là-bas n'importe le solveur par son nom de module).
    sys.path.insert(0, str(Path(chemin_solveur).parent))

    collecteur = _CollecteurResultats()
    try:
        # no:cacheprovider : évite une tentative d'écriture de .pytest_cache/ dans
        # /mnt, monté en lecture seule (échec silencieux sinon, mais autant l'éviter
        # explicitement plutôt que de compter sur la dégradation de pytest).
        code_sortie = pytest.main(["-q", "-p", "no:cacheprovider", chemin_tests], plugins=[collecteur])
    except Exception as erreur:  # pytest ne devrait jamais lever, mais le conteneur doit
        # TOUJOURS produire un JSON exploitable côté hôte, jamais planter sans trace.
        print(json.dumps({"tests": [], "erreur": f"pytest n'a pas pu s'exécuter : {erreur}"}))
        return

    # OK (0) et TESTS_FAILED (1) sont deux exécutions RÉUSSIES du point de vue du
    # harnais : certains tests générés ont juste échoué, ce n'est jamais une erreur
    # de collecte. INTERRUPTED/INTERNAL_ERROR/USAGE_ERROR/NO_TESTS_COLLECTED (2-5)
    # signalent que pytest n'a pas pu collecter/exécuter le module — remonté comme
    # `erreur`, distinction que `RapportTestsSandbox.reussi` doit pouvoir faire.
    if code_sortie in (pytest.ExitCode.OK, pytest.ExitCode.TESTS_FAILED):
        print(json.dumps({"tests": collecteur.resultats, "erreur": None}))
    else:
        print(
            json.dumps(
                {
                    "tests": collecteur.resultats,
                    "erreur": f"pytest n'a pas pu collecter/exécuter les tests (code {code_sortie})",
                }
            )
        )


if __name__ == "__main__":
    main()
