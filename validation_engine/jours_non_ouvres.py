"""Correction post-solveur : repousse toute opération qui chevaucherait un jour fermé
(`InstanceTRCO.jours_fermes`, samedi/dimanche par défaut, configurable via le formulaire
d'ingestion) — jamais au solveur généré d'apprendre à l'éviter par optimisation (voir
`sandbox/runner.py::executer_solveur_valide`, le seul appelant, juste avant `verifier_faisabilite`).

Écrit une seule fois, à la main, déterministe (Layer 1, même esprit que
`validation_engine/feasibility_checker.py`) — ne mute jamais le planning reçu, renvoie toujours un
nouveau `Planning`. `reference` (l'ancrage calendaire du jour 0) est résolu une seule fois par
l'appelant, jamais recalculé ici, pour rester testable — même idiome que
`adapters/greensig/translator_api.py::traduire_api(payload, date_reference)`.

Ne touche jamais aux opérations déjà gelées par un horizon de replanification
(`operations_gelees`, `debut < horizon_gele_jours`) : elles représentent un travail déjà réellement
engagé, les décaler violerait le contrat "generate once" du gel d'horizon.

Portée volontairement limitée aux jours de la semaine fermés (`jours_fermes`, samedi/dimanche par
défaut) et, en mode heures, aux heures hors de la plage ouvrée du jour (`heure_ouverture`/
`heure_fermeture`, 8h-22h par défaut) — une opération est continue, jamais coupée par la nuit : elle
commence à l'ouverture suivante si elle ne tient pas avant la fermeture. N'a rien à voir avec
`ContrainteDisponibiliteRessource` (mécanisme DSL séparé, opt-in, propre à chaque ressource,
inchangé par ce module).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

from dsl.schema import CompatibiliteRessourceTache, InstanceTRCO, OperationPlanifiee, Planning, Precedence

# `isoweekday() % 7` donne 0=dimanche..6=samedi — même convention que `InstanceTRCO.jours_fermes`
# et le formulaire d'ingestion (`Date.getDay()` JS), jamais celle de `datetime.weekday()` seul
# (0=lundi..6=dimanche) : ne jamais confondre les deux dans ce module.


def _est_bloque(
    instant: int,
    reference: datetime,
    unite_temps: str,
    jours_fermes: frozenset[int],
    heures_ouvrees: tuple[int, int] = (0, 24),
) -> bool:
    """Un jour fermé ou une heure hors plage ouvrée (mode heures seulement) est un fait calendaire
    global, valable identiquement pour toute ressource — contrairement à
    `ContrainteDisponibiliteRessource`, jamais propre à une ressource ici."""
    pas_heures = 24 if unite_temps == "jours" else 1
    moment = reference + timedelta(hours=instant * pas_heures)
    if moment.isoweekday() % 7 in jours_fermes:
        return True
    if unite_temps == "heures":
        ouverture, fermeture = heures_ouvrees
        return not (ouverture <= moment.hour < fermeture)
    return False


def _prochain_instant_libre(
    debut: int,
    duree: int,
    reference: datetime,
    unite_temps: str,
    jours_fermes: frozenset[int],
    heures_ouvrees: tuple[int, int] = (0, 24),
) -> int:
    """Plus petit `debut' >= debut` tel que `[debut', debut'+duree)` ne chevauche aucun instant
    bloqué — boucle pour gérer aussi bien un jour fermé isolé qu'une opération assez longue pour en
    chevaucher plusieurs d'affilée.

    Une opération dont la durée dépasse la plus longue plage continue de jours ouverts ne peut
    **par construction** jamais éviter tout instant bloqué, quel que soit son point de départ —
    pas une limite arbitraire, une conséquence mathématique d'un motif hebdomadaire périodique.
    Borne donc la recherche à un cycle complet (`longueur_cycle + 1` essais) : au-delà, aucun
    décalage supplémentaire ne peut aider (le motif se répète à l'identique), inutile de continuer
    à repousser indéfiniment — abandonne et renvoie le dernier `debut` essayé plutôt que de boucler
    sans fin (observé en conditions réelles : une opération de durée 10 jours provoquait une
    boucle de plusieurs millions d'itérations jusqu'à `OverflowError` sur l'arithmétique de
    dates)."""
    longueur_cycle = 168 if unite_temps == "heures" else 7
    debut_initial = debut
    for _ in range(longueur_cycle + 1):
        instants_bloques = [
            i
            for i in range(debut, debut + duree)
            if _est_bloque(i, reference, unite_temps, jours_fermes, heures_ouvrees)
        ]
        if not instants_bloques:
            return debut
        debut = max(instants_bloques) + 1
    # Aucune fenêtre assez longue : au moins commencer à un instant ouvert (jamais en pleine nuit).
    for i in range(debut_initial, debut_initial + longueur_cycle + 1):
        if not _est_bloque(i, reference, unite_temps, jours_fermes, heures_ouvrees):
            return i
    return debut


def repousser_hors_jours_non_ouvres(
    instance: InstanceTRCO,
    planning: Planning,
    reference: datetime,
    operations_gelees: frozenset[tuple[str, str]] = frozenset(),
) -> Planning:
    """Repousse en bloc (jamais ne réordonne, jamais ne comprime un écart déjà choisi par le
    solveur — voir docstring du module) toute opération dont l'intervalle chevaucherait un jour
    fermé (`instance.jours_fermes`). Sans effet si `jours_fermes` est vide, ou sur un planning qui
    ne touche jamais aucun de ces jours."""
    jours_fermes = frozenset(instance.jours_fermes)
    heures_ouvrees = (instance.heure_ouverture, instance.heure_fermeture)
    heures_restreintes = instance.unite_temps == "heures" and heures_ouvrees != (0, 24)
    if not jours_fermes and not heures_restreintes:
        return planning

    duree_par_couple: dict[tuple[str, str], int] = {
        (c.tache, c.ressource): c.duree for c in instance.contraintes if isinstance(c, CompatibiliteRessourceTache)
    }

    predecesseurs_par_tache: dict[str, list[str]] = defaultdict(list)
    for c in instance.contraintes:
        if isinstance(c, Precedence):
            predecesseurs_par_tache[c.apres].append(c.avant)

    operations_par_tache = {op.tache: op for op in planning.operations}

    def fin_originale(op: OperationPlanifiee) -> int:
        return op.debut + duree_par_couple.get((op.tache, op.ressource), 0)

    ordre = sorted(planning.operations, key=lambda op: (op.debut, op.tache))

    nouveau_debut: dict[str, int] = {}
    fin_ressource: dict[str, int] = {}
    derniere_op_ressource: dict[str, OperationPlanifiee] = {}

    for op in ordre:
        if (op.tache, op.ressource) in operations_gelees:
            nouveau_debut[op.tache] = op.debut
            fin_ressource[op.ressource] = fin_originale(op)
            derniere_op_ressource[op.ressource] = op
            continue

        duree = duree_par_couple.get((op.tache, op.ressource))
        if duree is None:
            # Ressource incompatible : déjà signalé ailleurs (incompatibilite_ressource_tache),
            # aucune durée connue pour ce couple — rien à décaler de façon fiable, laisse tel quel.
            nouveau_debut[op.tache] = op.debut
            continue

        plancher = op.debut
        op_precedente = derniere_op_ressource.get(op.ressource)
        if op_precedente is not None:
            gap_original = op.debut - fin_originale(op_precedente)
            plancher = max(plancher, fin_ressource[op.ressource] + gap_original)

        for tache_avant in predecesseurs_par_tache.get(op.tache, []):
            op_avant = operations_par_tache.get(tache_avant)
            if op_avant is None or tache_avant not in nouveau_debut:
                continue
            gap_original = op.debut - fin_originale(op_avant)
            duree_avant = duree_par_couple.get((tache_avant, op_avant.ressource), 0)
            fin_avant_decalee = nouveau_debut[tache_avant] + duree_avant
            plancher = max(plancher, fin_avant_decalee + gap_original)

        debut = _prochain_instant_libre(
            plancher, duree, reference, instance.unite_temps, jours_fermes, heures_ouvrees
        )
        nouveau_debut[op.tache] = debut
        fin_ressource[op.ressource] = debut + duree
        derniere_op_ressource[op.ressource] = op

    return Planning(
        operations=[
            OperationPlanifiee(tache=op.tache, ressource=op.ressource, debut=nouveau_debut.get(op.tache, op.debut))
            for op in planning.operations
        ]
    )
