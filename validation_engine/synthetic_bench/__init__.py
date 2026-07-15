"""synthetic_bench — Banc d'essai synthétique, en deux niveaux (§6.4) : vérité
terrain connue (`construction_inverse.py`) et faisabilité seule
(`instances_faisabilite_seule.py`, PH3-T3)."""

from .catalogue import CATALOGUE, DOSSIER_INSTANCES, generer_catalogue
from .construction_inverse import FormeJob, InstanceSynthetique, construire_instance
from .instances_faisabilite_seule import (
    CATALOGUE_FAISABILITE_SEULE,
    FormeJobPartage,
    InstanceFaisabiliteSeule,
    construire_instance_contention_partagee,
    generer_catalogue_faisabilite_seule,
)

__all__ = [
    "CATALOGUE",
    "CATALOGUE_FAISABILITE_SEULE",
    "DOSSIER_INSTANCES",
    "FormeJob",
    "FormeJobPartage",
    "InstanceFaisabiliteSeule",
    "InstanceSynthetique",
    "construire_instance",
    "construire_instance_contention_partagee",
    "generer_catalogue",
    "generer_catalogue_faisabilite_seule",
]
