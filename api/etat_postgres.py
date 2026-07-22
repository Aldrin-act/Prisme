"""Persistance Postgres de l'état de l'API (§5.2, §7 — extension proposée
dans le modèle conceptuel de données) : implémente exactement l'interface
publique d'`EtatAPI` (`api/etat.py`), mais en base plutôt qu'en mémoire —
c'est le remplacement que `EtatAPI` annonce lui-même dans son docstring
(« un déploiement réel remplacerait ceci par ... une base de données »).

Six tables, une par entité du modèle conceptuel :
`clients`, `instances_trco`, `executions`, `plannings`, `operations_planifiees`,
`decisions_humaines`. `instances_trco.payload` reste un blob JSONB (pas une
table par sous-type de `Contrainte`) : l'instance est déjà validée et typée
par Pydantic à l'ingestion (§6.7), la redécomposer en lignes SQL dupliquerait
une garantie déjà là, pour un bénéfice nul tant qu'aucune requête ne filtre
sur le détail d'une contrainte — même logique que pour le code figé dans
`solver_store/registry.py` (fichier sur disque, jamais éclaté en base).

Volontairement indépendant de `solver_store.registry.Registre` : aucune
clé étrangère de `executions.solveur_id` vers la table `solveurs` (schémas
potentiellement différents en test, et `solveurs.client_id` lui-même n'a pas
de contrainte de clé étrangère — même niveau de rigueur des deux côtés).

**Pas encore branché par défaut** : `api/dependencies.py`/`api/etat.py`
continuent de servir `EtatAPI` (mémoire) via `obtenir_etat()`. Pour utiliser
cette implémentation, substituer la dépendance FastAPI :
`app.dependency_overrides[obtenir_etat] = lambda: EtatPostgres()`.
"""

from __future__ import annotations

import json
import uuid
from contextlib import closing
from datetime import UTC, datetime

import psycopg
from psycopg import sql

from api.etat import Decision, DecisionHumaine, structure_contraintes
from dsl.schema import InstanceTRCO, OperationPlanifiee, Planning
from sandbox.runner import ResultatExecution
from solver_store.registry import SCHEMA_PAR_DEFAUT, dsn_par_defaut
from validation_engine.feasibility_checker import ResultatFaisabilite, Violation
from validation_engine.makespan import calculer_makespan


def _table(schema: str, nom: str) -> sql.Composed:
    return sql.Identifier(schema, nom)


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
                    "solveur_id TEXT NOT NULL, "
                    "date_execution TEXT NOT NULL, "
                    "statut TEXT NOT NULL, "
                    "erreur TEXT, "
                    "violations_faisabilite JSONB)"
                ).format(table=self._table("executions"), instances=self._table("instances_trco"))
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
            connexion.commit()

    def _connexion(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn)

    def _table(self, nom: str) -> sql.Composed:
        return _table(self._schema, nom)

    # --- Instances -----------------------------------------------------

    def enregistrer_instance(self, client_id: str, instance: InstanceTRCO) -> str:
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
                    "INSERT INTO {} (id, client_id, payload, structure_contraintes, date_ingestion) "
                    "VALUES (%s, %s, %s::jsonb, %s, %s)"
                ).format(self._table("instances_trco")),
                (
                    instance_id,
                    client_id,
                    instance.model_dump_json(),
                    structure,
                    datetime.now(UTC).isoformat(),
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

    def lister_instances(self) -> list[dict[str, object]]:
        """Vue de supervision (lecture seule) — équivalent SQL du repli
        Python de `EtatAPI.lister_instances` (jointure d'existence sur
        `executions` pour l'indicateur `executee`)."""
        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(
                sql.SQL(
                    "SELECT i.id, i.client_id, i.structure_contraintes, "
                    "EXISTS(SELECT 1 FROM {executions} e WHERE e.instance_id = i.id) AS executee "
                    "FROM {instances} i"
                ).format(executions=self._table("executions"), instances=self._table("instances_trco"))
            ).fetchall()
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

    def lister_executions(self) -> list[dict[str, object]]:
        with closing(self._connexion()) as connexion:
            lignes = connexion.execute(
                sql.SQL(
                    "SELECT e.id, e.solveur_id, e.instance_id, i.client_id, e.statut, e.erreur, d.decision "
                    "FROM {executions} e "
                    "JOIN {instances} i ON i.id = e.instance_id "
                    "LEFT JOIN {decisions} d ON d.execution_id = e.id"
                ).format(
                    executions=self._table("executions"),
                    instances=self._table("instances_trco"),
                    decisions=self._table("decisions_humaines"),
                )
            ).fetchall()
        return [
            {
                "execution_id": execution_id,
                "id_solveur": id_solveur,
                "instance_id": instance_id,
                "client_id": client_id,
                "reussi": statut == "reussi",
                "erreur": erreur,
                "decision": decision,
            }
            for execution_id, id_solveur, instance_id, client_id, statut, erreur, decision in lignes
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
