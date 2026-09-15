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
from api.unite_duree import detecter_unite_duree
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
        commande_id,
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
        commande_id=commande_id,
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
            # Migration idempotente : secteur d'activité (fonctionnalité
            # retirée, comme nom_projet/secteur_activite sur instances_trco
            # ci-dessous) — n'oriente plus le prompt de l'agent de
            # compréhension.
            connexion.execute(
                sql.SQL("ALTER TABLE {table} DROP COLUMN IF EXISTS secteur_activite").format(
                    table=self._table("sources_donnees")
                )
            )
            # Migration idempotente : `unite_duree` choisie à la main n'a plus
            # de sens sur une source (données brutes, pas encore de durées
            # analysables) depuis que l'unité d'affichage est calculée par
            # instance à partir de ses propres contraintes (voir
            # `api/unite_duree.py::detecter_unite_duree`, colonne équivalente
            # sur `instances_trco` ci-dessous, conservée).
            connexion.execute(
                sql.SQL("ALTER TABLE {table} DROP COLUMN IF EXISTS unite_duree").format(
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
            # Migration idempotente : durée globale prévue pour la commande, saisie librement par
            # l'utilisateur (heures) — pure métadonnée de traçabilité comme le reste de Commande
            # (voir sa docstring dans api/etat.py) : jamais dérivée en Echeance, jamais lue par le
            # DSL/solveur, affichée telle quelle.
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ADD COLUMN IF NOT EXISTS duree_heures INTEGER").format(
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
            # Migrations idempotentes : nom_projet/secteur_activite
            # (étiquette libre de regroupement + secteur d'activité déclaré)
            # — fonctionnalités retirées, n'ont plus de sens.
            connexion.execute(
                sql.SQL("ALTER TABLE {table} DROP COLUMN IF EXISTS nom_projet").format(
                    table=self._table("instances_trco")
                )
            )
            connexion.execute(
                sql.SQL("ALTER TABLE {table} DROP COLUMN IF EXISTS secteur_activite").format(
                    table=self._table("instances_trco")
                )
            )
            # Migration idempotente : unité d'affichage des durées/échéances
            # ("jours" implicite si NULL, "semaines", "mois") — purement
            # cosmétique, jamais lue par le DSL/solveur/faisabilité, calculée
            # une fois à `enregistrer_instance` à partir des durées réelles de
            # l'instance (voir `api/unite_duree.py::detecter_unite_duree`).
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
            # Migration idempotente : canal d'ingestion ayant produit cette instance
            # ("manuel", "csv", "json", "api", "agent_ia", "scenario") — purement
            # informatif côté affichage (page Instances), jamais lu par le solveur ni la
            # validation. NULL pour toute instance enregistrée avant l'ajout de ce champ.
            connexion.execute(
                sql.SQL("ALTER TABLE {table} ADD COLUMN IF NOT EXISTS canal_ingestion TEXT").format(
                    table=self._table("instances_trco")
                )
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
            # Migration idempotente : signal "commande en retard" (détecté sans LLM, voir
            # supervision/detecteurs.py::detecter_commandes_en_retard) — distingue plusieurs
            # commandes en retard sur une même instance, jamais renseigné pour les trois autres
            # signaux. Même politique ON DELETE SET NULL que instance_id ci-dessus : supprimer
            # une commande ne doit jamais faire disparaître une proposition déjà persistée.
            connexion.execute(
                sql.SQL(
                    "ALTER TABLE {table} ADD COLUMN IF NOT EXISTS commande_id TEXT "
                    "REFERENCES {commandes}(id) ON DELETE SET NULL"
                ).format(table=self._table("propositions_supervision"), commandes=self._table("commandes"))
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
                    "INSERT INTO {} (id, client_id, nom, donnees_brutes, date_creation) "
                    "VALUES (%s, %s, %s, %s, %s)"
                ).format(self._table("sources_donnees")),
                (
                    source_id,
                    client_id,
                    nom,
                    donnees_brutes,
                    datetime.now(UTC).isoformat(),
                ),
            )
            connexion.commit()
        return source_id

    def recuperer_source(self, source_id: str) -> SourceDonnees:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT id, client_id, nom, donnees_brutes, date_creation FROM {} WHERE id = %s").format(
                    self._table("sources_donnees")
                ),
                (source_id,),
            ).fetchone()
        if ligne is None:
            raise KeyError(source_id)
        id_, client_id, nom, donnees_brutes, date_creation = ligne
        return SourceDonnees(
            id=id_,
            client_id=client_id,
            nom=nom,
            donnees_brutes=donnees_brutes,
            date_creation=date_creation,
        )

    def lister_sources(self, client_id: str | None = None) -> list[dict[str, object]]:
        """`client_id=None` ne filtre rien (réservé à l'admin — voir
        `api/autorisation.py`)."""
        requete = sql.SQL(
            "SELECT s.id, s.client_id, s.nom, s.date_creation, "
            "(SELECT COUNT(*) FROM {instances} i WHERE i.source_id = s.id) AS nb_instances "
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
            }
            for id_, client_id, nom, date_creation, nb in lignes
        ]

    def lister_instances_pour_source(self, source_id: str) -> list[dict[str, object]]:
        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(
                sql.SQL(
                    "SELECT id, structure_contraintes FROM {} WHERE source_id = %s ORDER BY date_ingestion DESC"
                ).format(self._table("instances_trco")),
                (source_id,),
            ).fetchall()
        return [{"instance_id": id_, "structure_contraintes": structure} for id_, structure in lignes]

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
        duree_heures: int | None = None,
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
                    "INSERT INTO {} (id, instance_id, client_id, date_limite, taches, date_creation, "
                    "duree_heures) VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)"
                ).format(self._table("commandes")),
                (
                    commande_id,
                    instance_id,
                    client_id,
                    date_limite,
                    json.dumps(list(taches)),
                    datetime.now(UTC).isoformat(),
                    duree_heures,
                ),
            )
            connexion.commit()

    def recuperer_commande(self, commande_id: str) -> CommandeEnregistree:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL(
                    "SELECT id, instance_id, client_id, date_limite, taches, date_creation, duree_heures "
                    "FROM {} WHERE id = %s"
                ).format(self._table("commandes")),
                (commande_id,),
            ).fetchone()
        if ligne is None:
            raise KeyError(commande_id)
        id_, instance_id, client_id, date_limite, taches, date_creation, duree_heures = ligne
        return CommandeEnregistree(
            id=id_,
            instance_id=instance_id,
            client_id=client_id,
            date_limite=date_limite,
            taches=tuple(taches),
            date_creation=date_creation,
            duree_heures=duree_heures,
        )

    def lister_commandes(self, instance_id: str | None = None) -> list[CommandeEnregistree]:
        requete = sql.SQL(
            "SELECT id, instance_id, client_id, date_limite, taches, date_creation, duree_heures "
            "FROM {} WHERE 1 = 1"
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
                duree_heures=duree_heures,
            )
            for id_, iid, cid, date_limite, taches, date_creation, duree_heures in lignes
        ]

    # --- Instances -----------------------------------------------------

    def enregistrer_instance(
        self,
        client_id: str,
        instance: InstanceTRCO,
        source_id: str | None = None,
        description_metier: str | None = None,
        groupe_scenario_id: str | None = None,
        canal_ingestion: str | None = None,
    ) -> str:
        instance_id = str(uuid.uuid4())
        structure = structure_contraintes(instance)
        maintenant = datetime.now(UTC).isoformat()
        unite_duree = detecter_unite_duree(instance)
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
                    "description_metier, unite_duree, date_modification, groupe_scenario_id, canal_ingestion) "
                    "VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s)"
                ).format(self._table("instances_trco")),
                (
                    instance_id,
                    client_id,
                    instance.model_dump_json(),
                    structure,
                    maintenant,
                    source_id,
                    description_metier,
                    unite_duree,
                    maintenant,
                    groupe_scenario_id,
                    canal_ingestion,
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

    def racine_groupe_scenario(self, instance_id: str) -> str:
        """Voir `EtatAPI.racine_groupe_scenario` (même contrat) — lève `KeyError` si
        `instance_id` est inconnue, contrairement à `lister_instances_du_groupe_scenario`
        qui renvoie silencieusement `[]` (ses appelants valident déjà l'existence en amont,
        voir `comparer_scenarios`)."""
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT groupe_scenario_id FROM {} WHERE id = %s").format(self._table("instances_trco")),
                (instance_id,),
            ).fetchone()
        if ligne is None:
            raise KeyError(instance_id)
        return ligne[0] or instance_id

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

    def recuperer_unite_duree(self, instance_id: str) -> str | None:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT unite_duree FROM {} WHERE id = %s").format(self._table("instances_trco")),
                (instance_id,),
            ).fetchone()
        if ligne is None:
            raise KeyError(instance_id)
        return ligne[0]

    def recuperer_canal_ingestion(self, instance_id: str) -> str | None:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT canal_ingestion FROM {} WHERE id = %s").format(self._table("instances_trco")),
                (instance_id,),
            ).fetchone()
        if ligne is None:
            raise KeyError(instance_id)
        return ligne[0]

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

    def modifier_instance(self, instance_id: str, instance: InstanceTRCO) -> InstanceTRCO:
        with closing(self._connexion()) as connexion:
            existe = connexion.execute(
                sql.SQL("SELECT 1 FROM {} WHERE id = %s").format(self._table("instances_trco")),
                (instance_id,),
            ).fetchone()
            if existe is None:
                raise KeyError(instance_id)
            connexion.execute(
                sql.SQL(
                    "UPDATE {} SET payload = %s::jsonb, structure_contraintes = %s, "
                    "date_modification = %s WHERE id = %s"
                ).format(self._table("instances_trco")),
                (
                    instance.model_dump_json(),
                    structure_contraintes(instance),
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

    def lister_instances(self, client_id: str | None = None) -> list[dict[str, object]]:
        """Vue de supervision (lecture seule) — équivalent SQL du repli
        Python de `EtatAPI.lister_instances` (jointure d'existence sur
        `executions` pour l'indicateur `executee`). `client_id=None` ne
        filtre rien (réservé à l'admin — voir `api/autorisation.py`)."""
        requete = sql.SQL(
            "SELECT i.id, i.client_id, i.structure_contraintes, "
            "EXISTS(SELECT 1 FROM {executions} e WHERE e.instance_id = i.id) AS executee, "
            "i.unite_duree, i.date_modification, i.canal_ingestion "
            "FROM {instances} i WHERE 1 = 1"
        ).format(executions=self._table("executions"), instances=self._table("instances_trco"))
        parametres: list[str] = []
        if client_id is not None:
            requete += sql.SQL(" AND i.client_id = %s")
            parametres.append(client_id)

        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(requete, parametres).fetchall()
        return [
            {
                "instance_id": ligne[0],
                "client_id": ligne[1],
                "structure_contraintes": ligne[2],
                "executee": ligne[3],
                "unite_duree": ligne[4],
                "date_modification": ligne[5],
                "canal_ingestion": ligne[6],
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

    def recuperer_date_execution(self, execution_id: str) -> str:
        """Voir `EtatAPI.recuperer_date_execution` (même contrat, même usage : ancrage
        calendaire stable du Gantt)."""
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL("SELECT date_execution FROM {} WHERE id = %s").format(self._table("executions")),
                (execution_id,),
            ).fetchone()
        if ligne is None:
            raise KeyError(execution_id)
        return ligne[0]

    def date_derniere_execution_reussie(self, instance_id: str) -> str | None:
        """Voir `EtatAPI.date_derniere_execution_reussie` (même contrat) — requête indépendante
        de `dernier_planning_pour_instance` ci-dessous plutôt qu'une valeur de retour partagée :
        pas de jointure sur `plannings` nécessaire pour cette seule date."""
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL(
                    "SELECT date_execution FROM {} WHERE instance_id = %s AND statut = 'reussi' "
                    "ORDER BY date_execution DESC LIMIT 1"
                ).format(self._table("executions")),
                (instance_id,),
            ).fetchone()
        return ligne[0] if ligne else None

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
        commande_id: str | None = None,
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
                    "instance_id, execution_ids, structure_contraintes, signature_objectifs, commande_id) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, %s, %s, %s)"
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
                    commande_id,
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
                    "decision, horodatage_decision, commentaire, commande_id FROM {} WHERE id = %s"
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
            "decision, horodatage_decision, commentaire, commande_id FROM {} WHERE 1 = 1"
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
                "commande_id": p.commande_id,
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
