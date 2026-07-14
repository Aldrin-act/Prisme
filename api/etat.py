"""État en mémoire de l'API (démo PoC, §8). File d'instances ingérées et
résultats d'exécution — un simple tampon entre les routes, pas une
persistance réelle : la seule persistance durable du système est
`solver_store/` (§5.2). Un déploiement réel remplacerait ceci par une file
de tâches / base de données ; hors périmètre du noyau minimal.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from dsl.schema import InstanceTRCO
from sandbox.runner import ResultatExecution


def structure_contraintes(instance: InstanceTRCO) -> str:
    """Signature triée des types de contraintes présentes — la clé que le
    store (`solver_store/registry.py`) utilise pour retrouver le bon
    solveur pour cette forme d'instance (§7)."""
    types = sorted({contrainte.type for contrainte in instance.contraintes})
    return ",".join(types) if types else "aucune"


@dataclass
class EtatAPI:
    instances: dict[str, tuple[str, InstanceTRCO]] = field(default_factory=dict)
    executions: dict[str, tuple[str, ResultatExecution]] = field(default_factory=dict)

    def enregistrer_instance(self, client_id: str, instance: InstanceTRCO) -> str:
        instance_id = str(uuid.uuid4())
        self.instances[instance_id] = (client_id, instance)
        return instance_id

    def recuperer_instance(self, instance_id: str) -> tuple[str, InstanceTRCO]:
        if instance_id not in self.instances:
            raise KeyError(instance_id)
        return self.instances[instance_id]

    def enregistrer_execution(self, id_solveur: str, resultat: ResultatExecution) -> str:
        execution_id = str(uuid.uuid4())
        self.executions[execution_id] = (id_solveur, resultat)
        return execution_id

    def recuperer_execution(self, execution_id: str) -> tuple[str, ResultatExecution]:
        if execution_id not in self.executions:
            raise KeyError(execution_id)
        return self.executions[execution_id]


_ETAT_GLOBAL = EtatAPI()


def obtenir_etat() -> EtatAPI:
    return _ETAT_GLOBAL
