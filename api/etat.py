"""État en mémoire de l'API (démo PoC, §8). File d'instances ingérées,
résultats d'exécution et décisions humaines — un simple tampon entre les
routes, pas une persistance réelle : la seule persistance durable du
système est `solver_store/` (§5.2). Un déploiement réel remplacerait ceci
par une file de tâches / base de données ; hors périmètre du noyau minimal.

Un aléa atelier (panne, commande urgente, retard...) ne passe pas par un
type dédié ici : il se traduit directement dans les contraintes T-R-C-O de
l'instance réingérée (ex. la ressource en panne disparaît des
`CompatibiliteMachineTache`), puis un nouvel appel à `/execution/{instance_id}`
recalcule le planning — le processus exact varie d'un client à l'autre et
n'est donc pas figé dans le noyau.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from dsl.schema import InstanceTRCO
from sandbox.runner import ResultatExecution

Decision = Literal["acceptee", "refusee"]


def structure_contraintes(instance: InstanceTRCO) -> str:
    """Signature triée des types de contraintes présentes — la clé que le
    store (`solver_store/registry.py`) utilise pour retrouver le bon
    solveur pour cette forme d'instance (§7)."""
    types = sorted({contrainte.type for contrainte in instance.contraintes})
    return ",".join(types) if types else "aucune"


@dataclass(frozen=True)
class DecisionHumaine:
    """La décision humaine sur un planning proposé (§2.3, PH10-T2) — jamais
    prise automatiquement, toujours tracée."""

    execution_id: str
    decision: Decision
    horodatage: str
    commentaire: str | None = None


@dataclass
class EtatAPI:
    instances: dict[str, tuple[str, InstanceTRCO]] = field(default_factory=dict)
    executions: dict[str, tuple[str, str, ResultatExecution]] = field(default_factory=dict)
    decisions: dict[str, DecisionHumaine] = field(default_factory=dict)

    def enregistrer_instance(self, client_id: str, instance: InstanceTRCO) -> str:
        instance_id = str(uuid.uuid4())
        self.instances[instance_id] = (client_id, instance)
        return instance_id

    def recuperer_instance(self, instance_id: str) -> tuple[str, InstanceTRCO]:
        if instance_id not in self.instances:
            raise KeyError(instance_id)
        return self.instances[instance_id]

    def enregistrer_execution(self, id_solveur: str, instance_id: str, resultat: ResultatExecution) -> str:
        execution_id = str(uuid.uuid4())
        self.executions[execution_id] = (id_solveur, instance_id, resultat)
        return execution_id

    def recuperer_execution(self, execution_id: str) -> tuple[str, str, ResultatExecution]:
        if execution_id not in self.executions:
            raise KeyError(execution_id)
        return self.executions[execution_id]

    def lister_executions(self) -> list[dict[str, object]]:
        """Vue de supervision (lecture seule) sur toutes les exécutions connues."""
        resultats = []
        for execution_id, (id_solveur, instance_id, resultat) in self.executions.items():
            client_id, _ = self.instances[instance_id]
            decision = self.decisions.get(execution_id)
            resultats.append(
                {
                    "execution_id": execution_id,
                    "id_solveur": id_solveur,
                    "instance_id": instance_id,
                    "client_id": client_id,
                    "reussi": resultat.reussi,
                    "erreur": resultat.erreur,
                    "decision": decision.decision if decision else None,
                }
            )
        return resultats

    def lister_instances(self) -> list[dict[str, object]]:
        """Vue de supervision (lecture seule) sur toutes les instances
        ingérées, avec un indicateur `executee` pour repérer celles en attente."""
        instances_executees = {instance_id for (_, instance_id, _) in self.executions.values()}
        return [
            {
                "instance_id": instance_id,
                "client_id": client_id,
                "structure_contraintes": structure_contraintes(instance),
                "executee": instance_id in instances_executees,
            }
            for instance_id, (client_id, instance) in self.instances.items()
        ]

    def enregistrer_decision(self, execution_id: str, decision: Decision, commentaire: str | None = None) -> None:
        self.decisions[execution_id] = DecisionHumaine(
            execution_id=execution_id,
            decision=decision,
            horodatage=datetime.now(UTC).isoformat(),
            commentaire=commentaire,
        )

    def decision_pour(self, execution_id: str) -> DecisionHumaine | None:
        return self.decisions.get(execution_id)


_ETAT_GLOBAL = EtatAPI()


def obtenir_etat() -> EtatAPI:
    return _ETAT_GLOBAL
