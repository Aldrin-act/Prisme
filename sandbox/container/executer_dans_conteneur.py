"""Harnais exécuté À L'INTÉRIEUR du conteneur jetable (§5.2, §7).

Charge le code figé monté en lecture seule, l'exécute sur l'instance
également montée en lecture seule, écrit le planning résultant (ou `null`)
sur la sortie standard. Volontairement minimal : aucune dépendance à
`validation_engine/` ici — les deux garde-fous (§6.7) s'exécutent côté
hôte, avant l'appel (validation d'entrée) et après le retour du conteneur
(faisabilité), jamais dans le conteneur lui-même, qui ne doit faire tourner
que le code figé sur les données reçues.

Usage : executer_dans_conteneur.py <chemin_code> <chemin_instance>
"""

from __future__ import annotations

import importlib.util
import sys

from dsl.schema import InstanceTRCO


def _charger_solveur_fige(chemin: str):
    spec = importlib.util.spec_from_file_location("solveur_fige", chemin)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"impossible de charger le solveur figé depuis {chemin!r}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.resoudre


def main() -> None:
    chemin_code, chemin_instance = sys.argv[1], sys.argv[2]

    with open(chemin_instance, encoding="utf-8") as fichier:
        instance = InstanceTRCO.model_validate_json(fichier.read())

    resoudre = _charger_solveur_fige(chemin_code)
    planning = resoudre(instance)

    print("null" if planning is None else planning.model_dump_json())


if __name__ == "__main__":
    main()
