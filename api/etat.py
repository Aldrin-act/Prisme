"""État en mémoire de l'API (démo PoC, §8). File d'instances ingérées,
résultats d'exécution, alertes d'aléa et décisions humaines — un simple
tampon entre les routes, pas une persistance réelle : la seule persistance
durable du système est `solver_store/` (§5.2). Un déploiement réel
remplacerait ceci par une file de tâches / base de données ; hors périmètre
du noyau minimal.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from dsl.schema import InstanceTRCO
from sandbox.runner import ResultatExecution

TypeAlea = Literal["panne", "commande_urgente", "retard"]
StatutAlerte = Literal["nouvelle", "traitee"]
Decision = Literal["acceptee", "refusee"]


def structure_contraintes(instance: InstanceTRCO) -> str:
    """Signature triée des types de contraintes présentes — la clé que le
    store (`solver_store/registry.py`) utilise pour retrouver le bon
    solveur pour cette forme d'instance (§7)."""
    types = sorted({contrainte.type for contrainte in instance.contraintes})
    return ",".join(types) if types else "aucune"


@dataclass(frozen=True)
class Alerte:
    """Un aléa atelier signalé (§2.3) : panne, commande urgente, retard —
    jamais détecté automatiquement ici, toujours signalé explicitement
    (hors périmètre du noyau minimal de vraiment surveiller l'atelier)."""

    id: str
    instance_id: str
    client_id: str
    type_alea: TypeAlea
    description: str
    horodatage: str
    statut: StatutAlerte
    execution_id: str | None = None


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
    alertes: dict[str, Alerte] = field(default_factory=dict)
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

    def lever_alerte(self, instance_id: str, client_id: str, type_alea: TypeAlea, description: str) -> str:
        alerte_id = str(uuid.uuid4())
        self.alertes[alerte_id] = Alerte(
            id=alerte_id,
            instance_id=instance_id,
            client_id=client_id,
            type_alea=type_alea,
            description=description,
            horodatage=datetime.now(UTC).isoformat(),
            statut="nouvelle",
        )
        return alerte_id

    def recuperer_alerte(self, alerte_id: str) -> Alerte:
        if alerte_id not in self.alertes:
            raise KeyError(alerte_id)
        return self.alertes[alerte_id]

    def lister_alertes(self) -> list[Alerte]:
        return list(self.alertes.values())

    def marquer_alerte_traitee(self, alerte_id: str, execution_id: str) -> None:
        alerte = self.recuperer_alerte(alerte_id)
        self.alertes[alerte_id] = Alerte(
            id=alerte.id,
            instance_id=alerte.instance_id,
            client_id=alerte.client_id,
            type_alea=alerte.type_alea,
            description=alerte.description,
            horodatage=alerte.horodatage,
            statut="traitee",
            execution_id=execution_id,
        )

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
