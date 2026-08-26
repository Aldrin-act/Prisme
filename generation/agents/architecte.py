"""Agent Architecte (pipeline multi-agents, §5.6) — planifie la structure
interne du module (variables/contraintes CP-SAT, ou l'équivalent pour un
algorithme alternatif — encodage de solution, opérateurs...) à partir de la
spécification de l'agent Analyste et de l'algorithme recommandé par l'agent
Benchmarker (qui s'exécute avant lui dans le pipeline, voir
`generation.graph` — le Benchmarker ne dépend que des
caractéristiques de l'instance, jamais du plan de l'Architecte). Le contrat
impose un seul module/une seule fonction publique `resoudre()` : pas de
découpage en plusieurs fichiers, contrairement à un agent architecte
"logiciel" généraliste — voir le prompt pour cette adaptation explicite.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from generation.agents.analyste import ResultatAnalyse
from generation.agents.base import ErreurReponseAgentInvalide, charger_mission  # noqa: F401 — réexporté (tests)
from generation.agents.client_llm import invoquer_agent_structure
from generation.agents.outil_documentation import consulter_si_utile

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "architecte.md"

_PROMPT_SYSTEME = (
    "Tu es un architecte logiciel spécialisé en optimisation combinatoire (CP-SAT/OR-Tools et "
    "métaheuristiques d'ordonnancement — génétique, ACO, recuit simulé, tabou, dispatching). "
    "Tu réponds toujours en JSON strict, jamais en texte libre."
)


class _SchemaConception(BaseModel):
    variables: str = Field(description="Représentation de la solution (variables, encodage...).")
    contraintes_modele: str = Field(description="Contraintes métier à respecter dans le modèle.")
    objectif: str = Field(description="Objectif à optimiser.")
    fonctions_internes: str | None = Field(default=None, description="Fonctions internes éventuelles.")


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
    modele: BaseChatModel,
    analyse: ResultatAnalyse,
    algorithme: str = "cp_sat",
    parametres: dict | None = None,
    autoriser_documentation: bool = False,
) -> ResultatConception:
    """Args:
    modele: `BaseChatModel` LangChain (voir `client_llm.construire_modele_pour_agent`).
    analyse: Spécification produite par l'agent Analyste.
    algorithme: Algorithme recommandé par l'agent Benchmarker (ex. "cp_sat",
        "genetic", "tabu_search"...) — "cp_sat" par défaut si l'appelant
        n'exécute pas le Benchmarker (ex. rétrocompatibilité, tests).
    parametres: Paramètres suggérés par le Benchmarker pour cet algorithme.
    autoriser_documentation: si vrai, un petit appel préalable laisse l'agent demander lui-même
        un sujet de `outil_documentation` avant de concevoir le plan — désactivé par défaut
        (rétrocompatibilité des appelants existants, tests inclus) ; activé explicitement par
        `generation/graph.py::_noeud_architecte`.
    """
    documentation = (
        consulter_si_utile(modele, "concevoir le plan technique du solveur", algorithme)
        if autoriser_documentation
        else ""
    )
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(
        mission=charger_mission(),
        specification=analyse.en_texte(),
        algorithme=algorithme,
        parametres=_rendre_parametres(parametres),
        documentation=documentation or "aucune",
    )

    donnees, reponse_brute = invoquer_agent_structure(
        modele, _SchemaConception, [SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)]
    )
    return ResultatConception(
        reponse_brute=reponse_brute,
        variables=donnees.variables,
        contraintes_modele=donnees.contraintes_modele,
        objectif=donnees.objectif,
        fonctions_internes=donnees.fonctions_internes,
    )
