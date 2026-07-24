"""Client LLM générique pour l'agent générateur (§5.6).

Le fournisseur et le modèle sont choisis par variables d'environnement,
jamais codés en dur, pour ne lier ce projet à aucun fournisseur particulier :

- `PRISME_LLM_PROVIDER` : "mistral" (défaut), "qwen", "together", "nvidia", "minimax" ou "deepseek".
- `PRISME_LLM_MODEL` : nom du modèle (défaut selon le fournisseur, ci-dessous).
- la clé d'API suit la convention standard de chaque SDK (`MISTRAL_API_KEY`,
  `TOGETHER_API_KEY`, `NVIDIA_API_KEY`, `MINIMAX_API_KEY`, `DEEPSEEK_API_KEY`)
  — jamais lue, manipulée ou journalisée directement ici, uniquement passée
  telle quelle au SDK du fournisseur.

Le SDK du fournisseur choisi est importé à la demande (`extra` optionnel
`llm` du projet) : pas besoin d'installer les trois pour n'en utiliser qu'un.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable

# (prompt_systeme, prompt_utilisateur) -> texte de réponse brut du LLM
AppelLLM = Callable[[str, str], str]

_TENTATIVES_MAX = 5
_DELAI_BASE_SECONDES = 2.0
_DELAI_MAX_SECONDES = 30.0


def _est_erreur_transitoire(erreur: Exception) -> bool:
    """5xx (surcharge/panne côté fournisseur) ou timeout/coupure réseau — jamais
    une 4xx (clé invalide, prompt rejeté...) qui échouerait de façon identique
    à chaque nouvelle tentative, retenter ne ferait que perdre du temps."""
    code_statut = getattr(erreur, "status_code", None)
    if isinstance(code_statut, int):
        return code_statut >= 500
    nom_type = type(erreur).__name__
    return "Timeout" in nom_type or "Connection" in nom_type


def _avec_retry(appel: AppelLLM) -> AppelLLM:
    """Réessaie un appel LLM en cas d'erreur transitoire côté fournisseur
    (ex. 504 Gateway Timeout, vu en pratique sur les endpoints compatibles
    OpenAI de NVIDIA/Together) avec backoff exponentiel, pour qu'un blip
    réseau ne fasse pas échouer toute une tentative de génération (§5.6)."""

    def appel_avec_retry(prompt_systeme: str, prompt_utilisateur: str) -> str:
        for tentative in range(_TENTATIVES_MAX):
            try:
                return appel(prompt_systeme, prompt_utilisateur)
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
    "nvidia": "qwen/qwen3-next-80b-a3b-instruct",
    "minimax": "minimaxai/minimax-m2.7",
    "deepseek": "deepseek-ai/deepseek-v4-pro",
}


def _construire_appel_mistral(modele: str) -> AppelLLM:
    # `from mistralai import Mistral` échoue sur ce paquet (namespace package sans
    # réexport à la racine) — la classe vit dans le sous-module `mistralai.client`.
    from mistralai.client import Mistral

    client = Mistral(api_key=os.environ.get("MISTRAL_API_KEY"))

    def appel(prompt_systeme: str, prompt_utilisateur: str) -> str:
        reponse = client.chat.complete(
            model=modele,
            messages=[
                {"role": "system", "content": prompt_systeme},
                {"role": "user", "content": prompt_utilisateur},
            ],
        )
        return reponse.choices[0].message.content or ""

    return appel


def _construire_appel_together(modele: str) -> AppelLLM:
    """Together AI utilise une API compatible OpenAI."""
    import openai

    client = openai.OpenAI(base_url="https://api.together.xyz/v1", api_key=os.environ.get("TOGETHER_API_KEY"))

    def appel(prompt_systeme: str, prompt_utilisateur: str) -> str:
        reponse = client.chat.completions.create(
            model=modele,
            messages=[
                {"role": "system", "content": prompt_systeme},
                {"role": "user", "content": prompt_utilisateur},
            ],
            temperature=0.7,
            top_p=0.9,
            max_tokens=8192,
        )
        return reponse.choices[0].message.content or ""

    return appel


def _construire_appel_nvidia(modele: str) -> AppelLLM:
    """NVIDIA API utilise une API compatible OpenAI."""
    import openai

    client = openai.OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.environ.get("NVIDIA_API_KEY"),
    )

    def appel(prompt_systeme: str, prompt_utilisateur: str) -> str:
        reponse = client.chat.completions.create(
            model=modele,
            messages=[
                {"role": "system", "content": prompt_systeme},
                {"role": "user", "content": prompt_utilisateur},
            ],
            temperature=0.6,
            top_p=0.7,
            max_tokens=4096,
        )
        return reponse.choices[0].message.content or ""

    return appel


def _construire_appel_minimax(modele: str) -> AppelLLM:
    """MiniMax API via NVIDIA, utilise une API compatible OpenAI."""
    import openai

    client = openai.OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.environ.get("MINIMAX_API_KEY"),
    )

    def appel(prompt_systeme: str, prompt_utilisateur: str) -> str:
        reponse = client.chat.completions.create(
            model=modele,
            messages=[
                {"role": "system", "content": prompt_systeme},
                {"role": "user", "content": prompt_utilisateur},
            ],
            temperature=1,
            top_p=0.95,
            max_tokens=8192,
        )
        return reponse.choices[0].message.content or ""

    return appel


def _construire_appel_deepseek(modele: str) -> AppelLLM:
    """DeepSeek V4 Pro via NVIDIA, utilise une API compatible OpenAI avec support du mode thinking."""
    import openai

    client = openai.OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
    )

    def appel(prompt_systeme: str, prompt_utilisateur: str) -> str:
        reponse = client.chat.completions.create(
            model=modele,
            messages=[
                {"role": "system", "content": prompt_systeme},
                {"role": "user", "content": prompt_utilisateur},
            ],
            temperature=1,
            top_p=0.95,
            max_tokens=16384,
            extra_body={"chat_template_kwargs": {"thinking": False}},
        )
        return reponse.choices[0].message.content or ""

    return appel


def _construire_appel_qwen(modele: str) -> AppelLLM:
    """Alias pour Together AI (Qwen est hébergé sur Together)."""
    return _construire_appel_together(modele)


_CONSTRUCTEURS: dict[str, Callable[[str], AppelLLM]] = {
    "mistral": _construire_appel_mistral,
    "together": _construire_appel_together,
    "qwen": _construire_appel_qwen,
    "nvidia": _construire_appel_nvidia,
    "minimax": _construire_appel_minimax,
    "deepseek": _construire_appel_deepseek,
}


def construire_appel_llm() -> AppelLLM:
    """Construit l'appel LLM à utiliser, d'après `PRISME_LLM_PROVIDER` / `PRISME_LLM_MODEL`."""
    fournisseur = os.environ.get("PRISME_LLM_PROVIDER") or "mistral"
    constructeur = _CONSTRUCTEURS.get(fournisseur)
    if constructeur is None:
        raise ValueError(f"fournisseur LLM inconnu : {fournisseur!r} (attendu : {sorted(_CONSTRUCTEURS)})")
    # `.get(..., defaut)` ne renvoie le défaut que si la variable est absente —
    # or `.env` la déclare toujours, vide par défaut (`PRISME_LLM_MODEL=`), ce
    # qui donnerait `modele = ""` sans le `or` : Mistral (entre autres) rejette
    # alors l'appel avec "Missing model parameter" plutôt que d'utiliser son
    # propre défaut, l'erreur n'a rien d'évident depuis l'appelant.
    modele = os.environ.get("PRISME_LLM_MODEL") or _MODELES_PAR_DEFAUT[fournisseur]
    return _avec_retry(constructeur(modele))


def construire_appel_llm_pour_agent(nom_agent: str) -> AppelLLM:
    """Construit l'appel LLM optimal pour un agent spécifique.

    Utilise la configuration centralisée (`config_fournisseurs.py`) pour
    sélectionner le fournisseur le mieux adapté à chaque agent. Permet une
    surcharge par variable d'environnement `PRISME_LLM_PROVIDER_<AGENT>`.

    Args:
        nom_agent: Nom de l'agent (ex: "generateur", "debugger", "orchestrateur")

    Returns:
        Callable LLM configuré pour le fournisseur optimal de cet agent

    Exemples:
        >>> appel = construire_appel_llm_pour_agent("generateur")  # → deepseek
        >>> appel = construire_appel_llm_pour_agent("orchestrateur")  # → nvidia
    """
    # Import ici pour éviter une dépendance circulaire (config_fournisseurs
    # pourrait importer de client_llm dans le futur)
    from generation.agents.config_fournisseurs import obtenir_fournisseur_pour_agent

    fournisseur = obtenir_fournisseur_pour_agent(nom_agent)
    constructeur = _CONSTRUCTEURS.get(fournisseur)
    if constructeur is None:
        raise ValueError(
            f"fournisseur LLM inconnu pour l'agent {nom_agent!r} : {fournisseur!r} "
            f"(attendu : {sorted(_CONSTRUCTEURS)})"
        )

    # Le modèle peut toujours être surchargé par PRISME_LLM_MODEL_<AGENT>
    var_modele = f"PRISME_LLM_MODEL_{nom_agent.upper()}"
    modele = os.environ.get(var_modele) or _MODELES_PAR_DEFAUT[fournisseur]
    return _avec_retry(constructeur(modele))
