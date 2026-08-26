"""Outil de consultation documentaire pour les agents Architecte et Développeur (§5.6) — un vrai
usage d'outil, pas du tool-calling natif LangChain (`bind_tools`/`method="function_calling"`) :
ce mécanisme a été délibérément écarté pour l'ensemble du pipeline
(`generation/agents/client_llm.py::methode_sortie_structuree`) après des incidents de fin de vie
de modèles chez deux des cinq fournisseurs du projet — dont NVIDIA, qui sert justement Architecte
et Développeur par défaut (`config_fournisseurs.py`). Rester provider-agnostic.

Mécanisme retenu : un petit appel de décision en sortie structurée (même méthode que tout le
reste du pipeline) où l'agent choisit lui-même, parmi un catalogue fermé de sujets, lequel (s'il
y en a un) l'aiderait avant de continuer — puis une recherche exacte, locale et déterministe
(pas de RAG/embedding : le catalogue est volontairement restreint). Jamais bloquant : toute
réponse absente, mal formée, ou portant sur un sujet inconnu est traitée comme « aucun besoin »,
jamais comme une erreur qui interromprait la génération.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from generation.agents.client_llm import invoquer_agent_structure

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

_DOSSIER_REFERENCE = Path(__file__).resolve().parents[1] / "prompts" / "reference"
_CHEMIN_PROMPT_DECISION = Path(__file__).resolve().parents[1] / "prompts" / "decision_documentation.md"

_PROMPT_SYSTEME_DECISION = (
    "Tu réponds toujours en JSON strict, jamais en texte libre. Tu ne demandes un sujet de "
    "documentation que s'il t'apporterait réellement quelque chose de nouveau."
)

# Catalogue volontairement plat et restreint (§ voir docstring module) — un sujet = un fichier
# markdown sous prompts/reference/. Ajouter un sujet : une entrée ici + un fichier, rien d'autre.
_DESCRIPTIONS: dict[str, str] = {
    "cp_sat_avance": (
        "API CP-SAT au-delà des contraintes DSL déjà couvertes par la mission — AddCircuit, "
        "NewOptionalIntervalVar, paramètres du solveur, AddHint, statuts."
    ),
    "genetic": "Opérateurs d'algorithme génétique — croisement, mutation, sélection, élitisme.",
    "aco": "Optimisation par colonies de fourmis — matrice de phéromones, mise à jour, désirabilité heuristique.",
    "tabu_search": "Recherche tabou — liste taboue, tenure, voisinage, critère d'aspiration.",
    "simulated_annealing": "Recuit simulé — calendrier de refroidissement, probabilité d'acceptation, voisinage.",
    "dispatching": "Règles de priorité (SPT, LPT, EDD, ratio critique) pour les heuristiques de dispatching.",
    "greedy_local": "Heuristique gloutonne suivie d'une recherche locale (2-opt, échange) de raffinement.",
}


def lister_sujets_disponibles() -> dict[str, str]:
    """Copie du catalogue — jamais l'objet interne, pour empêcher un appelant de le modifier."""
    return dict(_DESCRIPTIONS)


def rechercher_documentation(sujet: str | None) -> str | None:
    """Renvoie le contenu du sujet demandé, ou `None` si absent, vide, ou inconnu — jamais
    d'exception : un sujet mal orthographié par le LLM ne doit jamais faire échouer la
    génération, seulement ne rien apporter (voir `consulter_si_utile`)."""
    if not sujet or sujet not in _DESCRIPTIONS:
        return None
    chemin = _DOSSIER_REFERENCE / f"{sujet}.md"
    if not chemin.exists():
        return None
    return chemin.read_text(encoding="utf-8")


class _SchemaBesoinDocumentation(BaseModel):
    sujet: str | None = Field(
        default=None, description="Nom exact d'un sujet du catalogue proposé, ou null si aucun besoin."
    )


def consulter_si_utile(modele: BaseChatModel, tache: str, algorithme: str) -> str:
    """Demande au modèle, via un petit appel de décision, s'il a besoin d'un des sujets de
    référence disponibles avant de `tache` pour l'algorithme `algorithme` — renvoie le contenu
    formaté à insérer dans le prompt principal (`{documentation}`), ou une chaîne vide si aucun
    besoin exprimé, sujet inconnu, ou tout échec de l'appel.

    Capture `Exception` au sens large (pas seulement `ErreurReponseAgentInvalide`) et lit
    `getattr(donnees, "sujet", None)` plutôt que `donnees.sujet` : un outil auxiliaire ne doit
    jamais faire échouer l'étape principale, même si l'objet renvoyé n'a pas la forme attendue
    (voir `tests/integration/test_graph_pipeline.py::_fabrique` — un même modèle factice y sert
    à la fois l'appel de décision et l'appel principal dans les tests existants)."""
    descriptions = "\n".join(f"- `{nom}` : {texte}" for nom, texte in _DESCRIPTIONS.items())
    prompt = _CHEMIN_PROMPT_DECISION.read_text(encoding="utf-8").format(
        tache=tache, algorithme=algorithme, sujets_disponibles=descriptions
    )
    try:
        donnees, _ = invoquer_agent_structure(
            modele,
            _SchemaBesoinDocumentation,
            [SystemMessage(content=_PROMPT_SYSTEME_DECISION), HumanMessage(content=prompt)],
        )
        sujet = getattr(donnees, "sujet", None)
    except Exception:  # noqa: BLE001 — outil auxiliaire, jamais bloquant pour l'étape principale
        return ""

    contenu = rechercher_documentation(sujet)
    if contenu is None:
        return ""
    return f"### {sujet}\n\n{contenu}"
