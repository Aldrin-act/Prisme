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
`CompatibiliteRessourceTache`), puis un nouvel appel à `/execution/{projet_id}`
recalcule le planning — le processus exact varie d'un client à l'autre et
n'est donc pas figé dans le noyau.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, Objectif
from sandbox.runner import ResultatExecution

if TYPE_CHECKING:
    from api.etat_postgres import EtatPostgres

Decision = Literal["acceptee", "refusee"]


class InstanceEnUsage(Exception):
    """`supprimer_instance` : au moins un projet référence encore cette
    instance comme instance courante (`Projet.instance_id`) — refuser la
    suppression plutôt qu'orpheliner silencieusement l'exécution de ces
    projets (chacun a désormais son propre historique d'exécution, §annexe
    modèle Instance/Projet)."""


class ClientIncompatible(Exception):
    """`associer_instance_projet` : l'instance et le projet n'appartiennent
    pas au même client — l'isolation client (§7) ne doit jamais pouvoir
    être contournée par un simple lien instance↔projet."""


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


def durees_par_contrainte(instance: InstanceTRCO) -> dict[str, int]:
    """Durée par couple (tâche, ressource), clé `"tache|ressource"` — `Planning`
    n'a délibérément pas de champ durée (`dsl/schema/planning.py`), elle vit
    sur `CompatibiliteRessourceTache`. Partagé par `routes/planning.py` et
    `routes/planifier.py` (le point d'entrée unique ingestion+exécution) pour
    ne calculer ça qu'à un seul endroit."""
    return {
        f"{contrainte.tache}|{contrainte.ressource}": contrainte.duree
        for contrainte in instance.contraintes
        if isinstance(contrainte, CompatibiliteRessourceTache)
    }


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
    sans jamais devoir être re-saisie ; `lister_instances_pour_projet` reste
    cet historique complet, inchangé.

    `instance_id` (nullable) est distinct : c'est l'instance *courante* de ce
    projet — celle contre laquelle l'exécution se déclenche (`enregistrer_execution`)
    et dont l'instance elle-même n'est plus la propriété exclusive de ce
    projet (`associer_instance_projet` permet à plusieurs projets de
    partager une même instance, réutilisée comme gabarit — voir `Instance`,
    déjà porteuse des règles métier d'un secteur donné). Mise à jour par
    `generer-instance` (pointe vers la dernière générée) ou explicitement via
    `associer_instance_projet` (réutilise une instance existante)."""

    id: str
    client_id: str
    nom: str | None
    donnees_brutes: str
    date_creation: str
    instance_id: str | None = None


@dataclass(frozen=True)
class EvenementGeneration:
    """Un pas du pipeline multi-agents (§6.6) — copie durable de l'évènement
    déjà diffusé en direct par `api/routes/generation.py` (flux SSE, mémoire
    process) : ici pour qu'il survive à un redémarrage serveur."""

    ordre: int
    agent: str
    statut: str
    resume: str


@dataclass(frozen=True)
class TentativeGeneration:
    """Une tentative de la boucle de réparation bornée (§6.6, jusqu'à 10) —
    conserve le code candidat même pour les tentatives rejetées, pour
    comprendre après coup pourquoi une génération a mis plusieurs essais
    (ou a fini par échouer)."""

    numero: int
    code_candidat: str
    reussi: bool
    erreur_execution: str | None
    revue_approuve: bool | None
    revue_reponse_brute: str | None
    revue_problemes: tuple[str, ...]
    validation_statique_valide: bool | None
    validation_statique_violations: tuple[str, ...]


@dataclass
class JobGeneration:
    """Historique complet et durable d'une génération de solveur — distinct
    du `_JobGeneration` en mémoire process de `api/routes/generation.py`
    (qui reste la source du flux SSE en direct) : celui-ci est la copie
    persistée, pour l'audit après coup, y compris après redémarrage."""

    id: str
    instance_id: str
    client_id: str
    cree_le: str
    termine: bool = False
    reussi: bool | None = None
    id_solveur: str | None = None
    specification: str | None = None
    plan_technique: str | None = None
    algorithme: str | None = None
    algorithme_raison: str | None = None
    algorithme_parametres: dict | None = None
    code_genere: str | None = None
    tests_generes: str | None = None
    code_final: str | None = None
    nombre_tentatives: int | None = None
    erreur: str | None = None
    termine_le: str | None = None
    evenements: list[EvenementGeneration] = field(default_factory=list)
    tentatives: list[TentativeGeneration] = field(default_factory=list)


@dataclass
class EtatAPI:
    instances: dict[str, tuple[str, InstanceTRCO]] = field(default_factory=dict)
    # (id_solveur, projet_id, instance_id, resultat) — instance_id nullable
    # (coupé si l'instance sous-jacente a été supprimée, voir supprimer_instance).
    executions: dict[str, tuple[str, str, str | None, ResultatExecution]] = field(default_factory=dict)
    decisions: dict[str, DecisionHumaine] = field(default_factory=dict)
    projets: dict[str, Projet] = field(default_factory=dict)
    projet_par_instance: dict[str, str] = field(default_factory=dict)
    clients: dict[str, Client] = field(default_factory=dict)
    dates_execution: dict[str, str] = field(default_factory=dict)
    jobs_generation: dict[str, JobGeneration] = field(default_factory=dict)

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

    def lister_projets(
        self, client_id: str | None = None, instance_id: str | None = None
    ) -> list[dict[str, object]]:
        """Vue de supervision (lecture seule) sur les projets connus, avec le
        nombre d'instances déjà générées pour chacun (historique, distinct de
        l'instance courante) et la structure de contraintes de l'instance
        courante (résolue depuis `Projet.instance_id`, `None` si aucune).
        `instance_id` filtre sur l'instance courante (relation inverse :
        quels projets utilisent aujourd'hui cette instance). `client_id=None`
        ne filtre rien (réservé à l'admin — voir `api/autorisation.py`)."""
        compteurs: dict[str, int] = {}
        for projet_id in self.projet_par_instance.values():
            compteurs[projet_id] = compteurs.get(projet_id, 0) + 1
        resultats = []
        for p in self.projets.values():
            if client_id is not None and p.client_id != client_id:
                continue
            if instance_id is not None and p.instance_id != instance_id:
                continue
            structure = None
            if p.instance_id is not None and p.instance_id in self.instances:
                structure = structure_contraintes(self.instances[p.instance_id][1])
            resultats.append(
                {
                    "projet_id": p.id,
                    "client_id": p.client_id,
                    "nom": p.nom,
                    "date_creation": p.date_creation,
                    "nb_instances": compteurs.get(p.id, 0),
                    "instance_id": p.instance_id,
                    "structure_contraintes": structure,
                }
            )
        return resultats

    def lister_instances_pour_projet(self, projet_id: str) -> list[dict[str, object]]:
        return [
            {
                "instance_id": instance_id,
                "structure_contraintes": structure_contraintes(self.instances[instance_id][1]),
            }
            for instance_id, pid in self.projet_par_instance.items()
            if pid == projet_id
        ]

    def associer_instance_projet(self, projet_id: str, instance_id: str) -> None:
        """Fait de `instance_id` l'instance courante de `projet_id` — permet
        de réutiliser une instance existante (gabarit sectoriel déjà validé)
        comme celle d'un autre projet, sans repasser par l'agent de
        compréhension. Appelée aussi par `generer-instance` (la dernière
        instance générée devient l'instance courante)."""
        if projet_id not in self.projets:
            raise KeyError(projet_id)
        if instance_id not in self.instances:
            raise KeyError(instance_id)
        client_id_instance, _ = self.instances[instance_id]
        projet = self.projets[projet_id]
        if client_id_instance != projet.client_id:
            raise ClientIncompatible(
                f"l'instance {instance_id!r} appartient à {client_id_instance!r}, "
                f"pas à {projet.client_id!r} (client du projet {projet_id!r})"
            )
        self.projets[projet_id] = replace(projet, instance_id=instance_id)

    def supprimer_projet(self, projet_id: str) -> None:
        """Supprime le projet — cascade sa propre histoire d'exécution
        (chaque projet a désormais son planning attitré, indépendant de
        l'instance qu'il utilise) et coupe le lien de provenance vers les
        instances qu'il a pu générer ; celles-ci restent, réutilisables par
        d'autres projets (même logique qu'avant l'inversion, juste côté
        exécution en plus)."""
        if projet_id not in self.projets:
            raise KeyError(projet_id)
        del self.projets[projet_id]
        for instance_id in [iid for iid, pid in self.projet_par_instance.items() if pid == projet_id]:
            del self.projet_par_instance[instance_id]
        for execution_id in [eid for eid, (_, pid, _, _) in self.executions.items() if pid == projet_id]:
            del self.executions[execution_id]
            self.decisions.pop(execution_id, None)
            self.dates_execution.pop(execution_id, None)

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
        """Refuse tant qu'au moins un projet a `instance_id` comme instance
        courante (`InstanceEnUsage`) — orpheliner ce lien silencieusement
        casserait l'exécution de ces projets. Une fois hors d'usage : les
        exécutions historiques qui ont tourné contre elle sont conservées
        (elles appartiennent à leur projet, jamais à l'instance, §annexe
        modèle Instance/Projet) — seule leur référence informative à
        `instance_id` est coupée, jamais l'exécution/planning elle-même."""
        if instance_id not in self.instances:
            raise KeyError(instance_id)
        if any(p.instance_id == instance_id for p in self.projets.values()):
            raise InstanceEnUsage(
                f"l'instance {instance_id!r} est encore l'instance courante d'au moins un projet"
            )
        del self.instances[instance_id]
        self.projet_par_instance.pop(instance_id, None)
        for execution_id, (id_solveur, projet_id, iid, resultat) in list(self.executions.items()):
            if iid == instance_id:
                self.executions[execution_id] = (id_solveur, projet_id, None, resultat)

    def enregistrer_execution(
        self, id_solveur: str, projet_id: str, instance_id: str | None, resultat: ResultatExecution
    ) -> str:
        execution_id = str(uuid.uuid4())
        self.executions[execution_id] = (id_solveur, projet_id, instance_id, resultat)
        self.dates_execution[execution_id] = datetime.now(UTC).isoformat()
        return execution_id

    def recuperer_execution(self, execution_id: str) -> tuple[str, str, str | None, ResultatExecution]:
        if execution_id not in self.executions:
            raise KeyError(execution_id)
        return self.executions[execution_id]

    def lister_executions(self, client_id: str | None = None) -> list[dict[str, object]]:
        """Vue de supervision (lecture seule) sur les exécutions connues,
        scopée par le client du *projet* (plus par celui de l'instance —
        une instance peut désormais être partagée entre clients... non, en
        pratique `associer_instance_projet` l'interdit, mais le projet reste
        la source de vérité pour le cloisonnement, §7). `client_id=None` ne
        filtre rien (réservé à l'admin)."""
        resultats = []
        for execution_id, (id_solveur, projet_id, instance_id, resultat) in self.executions.items():
            projet = self.projets.get(projet_id)
            client_id_projet = projet.client_id if projet is not None else None
            if client_id is not None and client_id_projet != client_id:
                continue
            decision = self.decisions.get(execution_id)
            resultats.append(
                {
                    "execution_id": execution_id,
                    "id_solveur": id_solveur,
                    "projet_id": projet_id,
                    "instance_id": instance_id,
                    "client_id": client_id_projet,
                    "date_execution": self.dates_execution.get(execution_id),
                    "reussi": resultat.reussi,
                    "erreur": resultat.erreur,
                    "decision": decision.decision if decision else None,
                }
            )
        return resultats

    def lister_instances(self, client_id: str | None = None) -> list[dict[str, object]]:
        """Vue de supervision (lecture seule) sur les instances ingérées,
        avec un indicateur `executee` pour repérer celles jamais utilisées.
        Affaibli depuis l'inversion Instance/Projet : signale qu'*une*
        exécution a un jour tourné contre cette instance (via un projet
        quelconque), pas que le(s) projet(s) qui l'utilisent aujourd'hui ont
        chacun une exécution — ce niveau de détail vit désormais sur
        `Projet`, pas sur `Instance`. `client_id=None` ne filtre rien
        (réservé à l'admin)."""
        instances_executees = {iid for (_, _, iid, _) in self.executions.values() if iid is not None}
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

    # --- Historique de génération (§6.6) ----------------------------------

    def enregistrer_job_generation(self, job_id: str, instance_id: str, client_id: str) -> None:
        self.jobs_generation[job_id] = JobGeneration(
            id=job_id,
            instance_id=instance_id,
            client_id=client_id,
            cree_le=datetime.now(UTC).isoformat(),
        )

    def ajouter_evenement_generation(self, job_id: str, agent: str, statut: str, resume: str) -> None:
        job = self.jobs_generation[job_id]
        job.evenements.append(
            EvenementGeneration(ordre=len(job.evenements), agent=agent, statut=statut, resume=resume)
        )

    def ajouter_tentative_generation(self, job_id: str, tentative: TentativeGeneration) -> None:
        self.jobs_generation[job_id].tentatives.append(tentative)

    def terminer_job_generation(
        self,
        job_id: str,
        *,
        reussi: bool | None,
        id_solveur: str | None = None,
        specification: str | None = None,
        plan_technique: str | None = None,
        algorithme: str | None = None,
        algorithme_raison: str | None = None,
        algorithme_parametres: dict | None = None,
        code_genere: str | None = None,
        tests_generes: str | None = None,
        code_final: str | None = None,
        nombre_tentatives: int | None = None,
        erreur: str | None = None,
    ) -> None:
        job = self.jobs_generation[job_id]
        job.termine = True
        job.reussi = reussi
        job.id_solveur = id_solveur
        job.specification = specification
        job.plan_technique = plan_technique
        job.algorithme = algorithme
        job.algorithme_raison = algorithme_raison
        job.algorithme_parametres = algorithme_parametres
        job.code_genere = code_genere
        job.tests_generes = tests_generes
        job.code_final = code_final
        job.nombre_tentatives = nombre_tentatives
        job.erreur = erreur
        job.termine_le = datetime.now(UTC).isoformat()

    def recuperer_job_generation(self, job_id: str) -> JobGeneration:
        if job_id not in self.jobs_generation:
            raise KeyError(job_id)
        return self.jobs_generation[job_id]

    def lister_jobs_generation_persistes(
        self, client_id: str | None = None, instance_id: str | None = None
    ) -> list[dict[str, object]]:
        return [
            {
                "job_id": j.id,
                "instance_id": j.instance_id,
                "client_id": j.client_id,
                "cree_le": j.cree_le,
                "termine": j.termine,
                "reussi": j.reussi,
                "id_solveur": j.id_solveur,
                "nombre_tentatives": j.nombre_tentatives,
                "erreur": j.erreur,
                "termine_le": j.termine_le,
            }
            for j in self.jobs_generation.values()
            if (client_id is None or j.client_id == client_id)
            and (instance_id is None or j.instance_id == instance_id)
        ]


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
