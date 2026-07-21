"""Client LLM générique pour l'agent générateur (§5.6).

Le fournisseur et le modèle sont choisis par variables d'environnement,
jamais codés en dur, pour ne lier ce projet à aucun fournisseur particulier :

- `PRISME_LLM_PROVIDER` : "anthropic" (défaut), "openai", "mistral", "qwen" ou "together".
- `PRISME_LLM_MODEL` : nom du modèle (défaut selon le fournisseur, ci-dessous).
- la clé d'API suit la convention standard de chaque SDK (`ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, `MISTRAL_API_KEY`, `TOGETHER_API_KEY`) — jamais lue, manipulée
  ou journalisée directement ici.

Le SDK du fournisseur choisi est importé à la demande (`extra` optionnel
`llm` du projet) : pas besoin d'installer les trois pour n'en utiliser qu'un.
"""

from __future__ import annotations

import os
from collections.abc import Callable

# (prompt_systeme, prompt_utilisateur) -> texte de réponse brut du LLM
AppelLLM = Callable[[str, str], str]

_MODELES_PAR_DEFAUT = {
    "anthropic": "claude-sonnet-5",
    "openai": "gpt-5",
    "mistral": "mistral-large-latest",
    "qwen": "Qwen/Qwen2.5-72B-Instruct",
    "together": "Qwen/Qwen2.5-72B-Instruct",
}


def _construire_appel_anthropic(modele: str) -> AppelLLM:
    import anthropic

    client = anthropic.Anthropic()

    def appel(prompt_systeme: str, prompt_utilisateur: str) -> str:
        reponse = client.messages.create(
            model=modele,
            max_tokens=8192,
            system=prompt_systeme,
            messages=[{"role": "user", "content": prompt_utilisateur}],
        )
        return "".join(bloc.text for bloc in reponse.content if bloc.type == "text")

    return appel


def _construire_appel_openai(modele: str) -> AppelLLM:
    import openai

    client = openai.OpenAI()

    def appel(prompt_systeme: str, prompt_utilisateur: str) -> str:
        reponse = client.chat.completions.create(
            model=modele,
            messages=[
                {"role": "system", "content": prompt_systeme},
                {"role": "user", "content": prompt_utilisateur},
            ],
        )
        return reponse.choices[0].message.content or ""

    return appel


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
    
    client = openai.OpenAI(
  base_url="https://integrate.api.nvidia.com/v1",
  api_key="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"
)

    def appel(prompt_systeme: str, prompt_utilisateur: str) -> str:
        reponse = client.chat.completions.create(
            model=modele,
            messages=[
                {"role": "system", "content": prompt_systeme},
                {"role": "user", "content": prompt_utilisateur},
            ],
        )
        return reponse.choices[0].message.content or ""

    return appel


def _construire_appel_qwen(modele: str) -> AppelLLM:
    """Alias pour Together AI (Qwen est hébergé sur Together)."""
    return _construire_appel_together(modele)


_CONSTRUCTEURS: dict[str, Callable[[str], AppelLLM]] = {
    "anthropic": _construire_appel_anthropic,
    "openai": _construire_appel_openai,
    "mistral": _construire_appel_mistral,
    "together": _construire_appel_together,
    "qwen": _construire_appel_qwen,
}


def construire_appel_llm() -> AppelLLM:
    """Construit l'appel LLM à utiliser, d'après `PRISME_LLM_PROVIDER` / `PRISME_LLM_MODEL`."""
    fournisseur = os.environ.get("PRISME_LLM_PROVIDER") or "anthropic"
    constructeur = _CONSTRUCTEURS.get(fournisseur)
    if constructeur is None:
        raise ValueError(f"fournisseur LLM inconnu : {fournisseur!r} (attendu : {sorted(_CONSTRUCTEURS)})")
    # `.get(..., defaut)` ne renvoie le défaut que si la variable est absente —
    # or `.env` la déclare toujours, vide par défaut (`PRISME_LLM_MODEL=`), ce
    # qui donnerait `modele = ""` sans le `or` : Mistral (entre autres) rejette
    # alors l'appel avec "Missing model parameter" plutôt que d'utiliser son
    # propre défaut, l'erreur n'a rien d'évident depuis l'appelant.
    modele = os.environ.get("PRISME_LLM_MODEL") or _MODELES_PAR_DEFAUT[fournisseur]
    return constructeur(modele)
