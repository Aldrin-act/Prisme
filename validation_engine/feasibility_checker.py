"""Vérificateur de faisabilité — le planning est-il légal ? (§6.2 brique 1, §6.7)

Écrit une seule fois, à la main, déterministe. Confronte une `InstanceTRCO` à
un `Planning` proposé et vérifie trois choses :

1. aucune précédence violée ;
2. aucune ressource occupée par deux tâches en même temps ;
3. aucune tâche affectée à une ressource incompatible.

Sert deux fois (§6.7, garde-fou déterministe) : hors ligne dans la validation
du code généré (couche 2, §6.1), et en ligne comme garde-fou de production
sur le planning réellement produit. Dans les deux usages, un appel a besoin
d'un verdict exploitable, jamais d'une exception — `verifier_faisabilite` ne
lève donc rien : toute anomalie, y compris structurelle (tâche non
planifiée, planifiée deux fois, référence inconnue), devient une entrée de
`ResultatFaisabilite.violations`.

Règle de compatibilité ressource-tâche (à garder synchronisée avec tout
solveur CP-SAT du dépôt, ex. `scripts/_solveur_minimal.py`) :
`CompatibiliteRessourceTache` est obligatoire — une tâche sans aucune n'est
pas rejetée ici (ce garde-fou-là
vit dans `InstanceTRCO`, §6.7), mais la contrainte porte aussi la durée
propre à ce couple (tâche, ressource), utilisée ci-dessous pour les calculs
de fin d'opération.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from dsl.schema import (
    CompatibiliteRessourceTache,
    Echeance,
    InstanceTRCO,
    OperationPlanifiee,
    Planning,
    Precedence,
)

TypeViolation = Literal[
    "tache_inconnue_dans_planning",
    "ressource_inconnue_dans_planning",
    "tache_non_planifiee",
    "tache_planifiee_plusieurs_fois",
    "precedence_violee",
    "incompatibilite_ressource_tache",
    "chevauchement_ressource",
    "echeance_depassee",
]


@dataclass(frozen=True)
class Violation:
    """Une anomalie diagnostiquée : son type, un message lisible, le contexte."""

    type: TypeViolation
    message: str
    tache: str | None = None
    ressource: str | None = None
    tache_secondaire: str | None = None


@dataclass(frozen=True)
class ResultatFaisabilite:
    """Le verdict : légal si et seulement si aucune violation n'a été relevée."""

    violations: tuple[Violation, ...]

    @property
    def legal(self) -> bool:
        return not self.violations


