"""synthetic_bench — Banc d'essai synthétique à vérité terrain connue (§6.4)."""

from .catalogue import CATALOGUE, DOSSIER_INSTANCES, generer_catalogue
from .construction_inverse import FormeJob, InstanceSynthetique, construire_instance

__all__ = [
    "CATALOGUE",
    "DOSSIER_INSTANCES",
    "FormeJob",
    "InstanceSynthetique",
    "construire_instance",
    "generer_catalogue",
]
