"""Agent Testeur (pipeline multi-agents, §5.6) — génère des tests pytest
complémentaires à la cascade de validation (`validation_engine/cascade.py`).

Ces tests sont exécutés une seule fois, en meilleur effort, dans le bac à
sable Docker après le succès de la boucle de réparation
(`generation/graph.py::_noeud_test_sandbox`,
`sandbox/runner.py::executer_tests_dans_sandbox`) — jamais un critère
d'acceptation du solveur, seule la cascade de validation l'est. Canal
d'audit pur : leur échec (ou l'indisponibilité du sandbox) n'affecte jamais
`boucle_reussie` ni la réponse de `/generation/{instance_id}`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from generation.agents.analyste import extraire_structure_instance
from generation.agents.base import ErreurReponseAgentInvalide, charger_mission  # noqa: F401 — réexporté (tests)
from generation.agents.client_llm import invoquer_agent_avec_outils

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "testeur.md"

_PROMPT_SYSTEME = (
    "Tu es un ingénieur qualité spécialisé en tests de solveurs d'optimisation combinatoire. "
    "Tu réponds toujours en JSON strict, jamais en texte libre."
)


class _SchemaTests(BaseModel):
    code_tests: str = Field(description="Module de tests pytest complémentaires.")


@dataclass(frozen=True)
class ResultatTests:
    reponse_brute: str
    code_tests: str
    # Trace des appels à consulter_cas_limites_banc_synthetique — jamais
    # relue par le pipeline, utile pour le diagnostic humain (voir
    # client_llm.invoquer_agent_avec_outils).
    appels_outils: tuple[str, ...] = ()


def decrire_cas_limites_banc_synthetique() -> str:
    """Fonction pure derrière l'outil LLM — testable sans modèle ni outil
    LangChain. Profils courts des cas du catalogue synthétique (Étape 3,
    `validation_engine/synthetic_bench/`) : chacun est une petite instance
    T-R-C-O construite à l'envers, à makespan optimal **connu par
    construction**, jamais calculé a posteriori (voir
    `construction_inverse.py`) — utile pour ancrer un test sur une structure
    d'instance réelle et une valeur attendue exacte, plutôt que d'inventer un
    scénario ou un seuil arbitraire."""
    from validation_engine.synthetic_bench.catalogue import generer_catalogue

    return "\n".join(
        f"- {cas.nom} : {len(cas.instance.taches)} tâche(s), {len(cas.instance.ressources)} ressource(s), "
        f"makespan optimal connu = {cas.optimum}"
        for cas in generer_catalogue()
    )


def _construire_outil_cas_limites_banc_synthetique():
    """Outil lié à ce module, jamais construit au niveau module (import
    paresseux de `langchain_core.tools`, comme le reste des dépendances
    LangChain de ce projet — voir `client_llm.py`)."""
    from langchain_core.tools import tool

    @tool
    def consulter_cas_limites_banc_synthetique() -> str:
        """Renvoie les cas du catalogue synthétique (Étape 3) — chacun une
        petite instance T-R-C-O à makespan optimal connu par construction —
        pour écrire un test qui vérifie une vraie valeur plutôt qu'un
        scénario inventé."""
        return decrire_cas_limites_banc_synthetique()

    return consulter_cas_limites_banc_synthetique


def generer_tests(
    modele: BaseChatModel,
    code_source: str,
    *,
    avec_outils: bool = True,
    instance_json: dict | None = None,
    algorithme: str = "cp_sat",
) -> ResultatTests:
    """`avec_outils` : si vrai (défaut), l'agent peut consulter
    `consulter_cas_limites_banc_synthetique` (voir plus haut) avant de
    répondre — jamais requis, purement consultatif. `False` retombe sur un
    appel structuré simple, sans outil (tests, comparaison avant/après).

    `instance_json`/`algorithme` : seule la *structure* de l'instance (types de contraintes et
    d'objectifs, jamais ses valeurs — même extraction que l'Analyste) et l'algorithme choisi par
    le Benchmarker atteignent le prompt. Sans eux, le Testeur écrivait des tests sur des types
    que le solveur n'a jamais eu à traiter (ex. une `Echeance` pour prouver l'infaisabilité d'une
    instance sans échéance), qui échouaient sur un solveur correct et poussaient le Debugger à
    l'abîmer."""
    structure = extraire_structure_instance(instance_json or {})
    gabarit = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = gabarit.format(
        mission=charger_mission(),
        code=code_source,
        algorithme=algorithme,
        types_contraintes=", ".join(structure.types_contraintes) or "inconnus (aucune instance fournie)",
        types_objectifs=", ".join(structure.types_objectifs) or "inconnus (aucune instance fournie)",
    )

    outils = [_construire_outil_cas_limites_banc_synthetique()] if avec_outils else []
    donnees, reponse_brute, appels_outils = invoquer_agent_avec_outils(
        modele, _SchemaTests, outils, [SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)]
    )
    return ResultatTests(
        reponse_brute=reponse_brute, code_tests=donnees.code_tests, appels_outils=tuple(appels_outils)
    )
