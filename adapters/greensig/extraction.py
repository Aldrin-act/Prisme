"""Extraction depuis la base GreenSIG réelle (service `db_greensig`, voir
`docker-compose.yml`) vers `PayloadGreenSIG` — la couche requête que
`schema_greensig.py` suppose déjà en place (§5.4) et que ce module fournit
enfin, une fois le dump réel disponible.

Connexion via `GREENSIG_DATABASE_URL` (voir `.env.example`) — jamais la même
base que `solver_store/registry.py` (`DATABASE_URL`) : un dump client réel,
volontairement isolé de la base applicative de PRISME.

Filtre en amont, côté SQL, ce qui n'a même pas vocation à devenir un
`PayloadGreenSIG` : seules les tâches encore à planifier
(`statut in STATUTS_A_PLANIFIER`) sont extraites — `TERMINEE`/`ANNULEE`
n'ont rien à faire dans une instance à ordonnancer. Le filtrage fin
(tâches supprimées, équipes inactives) reste dans `translator.traduire`,
inchangé.

Note sur `confirmee` : sur le dump `backup_20260503.sql`, cette colonne vaut
`false` pour les 2165 tâches sans exception — un filtre dessus viderait tout
le payload. Pas utilisée ici pour cette raison, pas parce qu'elle serait
dénuée de sens en général.
"""

from __future__ import annotations

import os
from collections import defaultdict
from contextlib import closing

import psycopg

from .schema_greensig import EquipeGreenSIG, PayloadGreenSIG, TacheGreenSIG, TypeTacheGreenSIG

STATUTS_A_PLANIFIER = ("PLANIFIEE", "EN_COURS")


def dsn_par_defaut() -> str:
    """`GREENSIG_DATABASE_URL` si défini ; sinon reconstruit depuis les
    variables `GREENSIG_DB_*` individuelles, hôte `localhost` et port `5433`
    par défaut (le port publié par `docker-compose.yml` pour un usage hors
    conteneur)."""
    url = os.environ.get("GREENSIG_DATABASE_URL")
    if url:
        return url
    mot_de_passe = os.environ.get("GREENSIG_DB_PASSWORD", "changeme")
    hote = os.environ.get("GREENSIG_DB_HOST", "localhost")
    port = os.environ.get("GREENSIG_DB_PORT", "5433")
    return f"postgresql://greensig:{mot_de_passe}@{hote}:{port}/greensig"


def extraire_payload(dsn: str | None = None) -> PayloadGreenSIG:
    """Interroge `db_greensig` et construit un `PayloadGreenSIG` : tâches
    encore à planifier, toutes les équipes, tous les types de tâche —
    `translator.traduire` se charge ensuite du filtrage fin et de la
    traduction vers `InstanceTRCO`."""
    with closing(psycopg.connect(dsn or dsn_par_defaut())) as connexion:
        equipes_par_tache: dict[int, list[int]] = defaultdict(list)
        for tache_id, equipe_id in connexion.execute(
            "SELECT tache_id, equipe_id FROM api_planification_tache_equipes"
        ).fetchall():
            equipes_par_tache[tache_id].append(equipe_id)

        taches = [
            TacheGreenSIG(
                id=id_,
                id_type_tache_id=id_type_tache_id,
                charge_estimee_heures=charge_estimee_heures,
                equipes_ids=equipes_par_tache.get(id_, []),
                deleted_at=deleted_at.isoformat() if deleted_at else None,
            )
            for id_, id_type_tache_id, charge_estimee_heures, deleted_at in connexion.execute(
                "SELECT id, id_type_tache_id, charge_estimee_heures, deleted_at "
                "FROM api_planification_tache WHERE statut = ANY(%s)",
                (list(STATUTS_A_PLANIFIER),),
            ).fetchall()
        ]

        equipes = [
            EquipeGreenSIG(id=id_, nom_equipe=nom_equipe, actif=actif)
            for id_, nom_equipe, actif in connexion.execute(
                "SELECT id, nom_equipe, actif FROM api_users_equipe"
            ).fetchall()
        ]

        types_tache = [
            TypeTacheGreenSIG(id=id_, nom_tache=nom_tache)
            for id_, nom_tache in connexion.execute(
                "SELECT id, nom_tache FROM api_planification_typetache"
            ).fetchall()
        ]

    return PayloadGreenSIG(taches=taches, equipes=equipes, types_tache=types_tache)
