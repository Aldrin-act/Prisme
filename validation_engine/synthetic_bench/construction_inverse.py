"""Construction inverse (§6.4) : on choisit un planning optimal, puis on
construit l'instance T-R-C-O autour de lui — jamais l'inverse. Le FJSP étant
NP-difficile, calculer l'optimum d'une grande instance a posteriori ne passe
pas à l'échelle ; la construction inverse le donne gratuitement, par
construction, quelle que soit la taille.

Technique retenue ici, volontairement simple à prouver correcte : des
« jobs » indépendants, chacun une chaîne de tâches liées par précédence,
chacun affecté à un lot de ressources qui lui est **dédié** (jamais partagé
entre jobs). Deux conséquences :

- la compatibilité machine-tâche est **forcée** (une seule ressource
  compatible par tâche déclarée) — aucun choix de routage, seulement
  l'ordonnancement dans le temps ;
- comme les jobs ne se disputent jamais de ressource, ils s'exécutent en
  parallèle sans interférence. La précédence impose alors, à elle seule, une
  borne inférieure triviale sur la durée d'un job : une chaîne de tâches
  liées par précédence ne peut pas s'exécuter plus vite que la somme de
  leurs durées. Le planning construit ici atteint exactement cette borne
  (aucun temps mort) pour chaque job, donc le makespan global — le plus
  grand des jobs — est prouvablement optimal, sans jamais faire tourner de
  solveur.

Simplification assumée : un job peut réutiliser une même ressource dédiée
plusieurs fois dans sa chaîne (si `n_ressources < n_taches`), ce qui exerce
réellement le vérificateur de faisabilité (Étape 2) sur le chevauchement de
ressource ; mais il n'y a jamais de choix de machine à faire, seulement un
ordre à respecter — la question du **choix** entre plusieurs machines
compatibles reste hors du périmètre de ce banc.
"""

from __future__ import annotations

from dataclasses import dataclass

from dsl.schema import (
    CompatibiliteMachineTache,
    Contrainte,
    InstanceTRCO,
    MinimiserMakespan,
    OperationPlanifiee,
    Planning,
    Precedence,
    Ressource,
    Tache,
)


@dataclass(frozen=True)
class FormeJob:
    """La forme d'un job : longueur de sa chaîne, nombre de ressources dédiées."""

    n_taches: int
    n_ressources: int

    def __post_init__(self) -> None:
        if self.n_taches < 1:
            raise ValueError("un job doit avoir au moins une tâche")
        if self.n_ressources < 1:
            raise ValueError("un job doit avoir au moins une ressource")


@dataclass(frozen=True)
class InstanceSynthetique:
    """Une instance T-R-C-O construite à l'envers, avec son optimum connu."""

    nom: str
    instance: InstanceTRCO
    planning_optimal: Planning
    optimum: int


def _duree(indice_job: int, indice_tache: int) -> int:
    """Durée déterministe et variée, sans dépendre d'un générateur aléatoire."""
    return 10 + ((indice_job * 31 + indice_tache * 17) % 50)


def construire_instance(nom: str, jobs: list[FormeJob]) -> InstanceSynthetique:
    """Construit une instance T-R-C-O et son planning optimal autour de `jobs`."""
    if not jobs:
        raise ValueError("il faut au moins un job")

    taches: list[Tache] = []
    ressources: list[Ressource] = []
    contraintes: list[Contrainte] = []
    operations: list[OperationPlanifiee] = []
    optimum = 0

    for indice_job, forme in enumerate(jobs):
        ressources_job = [
            f"J{indice_job}M{indice_ressource}" for indice_ressource in range(forme.n_ressources)
        ]
        ressources.extend(Ressource(id=ressource_id) for ressource_id in ressources_job)

        instant = 0
        tache_precedente: str | None = None
        for indice_tache in range(forme.n_taches):
            tache_id = f"J{indice_job}T{indice_tache}"
            duree = _duree(indice_job, indice_tache)
            ressource_id = ressources_job[indice_tache % forme.n_ressources]

            taches.append(Tache(id=tache_id, duree=duree))
            contraintes.append(
                CompatibiliteMachineTache(tache=tache_id, ressource=ressource_id)
            )
            if tache_precedente is not None:
                contraintes.append(Precedence(avant=tache_precedente, apres=tache_id))
            operations.append(
                OperationPlanifiee(tache=tache_id, ressource=ressource_id, debut=instant)
            )

            instant += duree
            tache_precedente = tache_id

        optimum = max(optimum, instant)

    instance = InstanceTRCO(
        taches=taches,
        ressources=ressources,
        contraintes=contraintes,
        objectifs=[MinimiserMakespan()],
    )
    planning_optimal = Planning(operations=operations)

    return InstanceSynthetique(
        nom=nom, instance=instance, planning_optimal=planning_optimal, optimum=optimum
    )
