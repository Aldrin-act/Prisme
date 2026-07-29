"""Client LLM générique pour les agents du pipeline (§5.6).

Le fournisseur et le modèle sont choisis par variables d'environnement,
jamais codés en dur, pour ne lier ce projet à aucun fournisseur particulier :

- `PRISME_LLM_PROVIDER` : "mistral" (défaut), "qwen", "together", "nvidia", "minimax" ou "deepseek".
- `PRISME_LLM_MODEL` : nom du modèle (défaut selon le fournisseur, ci-dessous).
- la clé d'API suit la convention standard de chaque SDK (`MISTRAL_API_KEY`,
  `TOGETHER_API_KEY`, `NVIDIA_API_KEY`, `MINIMAX_API_KEY`, `DEEPSEEK_API_KEY`)
  — jamais lue, manipulée ou journalisée directement ici, uniquement passée
  telle quelle au constructeur LangChain du fournisseur.

Construit sur LangChain (`langchain-core`/`langchain-openai`/`langchain-mistralai`,
`extra` optionnel `llm` du projet) plutôt que sur les SDK bruts : donne un
timeout HTTP réel par appel (absent de la version précédente — un blip réseau
pouvait bloquer indéfiniment, voir `_TIMEOUT_DEFAUT_SECONDES`) et prépare le
terrain pour la sortie structurée (`with_structured_output`). Tous les
agents exposent désormais un `BaseChatModel` LangChain brut — l'ancienne
forme `AppelLLM` (`Callable[[str, str], str]`, texte brut) a été retirée une
fois le dernier appelant converti ; `construire_modele_pour_agent` (par
agent) et `construire_modele` (générique, sans identité d'agent) sont les
seuls points d'entrée désormais.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

_TENTATIVES_MAX = 5
_DELAI_BASE_SECONDES = 2.0
_DELAI_MAX_SECONDES = 30.0

# Absent de la version pré-LangChain de ce module : sans timeout, une
# connexion qui ne répond jamais bloque indéfiniment (vécu en pratique — un
# job de génération resté bloqué plus de 9 minutes sur le tout premier appel
# LLM, aucune tentative de retry jamais atteinte puisque `_avec_retry` ne
# réagit qu'à une exception, pas à un silence). Surchargeable par agent, même
# convention que `PRISME_LLM_MODEL_<AGENT>`.
_TIMEOUT_DEFAUT_SECONDES = 120.0


def _est_erreur_transitoire(erreur: Exception) -> bool:
    """5xx (surcharge/panne côté fournisseur) ou timeout/coupure réseau — jamais
    une 4xx (clé invalide, prompt rejeté...) qui échouerait de façon identique
    à chaque nouvelle tentative, retenter ne ferait que perdre du temps."""
    code_statut = getattr(erreur, "status_code", None)
    if isinstance(code_statut, int):
        return code_statut >= 500
    nom_type = type(erreur).__name__
    return "Timeout" in nom_type or "Connection" in nom_type


def _avec_retry(appel: Callable) -> Callable:
    """Réessaie un appel en cas d'erreur transitoire côté fournisseur (ex. 504
    Gateway Timeout, vu en pratique sur les endpoints compatibles OpenAI de
    NVIDIA/Together) avec backoff exponentiel, pour qu'un blip réseau ne fasse
    pas échouer toute une tentative de génération (§5.6).

    Générique sur la signature de `appel` : sert aussi bien à envelopper
    `modele.invoke(messages)` en sortie brute qu'un appel `.invoke(messages)`
    sur un `Runnable` de sortie structurée — le prédicat de retry
    (`_est_erreur_transitoire`) ne dépend que de l'exception levée, jamais
    de la forme de `appel`.
    """

    def appel_avec_retry(*args, **kwargs):
        for tentative in range(_TENTATIVES_MAX):
            try:
                return appel(*args, **kwargs)
            except Exception as erreur:
                derniere_est_transitoire = _est_erreur_transitoire(erreur)
                if not derniere_est_transitoire or tentative == _TENTATIVES_MAX - 1:
                    raise
                time.sleep(min(_DELAI_BASE_SECONDES * (2**tentative), _DELAI_MAX_SECONDES))
        raise AssertionError("inatteignable")  # la boucle retourne ou lève à chaque itération

    return appel_avec_retry


_MODELES_PAR_DEFAUT = {
    "mistral": "mistral-large-latest",
    "qwen": "Qwen/Qwen2.5-72B-Instruct",
    "together": "Qwen/Qwen2.5-72B-Instruct",
    # qwen/qwen3-next-80b-a3b-instruct (précédent défaut) a atteint sa fin de
    # vie côté catalogue NVIDIA NIM (410 Gone, constaté en direct) — plus
    # aucun modèle Qwen n'y est disponible désormais, remplacé par un modèle
    # généraliste toujours actif, vérifié par appel réel.
    "nvidia": "meta/llama-3.3-70b-instruct",
    # minimaxai/minimax-m2.7 (précédent défaut) également en fin de vie —
    # minimax-m3 est son successeur direct sur le même catalogue, vérifié
    # par appel réel.
    "minimax": "minimaxai/minimax-m3",
    "deepseek": "deepseek-ai/deepseek-v4-pro",
}


def _timeout_pour_agent(nom_agent: str | None) -> float:
    if nom_agent:
        valeur = os.environ.get(f"PRISME_LLM_TIMEOUT_SECONDES_{nom_agent.upper()}")
        if valeur:
            return float(valeur)
    return float(os.environ.get("PRISME_LLM_TIMEOUT_SECONDES") or _TIMEOUT_DEFAUT_SECONDES)


def _construire_modele_mistral(modele: str, timeout: float) -> BaseChatModel:
    from langchain_mistralai import ChatMistralAI

    return ChatMistralAI(model=modele, api_key=os.environ.get("MISTRAL_API_KEY"), timeout=timeout)


def _construire_modele_openai_compatible(
    modele: str, base_url: str, cle_env: str, timeout: float, **kwargs
) -> BaseChatModel:
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(model=modele, base_url=base_url, api_key=os.environ.get(cle_env), timeout=timeout, **kwargs)


def _construire_modele_together(modele: str, timeout: float) -> BaseChatModel:
    """Together AI utilise une API compatible OpenAI."""
    return _construire_modele_openai_compatible(
        modele,
        "https://api.together.xyz/v1",
        "TOGETHER_API_KEY",
        timeout,
        temperature=0.7,
        top_p=0.9,
        max_tokens=8192,
    )


def _construire_modele_nvidia(modele: str, timeout: float) -> BaseChatModel:
    """NVIDIA API utilise une API compatible OpenAI."""
    return _construire_modele_openai_compatible(
        modele,
        "https://integrate.api.nvidia.com/v1",
        "NVIDIA_API_KEY",
        timeout,
        temperature=0.6,
        top_p=0.7,
        max_tokens=4096,
    )


def _construire_modele_minimax(modele: str, timeout: float) -> BaseChatModel:
    """MiniMax API via NVIDIA, utilise une API compatible OpenAI."""
    return _construire_modele_openai_compatible(
        modele,
        "https://integrate.api.nvidia.com/v1",
        "MINIMAX_API_KEY",
        timeout,
        temperature=1,
        top_p=0.95,
        max_tokens=8192,
    )


def _construire_modele_deepseek(modele: str, timeout: float) -> BaseChatModel:
    """DeepSeek V4 Pro via NVIDIA, utilise une API compatible OpenAI avec support du mode thinking."""
    return _construire_modele_openai_compatible(
        modele,
        "https://integrate.api.nvidia.com/v1",
        "DEEPSEEK_API_KEY",
        timeout,
        temperature=1,
        top_p=0.95,
        max_tokens=16384,
        extra_body={"chat_template_kwargs": {"thinking": False}},
    )


def _construire_modele_qwen(modele: str, timeout: float) -> BaseChatModel:
    """Alias pour Together AI (Qwen est hébergé sur Together)."""
    return _construire_modele_together(modele, timeout)


_CONSTRUCTEURS_MODELE: dict[str, Callable[[str, float], BaseChatModel]] = {
    "mistral": _construire_modele_mistral,
    "together": _construire_modele_together,
    "qwen": _construire_modele_qwen,
    "nvidia": _construire_modele_nvidia,
    "minimax": _construire_modele_minimax,
    "deepseek": _construire_modele_deepseek,
}


def _construire_modele(fournisseur: str, modele: str, timeout: float) -> BaseChatModel:
    constructeur = _CONSTRUCTEURS_MODELE.get(fournisseur)
    if constructeur is None:
        raise ValueError(f"fournisseur LLM inconnu : {fournisseur!r} (attendu : {sorted(_CONSTRUCTEURS_MODELE)})")
    return constructeur(modele, timeout)


def methode_sortie_structuree(modele: BaseChatModel) -> str:
    """`method=` à passer à `modele.with_structured_output(schema, method=...)`.

    Ne dépend jamais de la fidélité du tool-calling natif d'un fournisseur
    (`method="function_calling"`, le défaut LangChain) : deux des cinq
    fournisseurs de ce projet (nvidia, minimax) se sont révélés en fin de
    vie en pleine session — aucune confiance a priori dans un mécanisme plus
    exigeant que ce qui marche déjà en production. `"json_mode"` ne demande
    au modèle que d'émettre du JSON valide dans `.content`, exactement ce
    que l'ancien `extraire_json` + le prompt "réponds en JSON strict" (voir
    chaque `generation/prompts/*.md`) obtenait déjà de façon fiable.
    `ChatMistralAI` a son propre mode structuré natif (`"json_schema"`),
    utilisé à la place puisqu'il est mieux supporté que le mode générique
    côté Mistral."""
    from langchain_mistralai import ChatMistralAI

    if isinstance(modele, ChatMistralAI):
        return "json_schema"
    return "json_mode"


def construire_modele() -> BaseChatModel:
    """Construit le `BaseChatModel` générique, d'après `PRISME_LLM_PROVIDER` /
    `PRISME_LLM_MODEL` — sans identité d'agent, pour les chemins qui n'en ont
    pas (Étape 4 historique, scripts de connectivité). Voir
    `construire_modele_pour_agent` pour le routage par agent."""
    fournisseur = os.environ.get("PRISME_LLM_PROVIDER") or "mistral"
    # `.get(..., defaut)` ne renvoie le défaut que si la variable est absente —
    # or `.env` la déclare toujours, vide par défaut (`PRISME_LLM_MODEL=`), ce
    # qui donnerait `modele = ""` sans le `or` : Mistral (entre autres) rejette
    # alors l'appel avec "Missing model parameter" plutôt que d'utiliser son
    # propre défaut, l'erreur n'a rien d'évident depuis l'appelant.
    if fournisseur not in _CONSTRUCTEURS_MODELE:
        raise ValueError(f"fournisseur LLM inconnu : {fournisseur!r} (attendu : {sorted(_CONSTRUCTEURS_MODELE)})")
    modele_nom = os.environ.get("PRISME_LLM_MODEL") or _MODELES_PAR_DEFAUT[fournisseur]
    return _construire_modele(fournisseur, modele_nom, _timeout_pour_agent(None))


def construire_modele_pour_agent(nom_agent: str) -> BaseChatModel:
    """Construit le `BaseChatModel` LangChain optimal pour un agent
    spécifique. Le retry (`_avec_retry`) reste à la charge de l'appelant, qui
    l'applique au point d'appel réel (`.invoke(...)` sur le `Runnable`
    structuré ou brut), puisque le modèle renvoyé ici n'est pas encore
    l'objet invoqué.

    Utilise la configuration centralisée (`config_fournisseurs.py`) pour
    sélectionner le fournisseur le mieux adapté à cet agent. Permet une
    surcharge par variable d'environnement `PRISME_LLM_PROVIDER_<AGENT>` /
    `PRISME_LLM_MODEL_<AGENT>` / `PRISME_LLM_TIMEOUT_SECONDES_<AGENT>`.
    """
    from generation.agents.config_fournisseurs import obtenir_fournisseur_pour_agent

    fournisseur = obtenir_fournisseur_pour_agent(nom_agent)
    if fournisseur not in _CONSTRUCTEURS_MODELE:
        raise ValueError(
            f"fournisseur LLM inconnu pour l'agent {nom_agent!r} : {fournisseur!r} "
            f"(attendu : {sorted(_CONSTRUCTEURS_MODELE)})"
        )
    var_modele = f"PRISME_LLM_MODEL_{nom_agent.upper()}"
    modele_nom = os.environ.get(var_modele) or _MODELES_PAR_DEFAUT[fournisseur]
    return _construire_modele(fournisseur, modele_nom, _timeout_pour_agent(nom_agent))


def construire_modele_comprehension() -> BaseChatModel:
    """Dépendance FastAPI zero-arg (`Depends(...)`) pour l'agent de
    compréhension ERP (`adapters/agent_comprehension/`, §5.4 bis) — routé
    comme n'importe quel agent du pipeline via `config_fournisseurs.py`
    (clé `"comprehension"`), pas un client LLM à part."""
    return construire_modele_pour_agent("comprehension")
