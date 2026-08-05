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

    def enregistrer_source(self, client_id: str, donnees_brutes: str, nom: str | None = None) -> str:
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
                (source_id, client_id, nom, donnees_brutes, datetime.now(UTC).isoformat()),
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
            id=id_, client_id=client_id, nom=nom, donnees_brutes=donnees_brutes, date_creation=date_creation
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

    # --- Instances -----------------------------------------------------

    def enregistrer_instance(
        self,
        client_id: str,
        instance: InstanceTRCO,
        source_id: str | None = None,
        description_metier: str | None = None,
    ) -> str:
        instance_id = str(uuid.uuid4())
        structure = structure_contraintes(instance)
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
                    "description_metier) "
                    "VALUES (%s, %s, %s::jsonb, %s, %s, %s, %s)"
                ).format(self._table("instances_trco")),
                (
                    instance_id,
                    client_id,
                    instance.model_dump_json(),
                    structure,
                    datetime.now(UTC).isoformat(),
                    source_id,
                    description_metier,
                ),
            )
            connexion.commit()
        return instance_id

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
                sql.SQL("UPDATE {} SET payload = %s::jsonb, structure_contraintes = %s WHERE id = %s").format(
                    self._table("instances_trco")
                ),
                (nouvelle_instance.model_dump_json(), structure_contraintes(nouvelle_instance), instance_id),
            )
            connexion.commit()
        return nouvelle_instance

    def supprimer_instance(self, instance_id: str) -> None:
        """Cascade-supprime son propre historique d'exécution (exécutions,
        plannings, opérations planifiées, décisions humaines associées) —
        une exécution n'existe jamais sans l'instance qui l'a produite. Le
        lien de provenance depuis `sources_donnees` (`ON DELETE SET NULL`)
        et depuis `jobs_generation` (même comportement, préserve l'audit de
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
            "EXISTS(SELECT 1 FROM {executions} e WHERE e.instance_id = i.id) AS executee "
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
                "instance_id": instance_id,
                "client_id": client_id,
                "structure_contraintes": structure,
                "executee": executee,
            }
            for instance_id, client_id, structure, executee in lignes
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
        with closing(self._connexion()) as connexion:
            connexion.execute(
                sql.SQL(
                    "UPDATE {} SET termine = TRUE, reussi = %s, id_solveur = %s, specification = %s, "
                    "plan_technique = %s, algorithme = %s, algorithme_raison = %s, "
                    "algorithme_parametres = %s::jsonb, code_genere = %s, tests_generes = %s, code_final = %s, "
                    "nombre_tentatives = %s, erreur = %s, termine_le = %s WHERE id = %s"
                ).format(self._table("jobs_generation")),
                (
                    reussi,
                    id_solveur,
                    specification,
                    plan_technique,
                    algorithme,
                    algorithme_raison,
                    json.dumps(algorithme_parametres) if algorithme_parametres is not None else None,
                    code_genere,
                    tests_generes,
                    code_final,
                    nombre_tentatives,
                    erreur,
                    datetime.now(UTC).isoformat(),
                    job_id,
                ),
            )
            connexion.commit()

    def recuperer_job_generation(self, job_id: str) -> JobGeneration:
        with closing(self._connexion()) as connexion:
            ligne = connexion.execute(
                sql.SQL(
                    "SELECT id, instance_id, client_id, cree_le, termine, reussi, id_solveur, specification, "
                    "plan_technique, algorithme, algorithme_raison, algorithme_parametres, code_genere, "
                    "tests_generes, code_final, nombre_tentatives, erreur, termine_le FROM {} WHERE id = %s"
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
