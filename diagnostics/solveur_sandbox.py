"""Enveloppe un solveur du store (`solver_store/registry.py`) en fonction
appelable — le pont entre le store et `diagnostics.diagnostiquer()`, qui a
besoin d'un `Callable[[InstanceTRCO], Planning | None]`, pas d'un artefact.

Avertissement de performance : `diagnostiquer` rejoue ce solveur sur tout le
banc synthétique (5 cas) puis, si nécessaire, tous les cas de référence
(3 cas) — jusqu'à 8 lancements de conteneur Docker séquentiels par appel,
donc plusieurs secondes de latence. Acceptable pour un diagnostic déclenché
manuellement depuis le dashboard (avec indicateur de chargement côté
frontend) ; pas conçu pour un usage à haute fréquence.
"""

from __future__ import annotations

from dsl.schema import InstanceTRCO, Planning
from sandbox.runner import ErreurExecutionSandbox, executer_dans_sandbox
from solver_store.registry import Registre
from validation_engine.cascade import Solveur


def construire_solveur_sandbox(registre: Registre, id_solveur: str) -> Solveur:
    """Récupère `id_solveur` dans le store et renvoie une fonction qui
    l'exécute en sandbox à chaque appel — un planning `None` (échec sandbox
    inclus) est traité par la cascade comme un échec de la brique
    faisabilité, sans cas particulier à gérer ici."""
    artefact = registre.recuperer_solveur(id_solveur)

    def solveur(instance: InstanceTRCO) -> Planning | None:
        try:
            return executer_dans_sandbox(artefact.chemin_code, instance)
        except ErreurExecutionSandbox:
            return None

    return solveur
