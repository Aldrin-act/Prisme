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

from generation.agents.base import ErreurReponseAgentInvalide, charger_mission  # noqa: F401 — réexporté (tests)
from generation.agents.client_llm import invoquer_agent_avec_outils

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


def _structure_contraintes_str(instance_json: dict) -> str:
    """Même format exact que `api/etat.py::structure_contraintes` (clé de
    matching du registre) — recalculé ici sur le `dict` brut plutôt
    qu'importé, `generation/agents/` restant indépendant de `api/`."""
    types = sorted({c["type"] for c in instance_json.get("contraintes", [])})
    return ",".join(types) if types else "aucune"


def _signature_objectifs_str(instance_json: dict) -> str:
    """Même format exact que `api/etat.py::signature_objectifs`."""
    types = sorted({o["type"] for o in instance_json.get("objectifs", [])})
    return ",".join(types)


def _resumer_solveurs_similaires(solveurs: list, client_id: str | None) -> str:
    """Fonction pure derrière l'outil LLM — testable sans registre réel."""
    if not solveurs:
        return "Aucun solveur déjà enregistré pour cette structure de contraintes et ces objectifs."
    memes_client = sum(1 for s in solveurs if client_id is not None and s.client_id == client_id)
    return (
        f"{len(solveurs)} solveur(s) déjà validé(s) et enregistré(s) pour cette structure de "
        f"contraintes et ces objectifs ({memes_client} pour ce client précis, "
        f"{len(solveurs) - memes_client} pour d'autres clients)."
    )


def construire_outil_instances_similaires(
    structure_contraintes: str, signature_objectifs: str, client_id: str | None
):
    """Construit l'outil de recherche d'instances similaires, connecté au
    registre de solveurs (`solver_store/registry.py`) — `None` si la base
    est injoignable, jamais bloquant (même philosophie que `test_sandbox`,
    `generation/graph.py` : l'infrastructure indisponible dégrade en
    silence, ne bloque jamais une tentative de génération).

    `structure_contraintes`/`signature_objectifs`/`client_id` sont figés à
    la construction (fermeture), pas des paramètres du modèle : l'agent
    décide seulement s'il consulte l'outil, jamais avec quels arguments —
    la question posée à cet outil, « existe-t-il déjà un solveur pour CETTE
    instance ? », n'a par nature qu'une seule réponse possible."""
    try:
        from solver_store.registry import Registre

        registre = Registre()
    except Exception:  # noqa: BLE001 — base injoignable/mal configurée, jamais bloquant ici
        return None

    from langchain_core.tools import tool

    @tool
    def rechercher_instances_similaires() -> str:
        """Recherche, parmi les solveurs déjà validés et enregistrés dans le
        registre, ceux qui partagent exactement la même structure de
        contraintes et les mêmes objectifs que l'instance en cours
        d'analyse — utile pour savoir si ce type de problème a déjà été
        résolu par le passé, pour ce client ou pour un autre."""
        solveurs = registre.rechercher_solveurs(
            client_id=None, structure_contraintes=structure_contraintes, signature_objectifs=signature_objectifs
        )
        return _resumer_solveurs_similaires(solveurs, client_id)

    return rechercher_instances_similaires


@dataclass(frozen=True)
class ResultatAnalyse:
    reponse_brute: str
    entrees: str
    sorties: str
    contraintes_a_couvrir: tuple[str, ...]
    # Trace des appels à rechercher_instances_similaires — jamais relue par
    # le pipeline, utile pour le diagnostic humain (voir
    # client_llm.invoquer_agent_avec_outils).
    appels_outils: tuple[str, ...] = ()

    def en_texte(self) -> str:
        """Rendu lisible, pour l'injecter dans le prompt de l'agent Architecte."""
        contraintes = "\n".join(f"- {c}" for c in self.contraintes_a_couvrir)
        return (
            f"### Entrées\n{self.entrees}\n\n"
            f"### Sorties\n{self.sorties}\n\n"
            f"### Contraintes à couvrir\n{contraintes}"
        )


def analyser_mission(
    modele: BaseChatModel,
    instance_json: dict | None = None,
    *,
    client_id: str | None = None,
    avec_outils: bool = True,
) -> ResultatAnalyse:
    """`instance_json` : instance T-R-C-O de l'instance en cours de génération (dict JSON) —
    optionnel pour les appelants historiques sans instance sous la main (scripts, tests) ; seule
    sa structure (types de contraintes/objectifs présents, compteurs) atteint le prompt, jamais
    ses valeurs (voir `extraire_structure_instance` et la docstring du module).

    `avec_outils` : si vrai (défaut) et `instance_json` fourni, l'agent reçoit l'outil
    `rechercher_instances_similaires` (voir `construire_outil_instances_similaires`) —
    dégradé en silence à aucun outil si le registre est injoignable ou si aucune
    instance n'est fournie (scripts/tests historiques)."""
    instance_json = instance_json or {}
    structure_instance = extraire_structure_instance(instance_json)
    prompt = CHEMIN_PROMPT.read_text(encoding="utf-8").format(
        mission=charger_mission(),
        types_contraintes=", ".join(structure_instance.types_contraintes) or "aucune",
        types_objectifs=", ".join(structure_instance.types_objectifs) or "aucun",
        nb_taches=structure_instance.nb_taches,
        nb_ressources=structure_instance.nb_ressources,
    )

    outils = []
    if avec_outils and instance_json:
        outil = construire_outil_instances_similaires(
            _structure_contraintes_str(instance_json), _signature_objectifs_str(instance_json), client_id
        )
        if outil is not None:
            outils = [outil]

    donnees, reponse_brute, appels_outils = invoquer_agent_avec_outils(
        modele,
        _SchemaAnalyse,
        outils,
        [SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)],
    )
    return ResultatAnalyse(
        reponse_brute=reponse_brute,
        entrees=donnees.entrees,
        sorties=donnees.sorties,
        contraintes_a_couvrir=tuple(donnees.contraintes_a_couvrir),
        appels_outils=tuple(appels_outils),
    )
