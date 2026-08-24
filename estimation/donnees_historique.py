"""Données d'entraînement pour l'estimation de durée — synthétiques, faute
d'historique d'exécution réel disponible nulle part dans PRISME aujourd'hui
(aucune table ne capture de durée réellement observée — voir
`docs/perspective_estimation_charge.md`). Réutilise le banc synthétique de
l'Étape 3 (`validation_engine/synthetic_bench/`) plutôt que d'inventer un
second générateur de données : chaque cas y porte déjà des `Tache`/
`Ressource`/`CompatibiliteRessourceTache` réels, il suffit de leur adjoindre
des traits (quantité, priorité, type de ressource, compétences) et une
« durée observée » calculée comme une fonction connue de ces traits plus un
résidu déterministe — jamais un générateur aléatoire opaque, même principe
que `construction_inverse.py::_duree` : reproductible, diffable, et surtout
vérifiable (un test peut confirmer qu'un modèle entraîné dessus retrouve le
signal connu par construction).
"""

from __future__ import annotations

from dataclasses import dataclass

from dsl.schema import CompatibiliteRessourceTache
from validation_engine.synthetic_bench.catalogue import generer_catalogue
from validation_engine.synthetic_bench.construction_inverse import InstanceSynthetique

TYPES_RESSOURCE_CYCLE = ("machine", "humain", "equipe")


@dataclass(frozen=True)
class ObservationDuree:
    """Une observation d'entraînement : traits tâche/ressource et la durée
    « observée » associée. `duree_declaree_jours` est conservée à titre
    informatif (ce que le banc synthétique avait initialement posé) mais
    n'est jamais un trait d'entraînement — le modèle apprend à partir des
    traits tâche/ressource, pas en trichant avec une valeur déjà proche de
    la cible (voir `estimation/README.md`)."""

    tache_id: str
    ressource_id: str
    duree_declaree_jours: int
    tache_quantite: int
    tache_priorite: int
    ressource_type_index: int  # index dans TYPES_RESSOURCE_CYCLE
    ressource_nb_competences: int
    duree_observee_jours: int


def _traits_synthetiques(indice: int) -> tuple[int, int, int, int]:
    """Traits tâche/ressource déterministes dérivés d'un indice croissant —
    le banc synthétique (Étape 3) ne porte pas de vraies valeurs `quantite`/
    `priorite`/`type`/`competences` (il n'en a pas besoin pour son propre
    objectif, prouver l'optimalité d'un planning), donc ce module leur en
    attribue, de façon reproductible."""
    quantite = 1 + (indice * 3) % 20
    priorite = 1 + indice % 5
    type_index = indice % len(TYPES_RESSOURCE_CYCLE)
    nb_competences = indice % 4
    return quantite, priorite, type_index, nb_competences


def _residu(tache_id: str, ressource_id: str) -> int:
    """Petit écart déterministe (entre -2 et +2 jours), dépendant seulement
    des identifiants — pour que le signal appris ne soit pas parfaitement
    linéaire (donc trivial), sans jamais dépendre d'un générateur aléatoire."""
    graine = sum(ord(c) for c in tache_id) * 3 + sum(ord(c) for c in ressource_id) * 7
    return (graine % 5) - 2


def _duree_observee(quantite: int, priorite: int, type_index: int, nb_competences: int, residu: int) -> int:
    """Fonction connue et vérifiable des traits — c'est le signal que le
    modèle doit retrouver. Aucune de ces pondérations n'a de valeur métier
    réelle (faute de données réelles pour l'établir) : elles ne servent qu'à
    donner au modèle un signal non trivial à apprendre et à un test le moyen
    de vérifier qu'il l'a bien appris."""
    base = 12
    effet_quantite = quantite // 4  # lot plus gros → plus long
    effet_type = (2 - type_index) * 2  # machine(0) > humain(1) > equipe(2)
    effet_competences = -nb_competences  # ressource plus qualifiée → plus rapide
    effet_priorite = (5 - priorite) // 2  # tâche critique (priorite=1) → un peu plus de soin
    return max(1, base + effet_quantite + effet_type + effet_competences + effet_priorite + residu)


def observations_depuis_cas(cas: InstanceSynthetique, indice_depart: int = 0) -> list[ObservationDuree]:
    """Dérive des observations d'entraînement à partir d'un cas du banc
    synthétique : une observation par `CompatibiliteRessourceTache` déjà
    déclarée dans l'instance. `indice_depart` permet d'enchaîner plusieurs
    cas sans répéter la même séquence de traits d'un cas à l'autre."""
    observations: list[ObservationDuree] = []
    compatibilites = [c for c in cas.instance.contraintes if isinstance(c, CompatibiliteRessourceTache)]
    for decalage, compat in enumerate(compatibilites):
        quantite, priorite, type_index, nb_competences = _traits_synthetiques(indice_depart + decalage)
        residu = _residu(compat.tache, compat.ressource)
        duree_observee = _duree_observee(quantite, priorite, type_index, nb_competences, residu)
        observations.append(
            ObservationDuree(
                tache_id=compat.tache,
                ressource_id=compat.ressource,
                duree_declaree_jours=compat.duree,
                tache_quantite=quantite,
                tache_priorite=priorite,
                ressource_type_index=type_index,
                ressource_nb_competences=nb_competences,
                duree_observee_jours=duree_observee,
            )
        )
    return observations


def historique_synthetique() -> list[ObservationDuree]:
    """Historique d'entraînement complet : toutes les observations dérivées
    de chaque cas du banc synthétique existant (Étape 3, `generer_catalogue`)."""
    observations: list[ObservationDuree] = []
    for cas in generer_catalogue():
        observations.extend(observations_depuis_cas(cas, indice_depart=len(observations)))
    return observations
