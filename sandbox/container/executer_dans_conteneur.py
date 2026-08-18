"""Harnais exécuté À L'INTÉRIEUR du conteneur jetable (§5.2, §7).

Charge le code figé monté en lecture seule, l'exécute sur l'instance
également montée en lecture seule, écrit le planning résultant (ou `null`)
sur la sortie standard. Volontairement minimal : aucune dépendance à
`validation_engine/` ici — les deux garde-fous (§6.7) s'exécutent côté
hôte, avant l'appel (validation d'entrée) et après le retour du conteneur
(faisabilité), jamais dans le conteneur lui-même, qui ne doit faire tourner
que le code figé sur les données reçues.

Usage : executer_dans_conteneur.py <chemin_code> <chemin_instance> [<chemin_planning_precedent>|-
    [<horizon_gele_jours>]]

Les deux derniers argv sont optionnels (Phase 2, replanification à horizon glissant) : absents,
le harnais appelle `resoudre(instance)` exactement comme avant leur ajout — c'est ce qui garantit
qu'un solveur enregistré avant cette fonctionnalité continue de fonctionner sans changement.
L'appelant hôte (`sandbox/runner.py::executer_solveur_valide`) a déjà vérifié statiquement (sans
exécuter le code) que le solveur ciblé supporte ces paramètres avant de les fournir ici — ce
harnais ne le revérifie pas.
"""

from __future__ import annotations

import importlib.util
import sys

from dsl.schema import InstanceTRCO, Planning


def _charger_solveur_fige(chemin: str):
    spec = importlib.util.spec_from_file_location("solveur_fige", chemin)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"impossible de charger le solveur figé depuis {chemin!r}")
    module = importlib.util.module_from_spec(spec)
    # `dataclasses` (`_is_type`) résout `sys.modules[cls.__module__]` pour évaluer les
    # annotations différées ; sans cet enregistrement, un solveur figé définissant une
    # dataclass plante avec `AttributeError: 'NoneType' object has no attribute '__dict__'`.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.resoudre


def main() -> None:
    chemin_code, chemin_instance = sys.argv[1], sys.argv[2]
    horizon_gele_jours = int(sys.argv[4]) if len(sys.argv) > 4 else 0

    with open(chemin_instance, encoding="utf-8") as fichier:
        instance = InstanceTRCO.model_validate_json(fichier.read())

    resoudre = _charger_solveur_fige(chemin_code)

    if horizon_gele_jours > 0:
        planning_precedent: Planning | None = None
        chemin_planning_precedent = sys.argv[3] if len(sys.argv) > 3 else "-"
        if chemin_planning_precedent != "-":
            with open(chemin_planning_precedent, encoding="utf-8") as fichier:
                planning_precedent = Planning.model_validate_json(fichier.read())
        planning = resoudre(instance, planning_precedent=planning_precedent, horizon_gele_jours=horizon_gele_jours)
    else:
        planning = resoudre(instance)

    print("null" if planning is None else planning.model_dump_json())


if __name__ == "__main__":
    main()
