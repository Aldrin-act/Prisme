"""estimation — Estimation de durée par apprentissage supervisé (MT3 du plan
directeur), entraînée aujourd'hui sur des données synthétiques faute
d'historique d'exécution réel disponible (voir
`docs/perspective_estimation_charge.md` et `estimation/README.md`)."""

from .donnees_historique import ObservationDuree, historique_synthetique
from .modele import EstimateurDuree, EstimationDuree, vers_durees_estimees_par_tache

__all__ = [
    "EstimateurDuree",
    "EstimationDuree",
    "ObservationDuree",
    "historique_synthetique",
    "vers_durees_estimees_par_tache",
]
