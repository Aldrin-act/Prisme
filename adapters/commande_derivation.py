"""Dérivation d'échéances à partir de commandes — partagée entre les adaptateurs d'ingestion qui
la proposent (`csv_import`, `json_import`), même patron que
`adapters/competence_derivation.py` pour la compatibilité ressource-tâche.

`Commande` (id, client, date_limite, tâches liées) reste une **métadonnée de traçabilité
d'ingestion**, jamais un axe T-R-C-O : le solveur ne voit jamais la notion de "commande",
seulement les `Echeance` DSL qu'il connaît déjà (§5.3 — vocabulaire DSL fini, borne la surface de
génération de l'IA). Une commande porteuse d'une `date_limite` dérive une `Echeance` identique
pour chaque tâche qui lui est liée — exactement ce qu'un planificateur ferait à la main, en plus
rapide et sans oubli.

Une `Echeance` déjà explicite pour une tâche l'emporte toujours sur une dérivation pour cette
même tâche (même principe que la compatibilité dérivée par compétence : explicite > dérivé,
jamais un doublon contradictoire). Une tâche liée à plusieurs commandes avec des dates limites
différentes retient la plus contraignante (la plus proche) — c'est elle qui borne réellement le
planning, pas une moyenne ni la dernière rencontrée.
"""

from __future__ import annotations

from dataclasses import dataclass

from dsl.schema import Contrainte, Echeance


@dataclass(frozen=True)
class Commande:
    """Une commande/demande cliente reliant un ensemble de tâches à une échéance commune.
    `date_limite` : jours relatifs, même référentiel que `Echeance.echeance` — `None` si la
    commande n'a pas de délai (pure traçabilité, aucune échéance dérivée pour ses tâches)."""

    id: str
    taches: tuple[str, ...]
    client: str | None = None
    date_limite: int | None = None


def deriver_echeances_par_commande(commandes: list[Commande], contraintes: list[Contrainte]) -> list[Contrainte]:
    """Renvoie les `Echeance` dérivées à ajouter aux contraintes existantes (jamais les
    contraintes déjà présentes elles-mêmes) — voir docstring module pour les règles de
    préséance (explicite > dérivé, échéance la plus proche si plusieurs commandes)."""
    taches_avec_echeance_explicite = {c.tache for c in contraintes if isinstance(c, Echeance)}

    echeance_derivee_par_tache: dict[str, int] = {}
    for commande in commandes:
        if commande.date_limite is None:
            continue
        for tache_id in commande.taches:
            if tache_id in taches_avec_echeance_explicite:
                continue
            actuelle = echeance_derivee_par_tache.get(tache_id)
            if actuelle is None or commande.date_limite < actuelle:
                echeance_derivee_par_tache[tache_id] = commande.date_limite

    return [
        Echeance(tache=tache_id, echeance=echeance) for tache_id, echeance in echeance_derivee_par_tache.items()
    ]
