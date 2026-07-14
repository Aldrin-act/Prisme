"""Client LLM générique pour l'agent générateur (§5.6).

Le fournisseur et le modèle sont choisis par variables d'environnement,
jamais codés en dur, pour ne lier ce projet à aucun fournisseur particulier :

- `PRISME_LLM_PROVIDER` : "anthropic" (défaut) ou "openai".
- `PRISME_LLM_MODEL` : nom du modèle (défaut selon le fournisseur, ci-dessous).
- la clé d'API suit la convention standard de chaque SDK (`ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`) — jamais lue, manipulée ou journalisée directement ici.

Le SDK du fournisseur choisi est importé à la demande (`extra` optionnel
`llm` du projet) : pas besoin d'installer les deux pour n'en utiliser qu'un.
"""

from __future__ import annotations

import os
from collections.abc import Callable

# (prompt_systeme, prompt_utilisateur) -> texte de réponse brut du LLM
AppelLLM = Callable[[str, str], str]

_MODELES_PAR_DEFAUT = {
    "anthropic": "claude-sonnet-5",
    "openai": "gpt-5",
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


_CONSTRUCTEURS: dict[str, Callable[[str], AppelLLM]] = {
    "anthropic": _construire_appel_anthropic,
    "openai": _construire_appel_openai,
}


def construire_appel_llm() -> AppelLLM:
    """Construit l'appel LLM à utiliser, d'après `PRISME_LLM_PROVIDER` / `PRISME_LLM_MODEL`."""
    fournisseur = os.environ.get("PRISME_LLM_PROVIDER", "anthropic")
    constructeur = _CONSTRUCTEURS.get(fournisseur)
    if constructeur is None:
        raise ValueError(
            f"fournisseur LLM inconnu : {fournisseur!r} (attendu : {sorted(_CONSTRUCTEURS)})"
        )
    modele = os.environ.get("PRISME_LLM_MODEL", _MODELES_PAR_DEFAUT[fournisseur])
    return constructeur(modele)
