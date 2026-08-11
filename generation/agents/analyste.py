"""Agent Analyste (pipeline multi-agents, §5.6) — transforme la mission en
spécification technique structurée (entrées, sorties, contraintes à
couvrir), sans écrire de code. Première étape du pipeline, avant l'agent
Architecte.

Reçoit aussi la structure de l'instance en cours de génération (types de
contraintes/objectifs présents + compteurs, jamais leurs valeurs réelles) —
même précédent que `benchmarker.py::analyser_caracteristiques_instance` :
un solveur généré pour une structure donnée est réexécuté sur toute
instance future partageant cette même structure (§"generate once,
re-execute many", `CLAUDE.md`), donc seule l'information stable dans le
temps (quels types existent) peut orienter la spécification — jamais une
valeur précise (identifiant de tâche, échéance, poids...), qui varierait
d'une réexécution à l'autre."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from generation.agents.base import ErreurReponseAgentInvalide, charger_mission, extraire_texte_brut
from generation.agents.client_llm import _avec_retry, methode_sortie_structuree

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "analyste.md"

_PROMPT_SYSTEME = (
    "Tu es un analyste technique spécialisé en ordonnancement (FJSP) et en modélisation. "
    "Tu réponds toujours en JSON strict, jamais en texte libre."
)


class _SchemaAnalyse(BaseModel):
    entrees: str = Field(description="Description des données d'entrée de la mission.")
    sorties: str = Field(description="Description du format de sortie attendu.")
    contraintes_a_couvrir: list[str] = Field(description="Liste des contraintes à modéliser.")


@dataclass(frozen=True)
class StructureInstance:
    """Types de contraintes/objectifs présents dans l'instance en cours de
    génération, plus quelques compteurs — jamais une valeur réelle (voir
    docstring du module). `types_contraintes`/`types_objectifs` : mêmes
    valeurs que `api/etat.py::structure_contraintes`/`signature_objectifs`,
    recalculées ici sur le `dict` JSON brut plutôt qu'importées depuis
    `api/` (`generation/agents/` reste indépendant de la couche API)."""

    types_contraintes: tuple[str, ...]
    types_objectifs: tuple[str, ...]
    nb_taches: int
    nb_ressources: int


def extraire_structure_instance(instance_json: dict) -> StructureInstance:
    types_contraintes = sorted({c["type"] for c in instance_json.get("contraintes", [])})
    types_objectifs = sorted({o["type"] for o in instance_json.get("objectifs", [])})
    return StructureInstance(
        types_contraintes=tuple(types_contraintes),
        types_objectifs=tuple(types_objectifs),
        nb_taches=len(instance_json.get("taches", [])),
        nb_ressources=len(instance_json.get("ressources", [])),
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


def analyser_mission(modele: BaseChatModel, instance_json: dict | None = None) -> ResultatAnalyse:
    """`instance_json` : instance T-R-C-O de l'instance en cours de génération (dict JSON) —
    optionnel pour les appelants historiques sans instance sous la main (scripts, tests) ; seule
    sa structure (types de contraintes/objectifs présents, compteurs) atteint le prompt, jamais
    ses valeurs (voir `extraire_structure_instance` et la docstring du module)."""
    structure_instance = extraire_structure_instance(instance_json or {})
    prompt = CHEMIN_PROMPT.read_text(encoding="utf-8").format(
        mission=charger_mission(),
        types_contraintes=", ".join(structure_instance.types_contraintes) or "aucune",
        types_objectifs=", ".join(structure_instance.types_objectifs) or "aucun",
        nb_taches=structure_instance.nb_taches,
        nb_ressources=structure_instance.nb_ressources,
    )

    structure = modele.with_structured_output(
        _SchemaAnalyse, include_raw=True, method=methode_sortie_structuree(modele)
    )
    sortie = _avec_retry(structure.invoke)([SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)])
    reponse_brute = extraire_texte_brut(sortie["raw"])
    if sortie["parsing_error"] is not None:
        raise ErreurReponseAgentInvalide(
            f"réponse non conforme au schéma reçue de l'agent : {reponse_brute[:200]!r}"
        ) from sortie["parsing_error"]

    donnees = sortie["parsed"]
    return ResultatAnalyse(
        reponse_brute=reponse_brute,
        entrees=donnees.entrees,
        sorties=donnees.sorties,
        contraintes_a_couvrir=tuple(donnees.contraintes_a_couvrir),
    )
