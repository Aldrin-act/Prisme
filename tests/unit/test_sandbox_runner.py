"""Couche 1 (§6.1) : `sandbox.runner.solveur_supporte_horizon_gele` est un `ast.parse` pur
(jamais d'exécution de code, §5.3) — le reste de `sandbox/runner.py` nécessite un vrai Docker et
est couvert par `tests/integration/test_sandbox_execution.py`."""

from __future__ import annotations

import pytest

from sandbox import runner
from sandbox.runner import solveur_supporte_horizon_gele

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
    assert solveur_supporte_horizon_gele(_SOURCE_ANCIENNE_SIGNATURE) is False


def test_solveur_nouvelle_signature_supporte_horizon_gele() -> None:
    assert solveur_supporte_horizon_gele(_SOURCE_NOUVELLE_SIGNATURE) is True


def test_solveur_nouvelle_signature_kwonly_supporte_horizon_gele() -> None:
    assert solveur_supporte_horizon_gele(_SOURCE_NOUVELLE_SIGNATURE_KWONLY) is True


def test_solveur_avec_un_seul_des_deux_nouveaux_parametres_ne_supporte_pas() -> None:
    assert solveur_supporte_horizon_gele(_SOURCE_UN_SEUL_DES_DEUX_PARAMETRES) is False


def test_source_sans_fonction_resoudre_ne_supporte_pas() -> None:
    assert solveur_supporte_horizon_gele(_SOURCE_SANS_RESOUDRE) is False


def test_source_syntaxiquement_invalide_ne_supporte_pas() -> None:
    assert solveur_supporte_horizon_gele("def resoudre(:\n    invalide") is False


# --- Budget de temps (`PRISME_SANDBOX_LIMITE_TEMPS_S`) ------------------------------------------
# Porté de 30 s à 120 s : un solveur valide de 84 tâches demandait ~90 s, et le budget trop court
# le transformait en échec d'exécution alors qu'il avait passé toute la validation.


def test_budget_de_temps_par_defaut(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PRISME_SANDBOX_LIMITE_TEMPS_S", raising=False)

    assert runner.LimitesSandbox().limite_temps_s == 120.0


def test_budget_de_temps_surchargeable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_SANDBOX_LIMITE_TEMPS_S", "240")

    assert runner.LimitesSandbox().limite_temps_s == 240.0


def test_budget_explicite_l_emporte_sur_l_environnement(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un appelant qui fixe lui-même le budget — diagnostic, script — n'est jamais contredit."""
    monkeypatch.setenv("PRISME_SANDBOX_LIMITE_TEMPS_S", "240")

    assert runner.LimitesSandbox(limite_temps_s=15.0).limite_temps_s == 15.0


@pytest.mark.parametrize("valeur", ["deux minutes", "0", "-5"])
def test_budget_invalide_leve_une_erreur_explicite(monkeypatch: pytest.MonkeyPatch, valeur: str) -> None:
    monkeypatch.setenv("PRISME_SANDBOX_LIMITE_TEMPS_S", valeur)

    with pytest.raises(ValueError, match="PRISME_SANDBOX_LIMITE_TEMPS_S"):
        runner.LimitesSandbox()
