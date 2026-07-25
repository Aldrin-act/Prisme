"""État de l'API (§8). File d'instances ingérées, résultats d'exécution et
décisions humaines. `EtatAPI` (ci-dessous) reste l'implémentation en
mémoire — utilisée par les tests (`app.dependency_overrides`, isolation
gratuite par test) — mais `obtenir_etat()` sert par défaut `EtatPostgres`
(`api/etat_postgres.py`, §7 extension) : la persistance réelle du système
n'est donc plus limitée à `solver_store/` (§5.2), elle couvre aussi
instances/exécutions/décisions.

Un aléa atelier (panne, commande urgente, retard...) ne passe pas par un
type dédié ici : il se traduit directement dans les contraintes T-R-C-O de
l'instance réingérée (ex. la ressource en panne disparaît des
`CompatibiliteRessourceTache`), puis un nouvel appel à `/execution/{instance_id}`
recalcule le planning — le processus exact varie d'un client à l'autre et
n'est donc pas figé dans le noyau.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from dsl.schema import InstanceTRCO, Objectif
from sandbox.runner import ResultatExecution

if TYPE_CHECKING:
    from api.etat_postgres import EtatPostgres

Decision = Literal["acceptee", "refusee"]


def structure_contraintes(instance: InstanceTRCO) -> str:
    """Signature triée des types de contraintes présentes — la clé que le
    store (`solver_store/registry.py`) utilise pour retrouver le bon
    solveur pour cette forme d'instance (§7)."""
    types = sorted({contrainte.type for contrainte in instance.contraintes})
    return ",".join(types) if types else "aucune"


def signature_objectifs(instance: InstanceTRCO) -> str:
    """Signature triée des types d'objectifs demandés — seconde moitié de la
    clé de matching solveur (avec `structure_contraintes`) : un solveur
    généré pour `minimiser_makespan` ne doit jamais être exécuté
    silencieusement sur une instance visant `equilibrer_charge`."""
    types = sorted({objectif.type for objectif in instance.objectifs})
    return ",".join(types)


@dataclass(frozen=True)
class DecisionHumaine:
    """La décision humaine sur un planning proposé (§2.3, PH10-T2) — jamais
    prise automatiquement, toujours tracée."""

    execution_id: str
    decision: Decision
    horodatage: str
    commentaire: str | None = None


@dataclass(frozen=True)
class Client:
    """Un client (tenant métier) — l'unité de cloisonnement des données dans
    tout le système (§7) : matching des solveurs (`solver_store/registry.py`),
    visibilité des instances/projets (`api/autorisation.py`). Créé
    explicitement (ce module) plutôt qu'implicitement au premier usage, pour
    porter un vrai nom et pouvoir être choisi à l'inscription d'un compte."""

    id: str
    nom: str | None


@dataclass(frozen=True)
class Projet:
    """Regroupe des données brutes persistées (ex. export ERP collé/déposé
    par un humain) et l'historique des instances T-R-C-O générées à partir
    d'elles via l'agent de compréhension — une même donnée brute peut être
    reconvertie plusieurs fois (nouvel essai après un rejet, DSL affiné...)
    sans jamais devoir être re-saisie."""

    id: str
    client_id: str
    nom: str | None
    donnees_brutes: str
    date_creation: str


