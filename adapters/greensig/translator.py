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

Compatibilité tâche-ressource : dérivée de la compétence réelle (quelle
équipe a un opérateur qualifié pour ce type de tâche, `mapping/
competences_types_tache.py`) quand ce type est mappé — jamais de
l'affectation historique dans ce cas, même si une équipe non qualifiée a été
affectée par le passé (voir `mapping/regles.md`). Pour un type de tâche non
mappé (la majorité, faute de correspondance connue), on retombe sur
l'affectation historique (`equipes_ids`), comportement inchangé.
"""

from __future__ import annotations

from dsl.schema import (
    CompatibiliteRessourceTache,
    Contrainte,
    InstanceTRCO,
    MinimiserMakespan,
    Ressource,
    Tache,
)

from .mapping.competences_types_tache import COMPETENCES_PAR_TYPE_TACHE
from .schema_greensig import OperateurGreenSIG, PayloadGreenSIG, TacheGreenSIG

_MINUTES_PAR_HEURE = 60
_DUREE_PAR_DEFAUT_MINUTES = 30  # tâche sans charge_estimee_heures renseignée
_DUREE_MINIMALE_MINUTES = 1  # `CompatibiliteRessourceTache.duree` exige > 0 ; jamais 0 par arrondi


def id_tache(id_brut: int) -> str:
    return f"T{id_brut}"


def id_ressource(id_brut: int) -> str:
    return f"E{id_brut}"


def duree_minutes_pour(charge_estimee_heures: float | None) -> int:
    """La règle de conversion durée exacte utilisée par `traduire` — publique
    pour que d'autres outils (ex. `scripts/rapport_greensig_dsl.py`) puissent
    reproduire le même calcul sans dupliquer la logique.

    Sur données réelles (voir `tests/integration/test_greensig_extraction.py`),
    une charge non nulle mais minuscule (ex. 0.0006h, quelques secondes)
    arrondirait à 0 minute — `max(..., _DUREE_MINIMALE_MINUTES)` l'empêche
    sans pour autant gonfler ces tâches au défaut de 30 min (qui ne vaut que
    pour une charge réellement absente)."""
    if not charge_estimee_heures:
        return _DUREE_PAR_DEFAUT_MINUTES
    return max(round(charge_estimee_heures * _MINUTES_PAR_HEURE), _DUREE_MINIMALE_MINUTES)


def equipes_competentes_pour(
    id_type_tache: int, operateurs: list[OperateurGreenSIG], ids_ressources_actives: set[str]
) -> set[str] | None:
    """Équipes actives ayant ≥1 opérateur qualifié pour ce type de tâche
    d'après `COMPETENCES_PAR_TYPE_TACHE` — `None` si ce type de tâche n'a pas
    de correspondance connue, signal pour `traduire` de retomber sur
    l'affectation historique (`TacheGreenSIG.equipes_ids`)."""
    competences_requises = COMPETENCES_PAR_TYPE_TACHE.get(id_type_tache)
    if competences_requises is None:
        return None
    equipes: set[str] = set()
    for operateur in operateurs:
        if operateur.equipe_id is None:
            continue
        id_ress = id_ressource(operateur.equipe_id)
        if id_ress in ids_ressources_actives and not competences_requises.isdisjoint(operateur.competences_ids):
            equipes.add(id_ress)
    return equipes


def equipes_compatibles_pour(
    tache: TacheGreenSIG, operateurs: list[OperateurGreenSIG], ids_ressources_actives: set[str]
) -> set[str]:
    """Équipes compatibles avec cette tâche — compétence si le type est mappé,
    sinon affectation historique. Publique : réutilisée par
    `scripts/rapport_greensig_dsl.py` pour ne pas dupliquer la règle de
    dérivation (même motif que `duree_minutes_pour`)."""
    equipes_par_competence = equipes_competentes_pour(tache.id_type_tache_id, operateurs, ids_ressources_actives)
    if equipes_par_competence is not None:
        return equipes_par_competence
    return {id_ressource(id_equipe) for id_equipe in tache.equipes_ids} & ids_ressources_actives


def traduire(payload: PayloadGreenSIG) -> InstanceTRCO:
    """Traduit un extrait GreenSIG (tâches de planification + équipes) en instance T-R-C-O.

    Les tâches supprimées (`deleted_at` renseigné) et les équipes inactives
    (`actif=False`) sont exclues avant traduction — ni l'une ni l'autre
    n'existe côté canonique. La compatibilité tâche-ressource privilégie la
    compétence réelle sur l'affectation historique quand le type de tâche
    est mappé (voir `equipes_competentes_pour`) ; sinon, comportement
    inchangé (affectation historique).
    """
    taches_actives = [t for t in payload.taches if t.deleted_at is None]
    equipes_actives = [e for e in payload.equipes if e.actif]

    taches = [Tache(id=id_tache(t.id)) for t in taches_actives]
    ressources = [Ressource(id=id_ressource(e.id)) for e in equipes_actives]
    ids_ressources_actives = {r.id for r in ressources}

    contraintes: list[Contrainte] = []
    for tache in taches_actives:
        duree_minutes = duree_minutes_pour(tache.charge_estimee_heures)
        for id_ress in equipes_compatibles_pour(tache, payload.operateurs, ids_ressources_actives):
            contraintes.append(
                CompatibiliteRessourceTache(tache=id_tache(tache.id), ressource=id_ress, duree=duree_minutes)
            )

    return InstanceTRCO(
        taches=taches,
        ressources=ressources,
        contraintes=contraintes,
        objectifs=[MinimiserMakespan()],
    )
