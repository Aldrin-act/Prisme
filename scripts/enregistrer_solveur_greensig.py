"""Enregistre dans le store (§7) le solveur génétique déjà généré et validé
par le pipeline multi-agents pour l'instance GreenSig simulée (2165 tâches,
voir `solveur_greensig.py` à la racine — issu de
`scripts/test_pipeline_avec_benchmarker.py`, option 4).

Aucun nouvel appel LLM ici : le code existe déjà, on rejoue seulement la
cascade de validation (§5, avec la tolérance propre à un algorithme
non-CP-SAT — voir `generation.pipeline_multi_agents._parametres_cascade_pour_algorithme`)
pour obtenir un `VerdictCascade` réel à passer à `Registre.enregistrer_solveur`
— le store n'accepte jamais un verdict qu'on n'a pas vérifié.

Usage, depuis la racine du dépôt : python -m scripts.enregistrer_solveur_greensig
"""

from __future__ import annotations

import sys
from pathlib import Path

from generation.executer import executer_code_genere
from generation.pipeline_multi_agents import _parametres_cascade_pour_algorithme
from generation.validation_statique import valider_code_genere
from solver_store.registry import Registre
from validation_engine.cascade import evaluer_cascade

CHEMIN_CODE = Path(__file__).resolve().parent.parent / "solveur_greensig.py"
CLIENT_ID = "greensig"
STRUCTURE_CONTRAINTES = "compatibilite_ressource_tache"  # instance GreenSig : aucune precedence
ALGORITHME = "genetic"  # recommande par le Benchmarker pour cette instance (2165 taches)


def enregistrer(registre: Registre) -> str:
    """Idempotent : réutilise un solveur déjà enregistré pour ce client et
    cette structure plutôt que d'en dupliquer un (même convention que
    `scripts.enregistrer_solveur_reference.enregistrer`)."""
    existants = registre.rechercher_solveurs(client_id=CLIENT_ID, structure_contraintes=STRUCTURE_CONTRAINTES)
    if existants:
        return existants[0].id

    code_source = CHEMIN_CODE.read_text(encoding="utf-8")

    validation = valider_code_genere(code_source)
    if not validation.valide:
        raise RuntimeError(f"validation statique échouée : {validation.violations}")

    solveur = executer_code_genere(code_source)

    tolerance_relative, comparer_affectation = _parametres_cascade_pour_algorithme(ALGORITHME)
    verdict = evaluer_cascade(solveur, tolerance_relative, comparer_affectation)
    if not verdict.reussi:
        raise RuntimeError(f"cascade de validation échouée : {verdict.echecs}")

    return registre.enregistrer_solveur(
        code_source=code_source,
        structure_contraintes=STRUCTURE_CONTRAINTES,
        verdict_cascade=verdict,
        client_id=CLIENT_ID,
    )


def main() -> None:
    if not CHEMIN_CODE.exists():
        print(f"introuvable : {CHEMIN_CODE}")
        sys.exit(1)

    id_solveur = enregistrer(Registre())
    print(f"solveur GreenSig enregistré : id={id_solveur!r}, client_id={CLIENT_ID!r}")


if __name__ == "__main__":
    main()
