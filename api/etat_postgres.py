"""Persistance Postgres de l'état de l'API (§5.2, §7 — extension proposée
dans le modèle conceptuel de données) : implémente exactement l'interface
publique d'`EtatAPI` (`api/etat.py`), mais en base plutôt qu'en mémoire —
c'est le remplacement que `EtatAPI` annonce lui-même dans son docstring
(« un déploiement réel remplacerait ceci par ... une base de données »).

Dix tables, une par entité du modèle conceptuel :
`clients`, `sources_donnees`, `instances_trco`, `executions`, `plannings`, `operations_planifiees`,
`decisions_humaines`, `jobs_generation`, `evenements_generation`, `tentatives_generation`
(historique durable du pipeline multi-agents, §6.6 — voir plus bas).

Une `Instance` (T-R-C-O) porte directement son propre historique d'exécution
(`executions.instance_id`, `NOT NULL` — une exécution n'existe jamais sans
l'instance qui l'a produite) : l'exécuter (`enregistrer_execution`) et la
supprimer (`supprimer_instance`, qui cascade-supprime cet historique) se font
toutes deux directement par son `instance_id`, sans intermédiaire.
`sources_donnees` est volontairement indépendante de tout ça : une source
persiste juste des données brutes rejouables via l'agent de compréhension
(`generer-instance`) — `instances_trco.source_id` (nullable, `ON DELETE SET
NULL`) n'enregistre que la *provenance* (quelle source a généré cette
instance, le cas échéant ; une instance ingérée par un autre canal — T-R-C-O,
Excel, ERP — n'en a pas), jamais une relation d'usage ou de propriété.
`instances_trco.payload` reste un blob JSONB (pas une table par sous-type de
`Contrainte`) : l'instance est déjà validée et typée par Pydantic à
l'ingestion (§6.7), la redécomposer en lignes SQL dupliquerait une garantie
déjà là, pour un bénéfice nul tant qu'aucune requête ne filtre sur le détail
d'une contrainte — même logique que pour le code figé dans
`solver_store/registry.py` (fichier sur disque, jamais éclaté en base).

Volontairement indépendant de `solver_store.registry.Registre` : aucune
clé étrangère de `executions.solveur_id` vers la table `solveurs` (schémas
potentiellement différents en test, et `solveurs.client_id` lui-même n'a pas
de contrainte de clé étrangère — même niveau de rigueur des deux côtés).

`api/etat.py`'s `obtenir_etat()` sert cette implémentation par défaut (instanciation
paresseuse au premier appel réel) ; seuls les tests la substituent, via
`app.dependency_overrides[obtenir_etat] = lambda: EtatAPI()`, pour rester en mémoire
et isolés les uns des autres.
"""

from __future__ import annotations

import json
import uuid
from contextlib import closing
from datetime import UTC, datetime

import psycopg
from psycopg import sql

from api.etat import (
    ActionSuggeree,
    Client,
    CommandeEnregistree,
    Decision,
    DecisionHumaine,
    EvenementGeneration,
    JobGeneration,
    Priorite,
    PropositionSupervision,
    SourceDonnees,
    TentativeGeneration,
    TypeSignal,
    structure_contraintes,
)
from dsl.schema import InstanceTRCO, Objectif, OperationPlanifiee, Planning
from sandbox.runner import ResultatExecution
from solver_store.registry import SCHEMA_PAR_DEFAUT, dsn_par_defaut
from validation_engine.feasibility_checker import ResultatFaisabilite, Violation
from validation_engine.makespan import calculer_makespan


def _table(schema: str, nom: str) -> sql.Composed:
    return sql.Identifier(schema, nom)


def _proposition_depuis_ligne(ligne: tuple) -> PropositionSupervision:
    (
        id_,
        client_id,
        type_signal,
        action_suggeree,
        resume,
        priorite,
        details,
        date_creation,
        instance_id,
        execution_ids,
        structure_contraintes,
        signature_objectifs,
        decision,
        horodatage_decision,
        commentaire,
    ) = ligne
    return PropositionSupervision(
        id=id_,
        client_id=client_id,
        type_signal=type_signal,
        action_suggeree=action_suggeree,
        resume=resume,
        priorite=priorite,
        details=tuple(details or []),
        date_creation=date_creation,
        instance_id=instance_id,
        execution_ids=tuple(execution_ids or []),
        structure_contraintes=structure_contraintes,
        signature_objectifs=signature_objectifs,
        decision=decision,
        horodatage_decision=horodatage_decision,
        commentaire=commentaire,
    )


