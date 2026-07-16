"""Agent Analyste (pipeline multi-agents, §5.6) — transforme la mission en
spécification technique structurée (entrées, sorties, contraintes à
couvrir), sans écrire de code. Première étape du pipeline, avant l'agent
Architecte.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from generation.agents.base import charger_mission, extraire_json
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "analyste.md"

_PROMPT_SYSTEME = (
    "Tu es un analyste technique spécialisé en ordonnancement (FJSP) et en modélisation. "
    "Tu réponds toujours en JSON strict, jamais en texte libre."
)


@dataclass(frozen=True)
class ResultatAnalyse:
    reponse_brute: str
    entrees: str
    sorties: str
    contraintes_a_couvrir: tuple[str, ...]

    def en_texte(self) -> str:
        """Rendu lisible, pour l'injecter dans le prompt de l'agent Architecte."""
        contraintes = "\n".join(f"- {c}" for c in self.contraintes_a_couvrir)
        return (
            f"### Entrées\n{self.entrees}\n\n"
            f"### Sorties\n{self.sorties}\n\n"
            f"### Contraintes à couvrir\n{contraintes}"
        )


def analyser_mission(appel_llm: AppelLLM) -> ResultatAnalyse:
    prompt = CHEMIN_PROMPT.read_text(encoding="utf-8").format(mission=charger_mission())
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    donnees = extraire_json(reponse)
    return ResultatAnalyse(
        reponse_brute=reponse,
        entrees=donnees["entrees"],
        sorties=donnees["sorties"],
        contraintes_a_couvrir=tuple(donnees["contraintes_a_couvrir"]),
    )
