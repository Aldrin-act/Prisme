"""Agent Architecte (pipeline multi-agents, §5.6) — planifie la structure
interne du module (variables/contraintes CP-SAT, ou l'équivalent pour un
algorithme alternatif — encodage de solution, opérateurs...) à partir de la
spécification de l'agent Analyste et de l'algorithme recommandé par l'agent
Benchmarker (qui s'exécute avant lui dans le pipeline, voir
`generation.pipeline_multi_agents` — le Benchmarker ne dépend que des
caractéristiques de l'instance, jamais du plan de l'Architecte). Le contrat
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
    "Tu es un architecte logiciel spécialisé en optimisation combinatoire (CP-SAT/OR-Tools et "
    "métaheuristiques d'ordonnancement — génétique, ACO, recuit simulé, tabou, dispatching). "
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
        """Rendu lisible, pour l'injecter dans le prompt de l'agent Développeur.
        Titres génériques (pas "CP-SAT" en dur) car le contenu peut décrire un
        algorithme alternatif recommandé par le Benchmarker."""
        fonctions = self.fonctions_internes or "aucune — une seule fonction resoudre() suffit"
        return (
            f"### Représentation de la solution\n{self.variables}\n\n"
            f"### Contraintes métier à respecter\n{self.contraintes_modele}\n\n"
            f"### Objectif\n{self.objectif}\n\n"
            f"### Fonctions internes éventuelles\n{fonctions}"
        )


def _rendre_parametres(parametres: dict | None) -> str:
    if not parametres:
        return "aucun paramètre particulier suggéré"
    return "\n".join(f"- {cle} : {valeur}" for cle, valeur in parametres.items())


def concevoir_modele(
    appel_llm: AppelLLM,
    analyse: ResultatAnalyse,
    algorithme: str = "cp_sat",
    parametres: dict | None = None,
) -> ResultatConception:
    """Args:
    appel_llm: Client LLM.
    analyse: Spécification produite par l'agent Analyste.
    algorithme: Algorithme recommandé par l'agent Benchmarker (ex. "cp_sat",
        "genetic", "tabu_search"...) — "cp_sat" par défaut si l'appelant
        n'exécute pas le Benchmarker (ex. rétrocompatibilité, tests).
    parametres: Paramètres suggérés par le Benchmarker pour cet algorithme.
    """
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(
        mission=charger_mission(),
        specification=analyse.en_texte(),
        algorithme=algorithme,
        parametres=_rendre_parametres(parametres),
    )
    reponse = appel_llm(_PROMPT_SYSTEME, prompt)
    donnees = extraire_json(reponse)
    return ResultatConception(
        reponse_brute=reponse,
        variables=donnees["variables"],
        contraintes_modele=donnees["contraintes_modele"],
        objectif=donnees["objectif"],
        fonctions_internes=donnees.get("fonctions_internes"),
    )