class EtatPostgres:
    """Équivalent Postgres d'`EtatAPI` — même méthodes, mêmes signatures,
    mêmes types de retour, pour rester substituable sans toucher aux routes."""

    def __init__(self, dsn: str | None = None, schema: str = SCHEMA_PAR_DEFAUT) -> None:
        self._dsn = dsn or dsn_par_defaut()
        self._schema = schema
        with closing(self._connexion()) as connexion:
            if self._schema != SCHEMA_PAR_DEFAUT:
                connexion.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self._schema)))

            connexion.execute(
                sql.SQL("CREATE TABLE IF NOT EXISTS {table} (id TEXT PRIMARY KEY, nom TEXT)").format(
                    table=self._table("clients")
                )
            )
            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "client_id TEXT NOT NULL REFERENCES {clients}(id), "
                    "nom TEXT, "
                    "donnees_brutes TEXT NOT NULL, "
                    "date_creation TEXT NOT NULL)"
                ).format(table=self._table("sources_donnees"), clients=self._table("clients"))
            )
            # Migration idempotente : secteur d'activité déclaré une fois à
            # la création de la source, réutilisé sur chaque reconversion
            # (`generer_instance`) — oriente le prompt de l'agent de
            # compréhension sans devoir être re-saisi à chaque tentative.
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ADD COLUMN IF NOT EXISTS secteur_activite TEXT").format(
                    table=self._table("sources_donnees")
                )
            )
            # Migration idempotente : unité choisie pour l'affichage des
            # durées/échéances ("jours" implicite si NULL, "semaines", "mois")
            # — purement cosmétique, jamais lue par le DSL/solveur/faisabilité,
            # voir `SourceDonnees.unite_duree`.
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ADD COLUMN IF NOT EXISTS unite_duree TEXT").format(
                    table=self._table("sources_donnees")
                )
            )
            # Ancienne table Gammes produit (gabarits de routage, fonctionnalité retirée) —
            # les commandes référencent désormais des tâches déjà existantes plutôt que
            # d'exploser une gamme (voir `commandes.gamme_id` retiré ci-dessous).
            connexion.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(self._table("gammes_produit")))

            # Ancienne table Projet (portait un pointeur "instance courante" +
            # son propre historique d'exécution) — retirée, remplacée par
            # `sources_donnees` (ci-dessus, ne porte que des données brutes
            # rejouables) + exécution directement par `instance_id`. CASCADE
            # retire aussi les FK pendantes vers cette table depuis
            # `instances_trco.projet_id`/`executions.projet_id` ci-dessous.
            connexion.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(self._table("projets")))

            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "client_id TEXT NOT NULL REFERENCES {clients}(id), "
                    "payload JSONB NOT NULL, "
                    "structure_contraintes TEXT NOT NULL, "
                    "date_ingestion TEXT NOT NULL)"
                ).format(table=self._table("instances_trco"), clients=self._table("clients"))
            )
            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "instance_id TEXT NOT NULL REFERENCES {instances}(id), "
                    "client_id TEXT NOT NULL REFERENCES {clients}(id), "
                    "date_limite INTEGER, "
                    "taches JSONB NOT NULL, "
                    "date_creation TEXT NOT NULL)"
                ).format(
                    table=self._table("commandes"),
                    instances=self._table("instances_trco"),
                    clients=self._table("clients"),
                )
            )
            # Migrations idempotentes : la commande référence désormais des tâches déjà
            # existantes (adapters/commande_derivation.py) plutôt que d'exploser une gamme
            # (fonctionnalité retirée) — gamme_id/quantite n'ont plus de sens.
            connexion.execute(
                sql.SQL("ALTER TABLE {table} DROP COLUMN IF EXISTS gamme_id").format(
                    table=self._table("commandes")
                )
            )
            connexion.execute(
                sql.SQL("ALTER TABLE {table} DROP COLUMN IF EXISTS quantite").format(
                    table=self._table("commandes")
                )
            )
            connexion.execute(
                sql.SQL("ALTER TABLE {table} DROP COLUMN IF EXISTS projet_id").format(
                    table=self._table("instances_trco")
                )
            )
            # Migration idempotente : lien de provenance optionnel vers la
            # source dont l'instance a été générée (agent de compréhension)
            # — NULL pour toute instance ingérée par un autre canal
            # (T-R-C-O, Excel, ERP), ou si la source a depuis été supprimée
            # (`ON DELETE SET NULL` — purement informatif, jamais un
            # verrou de suppression).
            connexion.execute(
                sql.SQL(
                    "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS source_id TEXT "
                    "REFERENCES {sources}(id) ON DELETE SET NULL"
                ).format(table=self._table("instances_trco"), sources=self._table("sources_donnees"))
            )
            # Migration idempotente : description métier proposée par l'agent
            # de compréhension (§5.4 bis) — NULL pour toute instance ingérée
            # par un autre canal (T-R-C-O direct, Excel, ERP). Hors
            # `InstanceTRCO` elle-même (`extra="forbid"`) : une colonne
            # dédiée sur l'entité Instance côté API, pas un champ du DSL.
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ADD COLUMN IF NOT EXISTS description_metier TEXT").format(
                    table=self._table("instances_trco")
                )
            )
            # Migration idempotente : étiquette libre choisie par
            # l'utilisateur pour retrouver/regrouper des instances liées
            # entre elles (réingestions successives d'un même atelier après
            # un aléa) — pure métadonnée de confort, jamais consultée par la
            # sélection de solveur ni la détection de signaux de
            # supervision.
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ADD COLUMN IF NOT EXISTS nom_projet TEXT").format(
                    table=self._table("instances_trco")
                )
            )
            # Migration idempotente : secteur d'activité de l'instance —
            # copié depuis sa source au moment de `enregistrer_instance`
            # quand elle en a une, sinon fourni directement pour les canaux
            # sans SourceDonnees. Même statut de métadonnée pure que
            # nom_projet ci-dessus.
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ADD COLUMN IF NOT EXISTS secteur_activite TEXT").format(
                    table=self._table("instances_trco")
                )
            )
            # Migration idempotente : même métadonnée que sur sources_donnees
            # ci-dessus, copiée à la génération (voir enregistrer_instance).
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ADD COLUMN IF NOT EXISTS unite_duree TEXT").format(
                    table=self._table("instances_trco")
                )
            )
            # Migration idempotente : dernière modification du contenu
            # T-R-C-O (création, `modifier_instance` ou `modifier_objectifs`)
            # — comparée à la date de dernière exécution par
            # `supervision/detecteurs.py` pour détecter qu'une instance déjà
            # exécutée a depuis été modifiée et doit être ré-exécutée.
            # Backfill sur `date_ingestion` pour les lignes déjà en base
            # avant cette migration (sinon NULL, jamais périmée par défaut —
            # cohérent avec "aucune modification connue depuis la création").
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ADD COLUMN IF NOT EXISTS date_modification TEXT").format(
                    table=self._table("instances_trco")
                )
            )
            connexion.execute(
                sql.SQL(
                    "UPDATE {table} SET date_modification = date_ingestion WHERE date_modification IS NULL"
                ).format(table=self._table("instances_trco"))
            )
            # Migration idempotente : scénarios comparatifs (what-if) — une instance variante
            # créée par POST /ingestion/{instance_id}/scenarios pointe ici vers l'instance de
            # base dont elle dérive. Sans rapport avec l'ancien instance_parente_id (retiré
            # ci-dessous) : celui-là suivait un historique de modification en place (une seule
            # lignée) ; ceci relie des variantes délibérées, créées pour coexister et être
            # comparées, jamais fusionnées ni éditées l'une dans l'autre. FK auto-référencée,
            # ON DELETE SET NULL : supprimer l'instance de base ne cascade jamais sur ses
            # variantes (elles restent, juste orphelines de groupe).
            connexion.execute(
                sql.SQL(
                    "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS groupe_scenario_id TEXT "
                    "REFERENCES {table}(id) ON DELETE SET NULL"
                ).format(table=self._table("instances_trco"))
            )
            # Ancienne racine de lignée ("dérivée de") — retirée : une
            # instance se modifie désormais en place (`modifier_instance`,
            # même instance_id) plutôt que de générer une dérivée. La FK
            # auto-référencée part avec la colonne, pas de `DROP CONSTRAINT`
            # séparé nécessaire — même discipline que `projet_id` ci-dessus.
            connexion.execute(
                sql.SQL("ALTER TABLE {table} DROP COLUMN IF EXISTS instance_parente_id").format(
                    table=self._table("instances_trco")
                )
            )
            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "instance_id TEXT REFERENCES {instances}(id), "
                    "solveur_id TEXT NOT NULL, "
                    "date_execution TEXT NOT NULL, "
                    "statut TEXT NOT NULL, "
                    "erreur TEXT, "
                    "violations_faisabilite JSONB)"
                ).format(table=self._table("executions"), instances=self._table("instances_trco"))
            )
            connexion.execute(
                sql.SQL("ALTER TABLE {table} DROP COLUMN IF EXISTS projet_id").format(
                    table=self._table("executions")
                )
            )
            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "execution_id TEXT NOT NULL UNIQUE REFERENCES {executions}(id), "
                    "makespan INTEGER)"
                ).format(table=self._table("plannings"), executions=self._table("executions"))
            )
            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "planning_id TEXT NOT NULL REFERENCES {plannings}(id), "
                    "tache TEXT NOT NULL, "
                    "ressource TEXT NOT NULL, "
                    "debut INTEGER NOT NULL)"
                ).format(table=self._table("operations_planifiees"), plannings=self._table("plannings"))
            )
            # Gantt interactif (Phase 3) : révision ajustée à la main d'un planning, distincte
            # de l'original ci-dessus — une seule révision "courante" par exécution (écrasée à
            # chaque nouvel ajustement légal, jamais un historique), jamais lue par le chemin
            # existant (recuperer_execution/GET /planning/{execution_id}).
            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "execution_id TEXT NOT NULL UNIQUE REFERENCES {executions}(id), "
                    "makespan INTEGER, "
                    "date_ajustement TEXT NOT NULL)"
                ).format(table=self._table("plannings_ajustes"), executions=self._table("executions"))
            )
            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "planning_ajuste_id TEXT NOT NULL REFERENCES {plannings_ajustes}(id), "
                    "tache TEXT NOT NULL, "
                    "ressource TEXT NOT NULL, "
                    "debut INTEGER NOT NULL)"
                ).format(
                    table=self._table("operations_planifiees_ajustees"),
                    plannings_ajustes=self._table("plannings_ajustes"),
                )
            )
            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "execution_id TEXT NOT NULL UNIQUE REFERENCES {executions}(id), "
                    "decision TEXT NOT NULL, "
                    "horodatage TEXT NOT NULL, "
                    "commentaire TEXT)"
                ).format(table=self._table("decisions_humaines"), executions=self._table("executions"))
            )
            # Migration idempotente : une exécution appartient désormais
            # directement à son instance — plus de propriétaire intermédiaire
            # (Projet) susceptible de l'orpheliner. Nettoie d'abord les
            # lignes déjà orphelines de l'ancien comportement (instance
            # supprimée, `instance_id` mis à NULL) avant d'imposer NOT NULL —
            # sous le nouveau modèle, `supprimer_instance` cascade-supprime
            # ses exécutions plutôt que de les orpheliner, cette situation ne
            # peut plus se reproduire. Doit tourner après la création de
            # `plannings`/`operations_planifiees`/`decisions_humaines`
            # (ci-dessus) : leurs FK vers `executions` interdisent de
            # supprimer une exécution encore référencée, même orpheline.
            connexion.execute(
                sql.SQL(
                    "DELETE FROM {ops} WHERE planning_id IN ("
                    "SELECT pl.id FROM {plannings} pl JOIN {execs} e ON e.id = pl.execution_id "
                    "WHERE e.instance_id IS NULL)"
                ).format(
                    ops=self._table("operations_planifiees"),
                    plannings=self._table("plannings"),
                    execs=self._table("executions"),
                )
            )
            connexion.execute(
                sql.SQL(
                    "DELETE FROM {decisions} WHERE execution_id IN "
                    "(SELECT id FROM {execs} WHERE instance_id IS NULL)"
                ).format(decisions=self._table("decisions_humaines"), execs=self._table("executions"))
            )
            connexion.execute(
                sql.SQL(
                    "DELETE FROM {plannings} WHERE execution_id IN "
                    "(SELECT id FROM {execs} WHERE instance_id IS NULL)"
                ).format(plannings=self._table("plannings"), execs=self._table("executions"))
            )
            connexion.execute(
                sql.SQL("DELETE FROM {} WHERE instance_id IS NULL").format(self._table("executions"))
            )
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ALTER COLUMN instance_id SET NOT NULL").format(
                    table=self._table("executions")
                )
            )
            # Historique durable du pipeline multi-agents (§6.6) — distinct du
            # job en mémoire process de `api/routes/generation.py` (source du
            # flux SSE en direct) : copie persistée pour l'audit après coup,
            # y compris après redémarrage serveur.
            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "instance_id TEXT REFERENCES {instances}(id), "
                    "client_id TEXT NOT NULL REFERENCES {clients}(id), "
                    "cree_le TEXT NOT NULL, "
                    "termine BOOLEAN NOT NULL DEFAULT FALSE, "
                    "reussi BOOLEAN, "
                    "id_solveur TEXT, "
                    "specification TEXT, "
                    "plan_technique TEXT, "
                    "code_genere TEXT, "
                    "tests_generes TEXT, "
                    "code_final TEXT, "
                    "nombre_tentatives INTEGER, "
                    "erreur TEXT, "
                    "termine_le TEXT)"
                ).format(
                    table=self._table("jobs_generation"),
                    instances=self._table("instances_trco"),
                    clients=self._table("clients"),
                )
            )
            # Migration idempotente : algorithme recommandé par l'agent
            # Benchmarker (toujours appelé désormais, voir
            # generation/graph.py) — NULL pour tout job généré
            # avant cette migration.
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ADD COLUMN IF NOT EXISTS algorithme TEXT").format(
                    table=self._table("jobs_generation")
                )
            )
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ADD COLUMN IF NOT EXISTS algorithme_raison TEXT").format(
                    table=self._table("jobs_generation")
                )
            )
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ADD COLUMN IF NOT EXISTS algorithme_parametres JSONB").format(
                    table=self._table("jobs_generation")
                )
            )
            # Migration idempotente : sortie de l'agent Documentation (§6.6),
            # jusqu'ici produite mais jamais persistée — NULL pour tout job
            # généré avant cette migration.
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ADD COLUMN IF NOT EXISTS documentation TEXT").format(
                    table=self._table("jobs_generation")
                )
            )
            # Migration idempotente : rapport d'exécution des tests générés par l'agent
            # Testeur dans le bac à sable (canal d'audit — jamais un critère d'acceptation,
            # voir generation/agents/testeur.py) — NULL pour tout job généré avant cette
            # migration.
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ADD COLUMN IF NOT EXISTS rapport_tests_sandbox JSONB").format(
                    table=self._table("jobs_generation")
                )
            )
            # Migration idempotente : `instance_id` devient nullable —
            # `supprimer_instance` oprheline désormais les jobs de génération
            # qui la référencent (`ON DELETE SET NULL`) plutôt que de les
            # supprimer, pour préserver l'audit de génération (spécification,
            # plan technique, code candidat) même après suppression de
            # l'instance source.
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ALTER COLUMN instance_id DROP NOT NULL").format(
                    table=self._table("jobs_generation")
                )
            )
            connexion.execute(
                sql.SQL("ALTER TABLE {table} DROP CONSTRAINT IF EXISTS jobs_generation_instance_id_fkey").format(
                    table=self._table("jobs_generation")
                )
            )
            connexion.execute(
                sql.SQL(
                    "ALTER TABLE {table} ADD CONSTRAINT jobs_generation_instance_id_fkey "
                    "FOREIGN KEY (instance_id) REFERENCES {instances}(id) ON DELETE SET NULL"
                ).format(table=self._table("jobs_generation"), instances=self._table("instances_trco"))
            )
            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "job_id TEXT NOT NULL REFERENCES {jobs}(id), "
                    "ordre INTEGER NOT NULL, "
                    "agent TEXT NOT NULL, "
                    "statut TEXT NOT NULL, "
                    "resume TEXT NOT NULL)"
                ).format(table=self._table("evenements_generation"), jobs=self._table("jobs_generation"))
            )
            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "job_id TEXT NOT NULL REFERENCES {jobs}(id), "
                    "numero INTEGER NOT NULL, "
                    "code_candidat TEXT NOT NULL, "
                    "reussi BOOLEAN NOT NULL, "
                    "erreur_execution TEXT, "
                    "revue_approuve BOOLEAN, "
                    "revue_reponse_brute TEXT, "
                    "revue_problemes JSONB, "
                    "validation_statique_valide BOOLEAN, "
                    "validation_statique_violations JSONB)"
                ).format(table=self._table("tentatives_generation"), jobs=self._table("jobs_generation"))
            )
            # Propositions de l'agent de supervision (MT7) — table neuve, pas de
            # migration à faire : `execution_ids`/`details` en JSONB (mêmes
            # conventions que `revue_problemes` ci-dessus), `instance_id`
            # nullable avec `ON DELETE SET NULL` posé directement (même
            # comportement que `jobs_generation`, la proposition survit à la
            # suppression de l'instance qu'elle référençait). Pas de FK vers
            # `solver_store.registry.Registre` ni vers `executions` pour
            # `execution_ids` (tableau, une seule colonne ne peut pas porter
            # plusieurs clés étrangères) — même niveau de rigueur que le reste
            # du module vis-à-vis du registre des solveurs (voir docstring).
            connexion.execute(
                sql.SQL(
                    "CREATE TABLE IF NOT EXISTS {table} ("
                    "id TEXT PRIMARY KEY, "
                    "client_id TEXT NOT NULL REFERENCES {clients}(id), "
                    "type_signal TEXT NOT NULL, "
                    "action_suggeree TEXT NOT NULL, "
                    "resume TEXT NOT NULL, "
                    "priorite TEXT NOT NULL, "
                    "details JSONB NOT NULL, "
                    "date_creation TEXT NOT NULL, "
                    "instance_id TEXT REFERENCES {instances}(id) ON DELETE SET NULL, "
                    "execution_ids JSONB NOT NULL, "
                    "structure_contraintes TEXT, "
                    "signature_objectifs TEXT, "
                    "decision TEXT, "
                    "horodatage_decision TEXT, "
                    "commentaire TEXT)"
                ).format(
                    table=self._table("propositions_supervision"),
                    clients=self._table("clients"),
                    instances=self._table("instances_trco"),
                )
            )
            connexion.commit()

    def _connexion(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn)

    def _table(self, nom: str) -> sql.Composed:
        return _table(self._schema, nom)

    # --- Clients -----------------------------------------------------------

    def enregistrer_client(self, client_id: str, nom: str | None = None) -> None:
        """`ON CONFLICT DO NOTHING` : un nom déjà posé pour ce client_id
        n'est jamais écrasé par un enregistrement implicite ultérieur
        (ex. `enregistrer_instance` sur un client déjà nommé)."""
        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL("INSERT INTO {} (id, nom) VALUES (%s, %s) ON CONFLICT (id) DO NOTHING").format(
                    self._table("clients")
                ),
                (client_id, nom),
            )
            connexion.commit()

    def recuperer_client(self, client_id: str) -> Client:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT id, nom FROM {} WHERE id = %s").format(self._table("clients")),
                (client_id,),
            ).fetchone()
        if ligne is None:
            raise KeyError(client_id)
        id_, nom = ligne
        return Client(id=id_, nom=nom)

    def lister_clients(self) -> list[dict[str, object]]:
        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(
                sql.SQL("SELECT id, nom FROM {} ORDER BY id").format(self._table("clients"))
            ).fetchall()
        return [{"client_id": id_, "nom": nom} for id_, nom in lignes]

    # --- Sources de données ------------------------------------------------

    def enregistrer_source(
        self,
        client_id: str,
        donnees_brutes: str,
        nom: str | None = None,
        secteur_activite: str | None = None,
        unite_duree: str | None = None,
    ) -> str:
        source_id = str(uuid.uuid4())
        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL("INSERT INTO {} (id, nom) VALUES (%s, NULL) ON CONFLICT (id) DO NOTHING").format(
                    self._table("clients")
                ),
                (client_id,),
            )
            connexion.execute(
                sql.SQL(
                    "INSERT INTO {} (id, client_id, nom, donnees_brutes, date_creation, secteur_activite, "
                    "unite_duree) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                ).format(self._table("sources_donnees")),
                (
                    source_id,
                    client_id,
                    nom,
                    donnees_brutes,
                    datetime.now(UTC).isoformat(),
                    secteur_activite,
                    unite_duree,
                ),
            )
            connexion.commit()
        return source_id

    def recuperer_source(self, source_id: str) -> SourceDonnees:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL(
                    "SELECT id, client_id, nom, donnees_brutes, date_creation, secteur_activite, "
                    "unite_duree FROM {} WHERE id = %s"
                ).format(self._table("sources_donnees")),
                (source_id,),
            ).fetchone()
        if ligne is None:
            raise KeyError(source_id)
        id_, client_id, nom, donnees_brutes, date_creation, secteur_activite, unite_duree = ligne
        return SourceDonnees(
            id=id_,
            client_id=client_id,
            nom=nom,
            donnees_brutes=donnees_brutes,
            date_creation=date_creation,
            secteur_activite=secteur_activite,
            unite_duree=unite_duree,
        )

    def lister_sources(self, client_id: str | None = None) -> list[dict[str, object]]:
        """`client_id=None` ne filtre rien (réservé à l'admin — voir
        `api/autorisation.py`)."""
        requete = sql.SQL(
            "SELECT s.id, s.client_id, s.nom, s.date_creation, "
            "(SELECT COUNT(*) FROM {instances} i WHERE i.source_id = s.id) AS nb_instances, "
            "s.secteur_activite, s.unite_duree "
            "FROM {sources} s WHERE 1 = 1"
        ).format(sources=self._table("sources_donnees"), instances=self._table("instances_trco"))
        parametres: list[str] = []
        if client_id is not None:
            requete += sql.SQL(" AND s.client_id = %s")
            parametres.append(client_id)
        requete += sql.SQL(" ORDER BY s.date_creation DESC")

        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(requete, parametres).fetchall()
        return [
            {
                "source_id": id_,
                "client_id": client_id,
                "nom": nom,
                "date_creation": date_creation,
                "nb_instances": nb,
                "secteur_activite": secteur_activite,
                "unite_duree": unite_duree,
            }
            for id_, client_id, nom, date_creation, nb, secteur_activite, unite_duree in lignes
        ]

    def lister_instances_pour_source(self, source_id: str) -> list[dict[str, object]]:
        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(
                sql.SQL(
                    "SELECT id, structure_contraintes, nom_projet FROM {} "
                    "WHERE source_id = %s ORDER BY date_ingestion DESC"
                ).format(self._table("instances_trco")),
                (source_id,),
            ).fetchall()
        return [
            {"instance_id": id_, "structure_contraintes": structure, "nom_projet": nom_projet}
            for id_, structure, nom_projet in lignes
        ]

    def supprimer_source(self, source_id: str) -> None:
        """Coupe uniquement le lien de provenance vers les instances générées
        à partir d'elle (`instances_trco.source_id ON DELETE SET NULL`, géré
        par Postgres lui-même) — elles restent, exécutables indépendamment.
        Une source ne porte aucun historique d'exécution à cascader."""
        with closing(self._connexion()) as connexion:
            existe = connexion.execute(
                sql.SQL("SELECT 1 FROM {} WHERE id = %s").format(self._table("sources_donnees")),
                (source_id,),
            ).fetchone()
            if existe is None:
                raise KeyError(source_id)
            connexion.execute(
                sql.SQL("DELETE FROM {} WHERE id = %s").format(self._table("sources_donnees")),
                (source_id,),
            )
            connexion.commit()

    # --- Commandes -------------------------------------------------------

    def enregistrer_commande(
        self,
        commande_id: str,
        instance_id: str,
        client_id: str,
        date_limite: int | None,
        taches: tuple[str, ...],
    ) -> None:
        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL("INSERT INTO {} (id, nom) VALUES (%s, NULL) ON CONFLICT (id) DO NOTHING").format(
                    self._table("clients")
                ),
                (client_id,),
            )
            connexion.execute(
                sql.SQL(
                    "INSERT INTO {} (id, instance_id, client_id, date_limite, taches, date_creation) "
                    "VALUES (%s, %s, %s, %s, %s::jsonb, %s)"
                ).format(self._table("commandes")),
                (
                    commande_id,
                    instance_id,
                    client_id,
                    date_limite,
                    json.dumps(list(taches)),
                    datetime.now(UTC).isoformat(),
                ),
            )
            connexion.commit()

    def recuperer_commande(self, commande_id: str) -> CommandeEnregistree:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL(
                    "SELECT id, instance_id, client_id, date_limite, taches, date_creation FROM {} WHERE id = %s"
                ).format(self._table("commandes")),
                (commande_id,),
            ).fetchone()
        if ligne is None:
            raise KeyError(commande_id)
        id_, instance_id, client_id, date_limite, taches, date_creation = ligne
        return CommandeEnregistree(
            id=id_,
            instance_id=instance_id,
            client_id=client_id,
            date_limite=date_limite,
            taches=tuple(taches),
            date_creation=date_creation,
        )

    def lister_commandes(self, instance_id: str | None = None) -> list[CommandeEnregistree]:
        requete = sql.SQL(
            "SELECT id, instance_id, client_id, date_limite, taches, date_creation FROM {} WHERE 1 = 1"
        ).format(self._table("commandes"))
        parametres: list[str] = []
        if instance_id is not None:
            requete += sql.SQL(" AND instance_id = %s")
            parametres.append(instance_id)

        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(requete, parametres).fetchall()
        return [
            CommandeEnregistree(
                id=id_,
                instance_id=iid,
                client_id=cid,
                date_limite=date_limite,
                taches=tuple(taches),
                date_creation=date_creation,
            )
            for id_, iid, cid, date_limite, taches, date_creation in lignes
        ]

    # --- Instances -----------------------------------------------------

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
        instance_id = str(uuid.uuid4())
        structure = structure_contraintes(instance)
        maintenant = datetime.now(UTC).isoformat()
        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL("INSERT INTO {} (id, nom) VALUES (%s, NULL) ON CONFLICT (id) DO NOTHING").format(
                    self._table("clients")
                ),
                (client_id,),
            )
            connexion.execute(
                sql.SQL(
                    "INSERT INTO {} "
                    "(id, client_id, payload, structure_contraintes, date_ingestion, source_id, "
                    "description_metier, nom_projet, secteur_activite, unite_duree, date_modification, "
                    "groupe_scenario_id) "
                    "VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                ).format(self._table("instances_trco")),
                (
                    instance_id,
                    client_id,
                    instance.model_dump_json(),
                    structure,
                    maintenant,
                    source_id,
                    description_metier,
                    nom_projet,
                    secteur_activite,
                    unite_duree,
                    maintenant,
                    groupe_scenario_id,
                ),
            )
            connexion.commit()
        return instance_id

    def lister_instances_du_groupe_scenario(self, instance_id: str) -> list[str]:
        """Toutes les instances du même groupe de scénarios que `instance_id`,
        elle comprise — voir `EtatAPI.lister_instances_du_groupe_scenario`
        pour la sémantique complète (même contrat, même docstring)."""
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT groupe_scenario_id FROM {} WHERE id = %s").format(self._table("instances_trco")),
                (instance_id,),
            ).fetchone()
            if ligne is None:
                return []
            groupe_id = ligne[0] or instance_id

            racine = connexion.execute(
                sql.SQL("SELECT id FROM {} WHERE id = %s").format(self._table("instances_trco")),
                (groupe_id,),
            ).fetchone()
            membres = {groupe_id} if racine is not None else set()

            variantes = connexion.execute(
                sql.SQL("SELECT id FROM {} WHERE groupe_scenario_id = %s").format(self._table("instances_trco")),
                (groupe_id,),
            ).fetchall()
            membres |= {row[0] for row in variantes}
        return sorted(membres)

    def recuperer_instance(self, instance_id: str) -> tuple[str, InstanceTRCO]:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT client_id, payload FROM {} WHERE id = %s").format(self._table("instances_trco")),
                (instance_id,),
            ).fetchone()
        if ligne is None:
            raise KeyError(instance_id)
        client_id, payload = ligne
        return client_id, InstanceTRCO.model_validate(payload)

    def recuperer_description_metier(self, instance_id: str) -> str | None:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT description_metier FROM {} WHERE id = %s").format(self._table("instances_trco")),
                (instance_id,),
            ).fetchone()
        if ligne is None:
            raise KeyError(instance_id)
        return ligne[0]

    def recuperer_nom_projet(self, instance_id: str) -> str | None:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT nom_projet FROM {} WHERE id = %s").format(self._table("instances_trco")),
                (instance_id,),
            ).fetchone()
        if ligne is None:
            raise KeyError(instance_id)
        return ligne[0]

    def recuperer_secteur_activite(self, instance_id: str) -> str | None:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT secteur_activite FROM {} WHERE id = %s").format(self._table("instances_trco")),
                (instance_id,),
            ).fetchone()
        if ligne is None:
            raise KeyError(instance_id)
        return ligne[0]

    def recuperer_unite_duree(self, instance_id: str) -> str | None:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT unite_duree FROM {} WHERE id = %s").format(self._table("instances_trco")),
                (instance_id,),
            ).fetchone()
        if ligne is None:
            raise KeyError(instance_id)
        return ligne[0]

    def lister_noms_projet(self, client_id: str | None = None) -> list[dict[str, object]]:
        """Noms de projet distincts déjà utilisés (avec leur nombre
        d'instances), pour peupler une auto-complétion côté client — voir
        `EtatAPI.lister_noms_projet`. `client_id=None` ne filtre rien
        (réservé à l'admin)."""
        requete = sql.SQL("SELECT nom_projet, COUNT(*) FROM {} WHERE nom_projet IS NOT NULL").format(
            self._table("instances_trco")
        )
        parametres: list[str] = []
        if client_id is not None:
            requete += sql.SQL(" AND client_id = %s")
            parametres.append(client_id)
        requete += sql.SQL(" GROUP BY nom_projet ORDER BY COUNT(*) DESC, nom_projet ASC")

        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(requete, parametres).fetchall()
        return [{"nom_projet": nom, "nb_instances": n} for nom, n in lignes]

    def modifier_objectifs(self, instance_id: str, objectifs: list[Objectif]) -> InstanceTRCO:
        """Remplace les objectifs d'une instance déjà ingérée — voir
        `EtatAPI.modifier_objectifs` pour la justification. Relit le payload
        existant, reconstruit l'instance entière (même garde-fou, §6.7) et
        réécrit le blob JSONB — pas de colonne dédiée aux objectifs, même
        logique que `payload` pour le reste (voir docstring de ce module)."""
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT payload FROM {} WHERE id = %s").format(self._table("instances_trco")),
                (instance_id,),
            ).fetchone()
            if ligne is None:
                raise KeyError(instance_id)

            instance_existante = InstanceTRCO.model_validate(ligne[0])
            nouvelle_instance = InstanceTRCO(
                taches=instance_existante.taches,
                ressources=instance_existante.ressources,
                contraintes=instance_existante.contraintes,
                objectifs=objectifs,
            )

            connexion.execute(
                sql.SQL(
                    "UPDATE {} SET payload = %s::jsonb, structure_contraintes = %s, "
                    "date_modification = %s WHERE id = %s"
                ).format(self._table("instances_trco")),
                (
                    nouvelle_instance.model_dump_json(),
                    structure_contraintes(nouvelle_instance),
                    datetime.now(UTC).isoformat(),
                    instance_id,
                ),
            )
            connexion.commit()
        return nouvelle_instance

    def modifier_instance(
        self,
        instance_id: str,
        instance: InstanceTRCO,
        nom_projet: str | None = None,
        secteur_activite: str | None = None,
    ) -> InstanceTRCO:
        with closing(self._connexion()) as connexion:
            existe = connexion.execute(
                sql.SQL("SELECT 1 FROM {} WHERE id = %s").format(self._table("instances_trco")),
                (instance_id,),
            ).fetchone()
            if existe is None:
                raise KeyError(instance_id)
            connexion.execute(
                sql.SQL(
                    "UPDATE {} SET payload = %s::jsonb, structure_contraintes = %s, nom_projet = %s, "
                    "secteur_activite = %s, date_modification = %s WHERE id = %s"
                ).format(self._table("instances_trco")),
                (
                    instance.model_dump_json(),
                    structure_contraintes(instance),
                    nom_projet,
                    secteur_activite,
                    datetime.now(UTC).isoformat(),
                    instance_id,
                ),
            )
            connexion.commit()
        return instance

    def supprimer_instance(self, instance_id: str) -> None:
        """Cascade-supprime son propre historique d'exécution (exécutions,
        plannings, opérations planifiées, décisions humaines, révisions de
        planning ajustées, commandes associées) — une exécution/commande
        n'existe jamais sans l'instance qui l'a produite. Le lien de
        provenance depuis `sources_donnees` (`ON DELETE SET NULL`) et depuis
        `jobs_generation` (même comportement, préserve l'audit de
        génération) sont gérés par Postgres lui-même via les contraintes de
        clé étrangère, rien à faire ici pour eux."""
        with closing(self._connexion()) as connexion:
            existe = connexion.execute(
                sql.SQL("SELECT 1 FROM {} WHERE id = %s").format(self._table("instances_trco")),
                (instance_id,),
            ).fetchone()
            if existe is None:
                raise KeyError(instance_id)

            connexion.execute(
                sql.SQL("DELETE FROM {} WHERE instance_id = %s").format(self._table("commandes")),
                (instance_id,),
            )
            connexion.execute(
                sql.SQL(
                    "DELETE FROM {ops} WHERE planning_id IN ("
                    "SELECT pl.id FROM {plannings} pl JOIN {execs} e ON e.id = pl.execution_id "
                    "WHERE e.instance_id = %s)"
                ).format(
                    ops=self._table("operations_planifiees"),
                    plannings=self._table("plannings"),
                    execs=self._table("executions"),
                ),
                (instance_id,),
            )
            connexion.execute(
                sql.SQL(
                    "DELETE FROM {decisions} WHERE execution_id IN (SELECT id FROM {execs} WHERE instance_id = %s)"
                ).format(decisions=self._table("decisions_humaines"), execs=self._table("executions")),
                (instance_id,),
            )
            connexion.execute(
                sql.SQL(
                    "DELETE FROM {plannings} WHERE execution_id IN (SELECT id FROM {execs} WHERE instance_id = %s)"
                ).format(plannings=self._table("plannings"), execs=self._table("executions")),
                (instance_id,),
            )
            connexion.execute(
                sql.SQL(
                    "DELETE FROM {ops} WHERE planning_ajuste_id IN ("
                    "SELECT pa.id FROM {plannings_ajustes} pa JOIN {execs} e ON e.id = pa.execution_id "
                    "WHERE e.instance_id = %s)"
                ).format(
                    ops=self._table("operations_planifiees_ajustees"),
                    plannings_ajustes=self._table("plannings_ajustes"),
                    execs=self._table("executions"),
                ),
                (instance_id,),
            )
            connexion.execute(
                sql.SQL(
                    "DELETE FROM {plannings_ajustes} WHERE execution_id IN "
                    "(SELECT id FROM {execs} WHERE instance_id = %s)"
                ).format(plannings_ajustes=self._table("plannings_ajustes"), execs=self._table("executions")),
                (instance_id,),
            )
            connexion.execute(
                sql.SQL("DELETE FROM {} WHERE instance_id = %s").format(self._table("executions")),
                (instance_id,),
            )
            connexion.execute(
                sql.SQL("DELETE FROM {} WHERE id = %s").format(self._table("instances_trco")),
                (instance_id,),
            )
            connexion.commit()

    def lister_instances(
        self,
        client_id: str | None = None,
        nom_projet: str | None = None,
        secteur_activite: str | None = None,
    ) -> list[dict[str, object]]:
        """Vue de supervision (lecture seule) — équivalent SQL du repli
        Python de `EtatAPI.lister_instances` (jointure d'existence sur
        `executions` pour l'indicateur `executee`). `client_id=None` ne
        filtre rien (réservé à l'admin — voir `api/autorisation.py`).
        `nom_projet`/`secteur_activite` filtrent en plus sur ces métadonnées
        libres."""
        requete = sql.SQL(
            "SELECT i.id, i.client_id, i.structure_contraintes, "
            "EXISTS(SELECT 1 FROM {executions} e WHERE e.instance_id = i.id) AS executee, "
            "i.nom_projet, i.secteur_activite, i.unite_duree, i.date_modification "
            "FROM {instances} i WHERE 1 = 1"
        ).format(executions=self._table("executions"), instances=self._table("instances_trco"))
        parametres: list[str] = []
        if client_id is not None:
            requete += sql.SQL(" AND i.client_id = %s")
            parametres.append(client_id)
        if nom_projet is not None:
            requete += sql.SQL(" AND i.nom_projet = %s")
            parametres.append(nom_projet)
        if secteur_activite is not None:
            requete += sql.SQL(" AND i.secteur_activite = %s")
            parametres.append(secteur_activite)

        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(requete, parametres).fetchall()
        return [
            {
                "instance_id": ligne[0],
                "client_id": ligne[1],
                "structure_contraintes": ligne[2],
                "executee": ligne[3],
                "nom_projet": ligne[4],
                "secteur_activite": ligne[5],
                "unite_duree": ligne[6],
                "date_modification": ligne[7],
            }
            for ligne in lignes
        ]

    # --- Exécutions ------------------------------------------------------

    def enregistrer_execution(self, id_solveur: str, instance_id: str, resultat: ResultatExecution) -> str:
        execution_id = str(uuid.uuid4())
        statut = "reussi" if resultat.reussi else "echec"

        violations_json: str | None = None
        if resultat.verdict_faisabilite is not None:
            violations_json = json.dumps(
                [
                    {"type": v.type, "message": v.message, "tache": v.tache, "ressource": v.ressource}
                    for v in resultat.verdict_faisabilite.violations
                ]
            )

        makespan: int | None = None
        if resultat.planning is not None:
            _, instance = self.recuperer_instance(instance_id)
            makespan = calculer_makespan(instance, resultat.planning)

        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL(
                    "INSERT INTO {} "
                    "(id, instance_id, solveur_id, date_execution, statut, erreur, violations_faisabilite) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)"
                ).format(self._table("executions")),
                (
                    execution_id,
                    instance_id,
                    id_solveur,
                    datetime.now(UTC).isoformat(),
                    statut,
                    resultat.erreur,
                    violations_json,
                ),
            )

            if resultat.planning is not None:
                planning_id = str(uuid.uuid4())
                connexion.execute(
                    sql.SQL("INSERT INTO {} (id, execution_id, makespan) VALUES (%s, %s, %s)").format(
                        self._table("plannings")
                    ),
                    (planning_id, execution_id, makespan),
                )
                for operation in resultat.planning.operations:
                    connexion.execute(
                        sql.SQL(
                            "INSERT INTO {} (id, planning_id, tache, ressource, debut) VALUES (%s, %s, %s, %s, %s)"
                        ).format(self._table("operations_planifiees")),
                        (str(uuid.uuid4()), planning_id, operation.tache, operation.ressource, operation.debut),
                    )

            connexion.commit()
        return execution_id

    def recuperer_execution(self, execution_id: str) -> tuple[str, str, ResultatExecution]:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL(
                    "SELECT instance_id, solveur_id, erreur, violations_faisabilite FROM {} WHERE id = %s"
                ).format(self._table("executions")),
                (execution_id,),
            ).fetchone()
            if ligne is None:
                raise KeyError(execution_id)
            instance_id, solveur_id, erreur, violations_json = ligne

            ligne_planning = connexion.execute(
                sql.SQL("SELECT id FROM {} WHERE execution_id = %s").format(self._table("plannings")),
                (execution_id,),
            ).fetchone()

            planning: Planning | None = None
            if ligne_planning is not None:
                (planning_id,) = ligne_planning
                lignes_ops = connexion.execute(
                    sql.SQL("SELECT tache, ressource, debut FROM {} WHERE planning_id = %s").format(
                        self._table("operations_planifiees")
                    ),
                    (planning_id,),
                ).fetchall()
                planning = Planning(
                    operations=[
                        OperationPlanifiee(tache=tache, ressource=ressource, debut=debut)
                        for tache, ressource, debut in lignes_ops
                    ]
                )

        verdict_faisabilite: ResultatFaisabilite | None = None
        if violations_json is not None:
            verdict_faisabilite = ResultatFaisabilite(
                violations=tuple(
                    Violation(
                        type=v["type"],
                        message=v["message"],
                        tache=v.get("tache"),
                        ressource=v.get("ressource"),
                    )
                    for v in violations_json
                )
            )

        resultat = ResultatExecution(planning=planning, verdict_faisabilite=verdict_faisabilite, erreur=erreur)
        return solveur_id, instance_id, resultat

    def dernier_planning_pour_instance(self, instance_id: str) -> Planning | None:
        """Équivalent Postgres d'`EtatAPI.dernier_planning_pour_instance` — voir sa docstring
        pour le contrat (Phase 2, replanification à horizon glissant). Ne considère que les
        exécutions `statut = 'reussi'`, la plus récente par `date_execution`."""
        with closing(self._connexion()) as connexion:
            ligne_planning = connexion.execute(
                sql.SQL(
                    "SELECT p.id FROM {executions} e JOIN {plannings} p ON p.execution_id = e.id "
                    "WHERE e.instance_id = %s AND e.statut = 'reussi' "
                    "ORDER BY e.date_execution DESC LIMIT 1"
                ).format(executions=self._table("executions"), plannings=self._table("plannings")),
                (instance_id,),
            ).fetchone()
            if ligne_planning is None:
                return None
            (planning_id,) = ligne_planning

            lignes_ops = connexion.execute(
                sql.SQL("SELECT tache, ressource, debut FROM {} WHERE planning_id = %s").format(
                    self._table("operations_planifiees")
                ),
                (planning_id,),
            ).fetchall()

        return Planning(
            operations=[
                OperationPlanifiee(tache=tache, ressource=ressource, debut=debut)
                for tache, ressource, debut in lignes_ops
            ]
        )

    def enregistrer_planning_ajuste(
        self, execution_id: str, planning: Planning, makespan: int | None = None
    ) -> None:
        """Écrase toute révision ajustée précédente de cette exécution — une seule révision
        "courante", jamais un historique (Gantt interactif, Phase 3). Ne touche jamais
        `plannings`/`operations_planifiees` (l'original figé par le solveur). `makespan` est
        calculé par l'appelant (`api/routes/planning.py`, qui a déjà l'instance sous la main
        pour `calculer_makespan`) plutôt que refetché ici — décoratif de toute façon, comme sur
        `plannings.makespan` : jamais relu par aucune route existante, seulement les opérations
        elles-mêmes (les durées sont toujours dérivées côté client depuis l'instance)."""
        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL(
                    "DELETE FROM {ops} WHERE planning_ajuste_id IN "
                    "(SELECT id FROM {plannings_ajustes} WHERE execution_id = %s)"
                ).format(
                    ops=self._table("operations_planifiees_ajustees"),
                    plannings_ajustes=self._table("plannings_ajustes"),
                ),
                (execution_id,),
            )
            connexion.execute(
                sql.SQL("DELETE FROM {} WHERE execution_id = %s").format(self._table("plannings_ajustes")),
                (execution_id,),
            )

            planning_ajuste_id = str(uuid.uuid4())
            connexion.execute(
                sql.SQL(
                    "INSERT INTO {} (id, execution_id, makespan, date_ajustement) VALUES (%s, %s, %s, %s)"
                ).format(self._table("plannings_ajustes")),
                (planning_ajuste_id, execution_id, makespan, datetime.now(UTC).isoformat()),
            )
            for operation in planning.operations:
                connexion.execute(
                    sql.SQL(
                        "INSERT INTO {} (id, planning_ajuste_id, tache, ressource, debut) "
                        "VALUES (%s, %s, %s, %s, %s)"
                    ).format(self._table("operations_planifiees_ajustees")),
                    (str(uuid.uuid4()), planning_ajuste_id, operation.tache, operation.ressource, operation.debut),
                )
            connexion.commit()

    def recuperer_planning_ajuste(self, execution_id: str) -> Planning | None:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT id FROM {} WHERE execution_id = %s").format(self._table("plannings_ajustes")),
                (execution_id,),
            ).fetchone()
            if ligne is None:
                return None
            (planning_ajuste_id,) = ligne

            lignes_ops = connexion.execute(
                sql.SQL("SELECT tache, ressource, debut FROM {} WHERE planning_ajuste_id = %s").format(
                    self._table("operations_planifiees_ajustees")
                ),
                (planning_ajuste_id,),
            ).fetchall()

        return Planning(
            operations=[
                OperationPlanifiee(tache=tache, ressource=ressource, debut=debut)
                for tache, ressource, debut in lignes_ops
            ]
        )

    def lister_executions(self, client_id: str | None = None) -> list[dict[str, object]]:
        """Scopée par le client de l'instance exécutée (`JOIN`, pas
        `LEFT JOIN` : une exécution garantit désormais une instance vivante,
        `supprimer_instance` cascade-supprime ses propres exécutions plutôt
        que de les orpheliner). `client_id=None` ne filtre rien (réservé à
        l'admin)."""
        requete = sql.SQL(
            "SELECT e.id, e.solveur_id, e.instance_id, i.client_id, e.date_execution, e.statut, "
            "e.erreur, d.decision "
            "FROM {executions} e "
            "JOIN {instances} i ON i.id = e.instance_id "
            "LEFT JOIN {decisions} d ON d.execution_id = e.id WHERE 1 = 1"
        ).format(
            executions=self._table("executions"),
            instances=self._table("instances_trco"),
            decisions=self._table("decisions_humaines"),
        )
        parametres: list[str] = []
        if client_id is not None:
            requete += sql.SQL(" AND i.client_id = %s")
            parametres.append(client_id)
        requete += sql.SQL(" ORDER BY e.date_execution DESC")

        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(requete, parametres).fetchall()
        return [
            {
                "execution_id": execution_id,
                "id_solveur": id_solveur,
                "instance_id": instance_id,
                "client_id": client_id,
                "date_execution": date_execution,
                "reussi": statut == "reussi",
                "erreur": erreur,
                "decision": decision,
            }
            for (
                execution_id,
                id_solveur,
                instance_id,
                client_id,
                date_execution,
                statut,
                erreur,
                decision,
            ) in lignes
        ]

    # --- Décisions humaines ----------------------------------------------

    def enregistrer_decision(self, execution_id: str, decision: Decision, commentaire: str | None = None) -> None:
        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL(
                    "INSERT INTO {} (id, execution_id, decision, horodatage, commentaire) "
                    "VALUES (%s, %s, %s, %s, %s) "
                    "ON CONFLICT (execution_id) DO UPDATE SET "
                    "decision = EXCLUDED.decision, horodatage = EXCLUDED.horodatage, "
                    "commentaire = EXCLUDED.commentaire"
                ).format(self._table("decisions_humaines")),
                (str(uuid.uuid4()), execution_id, decision, datetime.now(UTC).isoformat(), commentaire),
            )
            connexion.commit()

    def decision_pour(self, execution_id: str) -> DecisionHumaine | None:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL(
                    "SELECT execution_id, decision, horodatage, commentaire FROM {} WHERE execution_id = %s"
                ).format(self._table("decisions_humaines")),
                (execution_id,),
            ).fetchone()
        if ligne is None:
            return None
        execution_id_, decision, horodatage, commentaire = ligne
        return DecisionHumaine(
            execution_id=execution_id_, decision=decision, horodatage=horodatage, commentaire=commentaire
        )

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
        proposition_id = str(uuid.uuid4())
        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL("INSERT INTO {} (id, nom) VALUES (%s, NULL) ON CONFLICT (id) DO NOTHING").format(
                    self._table("clients")
                ),
                (client_id,),
            )
            connexion.execute(
                sql.SQL(
                    "INSERT INTO {} "
                    "(id, client_id, type_signal, action_suggeree, resume, priorite, details, date_creation, "
                    "instance_id, execution_ids, structure_contraintes, signature_objectifs) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s)"
                ).format(self._table("propositions_supervision")),
                (
                    proposition_id,
                    client_id,
                    type_signal,
                    action_suggeree,
                    resume,
                    priorite,
                    json.dumps(list(details)),
                    datetime.now(UTC).isoformat(),
                    instance_id,
                    json.dumps(list(execution_ids)),
                    structure_contraintes,
                    signature_objectifs,
                ),
            )
            connexion.commit()
        return proposition_id

    def recuperer_proposition(self, proposition_id: str) -> PropositionSupervision:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL(
                    "SELECT id, client_id, type_signal, action_suggeree, resume, priorite, details, "
                    "date_creation, instance_id, execution_ids, structure_contraintes, signature_objectifs, "
                    "decision, horodatage_decision, commentaire FROM {} WHERE id = %s"
                ).format(self._table("propositions_supervision")),
                (proposition_id,),
            ).fetchone()
        if ligne is None:
            raise KeyError(proposition_id)
        return _proposition_depuis_ligne(ligne)

    def lister_propositions(
        self, client_id: str | None = None, en_attente_seulement: bool = False
    ) -> list[dict[str, object]]:
        requete = sql.SQL(
            "SELECT id, client_id, type_signal, action_suggeree, resume, priorite, details, "
            "date_creation, instance_id, execution_ids, structure_contraintes, signature_objectifs, "
            "decision, horodatage_decision, commentaire FROM {} WHERE 1 = 1"
        ).format(self._table("propositions_supervision"))
        parametres: list[str] = []
        if client_id is not None:
            requete += sql.SQL(" AND client_id = %s")
            parametres.append(client_id)
        if en_attente_seulement:
            requete += sql.SQL(" AND decision IS NULL")
        requete += sql.SQL(" ORDER BY date_creation DESC")

        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(requete, parametres).fetchall()
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
            for p in (_proposition_depuis_ligne(ligne) for ligne in lignes)
        ]

    def decider_proposition(self, proposition_id: str, decision: Decision, commentaire: str | None = None) -> None:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT 1 FROM {} WHERE id = %s").format(self._table("propositions_supervision")),
                (proposition_id,),
            ).fetchone()
            if ligne is None:
                raise KeyError(proposition_id)
            connexion.execute(
                sql.SQL(
                    "UPDATE {} SET decision = %s, horodatage_decision = %s, commentaire = %s WHERE id = %s"
                ).format(self._table("propositions_supervision")),
                (decision, datetime.now(UTC).isoformat(), commentaire, proposition_id),
            )
            connexion.commit()

    # --- Historique de génération (§6.6) -----------------------------------

    def enregistrer_job_generation(self, job_id: str, instance_id: str, client_id: str) -> None:
        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL("INSERT INTO {} (id, instance_id, client_id, cree_le) VALUES (%s, %s, %s, %s)").format(
                    self._table("jobs_generation")
                ),
                (job_id, instance_id, client_id, datetime.now(UTC).isoformat()),
            )
            connexion.commit()

    def ajouter_evenement_generation(self, job_id: str, agent: str, statut: str, resume: str) -> None:
        with closing(self._connexion()) as connexion:
            (ordre,) = connexion.execute(
                sql.SQL("SELECT COUNT(*) FROM {} WHERE job_id = %s").format(self._table("evenements_generation")),
                (job_id,),
            ).fetchone()
            connexion.execute(
                sql.SQL(
                    "INSERT INTO {} (id, job_id, ordre, agent, statut, resume) VALUES (%s, %s, %s, %s, %s, %s)"
                ).format(self._table("evenements_generation")),
                (str(uuid.uuid4()), job_id, ordre, agent, statut, resume),
            )
            connexion.commit()

    def ajouter_tentative_generation(self, job_id: str, tentative: TentativeGeneration) -> None:
        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL(
                    "INSERT INTO {} "
                    "(id, job_id, numero, code_candidat, reussi, erreur_execution, revue_approuve, "
                    "revue_reponse_brute, revue_problemes, validation_statique_valide, "
                    "validation_statique_violations) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb)"
                ).format(self._table("tentatives_generation")),
                (
                    str(uuid.uuid4()),
                    job_id,
                    tentative.numero,
                    tentative.code_candidat,
                    tentative.reussi,
                    tentative.erreur_execution,
                    tentative.revue_approuve,
                    tentative.revue_reponse_brute,
                    json.dumps(list(tentative.revue_problemes)),
                    tentative.validation_statique_valide,
                    json.dumps(list(tentative.validation_statique_violations)),
                ),
            )
            connexion.commit()

    # Champs `dict | None` du job de génération, sérialisés en JSON avant écriture
    # (colonnes JSONB) — tout le reste passe tel quel. Voir `mettre_a_jour_job_generation`.
    _COLONNES_JSONB_JOB_GENERATION = frozenset({"algorithme_parametres", "rapport_tests_sandbox"})

    def mettre_a_jour_job_generation(self, job_id: str, **champs: object) -> None:
        """Persiste un ou plusieurs champs dès qu'ils sont connus, sans marquer le job
        terminé (contrairement à `terminer_job_generation`) — capture incrémentale des
        sorties d'agents au fil du pipeline (§6.6), pour ne rien perdre d'un plantage en
        cours de route. `UPDATE` dynamique ne portant que sur les colonnes fournies ;
        les champs `dict` (`_COLONNES_JSONB_JOB_GENERATION`) sont sérialisés en JSON."""
        if not champs:
            return
        colonnes = list(champs.keys())
        valeurs = [
            json.dumps(valeur) if colonne in self._COLONNES_JSONB_JOB_GENERATION else valeur
            for colonne, valeur in champs.items()
        ]
        set_clause = sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(colonne))
            if colonne not in self._COLONNES_JSONB_JOB_GENERATION
            else sql.SQL("{} = %s::jsonb").format(sql.Identifier(colonne))
            for colonne in colonnes
        )
        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL("UPDATE {table} SET {set_clause} WHERE id = %s").format(
                    table=self._table("jobs_generation"), set_clause=set_clause
                ),
                (*valeurs, job_id),
            )
            connexion.commit()

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

        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL(
                    "UPDATE {} SET termine = TRUE, reussi = %s, id_solveur = %s, "
                    "nombre_tentatives = %s, erreur = %s, termine_le = %s WHERE id = %s"
                ).format(self._table("jobs_generation")),
                (reussi, id_solveur, nombre_tentatives, erreur, datetime.now(UTC).isoformat(), job_id),
            )
            connexion.commit()

    def recuperer_job_generation(self, job_id: str) -> JobGeneration:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL(
                    "SELECT id, instance_id, client_id, cree_le, termine, reussi, id_solveur, specification, "
                    "plan_technique, algorithme, algorithme_raison, algorithme_parametres, code_genere, "
                    "tests_generes, code_final, rapport_tests_sandbox, documentation, nombre_tentatives, "
                    "erreur, termine_le "
                    "FROM {} WHERE id = %s"
                ).format(self._table("jobs_generation")),
                (job_id,),
            ).fetchone()
            if ligne is None:
                raise KeyError(job_id)

            lignes_evenements = connexion.execute(
                sql.SQL("SELECT ordre, agent, statut, resume FROM {} WHERE job_id = %s ORDER BY ordre").format(
                    self._table("evenements_generation")
                ),
                (job_id,),
            ).fetchall()

            lignes_tentatives = connexion.execute(
                sql.SQL(
                    "SELECT numero, code_candidat, reussi, erreur_execution, revue_approuve, "
                    "revue_reponse_brute, revue_problemes, validation_statique_valide, "
                    "validation_statique_violations FROM {} WHERE job_id = %s ORDER BY numero"
                ).format(self._table("tentatives_generation")),
                (job_id,),
            ).fetchall()

        (
            id_,
            instance_id,
            client_id,
            cree_le,
            termine,
            reussi,
            id_solveur,
            specification,
            plan_technique,
            algorithme,
            algorithme_raison,
            algorithme_parametres,
            code_genere,
            tests_generes,
            code_final,
            rapport_tests_sandbox,
            documentation,
            nombre_tentatives,
            erreur,
            termine_le,
        ) = ligne

        return JobGeneration(
            id=id_,
            instance_id=instance_id,
            client_id=client_id,
            cree_le=cree_le,
            termine=termine,
            reussi=reussi,
            id_solveur=id_solveur,
            specification=specification,
            plan_technique=plan_technique,
            algorithme=algorithme,
            algorithme_raison=algorithme_raison,
            algorithme_parametres=algorithme_parametres,
            code_genere=code_genere,
            tests_generes=tests_generes,
            code_final=code_final,
            rapport_tests_sandbox=rapport_tests_sandbox,
            documentation=documentation,
            nombre_tentatives=nombre_tentatives,
            erreur=erreur,
            termine_le=termine_le,
            evenements=[
                EvenementGeneration(ordre=ordre, agent=agent, statut=statut, resume=resume)
                for ordre, agent, statut, resume in lignes_evenements
            ],
            tentatives=[
                TentativeGeneration(
                    numero=numero,
                    code_candidat=code_candidat,
                    reussi=reussi_tentative,
                    erreur_execution=erreur_execution,
                    revue_approuve=revue_approuve,
                    revue_reponse_brute=revue_reponse_brute,
                    revue_problemes=tuple(revue_problemes or []),
                    validation_statique_valide=validation_statique_valide,
                    validation_statique_violations=tuple(validation_statique_violations or []),
                )
                for (
                    numero,
                    code_candidat,
                    reussi_tentative,
                    erreur_execution,
                    revue_approuve,
                    revue_reponse_brute,
                    revue_problemes,
                    validation_statique_valide,
                    validation_statique_violations,
                ) in lignes_tentatives
            ],
        )

    def lister_jobs_generation_persistes(
        self, client_id: str | None = None, instance_id: str | None = None
    ) -> list[dict[str, object]]:
        requete = sql.SQL(
            "SELECT id, instance_id, client_id, cree_le, termine, reussi, id_solveur, nombre_tentatives, "
            "erreur, termine_le FROM {} WHERE 1 = 1"
        ).format(self._table("jobs_generation"))
        parametres: list[str] = []
        if client_id is not None:
            requete += sql.SQL(" AND client_id = %s")
            parametres.append(client_id)
        if instance_id is not None:
            requete += sql.SQL(" AND instance_id = %s")
            parametres.append(instance_id)
        requete += sql.SQL(" ORDER BY cree_le DESC")

        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(requete, parametres).fetchall()
        return [
            {
                "job_id": job_id,
                "instance_id": instance_id,
                "client_id": client_id,
                "cree_le": cree_le,
                "termine": termine,
                "reussi": reussi,
                "id_solveur": id_solveur,
                "nombre_tentatives": nombre_tentatives,
                "erreur": erreur,
                "termine_le": termine_le,
            }
            for (
                job_id,
                instance_id,
                client_id,
                cree_le,
                termine,
                reussi,
                id_solveur,
                nombre_tentatives,
                erreur,
                termine_le,
            ) in lignes
        ]

    def lister_evenements_generation(self, client_id: str | None = None) -> list[dict[str, object]]:
        """Tous les évènements de tous les jobs (filtrés par client), `job_id` explicite —
        matière première des KPI d'agrégat (page Analytique). `evenements_generation` n'a
        pas de colonne `client_id` propre : jointure sur `jobs_generation` pour filtrer."""
        requete = sql.SQL(
            "SELECT e.job_id, e.ordre, e.agent, e.statut FROM {} e JOIN {} j ON j.id = e.job_id WHERE 1 = 1"
        ).format(self._table("evenements_generation"), self._table("jobs_generation"))
        parametres: list[str] = []
        if client_id is not None:
            requete += sql.SQL(" AND j.client_id = %s")
            parametres.append(client_id)
        requete += sql.SQL(" ORDER BY e.job_id, e.ordre")

        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(requete, parametres).fetchall()
        return [
            {"job_id": job_id, "ordre": ordre, "agent": agent, "statut": statut}
            for job_id, ordre, agent, statut in lignes
        ]

    def lister_tentatives_generation(self, client_id: str | None = None) -> list[dict[str, object]]:
        """Toutes les tentatives de tous les jobs (filtrées par client) — seulement
        `code_candidat`, pour les KPI d'agrégat (détection de stagnation). Même jointure
        que `lister_evenements_generation` (`tentatives_generation` n'a pas non plus de
        colonne `client_id`)."""
        requete = sql.SQL(
            "SELECT t.job_id, t.numero, t.code_candidat FROM {} t JOIN {} j ON j.id = t.job_id WHERE 1 = 1"
        ).format(self._table("tentatives_generation"), self._table("jobs_generation"))
        parametres: list[str] = []
        if client_id is not None:
            requete += sql.SQL(" AND j.client_id = %s")
            parametres.append(client_id)
        requete += sql.SQL(" ORDER BY t.job_id, t.numero")

        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(requete, parametres).fetchall()
        return [
            {"job_id": job_id, "numero": numero, "code_candidat": code_candidat}
            for job_id, numero, code_candidat in lignes
        ]
