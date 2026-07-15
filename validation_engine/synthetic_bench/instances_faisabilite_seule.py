"""Second niveau du banc synthétique (§6.4, PH3-T3) : des instances **sans
optimum connu**, mais dont la faisabilité (Étape 2) d'un planning candidat
reste vérifiable.

La construction inverse (niveau 1, `construction_inverse.py`) dédie une
ressource par job pour garantir l'optimum par simple arithmétique — ce qui
exclut, par construction, toute vraie contention de ressource entre jobs. Ce
module fait l'inverse : plusieurs jobs partagent réellement un pool de
machines communes, chaque tâche étant compatible avec toutes ces machines à
des durées différentes (FJSP flexible véritable). La complexité qui en
résulte est authentique — calculer l'optimum est NP-difficile et n'est
délibérément pas tenté ici.

Niveau plus faible que le premier (aucune garantie d'optimalité), mais
toujours utile : il élargit la couverture du DSL et du vérificateur à des
instances proches d'un atelier réel, que le niveau 1 ne peut jamais produire.
Utilisation prévue : faire tourner un solveur candidat (§6.2) sur ces
instances et vérifier que le planning produit est légal — jamais qu'il est
optimal, puisqu'aucun optimum de référence n'existe ici.
"""

from __future__ import annotations

from dataclasses import dataclass

from dsl.schema import (
    CompatibiliteMachineTache,
    Contrainte,
    InstanceTRCO,
    MinimiserMakespan,
    Precedence,
    Ressource,
    Tache,
)


@dataclass(frozen=True)
class FormeJobPartage:
    """La forme d'un job dans une instance à contention partagée : longueur de sa chaîne."""

    n_taches: int

    def __post_init__(self) -> None:
        if self.n_taches < 1:
            raise ValueError("un job doit avoir au moins une tâche")


@dataclass(frozen=True)
class InstanceFaisabiliteSeule:
    """Une instance T-R-C-O sans optimum connu ni planning attendu — seule sa
    faisabilité est vérifiable, une fois un planning produit par un solveur."""

    nom: str
    instance: InstanceTRCO


def _duree(indice_job: int, indice_tache: int, indice_ressource: int) -> int:
    """Durée déterministe et variée par (job, tâche, ressource), sans aléatoire."""
    return 10 + ((indice_job * 31 + indice_tache * 17 + indice_ressource * 13) % 40)


def construire_instance_contention_partagee(
    nom: str, jobs: list[FormeJobPartage], ressources_partagees: int
) -> InstanceFaisabiliteSeule:
    """Construit une instance où tous les jobs se disputent réellement un même
    pool de `ressources_partagees` machines — aucune résolution n'a lieu ici,
    donc aucun optimum n'est connu ; seule sa faisabilité (Étape 2) est
    garantie vérifiable, une fois un planning candidat produit ailleurs.
    """
    if ressources_partagees < 1:
        raise ValueError("il faut au moins une ressource partagée")
    if not jobs:
        raise ValueError("il faut au moins un job")

    ressources = [Ressource(id=f"M{indice}") for indice in range(ressources_partagees)]

    taches: list[Tache] = []
    contraintes: list[Contrainte] = []

    for indice_job, forme in enumerate(jobs):
        tache_precedente: str | None = None
        for indice_tache in range(forme.n_taches):
            tache_id = f"J{indice_job}T{indice_tache}"
            taches.append(Tache(id=tache_id))

            # Compatible avec TOUTES les ressources partagées (vrai choix de
            # routage), chacune à sa propre durée (FJSP flexible véritable) —
            # contrairement au niveau 1, où le choix de machine est absent.
            for indice_ressource, ressource in enumerate(ressources):
                contraintes.append(
                    CompatibiliteMachineTache(
                        tache=tache_id,
                        ressource=ressource.id,
                        duree=_duree(indice_job, indice_tache, indice_ressource),
                    )
                )

            if tache_precedente is not None:
                contraintes.append(Precedence(avant=tache_precedente, apres=tache_id))
            tache_precedente = tache_id

    instance = InstanceTRCO(
        taches=taches,
        ressources=ressources,
        contraintes=contraintes,
        objectifs=[MinimiserMakespan()],
    )
    return InstanceFaisabiliteSeule(nom=nom, instance=instance)


CATALOGUE_FAISABILITE_SEULE: list[tuple[str, list[FormeJobPartage], int]] = [
    ("contention_deux_jobs_une_ressource", [FormeJobPartage(2), FormeJobPartage(2)], 1),
    ("contention_trois_jobs_deux_ressources", [FormeJobPartage(3) for _ in range(3)], 2),
    ("contention_cinq_jobs_trois_ressources", [FormeJobPartage(4) for _ in range(5)], 3),
]


def generer_catalogue_faisabilite_seule() -> list[InstanceFaisabiliteSeule]:
    """Construit chaque cas du second niveau (déterministe, sans aléatoire) —
    pas de vérification de faisabilité ici, puisqu'aucun planning n'existe
    encore à cette étape (voir le module docstring : la vérification a lieu
    une fois un solveur candidat exécuté sur ces instances)."""
    return [
        construire_instance_contention_partagee(nom, jobs, n_ressources)
        for nom, jobs, n_ressources in CATALOGUE_FAISABILITE_SEULE
    ]
