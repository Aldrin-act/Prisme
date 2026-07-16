"""Couche 1 (§6.1) : `construire_appel_llm` ne doit jamais transmettre un
fournisseur/modèle vide à un SDK — régression trouvée en testant l'agent de
compréhension en conditions réelles : `.env` déclare `PRISME_LLM_MODEL=`
(présent, vide), distinct d'une variable absente pour `os.environ.get`,
Mistral rejetait alors l'appel avec "Missing model parameter" sans que
l'erreur ne pointe vers la vraie cause.
"""

from __future__ import annotations

import pytest

from generation.agents import client_llm


def test_modele_vide_dans_env_retombe_sur_le_defaut(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_LLM_PROVIDER", "factice")
    monkeypatch.setenv("PRISME_LLM_MODEL", "")  # présent mais vide, comme dans .env par défaut
    monkeypatch.setitem(client_llm._MODELES_PAR_DEFAUT, "factice", "modele-par-defaut")
    monkeypatch.setitem(client_llm._CONSTRUCTEURS, "factice", lambda modele: modele)

    appel = client_llm.construire_appel_llm()

    assert appel == "modele-par-defaut"


def test_modele_explicite_dans_env_est_respecte(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_LLM_PROVIDER", "factice")
    monkeypatch.setenv("PRISME_LLM_MODEL", "mon-modele-precis")
    monkeypatch.setitem(client_llm._MODELES_PAR_DEFAUT, "factice", "modele-par-defaut")
    monkeypatch.setitem(client_llm._CONSTRUCTEURS, "factice", lambda modele: modele)

    appel = client_llm.construire_appel_llm()

    assert appel == "mon-modele-precis"


def test_fournisseur_vide_dans_env_retombe_sur_anthropic(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_LLM_PROVIDER", "")
    monkeypatch.delenv("PRISME_LLM_MODEL", raising=False)
    appels: list[str] = []
    monkeypatch.setitem(client_llm._CONSTRUCTEURS, "anthropic", appels.append)

    client_llm.construire_appel_llm()

    assert appels  # bien passé par le constructeur "anthropic", pas une KeyError sur ""
