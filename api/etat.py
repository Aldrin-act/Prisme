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
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, Objectif, Planning
from sandbox.runner import ResultatExecution

if TYPE_CHECKING:
    from api.etat_postgres import EtatPostgres

Decision = Literal["acceptee", "refusee"]
TypeSignal = Literal["signature_orpheline", "echecs_repetes", "instance_a_replanifier"]
ActionSuggeree = Literal["regenerer_solveur", "executer", "diagnostiquer"]
Priorite = Literal["haute", "moyenne", "basse"]

# Vocabulaire fermé du secteur d'activité — métadonnée opérationnelle comme
# nom_projet (jamais lue par le solveur ni le vérificateur de faisabilité,
# donc absente de dsl/schema/), mais avec trois effets réels ailleurs :
# oriente le prompt de l'agent de compréhension (adapters/agent_comprehension/),
# filtre les pages Instances/Données, alimente des suggestions de ressources
# à l'ingestion (Front). Liste reprise de scripts/generer_donnees_brutes.py
# (la plus établie du projet) — aucune autre liste de secteurs du repo n'est
# canonique.
SecteurActivite = Literal[
    "atelier_mecanique",
    "assemblage_electronique",
    "production_agroalimentaire",
    "maintenance_industrielle",
    "imprimerie",
    "centre_appels",
]
LABELS_SECTEUR_ACTIVITE: dict[SecteurActivite, str] = {
    "atelier_mecanique": "Atelier mécanique",
    "assemblage_electronique": "Assemblage électronique",
    "production_agroalimentaire": "Production agroalimentaire",
    "maintenance_industrielle": "Maintenance industrielle",
    "imprimerie": "Imprimerie",
    "centre_appels": "Centre d'appels",
}


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


@dataclass
class PropositionSupervision:
    """Une proposition de l'agent de supervision (§2, MT7) — un signal détecté
    (signature orpheline, échecs répétés, instance en attente de
    replanification) habillé d'un résumé et d'une priorité par l'agent LLM,
    jamais appliquée automatiquement : `decision` reste `None` jusqu'à ce
    qu'un humain accepte ou refuse via `decider_proposition`. Mutable comme
    `JobGeneration` (créée une fois, mise à jour une fois à la décision),
    contrairement à `DecisionHumaine` qui n'est jamais partiellement modifiée."""

    id: str
    client_id: str
    type_signal: TypeSignal
    action_suggeree: ActionSuggeree
    resume: str
    priorite: Priorite
    details: tuple[str, ...]
    date_creation: str
    instance_id: str | None = None
    execution_ids: tuple[str, ...] = ()
    structure_contraintes: str | None = None
    signature_objectifs: str | None = None
    decision: Decision | None = None
    horodatage_decision: str | None = None
    commentaire: str | None = None


@dataclass(frozen=True)
class Client:
    """Un client (tenant métier) — l'unité de cloisonnement des données dans
    tout le système (§7) : matching des solveurs (`solver_store/registry.py`),
    visibilité des instances/sources (`api/autorisation.py`). Créé
    explicitement (ce module) plutôt qu'implicitement au premier usage, pour
    porter un vrai nom et pouvoir être choisi à l'inscription d'un compte."""

    id: str
    nom: str | None


