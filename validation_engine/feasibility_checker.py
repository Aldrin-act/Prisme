"""Vérificateur de faisabilité — le planning est-il légal ? (§6.2 brique 1, §6.7)

Écrit une seule fois, à la main, déterministe. Confronte une `InstanceTRCO` à
un `Planning` proposé et vérifie :

1. aucune précédence violée ;
2. aucune ressource occupée au-delà de sa capacité (1 par défaut, ou celle
   déclarée par `ContrainteCapacite` — extension optionnelle, §4.2) ;
3. aucune tâche affectée à une ressource incompatible ;
4. aucune paire de tâches déclarées incompatibles (`ContrainteIncompatibilite`)
   affectée à la même ressource, quelle que soit l'heure ;
5. aucune opération planifiée un jour où sa ressource est déclarée
   indisponible (`ContrainteDisponibiliteRessource` — extension optionnelle,
   §4.2 ; jours explicites et/ou motif récurrent hebdomadaire, les deux se
   combinent) ;
6. tout temps de changement de série (`ContrainteChangementSerie` — extension
   optionnelle, §4.2) respecté entre deux opérations directement consécutives
   sur une même ressource, sans effet si la paire déclarée ne se retrouve pas
   consécutive dans le planning proposé ;
7. aucun matériau dont le stock (`DeclarationMateriau.stock_initial` —
   extension optionnelle, §4.2) passe sous zéro au fil du planning — seule
   vérification **chronologique/stateful** du module (les six précédentes
   sont toutes locales, pairwise ou des agrégats statiques) : simule un
   stock qui décroît opération par opération, triées par `debut`, sans
   jamais se reconstituer (pas de réapprovisionnement dans ce v1, sans effet
   sur une instance sans `DeclarationMateriau`/`ConsommationMatiere`).

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
    ConsommationMatiere,
    ContrainteCapacite,
    ContrainteChangementSerie,
    ContrainteDisponibiliteRessource,
    ContrainteIncompatibilite,
    ContrainteTailleLot,
    DeclarationMateriau,
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
    "capacite_depassee",
    "incompatibilite_taches_violee",
    "ressource_indisponible",
    "taille_lot_hors_bornes",
    "changement_serie_insuffisant",
    "stock_insuffisant",
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

    # Validation statique de Tache.quantite contre les bornes déclarées — ne dépend ni du
    # planning ni des précalculs ci-dessus (contrairement à Echeance) : une donnée d'entrée,
    # jamais une décision d'ordonnancement. Rien à vérifier si quantite n'est pas renseignée.
    for contrainte in instance.contraintes:
        if not isinstance(contrainte, ContrainteTailleLot):
            continue
        tache = taches_par_id.get(contrainte.tache)
        if tache is None or tache.quantite is None:
            continue
        if not (contrainte.lot_min <= tache.quantite <= contrainte.lot_max):
            violations.append(
                Violation(
                    "taille_lot_hors_bornes",
                    f"quantité hors bornes : {contrainte.tache!r} produit {tache.quantite} "
                    f"unité(s), attendu entre {contrainte.lot_min} et {contrainte.lot_max}",
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

    capacite_par_ressource: dict[str, int] = {
        contrainte.ressource: contrainte.capacite
        for contrainte in instance.contraintes
        if isinstance(contrainte, ContrainteCapacite)
    }

    for ressource_id, intervalles in operations_par_ressource.items():
        capacite = capacite_par_ressource.get(ressource_id, 1)
        if capacite == 1:
            # Comportement historique inchangé (pas de ContrainteCapacite pour
            # cette ressource) : deux opérations ne peuvent jamais se chevaucher.
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
            continue

        # Capacité > 1 (`ContrainteCapacite`) : jusqu'à `capacite` opérations
        # peuvent se chevaucher simultanément — balayage des évènements
        # (début, +1)/(fin, -1) triés par instant, une fin traitée avant un
        # début au même instant (intervalle [debut, fin[ semi-ouvert, comme
        # le chevauchement à capacité 1 ci-dessus : `fin == debut` n'est
        # jamais un chevauchement).
        evenements: list[tuple[int, int, str]] = []
        for tache_id, debut, fin in intervalles:
            evenements.append((debut, 1, tache_id))
            evenements.append((fin, 0, tache_id))
        evenements.sort(key=lambda evenement: (evenement[0], evenement[1]))

        actives: set[str] = set()
        for instant, type_evenement, tache_id in evenements:
            if type_evenement == 0:
                actives.discard(tache_id)
                continue
            actives.add(tache_id)
            if len(actives) > capacite:
                violations.append(
                    Violation(
                        "capacite_depassee",
                        f"capacité de la ressource {ressource_id!r} dépassée à l'instant {instant} : "
                        f"{len(actives)} tâches simultanées {sorted(actives)!r} pour une capacité de {capacite}",
                        ressource=ressource_id,
                        tache=tache_id,
                    )
                )

    # Temps de changement de série : ne porte que sur des paires directement consécutives sur
    # une même ressource (triée par debut) — sans effet si tache_avant/tache_apres ne se
    # retrouvent jamais adjacentes dans le planning proposé (ContrainteChangementSerie n'impose
    # aucun ordre entre elles, seulement un coût *si* le solveur les enchaîne ainsi).
    setups_par_ressource: dict[str, dict[tuple[str, str], int]] = defaultdict(dict)
    for contrainte in instance.contraintes:
        if isinstance(contrainte, ContrainteChangementSerie):
            setups_par_ressource[contrainte.ressource][(contrainte.tache_avant, contrainte.tache_apres)] = (
                contrainte.duree_setup
            )

    for ressource_id, setups in setups_par_ressource.items():
        intervalles_tries = sorted(operations_par_ressource.get(ressource_id, []), key=lambda i: i[1])
        for (tache_a, _debut_a, fin_a), (tache_b, debut_b, _fin_b) in zip(
            intervalles_tries, intervalles_tries[1:]
        ):
            duree_setup = setups.get((tache_a, tache_b))
            if duree_setup is None:
                continue
            ecart = debut_b - fin_a
            if ecart < duree_setup:
                violations.append(
                    Violation(
                        "changement_serie_insuffisant",
                        f"changement de série insuffisant sur {ressource_id!r} entre {tache_a!r} et "
                        f"{tache_b!r} : {ecart} jour(s) laissé(s), {duree_setup} requis",
                        tache=tache_a,
                        tache_secondaire=tache_b,
                        ressource=ressource_id,
                    )
                )

    # `.update(...)`, jamais un remplacement : plusieurs `ContrainteDisponibiliteRessource`
    # pour la même ressource se combinent (jours explicites + motif récurrent, ou plusieurs
    # contraintes distinctes déclarées pour la même ressource), même principe que plusieurs
    # `CompatibiliteRessourceTache` pour une même tâche (§4.2) — voir docstring du schéma.
    jours_indisponibles_par_ressource: dict[str, set[int]] = defaultdict(set)
    motif_hebdo_par_ressource: dict[str, set[int]] = defaultdict(set)
    for contrainte in instance.contraintes:
        if not isinstance(contrainte, ContrainteDisponibiliteRessource):
            continue
        jours_indisponibles_par_ressource[contrainte.ressource].update(contrainte.jours_indisponibles)
        if contrainte.jours_semaine_indisponibles:
            motif_hebdo_par_ressource[contrainte.ressource].update(contrainte.jours_semaine_indisponibles)

    # Longueur du cycle du motif hebdomadaire récurrent — dépend de l'unité de temps déclarée
    # par l'instance (voir InstanceTRCO.unite_temps, dsl/schema/instance.py) : 7 en mode jours,
    # 168 en mode heures. `jours_semaine_indisponibles` a déjà été validé contre cette même borne
    # à l'ingestion (InstanceTRCO._disponibilite_dans_le_cycle).
    longueur_cycle = 7 if instance.unite_temps == "jours" else 168

    for ressource_id in jours_indisponibles_par_ressource.keys() | motif_hebdo_par_ressource.keys():
        jours_bloques = jours_indisponibles_par_ressource.get(ressource_id, set())
        motif_hebdo = motif_hebdo_par_ressource.get(ressource_id, set())
        for tache_id, debut, fin in operations_par_ressource.get(ressource_id, []):
            jours_occupes = set(range(debut, fin))
            jours_en_conflit = {
                jour for jour in jours_occupes if jour in jours_bloques or (jour % longueur_cycle) in motif_hebdo
            }
            if jours_en_conflit:
                violations.append(
                    Violation(
                        "ressource_indisponible",
                        f"tâche {tache_id!r} planifiée sur {ressource_id!r} un jour où cette "
                        f"ressource est indisponible : {sorted(jours_en_conflit)!r}",
                        tache=tache_id,
                        ressource=ressource_id,
                    )
                )

    for contrainte in instance.contraintes:
        if not isinstance(contrainte, ContrainteIncompatibilite):
            continue
        operation_1 = operations_valides.get(contrainte.tache)
        operation_2 = operations_valides.get(contrainte.tache_incompatible)
        if operation_1 is None or operation_2 is None:
            continue
        if operation_1.ressource == operation_2.ressource:
            violations.append(
                Violation(
                    "incompatibilite_taches_violee",
                    f"tâches incompatibles {contrainte.tache!r} et {contrainte.tache_incompatible!r} "
                    f"affectées à la même ressource : {operation_1.ressource!r}",
                    tache=contrainte.tache,
                    tache_secondaire=contrainte.tache_incompatible,
                    ressource=operation_1.ressource,
                )
            )

    # Stock de matériaux : seule vérification chronologique/stateful du module. Ne porte que sur
    # les opérations structurellement valides (tâche connue, planifiée une seule fois, ressource
    # connue) — une tâche déjà signalée non planifiée/dupliquée n'a pas de `debut` fiable à
    # intégrer dans la simulation. `DeclarationMateriau` n'a pas de liste top-level dédiée (voir
    # dsl/schema/instance.py) : le stock initial se lit directement dans `instance.contraintes`.
    consommations_par_tache: dict[str, list[ConsommationMatiere]] = defaultdict(list)
    stock_initial_par_materiau: dict[str, float] = {
        c.materiau: c.stock_initial for c in instance.contraintes if isinstance(c, DeclarationMateriau)
    }
    for contrainte in instance.contraintes:
        if isinstance(contrainte, ConsommationMatiere):
            consommations_par_tache[contrainte.tache].append(contrainte)

    if stock_initial_par_materiau and consommations_par_tache:
        evenements_par_materiau: dict[str, list[tuple[int, str, float]]] = defaultdict(list)
        for tache_id, operation in operations_valides.items():
            for consommation in consommations_par_tache.get(tache_id, []):
                evenements_par_materiau[consommation.materiau].append(
                    (operation.debut, tache_id, consommation.quantite)
                )

        for materiau_id, evenements in evenements_par_materiau.items():
            stock = stock_initial_par_materiau.get(materiau_id)
            if stock is None:
                # Matériau inconnu : déjà rejeté à la construction de l'instance
                # (InstanceTRCO._contraintes_referencent_des_entites_declarees) — ne peut pas
                # arriver ici, gardé défensif plutôt que silencieux.
                continue
            for debut, tache_id, quantite in sorted(evenements, key=lambda evenement: evenement[0]):
                stock -= quantite
                if stock < 0:
                    violations.append(
                        Violation(
                            "stock_insuffisant",
                            f"stock de {materiau_id!r} insuffisant : la tâche {tache_id!r} (jour "
                            f"{debut}) le fait passer à {stock}",
                            tache=tache_id,
                            ressource=None,
                        )
                    )

    return ResultatFaisabilite(tuple(violations))
