"""Mesure le taux de succès brut de la génération à tir unique (Étape 4).

Lance N tentatives indépendantes (un seul appel LLM chacune, sans boucle de
réparation) et rapporte, pour chacune, la validation statique, l'exécution,
et le verdict de la cascade complète (Étape 5). Le taux importe peu à ce
stade — l'objectif est de mesurer le point de départ avant toute boucle
generate-test-repair (Étape 6).

Nécessite une clé d'API Kimi valide (`KIMI_API_KEY`) et l'extra `llm`
installé (`uv sync --extra llm`).

Usage : python scripts/mesurer_taux_succes_generation.py [n_essais]
"""

from __future__ import annotations

import sys
from pathlib import Path

# Même motif que les autres scripts (`generer_avec_boucle.py`, `tester_analyste.py`) : sans ceci,
# les clés d'API déclarées dans `.env` restent invisibles à `os.environ`, et le fournisseur
# reçoit une clé absente/vide plutôt que la vraie (401 côté fournisseur, pas une erreur explicite
# côté script — constaté en conditions réelles).
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

from generation.agents.client_llm import construire_modele
from generation.tentative_unique import tenter_generation_unique


def main() -> None:
    n_essais = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    modele = construire_modele()

    reussites = 0
    for indice in range(n_essais):
        resultat = tenter_generation_unique(modele)
        statut = "OK" if resultat.reussi else "ECHEC"
        print(f"essai {indice + 1}/{n_essais} : {statut}")

        if not resultat.validation_statique.valide:
            print(f"  validation statique refusée : {resultat.validation_statique.violations}")
        elif resultat.erreur_execution is not None:
            print(f"  erreur d'exécution : {resultat.erreur_execution}")
        elif resultat.verdict_cascade is not None and not resultat.verdict_cascade.reussi:
            for echec in resultat.verdict_cascade.echecs:
                print(f"  cascade — {echec.nom} : {echec.brique_en_echec} ({echec.details})")

        if resultat.reussi:
            reussites += 1

    print(f"\ntaux de succès brut : {reussites}/{n_essais} ({reussites / n_essais:.0%})")


if __name__ == "__main__":
    main()
