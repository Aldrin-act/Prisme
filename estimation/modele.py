"""Modèle de régression supervisée estimant la durée d'une opération à
partir de traits tâche/ressource — scikit-learn plutôt que XGBoost (cité au
plan directeur initial, MT3) : même famille de méthode (boosting de
gradient), sans dépendance à une toolchain compilée en plus de `numpy`. Voir
`estimation/README.md` pour le cadrage et ses limites assumées.
"""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.ensemble import GradientBoostingRegressor

from dsl.schema import Ressource, Tache

from .donnees_historique import TYPES_RESSOURCE_CYCLE, ObservationDuree

SEUIL_CONFIANCE_PAR_DEFAUT = 0.5
OBSERVATIONS_MINIMALES = 5


def _index_type_ressource(type_ressource: str | None) -> int:
    """`Ressource.type` est optionnel et purement informatif dans le DSL
    (§4.2) — absent, on retombe sur une valeur neutre plutôt que de rejeter
    l'estimation."""
    if type_ressource in TYPES_RESSOURCE_CYCLE:
        return TYPES_RESSOURCE_CYCLE.index(type_ressource)
    return 0


def _vecteur(quantite: int, priorite: int, type_index: int, nb_competences: int) -> list[float]:
    """Un seul point d'encodage des traits, partagé entre l'entraînement et
    la prédiction — pour ne jamais désynchroniser l'ordre des colonnes."""
    return [float(quantite), float(priorite), float(type_index), float(nb_competences)]


@dataclass(frozen=True)
class EstimationDuree:
    """Résultat d'une estimation — jamais directement un
    `CompatibiliteRessourceTache` : une conversion explicite reste
    nécessaire avant que ceci n'entre dans le DSL (§FC4, décision humaine
    préservée — voir `vers_durees_estimees_par_tache`)."""

    tache: str
    ressource: str
    duree_estimee_jours: int
    confiance: float


class EstimateurDuree:
    """Enveloppe un `GradientBoostingRegressor` entraîné sur des
    `ObservationDuree`. `confiance` (0 à 1) est le score R² du modèle sur
    ses propres données d'entraînement — un indicateur grossier de la
    qualité de l'ajustement, jamais une probabilité calibrée ni une garantie
    de justesse sur une donnée réelle jamais vue."""

    def __init__(self, modele: GradientBoostingRegressor, confiance: float) -> None:
        self._modele = modele
        self._confiance = confiance

    @classmethod
    def entrainer(cls, observations: list[ObservationDuree]) -> EstimateurDuree:
        if len(observations) < OBSERVATIONS_MINIMALES:
            raise ValueError(
                f"au moins {OBSERVATIONS_MINIMALES} observations sont nécessaires pour entraîner un estimateur "
                f"({len(observations)} fournie(s))"
            )
        x = [
            _vecteur(o.tache_quantite, o.tache_priorite, o.ressource_type_index, o.ressource_nb_competences)
            for o in observations
        ]
        y = [float(o.duree_observee_jours) for o in observations]
        modele = GradientBoostingRegressor(random_state=0)
        modele.fit(x, y)
        confiance = max(0.0, min(1.0, modele.score(x, y)))
        return cls(modele, confiance)

    def estimer(self, tache: Tache, ressource: Ressource) -> EstimationDuree:
        quantite = tache.quantite if tache.quantite is not None else 1
        priorite = tache.priorite if tache.priorite is not None else 3
        type_index = _index_type_ressource(ressource.type)
        nb_competences = len(ressource.competences)
        prediction = self._modele.predict([_vecteur(quantite, priorite, type_index, nb_competences)])[0]
        duree_estimee = max(1, round(prediction))
        return EstimationDuree(
            tache=tache.id, ressource=ressource.id, duree_estimee_jours=duree_estimee, confiance=self._confiance
        )


def vers_durees_estimees_par_tache(
    estimations: list[EstimationDuree], seuil_confiance: float = SEUIL_CONFIANCE_PAR_DEFAUT
) -> dict[str, int]:
    """Convertit des `EstimationDuree` en la forme attendue par
    `adapters.competence_derivation.deriver_compatibilites_par_competence` —
    ne retient que les estimations dont la confiance atteint `seuil_confiance`
    : une estimation peu fiable ne doit jamais combler silencieusement un
    trou (§FC4) — mieux vaut laisser `CompetenceSansDureeEstimee` se lever et
    signaler l'absence à un humain que de deviner sans base solide."""
    return {e.tache: e.duree_estimee_jours for e in estimations if e.confiance >= seuil_confiance}
