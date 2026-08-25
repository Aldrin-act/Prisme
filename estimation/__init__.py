"""estimation — Estimation de durée par apprentissage supervisé (MT3 du plan
directeur), entraînée aujourd'hui sur des données synthétiques faute
d'historique d'exécution réel disponible (voir
`docs/perspective_estimation_charge.md` et `estimation/README.md`)."""

from functools import lru_cache

from .donnees_historique import ObservationDuree, historique_synthetique
from .modele import EstimateurDuree, EstimationDuree, vers_durees_estimees_par_tache

__all__ = [
    "EstimateurDuree",
    "EstimationDuree",
    "ObservationDuree",
    "estimateur_par_defaut",
    "historique_synthetique",
    "vers_durees_estimees_par_tache",
]


@lru_cache(maxsize=1)
def estimateur_par_defaut() -> EstimateurDuree:
    """Entraîne (une seule fois par process, résultat mis en cache — le jeu
    d'entraînement synthétique est déterministe, `GradientBoostingRegressor(
    random_state=0)`) l'estimateur utilisé par les adaptateurs d'ingestion
    (`api/routes/sources.py`, `api/routes/adapters.py`) quand `estimation`
    est installé (`uv sync --extra estimation`)."""
    return EstimateurDuree.entrainer(historique_synthetique())
