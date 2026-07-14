"""Catalogue versionné d'instances synthétiques à vérité terrain connue (§6.4).

Tailles croissantes : de la tâche unique à plusieurs dizaines de tâches
réparties sur plusieurs jobs, pour montrer que la construction inverse passe
à l'échelle sans jamais calculer d'optimum a posteriori. Les fichiers sous
`instances/` sont la version figée de ce catalogue ; `scripts/generer_banc_
synthetique.py` les régénère après toute modification de
`construction_inverse.py`.
"""

from __future__ import annotations

from pathlib import Path

from .construction_inverse import FormeJob, InstanceSynthetique, construire_instance

DOSSIER_INSTANCES = Path(__file__).resolve().parent / "instances"

CATALOGUE: list[tuple[str, list[FormeJob]]] = [
    ("taille_1_tache_unique", [FormeJob(n_taches=1, n_ressources=1)]),
    ("taille_2_chaine_simple", [FormeJob(n_taches=3, n_ressources=2)]),
    (
        "taille_3_jobs_paralleles",
        [FormeJob(n_taches=3, n_ressources=2) for _ in range(3)],
    ),
    (
        "taille_4_jobs_moyens",
        [FormeJob(n_taches=5, n_ressources=3) for _ in range(5)],
    ),
    (
        "taille_5_grande_instance",
        [FormeJob(n_taches=8, n_ressources=4) for _ in range(10)],
    ),
]


def generer_catalogue() -> list[InstanceSynthetique]:
    """Construit chaque cas du catalogue (déterministe, sans aléatoire)."""
    return [construire_instance(nom, jobs) for nom, jobs in CATALOGUE]
