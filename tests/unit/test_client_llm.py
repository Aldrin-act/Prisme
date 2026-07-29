"""Couche 1 (§6.1) : `construire_appel_llm`/`construire_modele_pour_agent` ne
doivent jamais transmettre un fournisseur/modèle vide à un SDK — régression
trouvée en testant l'agent de compréhension en conditions réelles : `.env`
déclare `PRISME_LLM_MODEL=` (présent, vide), distinct d'une variable absente
pour `os.environ.get`, Mistral rejetait alors l'appel avec "Missing model
parameter" sans que l'erreur ne pointe vers la vraie cause.

Aucun appel réseau ici : les constructeurs LangChain (`ChatOpenAI`,
`ChatMistralAI`) ne contactent le fournisseur qu'au premier `.invoke()`, leur
construction est pure — les tests de parité ci-dessous inspectent donc les
attributs de l'objet construit, jamais une réponse réelle.
"""

from __future__ import annotations

import pytest

from generation.agents import client_llm


def test_modele_vide_dans_env_retombe_sur_le_defaut(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_LLM_PROVIDER", "factice")
    monkeypatch.setenv("PRISME_LLM_MODEL", "")  # présent mais vide, comme dans .env par défaut
    monkeypatch.setitem(client_llm._MODELES_PAR_DEFAUT, "factice", "modele-par-defaut")
    modeles_construits: list[str] = []
    monkeypatch.setitem(
        client_llm._CONSTRUCTEURS_MODELE,
        "factice",
        lambda modele, timeout: modeles_construits.append(modele),
    )

    client_llm.construire_appel_llm()

    assert modeles_construits == ["modele-par-defaut"]


def test_modele_explicite_dans_env_est_respecte(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_LLM_PROVIDER", "factice")
    monkeypatch.setenv("PRISME_LLM_MODEL", "mon-modele-precis")
    monkeypatch.setitem(client_llm._MODELES_PAR_DEFAUT, "factice", "modele-par-defaut")
    modeles_construits: list[str] = []
    monkeypatch.setitem(
        client_llm._CONSTRUCTEURS_MODELE,
        "factice",
        lambda modele, timeout: modeles_construits.append(modele),
    )

    client_llm.construire_appel_llm()

    assert modeles_construits == ["mon-modele-precis"]


def test_fournisseur_vide_dans_env_retombe_sur_mistral(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_LLM_PROVIDER", "")
    monkeypatch.delenv("PRISME_LLM_MODEL", raising=False)
    appels: list[str] = []
    monkeypatch.setitem(client_llm._CONSTRUCTEURS_MODELE, "mistral", lambda modele, timeout: appels.append(modele))

    client_llm.construire_appel_llm()

    assert appels  # bien passé par le constructeur "mistral" (défaut du module), pas une KeyError sur ""


def test_fournisseur_inconnu_leve_une_erreur_explicite(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRISME_LLM_PROVIDER", "fournisseur-qui-n-existe-pas")

    with pytest.raises(ValueError, match="fournisseur LLM inconnu"):
        client_llm.construire_appel_llm()


class TestTimeoutParAgent:
    def test_defaut_global_si_aucune_surcharge(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PRISME_LLM_TIMEOUT_SECONDES", raising=False)
        monkeypatch.delenv("PRISME_LLM_TIMEOUT_SECONDES_ANALYSTE", raising=False)
        assert client_llm._timeout_pour_agent("analyste") == client_llm._TIMEOUT_DEFAUT_SECONDES

    def test_surcharge_globale(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRISME_LLM_TIMEOUT_SECONDES", "45")
        monkeypatch.delenv("PRISME_LLM_TIMEOUT_SECONDES_ANALYSTE", raising=False)
        assert client_llm._timeout_pour_agent("analyste") == 45.0

    def test_surcharge_par_agent_prioritaire_sur_la_globale(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PRISME_LLM_TIMEOUT_SECONDES", "45")
        monkeypatch.setenv("PRISME_LLM_TIMEOUT_SECONDES_ANALYSTE", "10")
        assert client_llm._timeout_pour_agent("analyste") == 10.0


class TestConstructeursModeleParite:
    """Vérifie que chaque fournisseur construit son `ChatOpenAI`/`ChatMistralAI`
    avec exactement les mêmes base_url/température/top_p/max_tokens que
    l'ancien client fait main — aucun appel réseau, seule la construction de
    l'objet est inspectée."""

    def test_nvidia_utilise_le_bon_base_url_et_les_bons_parametres(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("NVIDIA_API_KEY", "cle-test")
        modele = client_llm._construire_modele_nvidia("meta/llama-3.3-70b-instruct", 120.0)
        assert modele.openai_api_base == "https://integrate.api.nvidia.com/v1"
        assert modele.model_name == "meta/llama-3.3-70b-instruct"
        assert modele.temperature == 0.6
        assert modele.top_p == 0.7
        assert modele.request_timeout == 120.0

    def test_deepseek_transmet_extra_body_thinking_desactive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEEPSEEK_API_KEY", "cle-test")
        modele = client_llm._construire_modele_deepseek("deepseek-ai/deepseek-v4-pro", 120.0)
        assert modele.extra_body == {"chat_template_kwargs": {"thinking": False}}
        assert modele.max_tokens == 16384

    def test_qwen_est_bien_un_alias_de_together(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TOGETHER_API_KEY", "cle-test")
        modele = client_llm._construire_modele_qwen("Qwen/Qwen2.5-72B-Instruct", 120.0)
        assert modele.openai_api_base == "https://api.together.xyz/v1"

    def test_mistral_utilise_chat_mistral_ai(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MISTRAL_API_KEY", "cle-test")
        modele = client_llm._construire_modele_mistral("mistral-large-latest", 120.0)
        assert modele.model == "mistral-large-latest"


def test_construire_modele_pour_agent_respecte_la_surcharge_de_modele(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "cle-test")
    monkeypatch.setenv("PRISME_LLM_MODEL_DOCUMENTATION", "un-modele-precis")

    modele = client_llm.construire_modele_pour_agent("documentation")

    assert modele.model_name == "un-modele-precis"
