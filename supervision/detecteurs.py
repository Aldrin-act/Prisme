"""Détection de signaux (§2, MT7) — délègue la décision (quel signal s'applique à quelle
instance) à un appel LLM unique (`supervision.agent.detecter_signaux_llm`) plutôt qu'à des
comparaisons Python : c'est le LLM qui compare les `instance_id`, les dates de
modification/exécution et l'historique d'échecs, à partir des faits bruts assemblés ici. Ce
module se limite à rassembler ces faits et à valider ce que le LLM en tire avant de le convertir
en signaux typés — jamais recalculé ni redécidé ici, mais jamais non plus accepté aveuglément :
un `instance_id`, `id_solveur_disponible` ou `execution_id` qui ne correspond à aucune donnée
réellement fournie est silencieusement écarté plutôt que propagé (le LLM peut se tromper ou
halluciner, voir `supervision.agent.SignalBrutLLM`) — y compris un `id_solveur_disponible` réel
mais appartenant à une **autre** instance : un solveur ne sert jamais que l'instance qui l'a fait
générer (`solver_store/registry.py`), jamais une autre même de structure/objectifs identiques.

Trois signaux :

1. **Signature orpheline** — aucun solveur actif enregistré pour ce client n'a d'`instance_id`
   égal à celui de cette instance.
2. **Instance à replanifier** — un solveur actif a bien un `instance_id` égal à celui de cette
   instance (le sien), mais soit l'instance n'a jamais été exécutée, soit elle l'a été puis a été
   modifiée depuis (`modifier_instance`/`modifier_objectifs`, `api/etat.py`) sans être
   ré-exécutée.
3. **Échecs répétés** — les 3 dernières exécutions d'une même instance sont toutes en échec.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from api.etat import EtatAPI, signature_objectifs, structure_contraintes
from solver_store.registry import Registre
from supervision.agent import (
    ExecutionSupervision,
    InstanceSupervision,
    RaisonReplanification,
    SolveurSupervision,
    detecter_signaux_llm,
)

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


@dataclass(frozen=True)
class SignalSignatureOrpheline:
    instance_id: str
    client_id: str
    structure_contraintes: str
    signature_objectifs: str


@dataclass(frozen=True)
class SignalInstanceAReplanifier:
    instance_id: str
    client_id: str
    structure_contraintes: str
    signature_objectifs: str
    id_solveur_disponible: str
    raison: RaisonReplanification


@dataclass(frozen=True)
class SignalEchecsRepetes:
    instance_id: str
    client_id: str
    id_solveur: str
    execution_ids: tuple[str, ...]
    structure_contraintes: str
    signature_objectifs: str


SignalDetecte = SignalSignatureOrpheline | SignalInstanceAReplanifier | SignalEchecsRepetes


def detecter_signaux(
    etat: EtatAPI, registre: Registre, modele: BaseChatModel, client_id: str
) -> tuple[SignalDetecte, ...]:
    """Rassemble instances/solveurs/exécutions de ce client, délègue la détection à
    `supervision.agent.detecter_signaux_llm`, puis valide et convertit sa réponse. N'appelle
    jamais le LLM si le client n'a aucune instance — rien à détecter."""
    instances: dict[str, InstanceSupervision] = {}
    for info in etat.lister_instances(client_id=client_id):
        instance_id = info["instance_id"]
        _, instance = etat.recuperer_instance(instance_id)
        instances[instance_id] = InstanceSupervision(
            instance_id=instance_id,
            structure_contraintes=structure_contraintes(instance),
            signature_objectifs=signature_objectifs(instance),
            date_modification=info["date_modification"],
        )
    if not instances:
        return ()

    solveurs = {
        s.id: SolveurSupervision(
            id=s.id,
            instance_id=s.instance_id,
            structure_contraintes=s.structure_contraintes,
            signature_objectifs=s.signature_objectifs,
        )
        for s in registre.rechercher_solveurs(client_id=client_id)
    }

    executions = {
        e["execution_id"]: ExecutionSupervision(
            execution_id=e["execution_id"],
            instance_id=e["instance_id"],
            id_solveur=e["id_solveur"],
            date_execution=e["date_execution"],
            reussi=e["reussi"],
        )
        for e in etat.lister_executions(client_id=client_id)
    }

    bruts = detecter_signaux_llm(
        modele, tuple(instances.values()), tuple(solveurs.values()), tuple(executions.values())
    )

    signaux: list[SignalDetecte] = []
    for brut in bruts:
        instance = instances.get(brut.instance_id)
        if instance is None:
            continue  # instance_id halluciné — jamais propagé

        if brut.type_signal == "signature_orpheline":
            signaux.append(
                SignalSignatureOrpheline(
                    instance_id=instance.instance_id,
                    client_id=client_id,
                    structure_contraintes=instance.structure_contraintes,
                    signature_objectifs=instance.signature_objectifs,
                )
            )
        elif brut.type_signal == "instance_a_replanifier":
            # Un solveur ne sert que l'instance qui l'a fait générer — revérifié ici même si le
            # prompt (`detection.md`) l'interdit déjà : le LLM peut se tromper de solveur ou
            # halluciner, jamais fait confiance aveuglément (voir docstring de module).
            if (
                brut.raison is None
                or brut.id_solveur_disponible not in solveurs
                or solveurs[brut.id_solveur_disponible].instance_id != instance.instance_id
            ):
                continue
            signaux.append(
                SignalInstanceAReplanifier(
                    instance_id=instance.instance_id,
                    client_id=client_id,
                    structure_contraintes=instance.structure_contraintes,
                    signature_objectifs=instance.signature_objectifs,
                    id_solveur_disponible=brut.id_solveur_disponible,
                    raison=brut.raison,
                )
            )
        else:  # echecs_repetes
            ids_valides = tuple(e for e in brut.execution_ids if e in executions)
            if brut.id_solveur is None or not ids_valides:
                continue
            signaux.append(
                SignalEchecsRepetes(
                    instance_id=instance.instance_id,
                    client_id=client_id,
                    id_solveur=brut.id_solveur,
                    execution_ids=ids_valides,
                    structure_contraintes=instance.structure_contraintes,
                    signature_objectifs=instance.signature_objectifs,
                )
            )
    return tuple(signaux)
