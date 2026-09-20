"""Solveur heuristique minimal — **fixture de dev/démo/test, pas un composant du
système** (aucune route API n'en dépend). Préfixé `_` : pas un script
autonome comme les autres modules de `scripts/`, juste un module partagé
entre `enregistrer_solveur_reference.py` et quelques tests qui ont besoin
d'un "solveur réel connu-bon" pour prouver autre chose que la résolution
elle-même (le bouclage store→sandbox→garde-fou de l'Étape 7, l'attribution
de cause "données"/"aucune" du diagnostic, le niveau "faisabilité seule" du
banc synthétique) — même rôle que les solveurs bogués en pur Python de
`tests/unit/test_attribution.py`, juste correct au lieu de délibérément
cassé. Reste sous l'allowlist AST de `generation/validation_statique.py`
(dsl, collections, dataclasses, typing, random, math...) : un test peut le geler et
l'exécuter en sandbox comme n'importe quel code généré.

PRISME n'utilise aucun moteur exact (CP-SAT retiré) : ce solveur est un ordonnancement par
liste déterministe (aucun hasard, aucune limite de temps) — voir `resoudre`.
"""

from __future__ import annotations

from dsl.schema import (
    CompatibiliteRessourceTache,
    InstanceTRCO,
    OperationPlanifiee,
    Planning,
    Precedence,
)


def _premier_creneau(occupation: list[tuple[int, int]], pret: int, duree: int) -> int:
    """Premier instant >= `pret` où un intervalle de longueur `duree` tient sans chevaucher
    aucun intervalle déjà occupé (`occupation` trié, disjoint)."""
    debut = pret
    for debut_occupe, fin_occupe in occupation:
        if debut + duree <= debut_occupe:
            break
        debut = max(debut, fin_occupe)
    return debut


def resoudre(
    instance: InstanceTRCO,
    limite_temps_s: float = 30.0,
    planning_precedent: Planning | None = None,
    horizon_gele_jours: int = 0,
) -> Planning | None:
    """Ordonnancement par liste (*serial schedule generation scheme*) : à chaque tour, parmi les
    tâches dont tous les prédécesseurs sont placés, prend la plus contrainte (le moins de
    ressources compatibles, puis la plus longue, puis l'identifiant) et la place sur la ressource
    compatible qui la termine le plus tôt (égalité : identifiant de ressource). Légal par
    construction — précédence, compatibilité, non-chevauchement — jamais de pénalité.
    Déterministe : aucun hasard, aucune itération sur un `set`, `limite_temps_s` est conservé
    dans la signature (appelants existants) mais sans effet.

    `planning_precedent`/`horizon_gele_jours` (Phase 2, replanification à horizon glissant,
    additif — `resoudre(instance)` continue de marcher sans changement) : toute opération de
    `planning_precedent` dont `debut < horizon_gele_jours` est fixée (même ressource, même
    début) avant tout autre placement, voir `generation/prompts/generation_solveur.md`."""
    duree: dict[tuple[str, str], int] = {}
    candidats: dict[str, list[str]] = {}
    predecesseurs: dict[str, list[str]] = {tache.id: [] for tache in instance.taches}
    for contrainte in instance.contraintes:
        if isinstance(contrainte, CompatibiliteRessourceTache):
            duree[(contrainte.tache, contrainte.ressource)] = contrainte.duree
            candidats.setdefault(contrainte.tache, []).append(contrainte.ressource)
        elif isinstance(contrainte, Precedence):
            predecesseurs[contrainte.apres].append(contrainte.avant)
    for ressources in candidats.values():
        ressources.sort()

    occupation: dict[str, list[tuple[int, int]]] = {ressource.id: [] for ressource in instance.ressources}
    debut_de: dict[str, int] = {}
    fin_de: dict[str, int] = {}
    ressource_de: dict[str, str] = {}

    def placer(tache: str, ressource: str, debut: int) -> None:
        fin = debut + duree[(tache, ressource)]
        debut_de[tache] = debut
        fin_de[tache] = fin
        ressource_de[tache] = ressource
        occupation[ressource].append((debut, fin))
        occupation[ressource].sort()

    if planning_precedent is not None and horizon_gele_jours > 0:
        gelees = sorted(planning_precedent.operations, key=lambda op: (op.debut, op.tache))
        for operation in gelees:
            if operation.debut >= horizon_gele_jours or operation.tache in debut_de:
                continue
            if (operation.tache, operation.ressource) not in duree:
                continue  # tâche/ressource plus valide dans l'instance courante
            placer(operation.tache, operation.ressource, operation.debut)

    restantes = [tache.id for tache in instance.taches if tache.id not in debut_de]
    while restantes:
        pretes = [t for t in restantes if all(p in fin_de for p in predecesseurs[t])]
        if not pretes:
            return None  # cycle de précédences : aucun planning légal

        tache = min(
            pretes,
            key=lambda t: (len(candidats[t]), -min(duree[(t, r)] for r in candidats[t]), t),
        )
        pret = max((fin_de[p] for p in predecesseurs[tache]), default=0)

        meilleur: tuple[int, int, str] | None = None
        for ressource in candidats[tache]:
            debut = _premier_creneau(occupation[ressource], pret, duree[(tache, ressource)])
            candidat = (debut + duree[(tache, ressource)], debut, ressource)
            if meilleur is None or candidat < meilleur:
                meilleur = candidat
        assert meilleur is not None  # au moins une compatibilité par tâche : garanti par InstanceTRCO (§6.7)
        placer(tache, meilleur[2], meilleur[1])
        restantes.remove(tache)

    return Planning(
        operations=[
            OperationPlanifiee(tache=tache.id, ressource=ressource_de[tache.id], debut=debut_de[tache.id])
            for tache in instance.taches
        ]
    )
