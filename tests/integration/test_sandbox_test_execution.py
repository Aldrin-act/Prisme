"""Couche 1 (§6.1), Docker requis. Vérifie le nouveau mode audit du bac à
sable (`sandbox/runner.py::executer_tests_dans_sandbox`) — l'exécution
réelle des tests pytest générés par l'agent Testeur, jamais un critère
d'acceptation du solveur (voir `generation/agents/testeur.py`), pas la
cascade de validation elle-même (déjà couverte ailleurs).
"""

from __future__ import annotations

from sandbox.runner import executer_tests_dans_sandbox

CODE_SOLVEUR = "def resoudre(instance):\n    return None\n"


def test_rapport_reflete_tests_reussis_et_echoues(image_sandbox: str) -> None:
    code_tests = (
        "from solveur_candidat import resoudre\n\n\n"
        "def test_qui_passe():\n    assert resoudre(None) is None\n\n\n"
        "def test_qui_echoue():\n    assert resoudre(None) is not None\n"
    )
    rapport = executer_tests_dans_sandbox(CODE_SOLVEUR, code_tests)

    assert rapport.erreur is None
    assert rapport.reussi is False
    par_nom = {t.nom.rsplit("::", 1)[-1]: t for t in rapport.tests}
    assert par_nom["test_qui_passe"].reussi is True
    assert par_nom["test_qui_echoue"].reussi is False
    assert par_nom["test_qui_echoue"].message is not None


def test_erreur_de_collecte_peuplee_si_module_de_tests_casse(image_sandbox: str) -> None:
    code_tests_casse = "def test_syntaxe_invalide(:\n    pass\n"
    rapport = executer_tests_dans_sandbox(CODE_SOLVEUR, code_tests_casse)

    assert rapport.erreur is not None
    assert rapport.reussi is False
    assert rapport.tests == ()


def test_isolation_reseau_tient_meme_pour_un_test_genere(image_sandbox: str) -> None:
    """Défense en profondeur (comme test_sandbox_securite.py) : un test généré
    malveillant/compromis ne doit pas pouvoir joindre le réseau non plus —
    surface d'attaque distincte du solveur lui-même. Ici la coupure réseau
    est vue par pytest comme un échec de test normal (le conteneur, lui,
    sort avec le code 0 — contrairement au mode solveur où une exception non
    interceptée fait échouer tout le processus)."""
    code_tests_reseau = (
        "import socket\n\n\n"
        "def test_tentative_acces_reseau():\n"
        "    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)\n"
        "    s.settimeout(3)\n"
        "    s.connect(('8.8.8.8', 53))\n"
    )
    rapport = executer_tests_dans_sandbox(CODE_SOLVEUR, code_tests_reseau)

    assert rapport.erreur is None
    assert rapport.reussi is False
    assert len(rapport.tests) == 1
    assert rapport.tests[0].reussi is False
