"""Mesure le taux de succès brut de la génération à tir unique (Étape 4).

Lance N tentatives indépendantes (un seul appel LLM chacune, sans boucle de
réparation) et rapporte, pour chacune, la validation statique, l'exécution,
et le verdict de la cascade complète (Étape 5). Le taux importe peu à ce
stade — l'objectif est de mesurer le point de départ avant toute boucle
generate-test-repair (Étape 6).

Nécessite une clé d'API valide pour le fournisseur choisi
(`PRISME_LLM_PROVIDER`, défaut "anthropic" -> `ANTHROPIC_API_KEY`) et
l'extra `llm` installé (`pip install -e .[llm]`).

Usage : python scripts/mesurer_taux_succes_generation.py [n_essais]
"""

from __future__ import annotations

import sys

from generation.agents.client_llm import construire_appel_llm
from generation.tentative_unique import tenter_generation_unique


def main() -> None:
    n_essais = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    appel_llm = construire_appel_llm()

    reussites = 0
    for indice in range(n_essais):
        resultat = tenter_generation_unique(appel_llm)
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