@dataclass(frozen=True)
class SourceDonnees:
    """Données brutes persistées (ex. export ERP collé/déposé par un
    humain) — une même donnée brute peut être reconvertie plusieurs fois
    (nouvel essai après un rejet, DSL affiné...) via l'agent de
    compréhension sans jamais devoir être re-saisie ;
    `lister_instances_pour_source` reste cet historique complet.

    Volontairement minimal : ne porte ni pointeur "instance courante" ni
    historique d'exécution — chaque instance générée s'exécute directement
    par son propre `instance_id` (`routes/execution.py`), indépendamment de
    la source qui l'a produite."""

    id: str
    client_id: str
    nom: str | None
    donnees_brutes: str
    date_creation: str
    # Capturé une fois à la création de la source, réutilisé à chaque
    # reconversion (contrairement à nom_projet, connu seulement une fois
    # l'instance décidée) — oriente le prompt de l'agent de compréhension.
    # `str` libre (pas `SecteurActivite`) : un des 6 secteurs connus, ou un
    # secteur personnalisé saisi via "Autre" côté frontend — la liste fermée
    # `LABELS_SECTEUR_ACTIVITE` reste la source des suggestions/du menu,
    # mais n'est jamais une contrainte de validation sur la valeur stockée.
    secteur_activite: str | None = None
    # Unité dans laquelle l'interface affiche les durées/échéances de cette
    # source et des instances qu'elle génère — "jours" (défaut si absent),
    # "semaines" ou "mois". Purement cosmétique : le DSL, le solveur généré,
    # le vérificateur de faisabilité et le banc synthétique continuent de
    # raisonner en jours entiers, inchangés ; seule la présentation convertit.
    unite_duree: str | None = None


@dataclass(frozen=True)
class EtapeGamme:
    """Une étape d'une `GammeProduit` — jamais vue par le solveur : purement
    un gabarit, explosé en `Tache`/`Contrainte` DSL ordinaires par
    `adapters/gamme_derivation.py::exploser_gamme` à l'arrivée d'une
    commande. `competences` (>=1) plutôt qu'une ressource fixe : la
    compatibilité réelle se dérive à l'explosion via
    `adapters/competence_derivation.py`, donc la gamme reste valide même si
    le parc de ressources évolue. `predecesseurs` référence d'autres `id`
    d'étapes de la même gamme (jamais d'une autre) — plusieurs prédécesseurs
    pour une même étape expriment une fusion (plusieurs sous-produits qui
    convergent vers une étape commune), sans mécanisme dédié."""

    id: str
    competences: tuple[str, ...]
    predecesseurs: tuple[str, ...] = ()
    # Durée déclarée (jours) pour cette étape, appliquée à chaque tâche qu'elle produit —
    # même rôle que `TacheAvecDureeEstimee.duree_estimee_jours` des adaptateurs CSV/JSON
    # (`adapters/json_import/traducteur.py`) : source primaire de durée, l'estimateur ML
    # (`estimation/`) ne comble que ce qui reste manquant. Sans elle ET sans estimateur
    # configuré, l'explosion échoue explicitement (`CompetenceSansDureeEstimee`) plutôt que
    # de deviner une durée.
    duree_nominale: int | None = None


