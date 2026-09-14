"""Enregistre un solveur validé dans le store (§7), pour un client et une
structure de contraintes donnés — utilisé par la démo bout en bout
(`demo_bout_en_bout.py`) et par les tests d'intégration de l'API, qui ont
besoin d'un solveur déjà validé pour que `/execution` trouve quelque chose.

En situation réelle, c'est la boucle generate-test-repair (Étape 6, pas
encore construite) qui appellerait `Registre.enregistrer_solveur` à
l'issue d'une génération validée — ce script en est le substitut manuel,
via le solveur minimal de `scripts/_solveur_minimal.py` (fixture de
dev/démo/test, pas un composant système — voir son docstring).

Usage, depuis la racine du dépôt : python -m scripts.enregistrer_solveur_reference [client_id]
"""

from __future__ import annotations

import sys
from pathlib import Path

import scripts._solveur_minimal as _module_solveur_minimal
from scripts._solveur_minimal import resoudre
from solver_store.registry import Registre
from validation_engine.cascade import evaluer_cascade

STRUCTURE_MINIMALE = "compatibilite_ressource_tache,precedence"


def enregistrer(registre: Registre, instance_id: str, client_id: str = "demo") -> str:
    """Idempotent : réutilise un solveur déjà enregistré pour cette instance
    plutôt que d'en dupliquer un à chaque appel (le script et la démo
    peuvent être relancés sans effet de bord). `instance_id` obligatoire —
    un solveur ne sert que l'instance qui l'a fait générer
    (`solver_store/registry.py`), l'appelant doit donc avoir déjà créé son
    instance avant d'appeler cette fonction.

    Rejoue la cascade complète (Étape 5) sur le solveur minimal avant
    d'enregistrer — le store ne doit jamais recevoir un verdict qu'on n'a
    pas réellement vérifié.
    """
    existants = registre.rechercher_solveurs(
        client_id=client_id, instance_id=instance_id, structure_contraintes=STRUCTURE_MINIMALE
    )
    if existants:
        return existants[0].id

    verdict = evaluer_cascade(resoudre)
    if not verdict.reussi:
        raise RuntimeError(f"le solveur minimal n'a pas passé la cascade : {verdict.echecs}")

    code_source = Path(_module_solveur_minimal.__file__).read_text(encoding="utf-8")
    return registre.enregistrer_solveur(
        code_source=code_source,
        structure_contraintes=STRUCTURE_MINIMALE,
        verdict_cascade=verdict,
        instance_id=instance_id,
        client_id=client_id,
    )


def main() -> None:
    client_id = sys.argv[1] if len(sys.argv) > 1 else "demo"
    id_solveur = enregistrer(Registre(), client_id=client_id)
    print(f"solveur de référence enregistré : id={id_solveur!r}, client_id={client_id!r}")


if __name__ == "__main__":
    main()