def verifier_faisabilite(instance: InstanceTRCO, planning: Planning) -> ResultatFaisabilite:
    violations: list[Violation] = []

    taches_par_id = {t.id: t for t in instance.taches}
    ressources_connues = {r.id for r in instance.ressources}

    operations_par_tache: dict[str, list[OperationPlanifiee]] = defaultdict(list)
    for operation in planning.operations:
        operations_par_tache[operation.tache].append(operation)

    for operation in planning.operations:
        if operation.tache not in taches_par_id:
            violations.append(
                Violation(
                    "tache_inconnue_dans_planning",
                    f"planning référence une tâche inconnue : {operation.tache!r}",
                    tache=operation.tache,
                )
            )
        if operation.ressource not in ressources_connues:
            violations.append(
                Violation(
                    "ressource_inconnue_dans_planning",
                    f"planning référence une ressource inconnue : {operation.ressource!r}",
                    ressource=operation.ressource,
                )
            )

    for tache_id in taches_par_id:
        occurrences = operations_par_tache.get(tache_id, [])
        if not occurrences:
            violations.append(
                Violation(
                    "tache_non_planifiee",
                    f"tâche non planifiée : {tache_id!r}",
                    tache=tache_id,
                )
            )
        elif len(occurrences) > 1:
            violations.append(
                Violation(
                    "tache_planifiee_plusieurs_fois",
                    f"tâche planifiée plusieurs fois : {tache_id!r}",
                    tache=tache_id,
                )
            )

    # Au-delà des anomalies structurelles ci-dessus, les vérifications de
    # légalité (précédence, compatibilité, chevauchement) ne portent que sur
    # les tâches proprement planifiées : connues, planifiées une seule fois,
    # sur une ressource elle aussi connue. Le reste est déjà signalé.
    operations_valides: dict[str, OperationPlanifiee] = {}
    for tache_id, occurrences in operations_par_tache.items():
        if tache_id not in taches_par_id or len(occurrences) != 1:
            continue
        (operation,) = occurrences
        if operation.ressource not in ressources_connues:
            continue
        operations_valides[tache_id] = operation

    ressources_autorisees: dict[str, set[str]] = defaultdict(set)
    duree_par_couple: dict[tuple[str, str], int] = {}
    for contrainte in instance.contraintes:
        if isinstance(contrainte, CompatibiliteRessourceTache):
            ressources_autorisees[contrainte.tache].add(contrainte.ressource)
            duree_par_couple[(contrainte.tache, contrainte.ressource)] = contrainte.duree

    for contrainte in instance.contraintes:
        if not isinstance(contrainte, Precedence):
            continue
        operation_avant = operations_valides.get(contrainte.avant)
        operation_apres = operations_valides.get(contrainte.apres)
        if operation_avant is None or operation_apres is None:
            continue
        duree_avant = duree_par_couple.get((contrainte.avant, operation_avant.ressource))
        if duree_avant is None:
            # Ressource incompatible : déjà signalé séparément ci-dessous
            # (incompatibilite_ressource_tache), aucune durée connue pour ce
            # couple précis, donc pas de vérification de fin possible ici.
            continue
        fin_avant = operation_avant.debut + duree_avant
        if fin_avant > operation_apres.debut:
            violations.append(
                Violation(
                    "precedence_violee",
                    f"précédence violée : {contrainte.avant!r} doit finir avant le début de {contrainte.apres!r}",
                    tache=contrainte.avant,
                    tache_secondaire=contrainte.apres,
                )
            )

    for contrainte in instance.contraintes:
        if not isinstance(contrainte, Echeance):
            continue
        operation = operations_valides.get(contrainte.tache)
        if operation is None:
            continue
        duree = duree_par_couple.get((contrainte.tache, operation.ressource))
        if duree is None:
            # Ressource incompatible : déjà signalé séparément (incompatibilite_ressource_tache),
            # aucune durée connue pour ce couple, donc pas de vérification d'échéance possible ici.
            continue
        fin = operation.debut + duree
        if fin > contrainte.echeance:
            violations.append(
                Violation(
                    "echeance_depassee",
                    f"échéance dépassée : {contrainte.tache!r} finit à {fin} au lieu de {contrainte.echeance}",
                    tache=contrainte.tache,
                )
            )

    for tache_id, operation in operations_valides.items():
        restrictions = ressources_autorisees.get(tache_id)
        if restrictions and operation.ressource not in restrictions:
            violations.append(
                Violation(
                    "incompatibilite_ressource_tache",
                    f"tâche {tache_id!r} affectée à une ressource incompatible : {operation.ressource!r}",
                    tache=tache_id,
                    ressource=operation.ressource,
                )
            )

    operations_par_ressource: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for tache_id, operation in operations_valides.items():
        duree_operation = duree_par_couple.get((tache_id, operation.ressource))
        if duree_operation is None:
            # Ressource incompatible : déjà signalé séparément ci-dessus, pas
            # de durée connue pour ce couple, donc pas de chevauchement calculable.
            continue
        fin = operation.debut + duree_operation
        operations_par_ressource[operation.ressource].append((tache_id, operation.debut, fin))

    for ressource_id, intervalles in operations_par_ressource.items():
        intervalles_tries = sorted(intervalles, key=lambda intervalle: intervalle[1])
        for (tache_a, _debut_a, fin_a), (tache_b, debut_b, _fin_b) in zip(
            intervalles_tries, intervalles_tries[1:]
        ):
            if debut_b < fin_a:
                violations.append(
                    Violation(
                        "chevauchement_ressource",
                        f"ressource {ressource_id!r} occupée deux fois : "
                        f"{tache_a!r} et {tache_b!r} se chevauchent",
                        ressource=ressource_id,
                        tache=tache_a,
                        tache_secondaire=tache_b,
                    )
                )

    return ResultatFaisabilite(tuple(violations))