@dataclass
class EtatAPI:
    instances: dict[str, tuple[str, InstanceTRCO]] = field(default_factory=dict)
    executions: dict[str, tuple[str, str, ResultatExecution]] = field(default_factory=dict)
    decisions: dict[str, DecisionHumaine] = field(default_factory=dict)
    projets: dict[str, Projet] = field(default_factory=dict)
    projet_par_instance: dict[str, str] = field(default_factory=dict)
    clients: dict[str, Client] = field(default_factory=dict)
    dates_execution: dict[str, str] = field(default_factory=dict)

    def enregistrer_client(self, client_id: str, nom: str | None = None) -> None:
        """Idempotent au sens applicatif : ré-enregistrer un `client_id`
        existant ne l'écrase pas (même logique que le `ON CONFLICT DO
        NOTHING` de `EtatPostgres`) — un nom déjà posé n'est jamais perdu."""
        if client_id in self.clients:
            return
        self.clients[client_id] = Client(id=client_id, nom=nom)

    def recuperer_client(self, client_id: str) -> Client:
        if client_id not in self.clients:
            raise KeyError(client_id)
        return self.clients[client_id]

    def lister_clients(self) -> list[dict[str, object]]:
        return [{"client_id": c.id, "nom": c.nom} for c in self.clients.values()]

    def enregistrer_instance(self, client_id: str, instance: InstanceTRCO, projet_id: str | None = None) -> str:
        self.enregistrer_client(client_id)
        instance_id = str(uuid.uuid4())
        self.instances[instance_id] = (client_id, instance)
        if projet_id is not None:
            self.projet_par_instance[instance_id] = projet_id
        return instance_id

    def enregistrer_projet(self, client_id: str, donnees_brutes: str, nom: str | None = None) -> str:
        self.enregistrer_client(client_id)
        projet_id = str(uuid.uuid4())
        self.projets[projet_id] = Projet(
            id=projet_id,
            client_id=client_id,
            nom=nom,
            donnees_brutes=donnees_brutes,
            date_creation=datetime.now(UTC).isoformat(),
        )
        return projet_id

    def recuperer_projet(self, projet_id: str) -> Projet:
        if projet_id not in self.projets:
            raise KeyError(projet_id)
        return self.projets[projet_id]

    def lister_projets(self, client_id: str | None = None) -> list[dict[str, object]]:
        """Vue de supervision (lecture seule) sur les projets connus, avec le
        nombre d'instances déjà générées pour chacun. `client_id=None` ne
        filtre rien (réservé à l'admin — voir `api/autorisation.py`)."""
        compteurs: dict[str, int] = {}
        for projet_id in self.projet_par_instance.values():
            compteurs[projet_id] = compteurs.get(projet_id, 0) + 1
        return [
            {
                "projet_id": p.id,
                "client_id": p.client_id,
                "nom": p.nom,
                "date_creation": p.date_creation,
                "nb_instances": compteurs.get(p.id, 0),
            }
            for p in self.projets.values()
            if client_id is None or p.client_id == client_id
        ]

    def lister_instances_pour_projet(self, projet_id: str) -> list[dict[str, object]]:
        return [
            {
                "instance_id": instance_id,
                "structure_contraintes": structure_contraintes(self.instances[instance_id][1]),
            }
            for instance_id, pid in self.projet_par_instance.items()
            if pid == projet_id
        ]

    def supprimer_projet(self, projet_id: str) -> None:
        """Supprime le projet (données brutes) sans toucher aux instances déjà
        générées à partir de lui — elles restent, seul le lien disparaît
        (même logique inverse que `supprimer_instance`)."""
        if projet_id not in self.projets:
            raise KeyError(projet_id)
        del self.projets[projet_id]
        for instance_id in [iid for iid, pid in self.projet_par_instance.items() if pid == projet_id]:
            del self.projet_par_instance[instance_id]

    def recuperer_instance(self, instance_id: str) -> tuple[str, InstanceTRCO]:
        if instance_id not in self.instances:
            raise KeyError(instance_id)
        return self.instances[instance_id]

    def modifier_objectifs(self, instance_id: str, objectifs: list[Objectif]) -> InstanceTRCO:
        """Remplace les objectifs d'une instance déjà ingérée, seul champ pour
        lequel une modification en place a du sens (taches/ressources/
        contraintes définissent le problème, l'objectif ne fait qu'orienter
        le solveur dessus — changer d'objectif n'est pas réingérer un
        problème différent). Reconstruit l'instance en entier pour repasser
        par le même garde-fou (§6.7) que toute autre écriture."""
        if instance_id not in self.instances:
            raise KeyError(instance_id)
        client_id, instance = self.instances[instance_id]
        nouvelle_instance = InstanceTRCO(
            taches=instance.taches,
            ressources=instance.ressources,
            contraintes=instance.contraintes,
            objectifs=objectifs,
        )
        self.instances[instance_id] = (client_id, nouvelle_instance)
        return nouvelle_instance

    def supprimer_instance(self, instance_id: str) -> None:
        """Supprime l'instance et tout son historique d'exécution (plannings,
        décisions humaines) — jamais les solveurs (indépendants, §7) ni le
        projet dont elle a pu être générée, seul le lien disparaît."""
        if instance_id not in self.instances:
            raise KeyError(instance_id)
        del self.instances[instance_id]
        self.projet_par_instance.pop(instance_id, None)
        for execution_id in [eid for eid, (_, iid, _) in self.executions.items() if iid == instance_id]:
            del self.executions[execution_id]
            self.decisions.pop(execution_id, None)
            self.dates_execution.pop(execution_id, None)

    def enregistrer_execution(self, id_solveur: str, instance_id: str, resultat: ResultatExecution) -> str:
        execution_id = str(uuid.uuid4())
        self.executions[execution_id] = (id_solveur, instance_id, resultat)
        self.dates_execution[execution_id] = datetime.now(UTC).isoformat()
        return execution_id

    def recuperer_execution(self, execution_id: str) -> tuple[str, str, ResultatExecution]:
        if execution_id not in self.executions:
            raise KeyError(execution_id)
        return self.executions[execution_id]

    def lister_executions(self, client_id: str | None = None) -> list[dict[str, object]]:
        """Vue de supervision (lecture seule) sur les exécutions connues.
        `client_id=None` ne filtre rien (réservé à l'admin)."""
        resultats = []
        for execution_id, (id_solveur, instance_id, resultat) in self.executions.items():
            client_id_instance, _ = self.instances[instance_id]
            if client_id is not None and client_id_instance != client_id:
                continue
            decision = self.decisions.get(execution_id)
            resultats.append(
                {
                    "execution_id": execution_id,
                    "id_solveur": id_solveur,
                    "instance_id": instance_id,
                    "client_id": client_id_instance,
                    "date_execution": self.dates_execution.get(execution_id),
                    "reussi": resultat.reussi,
                    "erreur": resultat.erreur,
                    "decision": decision.decision if decision else None,
                }
            )
        return resultats

    def lister_instances(self, client_id: str | None = None) -> list[dict[str, object]]:
        """Vue de supervision (lecture seule) sur les instances ingérées,
        avec un indicateur `executee` pour repérer celles en attente.
        `client_id=None` ne filtre rien (réservé à l'admin)."""
        instances_executees = {instance_id for (_, instance_id, _) in self.executions.values()}
        return [
            {
                "instance_id": instance_id,
                "client_id": client_id_instance,
                "structure_contraintes": structure_contraintes(instance),
                "executee": instance_id in instances_executees,
            }
            for instance_id, (client_id_instance, instance) in self.instances.items()
            if client_id is None or client_id_instance == client_id
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


_ETAT_GLOBAL: EtatAPI | EtatPostgres | None = None


def obtenir_etat() -> EtatAPI | EtatPostgres:
    """Instanciation paresseuse, même principe que
    `api.dependencies.obtenir_registre` : `EtatPostgres()` ouvre une
    connexion Postgres et crée ses tables au premier appel réel — la
    retarder évite qu'un simple `import api.app` échoue si la base n'est
    pas encore joignable. Les tests substituent cette dépendance via
    `app.dependency_overrides` avec leur propre `EtatAPI()` en mémoire —
    ce code n'est donc jamais atteint pendant les tests."""
    global _ETAT_GLOBAL
    if _ETAT_GLOBAL is None:
        from api.etat_postgres import EtatPostgres as _EtatPostgres

        _ETAT_GLOBAL = _EtatPostgres()
    return _ETAT_GLOBAL