@dataclass(frozen=True)
class GammeProduit:
    """Gamme opératoire réutilisable pour un produit d'un client — décrite
    une fois, explosée à chaque commande (`traiter_nouvelle_commande`) en
    tâches concrètes plutôt que redéclarée à la main à chaque fois. Comme
    `SourceDonnees`, volontairement minimale : ne porte aucun historique
    d'exécution, aucune instance "courante"."""

    id: str
    client_id: str
    produit: str
    nom: str | None
    etapes: tuple[EtapeGamme, ...]


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
    persistée, pour l'audit après coup, y compris après redémarrage.

    `instance_id` nullable : `supprimer_instance` met ce champ à `None`
    plutôt que de supprimer le job — l'audit de génération (spécification,
    plan technique, code candidat) reste consultable même après suppression
    de l'instance qui l'a déclenché."""

    id: str
    instance_id: str | None
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
    rapport_tests_sandbox: dict | None = None
    documentation: str | None = None
    nombre_tentatives: int | None = None
    erreur: str | None = None
    termine_le: str | None = None
    evenements: list[EvenementGeneration] = field(default_factory=list)
    tentatives: list[TentativeGeneration] = field(default_factory=list)


@dataclass
class EtatAPI:
    instances: dict[str, tuple[str, InstanceTRCO]] = field(default_factory=dict)
    # (id_solveur, instance_id, resultat) — instance_id garanti exister :
    # supprimer_instance cascade-supprime ses propres exécutions plutôt que
    # de les orpheliner (voir supprimer_instance).
    executions: dict[str, tuple[str, str, ResultatExecution]] = field(default_factory=dict)
    decisions: dict[str, DecisionHumaine] = field(default_factory=dict)
    sources: dict[str, SourceDonnees] = field(default_factory=dict)
    source_par_instance: dict[str, str] = field(default_factory=dict)
    gammes: dict[str, GammeProduit] = field(default_factory=dict)
    # Description métier proposée par l'agent de compréhension (§5.4 bis) —
    # absente (None) pour toute instance ingérée hors de ce chemin (payload
    # T-R-C-O direct, adaptateur écrit à la main...). Hors `InstanceTRCO`
    # elle-même (`extra="forbid"`, vocabulaire fini du DSL) : c'est une
    # métadonnée de l'entité Instance côté API, pas un champ du problème
    # d'ordonnancement.
    descriptions_metier: dict[str, str | None] = field(default_factory=dict)
    # Étiquette libre choisie par l'utilisateur pour retrouver/regrouper des
    # instances liées entre elles (ex. réingestions successives d'un même
    # atelier après un aléa) — pure métadonnée de confort, jamais consultée
    # par la sélection de solveur (`structure_contraintes`/
    # `signature_objectifs`) ni par la détection de signaux de supervision.
    noms_projet: dict[str, str | None] = field(default_factory=dict)
    # Secteur d'activité de l'instance — copié depuis la source au moment de
    # `enregistrer_instance` quand elle en a une (voir enregistrer_instance),
    # ou fourni directement pour les canaux sans SourceDonnees (CSV/JSON/
    # GreenSIG/T-R-C-O manuel). Même statut de métadonnée pure que noms_projet.
    secteurs_activite: dict[str, str | None] = field(default_factory=dict)
    # Même statut que secteurs_activite (métadonnée pure, purement cosmétique
    # côté affichage) — voir `SourceDonnees.unite_duree`.
    unites_duree: dict[str, str | None] = field(default_factory=dict)
    # Dernière modification du contenu T-R-C-O d'une instance (création,
    # `modifier_instance` ou `modifier_objectifs`) — comparée à la date de sa
    # dernière exécution par `supervision/detecteurs.py` pour détecter
    # qu'une instance déjà exécutée a depuis été modifiée et doit être
    # ré-exécutée (signal `instance_a_replanifier`).
    dates_modification: dict[str, str] = field(default_factory=dict)
    # Scénarios comparatifs (what-if) : une instance variante créée par
    # `POST /ingestion/{instance_id}/scenarios` pointe ici vers l'instance de
    # base dont elle dérive — le groupe entier (base + variantes) se compare
    # ensuite via `GET /ingestion/{instance_id}/scenarios/comparaison`. Sans
    # rapport avec l'ancien `instance_parente_id` (retiré, voir
    # `api/etat_postgres.py`) : celui-là suivait un historique de
    # modification en place (une seule lignée) ; ceci relie des variantes
    # délibérées, créées pour coexister et être comparées, jamais fusionnées
    # ni éditées l'une dans l'autre.
    groupes_scenario: dict[str, str] = field(default_factory=dict)
    clients: dict[str, Client] = field(default_factory=dict)
    dates_execution: dict[str, str] = field(default_factory=dict)
    jobs_generation: dict[str, JobGeneration] = field(default_factory=dict)
    propositions: dict[str, PropositionSupervision] = field(default_factory=dict)
    # Gantt interactif (Phase 3) : révision ajustée à la main d'un planning, distincte de
    # l'original figé dans executions[execution_id][2].planning — une seule révision "courante"
    # par exécution (écrasée à chaque nouvel ajustement légal), jamais un historique de
    # révisions. Purgée avec l'exécution dans supprimer_instance.
    plannings_ajustes: dict[str, Planning] = field(default_factory=dict)

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

    def enregistrer_instance(
        self,
        client_id: str,
        instance: InstanceTRCO,
        source_id: str | None = None,
        description_metier: str | None = None,
        nom_projet: str | None = None,
        secteur_activite: str | None = None,
        unite_duree: str | None = None,
        groupe_scenario_id: str | None = None,
    ) -> str:
        self.enregistrer_client(client_id)
        instance_id = str(uuid.uuid4())
        self.instances[instance_id] = (client_id, instance)
        if source_id is not None:
            self.source_par_instance[instance_id] = source_id
        self.descriptions_metier[instance_id] = description_metier
        self.noms_projet[instance_id] = nom_projet
        self.secteurs_activite[instance_id] = secteur_activite
        self.unites_duree[instance_id] = unite_duree
        self.dates_modification[instance_id] = datetime.now(UTC).isoformat()
        if groupe_scenario_id is not None:
            self.groupes_scenario[instance_id] = groupe_scenario_id
        return instance_id

    def lister_instances_du_groupe_scenario(self, instance_id: str) -> list[str]:
        """Toutes les instances du même groupe de scénarios que `instance_id`,
        elle comprise — que `instance_id` soit l'instance de base (jamais
        elle-même dans `groupes_scenario`, sa propre présence dans
        `self.instances` suffit à la qualifier de racine) ou l'une des
        variantes créées ensuite. Ordre non garanti."""
        groupe_id = self.groupes_scenario.get(instance_id, instance_id)
        membres = {groupe_id} if groupe_id in self.instances else set()
        membres |= {iid for iid, gid in self.groupes_scenario.items() if gid == groupe_id}
        return sorted(membres)

    def enregistrer_source(
        self,
        client_id: str,
        donnees_brutes: str,
        nom: str | None = None,
        secteur_activite: str | None = None,
        unite_duree: str | None = None,
    ) -> str:
        self.enregistrer_client(client_id)
        source_id = str(uuid.uuid4())
        self.sources[source_id] = SourceDonnees(
            id=source_id,
            client_id=client_id,
            nom=nom,
            donnees_brutes=donnees_brutes,
            date_creation=datetime.now(UTC).isoformat(),
            secteur_activite=secteur_activite,
            unite_duree=unite_duree,
        )
        return source_id

    def recuperer_source(self, source_id: str) -> SourceDonnees:
        if source_id not in self.sources:
            raise KeyError(source_id)
        return self.sources[source_id]

    def lister_sources(self, client_id: str | None = None) -> list[dict[str, object]]:
        """Vue de supervision (lecture seule) sur les sources connues, avec le
        nombre d'instances déjà générées pour chacune. `client_id=None` ne
        filtre rien (réservé à l'admin — voir `api/autorisation.py`)."""
        compteurs: dict[str, int] = {}
        for source_id in self.source_par_instance.values():
            compteurs[source_id] = compteurs.get(source_id, 0) + 1
        return [
            {
                "source_id": s.id,
                "client_id": s.client_id,
                "nom": s.nom,
                "date_creation": s.date_creation,
                "nb_instances": compteurs.get(s.id, 0),
                "secteur_activite": s.secteur_activite,
                "unite_duree": s.unite_duree,
            }
            for s in self.sources.values()
            if client_id is None or s.client_id == client_id
        ]

    def lister_instances_pour_source(self, source_id: str) -> list[dict[str, object]]:
        return [
            {
                "instance_id": instance_id,
                "structure_contraintes": structure_contraintes(self.instances[instance_id][1]),
                "nom_projet": self.noms_projet.get(instance_id),
            }
            for instance_id, sid in self.source_par_instance.items()
            if sid == source_id
        ]

    def supprimer_source(self, source_id: str) -> None:
        """Coupe uniquement le lien de provenance vers les instances générées
        à partir d'elle (elles restent, exécutables indépendamment) — une
        source ne porte aucun historique d'exécution à cascader."""
        if source_id not in self.sources:
            raise KeyError(source_id)
        del self.sources[source_id]
        for instance_id in [iid for iid, sid in self.source_par_instance.items() if sid == source_id]:
            del self.source_par_instance[instance_id]

    def enregistrer_gamme(
        self, client_id: str, produit: str, etapes: tuple[EtapeGamme, ...], nom: str | None = None
    ) -> str:
        self.enregistrer_client(client_id)
        gamme_id = str(uuid.uuid4())
        self.gammes[gamme_id] = GammeProduit(
            id=gamme_id, client_id=client_id, produit=produit, nom=nom, etapes=etapes
        )
        return gamme_id

    def recuperer_gamme(self, gamme_id: str) -> GammeProduit:
        if gamme_id not in self.gammes:
            raise KeyError(gamme_id)
        return self.gammes[gamme_id]

    def lister_gammes(self, client_id: str | None = None) -> list[GammeProduit]:
        return [g for g in self.gammes.values() if client_id is None or g.client_id == client_id]

    def modifier_gamme(
        self, gamme_id: str, produit: str, etapes: tuple[EtapeGamme, ...], nom: str | None = None
    ) -> GammeProduit:
        """Remplace en place le contenu d'une gamme déjà enregistrée — même
        `id`/`client_id`, comme `modifier_instance` pour une instance."""
        if gamme_id not in self.gammes:
            raise KeyError(gamme_id)
        gamme = GammeProduit(
            id=gamme_id, client_id=self.gammes[gamme_id].client_id, produit=produit, nom=nom, etapes=etapes
        )
        self.gammes[gamme_id] = gamme
        return gamme

    def supprimer_gamme(self, gamme_id: str) -> None:
        if gamme_id not in self.gammes:
            raise KeyError(gamme_id)
        del self.gammes[gamme_id]

    def recuperer_instance(self, instance_id: str) -> tuple[str, InstanceTRCO]:
        if instance_id not in self.instances:
            raise KeyError(instance_id)
        return self.instances[instance_id]

    def recuperer_description_metier(self, instance_id: str) -> str | None:
        """`None` pour toute instance ingérée hors du chemin agent de
        compréhension (payload T-R-C-O direct, adaptateur écrit à la main...),
        pas seulement pour une instance inconnue — lève quand même `KeyError`
        dans ce dernier cas pour rester cohérent avec `recuperer_instance`."""
        if instance_id not in self.instances:
            raise KeyError(instance_id)
        return self.descriptions_metier.get(instance_id)

    def recuperer_nom_projet(self, instance_id: str) -> str | None:
        """`None` pour toute instance jamais nommée — même convention que
        `recuperer_description_metier` (lève `KeyError` pour une instance
        inconnue, pas seulement pour un nom absent)."""
        if instance_id not in self.instances:
            raise KeyError(instance_id)
        return self.noms_projet.get(instance_id)

    def recuperer_secteur_activite(self, instance_id: str) -> str | None:
        """`None` pour toute instance sans secteur déclaré — même convention
        que `recuperer_nom_projet` (lève `KeyError` pour une instance
        inconnue, pas seulement pour un secteur absent)."""
        if instance_id not in self.instances:
            raise KeyError(instance_id)
        return self.secteurs_activite.get(instance_id)

    def recuperer_unite_duree(self, instance_id: str) -> str | None:
        """`None` pour toute instance sans unité déclarée (jours implicite) —
        même convention que `recuperer_secteur_activite`."""
        if instance_id not in self.instances:
            raise KeyError(instance_id)
        return self.unites_duree.get(instance_id)

    def lister_noms_projet(self, client_id: str | None = None) -> list[dict[str, object]]:
        """Noms de projet distincts déjà utilisés (avec leur nombre
        d'instances), pour peupler une auto-complétion côté client et éviter
        qu'une faute de frappe fragmente silencieusement un regroupement.
        `client_id=None` ne filtre rien (réservé à l'admin)."""
        compteurs: Counter[str] = Counter()
        for instance_id, (client_id_instance, _) in self.instances.items():
            if client_id is not None and client_id_instance != client_id:
                continue
            nom = self.noms_projet.get(instance_id)
            if nom is not None:
                compteurs[nom] += 1
        return [{"nom_projet": nom, "nb_instances": n} for nom, n in compteurs.most_common()]

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
        self.dates_modification[instance_id] = datetime.now(UTC).isoformat()
        return nouvelle_instance

    def modifier_instance(
        self,
        instance_id: str,
        instance: InstanceTRCO,
        nom_projet: str | None = None,
        secteur_activite: str | None = None,
    ) -> InstanceTRCO:
        """Remplace en place le contenu T-R-C-O complet (tâches/ressources/
        contraintes/objectifs) d'une instance déjà ingérée — même
        instance_id, historique d'exécution/décisions intact (aucune
        cascade). L'appelant a déjà validé `instance` via
        `valider_payload_trco` (même garde-fou §6.7 qu'à la création).
        `nom_projet`/`secteur_activite` sont écrasés sans condition, comme à
        la création — l'appelant doit toujours renvoyer la valeur courante
        s'il veut la conserver, jamais l'omettre."""
        if instance_id not in self.instances:
            raise KeyError(instance_id)
        client_id, _ = self.instances[instance_id]
        self.instances[instance_id] = (client_id, instance)
        self.noms_projet[instance_id] = nom_projet
        self.secteurs_activite[instance_id] = secteur_activite
        self.dates_modification[instance_id] = datetime.now(UTC).isoformat()
        return instance

    def supprimer_instance(self, instance_id: str) -> None:
        """Cascade-supprime son propre historique d'exécution (exécutions,
        décisions humaines associées) — une exécution n'existe jamais sans
        l'instance qui l'a produite. Le lien de provenance vers sa source
        éventuelle est coupé. Les jobs de génération qui la référencent
        survivent, orphelins (`instance_id` devient `None`) — préserve
        l'audit de génération même après suppression de l'instance."""
        if instance_id not in self.instances:
            raise KeyError(instance_id)
        del self.instances[instance_id]
        self.source_par_instance.pop(instance_id, None)
        self.descriptions_metier.pop(instance_id, None)
        self.noms_projet.pop(instance_id, None)
        self.secteurs_activite.pop(instance_id, None)
        self.unites_duree.pop(instance_id, None)
        self.dates_modification.pop(instance_id, None)
        self.groupes_scenario.pop(instance_id, None)
        for execution_id in [eid for eid, (_, iid, _) in self.executions.items() if iid == instance_id]:
            del self.executions[execution_id]
            self.decisions.pop(execution_id, None)
            self.dates_execution.pop(execution_id, None)
            self.plannings_ajustes.pop(execution_id, None)
        for job in self.jobs_generation.values():
            if job.instance_id == instance_id:
                job.instance_id = None
        for proposition in self.propositions.values():
            if proposition.instance_id == instance_id:
                proposition.instance_id = None

    def enregistrer_execution(self, id_solveur: str, instance_id: str, resultat: ResultatExecution) -> str:
        execution_id = str(uuid.uuid4())
        self.executions[execution_id] = (id_solveur, instance_id, resultat)
        self.dates_execution[execution_id] = datetime.now(UTC).isoformat()
        return execution_id

    def recuperer_execution(self, execution_id: str) -> tuple[str, str, ResultatExecution]:
        if execution_id not in self.executions:
            raise KeyError(execution_id)
        return self.executions[execution_id]

    def dernier_planning_pour_instance(self, instance_id: str) -> Planning | None:
        """Le planning de la plus récente exécution *réussie* de `instance_id` — jamais une
        exécution échouée (`resultat.reussi`), même si elle est plus récente. Utilisé par
        `POST /execution/{instance_id}?horizon_gele_jours=...` (Phase 2, replanification à
        horizon glissant) pour retrouver ce qu'il faut potentiellement figer ; `None` si cette
        instance n'a encore jamais été exécutée avec succès."""
        candidats = [
            (self.dates_execution[execution_id], resultat.planning)
            for execution_id, (_, id_instance, resultat) in self.executions.items()
            if id_instance == instance_id and resultat.reussi
        ]
        if not candidats:
            return None
        candidats.sort(key=lambda candidat: candidat[0])
        return candidats[-1][1]

    def enregistrer_planning_ajuste(
        self, execution_id: str, planning: Planning, makespan: int | None = None
    ) -> None:
        """Écrase toute révision ajustée précédente de cette exécution — une seule révision
        "courante", jamais un historique (Gantt interactif, Phase 3). Ne touche jamais
        `executions[execution_id][2].planning` (l'original figé par le solveur). `makespan`
        accepté pour rester substituable avec `EtatPostgres` — jamais lu en mémoire, rien ne le
        consomme ici (les durées sont toujours dérivées côté client depuis l'instance)."""
        del makespan
        self.plannings_ajustes[execution_id] = planning

    def recuperer_planning_ajuste(self, execution_id: str) -> Planning | None:
        return self.plannings_ajustes.get(execution_id)

    def lister_executions(self, client_id: str | None = None) -> list[dict[str, object]]:
        """Vue de supervision (lecture seule) sur les exécutions connues,
        scopée par le client de l'instance exécutée. `client_id=None` ne
        filtre rien (réservé à l'admin)."""
        resultats = []
        for execution_id, (id_solveur, instance_id, resultat) in self.executions.items():
            client_id_instance = self.instances[instance_id][0]
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

    def lister_instances(
        self,
        client_id: str | None = None,
        nom_projet: str | None = None,
        secteur_activite: str | None = None,
    ) -> list[dict[str, object]]:
        """Vue de supervision (lecture seule) sur les instances ingérées,
        avec un indicateur `executee` pour repérer celles jamais utilisées.
        `client_id=None` ne filtre rien (réservé à l'admin). `nom_projet`/
        `secteur_activite` filtrent en plus sur ces métadonnées libres."""
        instances_executees = {iid for (_, iid, _) in self.executions.values()}
        return [
            {
                "instance_id": instance_id,
                "client_id": client_id_instance,
                "structure_contraintes": structure_contraintes(instance),
                "executee": instance_id in instances_executees,
                "nom_projet": self.noms_projet.get(instance_id),
                "secteur_activite": self.secteurs_activite.get(instance_id),
                "unite_duree": self.unites_duree.get(instance_id),
                "date_modification": self.dates_modification.get(instance_id),
            }
            for instance_id, (client_id_instance, instance) in self.instances.items()
            if (client_id is None or client_id_instance == client_id)
            and (nom_projet is None or self.noms_projet.get(instance_id) == nom_projet)
            and (secteur_activite is None or self.secteurs_activite.get(instance_id) == secteur_activite)
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

    # --- Agent de supervision (MT7) ---------------------------------------

    def enregistrer_proposition(
        self,
        client_id: str,
        type_signal: TypeSignal,
        action_suggeree: ActionSuggeree,
        resume: str,
        priorite: Priorite,
        details: tuple[str, ...],
        instance_id: str | None = None,
        execution_ids: tuple[str, ...] = (),
        structure_contraintes: str | None = None,
        signature_objectifs: str | None = None,
    ) -> str:
        self.enregistrer_client(client_id)
        proposition_id = str(uuid.uuid4())
        self.propositions[proposition_id] = PropositionSupervision(
            id=proposition_id,
            client_id=client_id,
            type_signal=type_signal,
            action_suggeree=action_suggeree,
            resume=resume,
            priorite=priorite,
            details=details,
            date_creation=datetime.now(UTC).isoformat(),
            instance_id=instance_id,
            execution_ids=execution_ids,
            structure_contraintes=structure_contraintes,
            signature_objectifs=signature_objectifs,
        )
        return proposition_id

    def recuperer_proposition(self, proposition_id: str) -> PropositionSupervision:
        if proposition_id not in self.propositions:
            raise KeyError(proposition_id)
        return self.propositions[proposition_id]

    def lister_propositions(
        self, client_id: str | None = None, en_attente_seulement: bool = False
    ) -> list[dict[str, object]]:
        return [
            {
                "proposition_id": p.id,
                "client_id": p.client_id,
                "type_signal": p.type_signal,
                "action_suggeree": p.action_suggeree,
                "resume": p.resume,
                "priorite": p.priorite,
                "details": list(p.details),
                "date_creation": p.date_creation,
                "instance_id": p.instance_id,
                "execution_ids": list(p.execution_ids),
                "structure_contraintes": p.structure_contraintes,
                "signature_objectifs": p.signature_objectifs,
                "decision": p.decision,
                "horodatage_decision": p.horodatage_decision,
                "commentaire": p.commentaire,
            }
            for p in self.propositions.values()
            if (client_id is None or p.client_id == client_id) and (not en_attente_seulement or p.decision is None)
        ]

    def decider_proposition(self, proposition_id: str, decision: Decision, commentaire: str | None = None) -> None:
        if proposition_id not in self.propositions:
            raise KeyError(proposition_id)
        proposition = self.propositions[proposition_id]
        proposition.decision = decision
        proposition.horodatage_decision = datetime.now(UTC).isoformat()
        proposition.commentaire = commentaire

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

    def mettre_a_jour_job_generation(self, job_id: str, **champs: object) -> None:
        """Persiste un ou plusieurs champs dès qu'ils sont connus, sans marquer le job
        terminé (contrairement à `terminer_job_generation`) — capture incrémentale des
        sorties d'agents au fil du pipeline (§6.6), pour ne rien perdre d'un plantage en
        cours de route."""
        job = self.jobs_generation[job_id]
        for champ, valeur in champs.items():
            setattr(job, champ, valeur)

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
        rapport_tests_sandbox: dict | None = None,
        documentation: str | None = None,
        nombre_tentatives: int | None = None,
        erreur: str | None = None,
    ) -> None:
        """`None` sur un champ de contenu signifie « ne pas toucher », jamais « écraser à
        vide » — ces champs peuvent déjà avoir été posés incrémentalement par
        `mettre_a_jour_job_generation` pendant le pipeline (§6.6) ; les réécraser à `None`
        sur un plantage effacerait ce qui a déjà été sauvé."""
        champs_contenu = {
            "specification": specification,
            "plan_technique": plan_technique,
            "algorithme": algorithme,
            "algorithme_raison": algorithme_raison,
            "algorithme_parametres": algorithme_parametres,
            "code_genere": code_genere,
            "tests_generes": tests_generes,
            "code_final": code_final,
            "rapport_tests_sandbox": rapport_tests_sandbox,
            "documentation": documentation,
        }
        self.mettre_a_jour_job_generation(job_id, **{k: v for k, v in champs_contenu.items() if v is not None})

        job = self.jobs_generation[job_id]
        job.termine = True
        job.reussi = reussi
        job.id_solveur = id_solveur
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

    def lister_evenements_generation(self, client_id: str | None = None) -> list[dict[str, object]]:
        """Tous les évènements de tous les jobs (filtrés par client), `job_id` explicite —
        matière première des KPI d'agrégat (page Analytique), jamais consultés job par job
        ici contrairement à `recuperer_job_generation`."""
        return [
            {"job_id": j.id, "ordre": e.ordre, "agent": e.agent, "statut": e.statut}
            for j in self.jobs_generation.values()
            if client_id is None or j.client_id == client_id
            for e in j.evenements
        ]

    def lister_tentatives_generation(self, client_id: str | None = None) -> list[dict[str, object]]:
        """Toutes les tentatives de tous les jobs (filtrées par client) — seulement
        `code_candidat` (les autres champs de détail restent réservés à la vue par job,
        `recuperer_job_generation`), pour les KPI d'agrégat (détection de stagnation)."""
        return [
            {"job_id": j.id, "numero": t.numero, "code_candidat": t.code_candidat}
            for j in self.jobs_generation.values()
            if client_id is None or j.client_id == client_id
            for t in j.tentatives
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
