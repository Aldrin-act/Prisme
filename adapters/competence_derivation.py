"""Dérivation de compatibilité ressource-tâche à partir des compétences —
partagée entre les adaptateurs d'ingestion qui la proposent (`csv_import`,
`json_import`) plutôt que dupliquée : une ressource est jugée compatible avec
une tâche si `Ressource.competences` couvre *toutes* les compétences exigées
par cette tâche (`CompetenceRequise`), avec la durée estimée de la tâche
(fournie à part, hors DSL — `Tache` n'a délibérément aucun champ de durée,
§4.2, elle dépend de la ressource en vrai FJSP flexible) appliquée telle
quelle à chaque ressource ainsi qualifiée. Même principe que
`adapters/greensig/translator.py` (`equipes_compatibles_pour`/
`duree_jours_pour`) : une durée par tâche, pas par couple, faute de mieux
quand seules des compétences sont déclarées.

Une compatibilité déjà explicite pour un couple (tâche, ressource) l'emporte
toujours sur une dérivation pour ce même couple, plutôt que de produire un
doublon contradictoire (deux durées différentes pour la même paire). Le DSL
lui-même (`dsl/schema/instance.py`, `InstanceTRCO._competences_requises_respectees`)
revérifie ensuite que toute compatibilité pour une tâche à compétences
requises — dérivée ou explicite — les couvre bien toutes ; un garde-fou de
plus, jamais remplacé ici.
"""

from __future__ import annotations

from collections import defaultdict

from dsl.schema import CompatibiliteRessourceTache, CompetenceRequise, Contrainte, Ressource


class CompetenceSansDureeEstimee(Exception):
    """Une tâche exige une compétence mais aucune durée estimée n'est fournie
    pour elle — impossible de dériver sa compatibilité sans savoir combien de
    temps l'opération prend."""

    def __init__(self, tache_id: str) -> None:
        self.tache_id = tache_id
        super().__init__(
            f"durée estimée manquante pour {tache_id!r}, requise pour dériver sa compatibilité par compétence"
        )


def deriver_compatibilites_par_competence(
    contraintes: list[Contrainte],
    ressources: list[Ressource],
    durees_estimees_par_tache: dict[str, int],
) -> list[Contrainte]:
    """Renvoie les `CompatibiliteRessourceTache` dérivées à ajouter aux
    contraintes existantes (jamais les contraintes déjà présentes elles-mêmes).
    Lève `CompetenceSansDureeEstimee` si une tâche exige une compétence sans
    durée estimée connue dans `durees_estimees_par_tache`."""
    competences_requises_par_tache: dict[str, set[str]] = defaultdict(set)
    paires_deja_explicites: set[tuple[str, str]] = set()
    for contrainte in contraintes:
        if isinstance(contrainte, CompetenceRequise):
            competences_requises_par_tache[contrainte.tache].add(contrainte.competence)
        elif isinstance(contrainte, CompatibiliteRessourceTache):
            paires_deja_explicites.add((contrainte.tache, contrainte.ressource))

    derivees: list[Contrainte] = []
    for tache_id, requises in competences_requises_par_tache.items():
        duree = durees_estimees_par_tache.get(tache_id)
        if duree is None:
            raise CompetenceSansDureeEstimee(tache_id)
        for ressource in ressources:
            if (tache_id, ressource.id) in paires_deja_explicites:
                continue
            if requises <= set(ressource.competences):
                derivees.append(CompatibiliteRessourceTache(tache=tache_id, ressource=ressource.id, duree=duree))
    return derivees
