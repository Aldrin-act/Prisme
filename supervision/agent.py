"""Agent(s) LLM de supervision (§2, MT7). Deux appels distincts, jamais fusionnés en un seul —
même logique de séparation des responsabilités que le pipeline de génération (Benchmarker,
Architecte, Développeur... chacun un rôle) :

1. `detecter_signaux_llm` — reçoit les données brutes d'**un seul atelier** (l'instance, ses
   solveurs enregistrés, son historique d'exécutions, assemblées par `supervision/detecteurs.py`)
   et décide lui-même quel signal (signature orpheline / instance à replanifier / échecs répétés, voir
   `supervision/prompts/detection.md`) s'applique à quelle instance — comparaisons de signatures,
   de dates, d'historique d'échecs, tout est fait par le LLM, rien n'est précalculé côté Python
   au-delà de l'assemblage des faits bruts.
2. `proposer_actions` — reçoit les signaux déjà détectés pour ce même atelier et se
   contente de les prioriser et de les rédiger en langage naturel pour un humain non technicien.

`supervision/detecteurs.py` ne fait confiance à aucun des deux aveuglément : tout identifiant
(`instance_id`, `id_solveur_disponible`, `execution_id`...) recopié par le LLM est revérifié
contre les données réellement fournies avant d'être converti en signal typé.

Vit en dehors de `generation/agents/` car ce n'est pas un nœud du
`StateGraph` de génération (`generation/graph.py`) — même précédent que
`adapters/agent_comprehension/` : un agent autonome qui réutilise
`generation.agents.base`/`generation.agents.client_llm`, prompt local au
package plutôt que dans `generation/prompts/`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from generation.agents.base import ErreurReponseAgentInvalide, extraire_texte_brut
from generation.agents.client_llm import _avec_retry, methode_sortie_structuree

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel

CHEMIN_PROMPT = Path(__file__).resolve().parent / "prompts" / "supervision.md"
CHEMIN_PROMPT_DETECTION = Path(__file__).resolve().parent / "prompts" / "detection.md"

_PROMPT_SYSTEME = (
    "Tu es un expert en supervision de systèmes d'ordonnancement industriel. "
    "Tu ne détectes rien toi-même : tu priorises et rédiges en langage naturel des faits "
    "déjà détectés par un module déterministe. Tu réponds toujours en JSON strict."
)

_PROMPT_SYSTEME_DETECTION = (
    "Tu es un expert en supervision de systèmes d'ordonnancement industriel. Tu compares des "
    "données brutes (instances, solveurs enregistrés, historique d'exécutions) pour détecter des "
    "signaux selon des règles précises — aucun calcul n'est fait avant toi. "
    "Tu réponds toujours en JSON strict."
)

RaisonReplanification = Literal["jamais_executee", "modifiee_apres_derniere_execution"]
TypeSignalDetecte = Literal["signature_orpheline", "instance_a_replanifier", "echecs_repetes"]


class _SchemaPropositionUnitaire(BaseModel):
    reference: str = Field(description="Identifiant du fait, recopié tel quel depuis la liste fournie.")
    resume: str = Field(description="Résumé clair en une ou deux phrases, destiné à un humain non technicien.")
    priorite: Literal["haute", "moyenne", "basse"] = Field(default="moyenne")


class _SchemaSupervision(BaseModel):
    propositions: list[_SchemaPropositionUnitaire] = Field(default_factory=list)


@dataclass(frozen=True)
class FaitSignal:
    """Un signal détecté par `supervision/detecteurs.py`, réduit à ce dont
    l'agent LLM a besoin : une référence stable (que le LLM doit recopier
    telle quelle, jamais reformuler) et une description factuelle."""

    reference: str  # "{type_signal}:{instance_id}" — clé stable, voir supervision/orchestrateur.py
    description: str


@dataclass(frozen=True)
class PropositionLLM:
    reference: str
    resume: str
    priorite: Literal["haute", "moyenne", "basse"]


@dataclass(frozen=True)
class ResultatSupervision:
    reponse_brute: str
    propositions: tuple[PropositionLLM, ...]


def _formater_faits(faits: tuple[FaitSignal, ...]) -> str:
    return "\n".join(f"- `{fait.reference}` : {fait.description}" for fait in faits)


def proposer_actions(modele: BaseChatModel, faits: tuple[FaitSignal, ...]) -> ResultatSupervision:
    """Priorise et rédige une proposition par fait. N'appelle jamais le LLM
    sur une liste vide — à la charge de l'appelant (`supervision/orchestrateur.py`)
    de ne pas invoquer cette fonction s'il n'y a rien de nouveau à proposer."""
    prompt_template = CHEMIN_PROMPT.read_text(encoding="utf-8")
    prompt = prompt_template.format(faits=_formater_faits(faits))

    structure = modele.with_structured_output(
        _SchemaSupervision, include_raw=True, method=methode_sortie_structuree(modele)
    )
    sortie = _avec_retry(structure.invoke)([SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)])
    reponse_brute = extraire_texte_brut(sortie["raw"])
    if sortie["parsing_error"] is not None:
        raise ErreurReponseAgentInvalide(
            f"réponse non conforme au schéma reçue de l'agent : {reponse_brute[:200]!r}"
        ) from sortie["parsing_error"]

    donnees = sortie["parsed"]
    propositions = tuple(
        PropositionLLM(reference=p.reference, resume=p.resume, priorite=p.priorite) for p in donnees.propositions
    )
    return ResultatSupervision(reponse_brute=reponse_brute, propositions=propositions)


# ---------------------------------------------------------------------------
# Détection (voir docstring de module) — remplace les comparaisons Python qui
# vivaient auparavant dans supervision/detecteurs.py.
# ---------------------------------------------------------------------------


class _SchemaSignalDetecte(BaseModel):
    instance_id: str
    type_signal: TypeSignalDetecte
    raison: RaisonReplanification | None = Field(
        default=None, description="Uniquement pour instance_a_replanifier."
    )
    id_solveur_disponible: str | None = Field(default=None, description="Uniquement pour instance_a_replanifier.")
    id_solveur: str | None = Field(default=None, description="Uniquement pour echecs_repetes.")
    execution_ids: list[str] = Field(default_factory=list, description="Uniquement pour echecs_repetes.")


class _SchemaDetectionSupervision(BaseModel):
    signaux: list[_SchemaSignalDetecte] = Field(default_factory=list)


@dataclass(frozen=True)
class InstanceSupervision:
    instance_id: str
    structure_contraintes: str
    signature_objectifs: str
    date_modification: str | None


@dataclass(frozen=True)
class SolveurSupervision:
    id: str
    instance_id: str | None
    structure_contraintes: str
    signature_objectifs: str


@dataclass(frozen=True)
class ExecutionSupervision:
    execution_id: str
    instance_id: str
    id_solveur: str
    date_execution: str | None
    reussi: bool


@dataclass(frozen=True)
class SignalBrutLLM:
    """Sortie non validée de `detecter_signaux_llm` — à `supervision.detecteurs.detecter_signaux`
    de vérifier que chaque identifiant recopié correspond bien à une donnée réellement fournie
    avant de s'en servir (même prudence qu'`orchestrateur.py` envers les références de
    `proposer_actions` : un LLM se trompe parfois, jamais propagé aveuglément)."""

    instance_id: str
    type_signal: TypeSignalDetecte
    raison: RaisonReplanification | None
    id_solveur_disponible: str | None
    id_solveur: str | None
    execution_ids: tuple[str, ...]


def _formater_instances(instances: tuple[InstanceSupervision, ...]) -> str:
    if not instances:
        return "(aucune instance)"
    return "\n".join(
        f"- `{i.instance_id}` : structure_contraintes=`{i.structure_contraintes}`, "
        f"signature_objectifs=`{i.signature_objectifs}`, date_modification={i.date_modification!r}"
        for i in instances
    )


def _formater_solveurs(solveurs: tuple[SolveurSupervision, ...]) -> str:
    if not solveurs:
        return "(aucun solveur enregistré)"
    return "\n".join(
        f"- `{s.id}` : instance_id=`{s.instance_id}`, structure_contraintes=`{s.structure_contraintes}`, "
        f"signature_objectifs=`{s.signature_objectifs}` (structure/objectifs informatifs uniquement — "
        f"seul instance_id détermine à quelle instance ce solveur appartient)"
        for s in solveurs
    )


def _formater_executions(executions: tuple[ExecutionSupervision, ...]) -> str:
    if not executions:
        return "(aucune exécution)"
    return "\n".join(
        f"- `{e.execution_id}` : instance_id=`{e.instance_id}`, id_solveur=`{e.id_solveur}`, "
        f"date_execution={e.date_execution!r}, reussi={e.reussi}"
        for e in executions
    )


def detecter_signaux_llm(
    modele: BaseChatModel,
    instances: tuple[InstanceSupervision, ...],
    solveurs: tuple[SolveurSupervision, ...],
    executions: tuple[ExecutionSupervision, ...],
) -> tuple[SignalBrutLLM, ...]:
    """Un appel LLM par atelier : `supervision.detecteurs.detecter_signaux_instance` ne passe
    jamais que l'instance analysée, ses propres solveurs et ses propres exécutions — jamais les
    données d'un autre atelier dans le même prompt. Renvoie la sortie du LLM telle quelle,
    non validée contre les données réelles (voir `SignalBrutLLM`) ; c'est
    `supervision.detecteurs.detecter_signaux` qui s'en charge avant de construire les signaux
    typés persistables."""
    prompt_template = CHEMIN_PROMPT_DETECTION.read_text(encoding="utf-8")
    prompt = prompt_template.format(
        instances=_formater_instances(instances),
        solveurs=_formater_solveurs(solveurs),
        executions=_formater_executions(executions),
    )

    structure = modele.with_structured_output(
        _SchemaDetectionSupervision, include_raw=True, method=methode_sortie_structuree(modele)
    )
    sortie = _avec_retry(structure.invoke)(
        [SystemMessage(content=_PROMPT_SYSTEME_DETECTION), HumanMessage(content=prompt)]
    )
    reponse_brute = extraire_texte_brut(sortie["raw"])
    if sortie["parsing_error"] is not None:
        raise ErreurReponseAgentInvalide(
            f"réponse non conforme au schéma reçue de l'agent de détection : {reponse_brute[:200]!r}"
        ) from sortie["parsing_error"]

    donnees = sortie["parsed"]
    return tuple(
        SignalBrutLLM(
            instance_id=s.instance_id,
            type_signal=s.type_signal,
            raison=s.raison,
            id_solveur_disponible=s.id_solveur_disponible,
            id_solveur=s.id_solveur,
            execution_ids=tuple(s.execution_ids),
        )
        for s in donnees.signaux
    )
