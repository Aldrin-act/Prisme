"""Couche 1 (§6.1) : `sandbox.runner._solveur_supporte_horizon_gele` est un `ast.parse` pur
(jamais d'exécution de code, §5.3) — le reste de `sandbox/runner.py` nécessite un vrai Docker et
est couvert par `tests/integration/test_sandbox_execution.py`."""

from __future__ import annotations

from sandbox.runner import _solveur_supporte_horizon_gele

_SOURCE_ANCIENNE_SIGNATURE = """
def resoudre(instance):
    return None
"""

_SOURCE_NOUVELLE_SIGNATURE = """
def resoudre(instance, planning_precedent=None, horizon_gele_jours=0):
    return None
"""

_SOURCE_NOUVELLE_SIGNATURE_KWONLY = """
def resoudre(instance, *, planning_precedent=None, horizon_gele_jours=0):
    return None
"""

_SOURCE_UN_SEUL_DES_DEUX_PARAMETRES = """
def resoudre(instance, planning_precedent=None):
    return None
"""

_SOURCE_SANS_RESOUDRE = """
def autre_fonction(instance):
    return None
"""


def test_solveur_ancienne_signature_ne_supporte_pas_horizon_gele() -> None:
    assert _solveur_supporte_horizon_gele(_SOURCE_ANCIENNE_SIGNATURE) is False


def test_solveur_nouvelle_signature_supporte_horizon_gele() -> None:
    assert _solveur_supporte_horizon_gele(_SOURCE_NOUVELLE_SIGNATURE) is True


def test_solveur_nouvelle_signature_kwonly_supporte_horizon_gele() -> None:
    assert _solveur_supporte_horizon_gele(_SOURCE_NOUVELLE_SIGNATURE_KWONLY) is True


def test_solveur_avec_un_seul_des_deux_nouveaux_parametres_ne_supporte_pas() -> None:
    assert _solveur_supporte_horizon_gele(_SOURCE_UN_SEUL_DES_DEUX_PARAMETRES) is False


def test_source_sans_fonction_resoudre_ne_supporte_pas() -> None:
    assert _solveur_supporte_horizon_gele(_SOURCE_SANS_RESOUDRE) is False


def test_source_syntaxiquement_invalide_ne_supporte_pas() -> None:
    assert _solveur_supporte_horizon_gele("def resoudre(:\n    invalide") is False
