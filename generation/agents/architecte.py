"""Agent Architecte (pipeline multi-agents, §5.6) — planifie la structure
interne du module CP-SAT (variables, contraintes, fonctions internes
éventuelles) à partir de la spécification de l'agent Analyste. Le contrat
impose un seul module/une seule fonction publique `resoudre()` : pas de
découpage en plusieurs fichiers, contrairement à un agent architecte
"logiciel" généraliste — voir le prompt pour cette adaptation explicite.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from generation.agents.analyste import ResultatAnalyse
from generation.agents.base import charger_mission, extraire_json
from generation.agents.client_llm import AppelLLM

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "architecte.md"

_PROMPT_SYSTEME = (
    "Tu es un architecte logiciel spécialisé en modélisation de contraintes (CP-SAT, OR-Tools). "
    "Tu réponds toujours en JSON strict, jamais en texte libre."
)


@dataclass(frozen=True)
class ResultatConception:
    reponse_brute: str
    variables: str
    contraintes_modele: str
    objectif: str
    fonctions_internes: str | None

    def en_texte(self) -> str:
        """Rendu lisible, pour l'injecter dans le prompt de l'agent Développeur."""
        fonctions = self.fonctions_internes or "aucune — une seule fonction resoudre() suffit"
        return (
            f"### Variables du modèle CP-SAT\n{self.variables}\n\n"
            f"### Contraintes du modèle\n{self.contraintes_modele}\n\n"
            f"### Objectif\n{self.objectif}\n\n"
            f"### Fonctions internes éventuelles\n{fonctions}"
        )


def concevoir_modele(appel_llm: AppelLLM, analyse: ResultatAnalyse) -> ResultatConception:
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(mission=charger_mission(), specification=analyse.en_texte())
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    donnees = extraire_json(reponse)
    return ResultatConception(
        reponse_brute=reponse,
        variables=donnees["variables"],
        contraintes_modele=donnees["contraintes_modele"],
        objectif=donnees["objectif"],
        fonctions_internes=donnees.get("fonctions_internes"),
    )
