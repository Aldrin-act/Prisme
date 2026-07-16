"""Traduction GreenSIG → T-R-C-O : couche anti-corruption pour cet ERP
(§5.4). Deux limites propres à ce schéma précis, pas au DSL :

- pas de précédence entre tâches (aucune colonne de ce type sur
  `api_planification_tache` — `chaine_report_id`/`ordre_dans_chaine`
  concernent les reports de distribution de charge, pas l'ordonnancement) ;
- pas de durée par couple (tâche, équipe) : GreenSIG ne stocke qu'une
  `charge_estimee_heures` par tâche, appliquée ici identiquement à chaque
  équipe compatible — une vraie modélisation FJSP demanderait une
  productivité par équipe, absente de ce schéma.

Un adaptateur pour un ERP plus riche pourrait fournir les deux.
"""

from __future__ import annotations

from dsl.schema import (
    CompatibiliteMachineTache,
    Contrainte,
    InstanceTRCO,
    MinimiserMakespan,
    Ressource,
    Tache,
)

from .schema_greensig import PayloadGreenSIG

_MINUTES_PAR_HEURE = 60
_DUREE_PAR_DEFAUT_MINUTES = 30  # tâche sans charge_estimee_heures renseignée


def _id_tache(id_brut: int) -> str:
    return f"T{id_brut}"


def _id_ressource(id_brut: int) -> str:
    return f"E{id_brut}"


def traduire(payload: PayloadGreenSIG) -> InstanceTRCO:
    """Traduit un extrait GreenSIG (tâches de planification + équipes) en instance T-R-C-O.

    Les tâches supprimées (`deleted_at` renseigné) et les équipes inactives
    (`actif=False`) sont exclues avant traduction — ni l'une ni l'autre
    n'existe côté canonique.
    """
    taches_actives = [t for t in payload.taches if t.deleted_at is None]
    equipes_actives = [e for e in payload.equipes if e.actif]

    taches = [Tache(id=_id_tache(t.id)) for t in taches_actives]
    ressources = [Ressource(id=_id_ressource(e.id)) for e in equipes_actives]
    ids_ressources_actives = {r.id for r in ressources}

    contraintes: list[Contrainte] = []
    for tache in taches_actives:
        duree_minutes = (
            round(tache.charge_estimee_heures * _MINUTES_PAR_HEURE)
            if tache.charge_estimee_heures
            else _DUREE_PAR_DEFAUT_MINUTES
        )
        for id_equipe in tache.equipes_ids:
            id_ressource = _id_ressource(id_equipe)
            if id_ressource not in ids_ressources_actives:
                continue  # équipe désaffectée ou hors payload : compatibilité ignorée
            contraintes.append(
                CompatibiliteMachineTache(tache=_id_tache(tache.id), ressource=id_ressource, duree=duree_minutes)
            )

    return InstanceTRCO(
        taches=taches,
        ressources=ressources,
        contraintes=contraintes,
        objectifs=[MinimiserMakespan()],
    )
