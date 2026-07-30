"""Génère le gabarit CSV d'ingestion T-R-C-O — trois fichiers séparés
(Tâches, Ressources, Contraintes), la version CSV de
`scripts/generer_gabarit_ingestion.py` (xlsx) pour qui préfère exporter/
remplir des CSV plutôt qu'un classeur Excel. Chaque fichier est ingéré tel
quel via `POST /adapters/csv/{client_id}` (`adapters/csv_import/`), qui lit
exactement les colonnes produites ici.

À relancer si les règles du DSL (`dsl/schema/`) changent — et si les noms de
colonnes changent, mettre à jour `adapters/csv_import/traducteur.py` en même
temps, les deux doivent rester en accord.

Le frontend (page Données, import de données brutes) sert sa propre copie de
ces gabarits en téléchargement direct — `Front/prismatron-solver-forge/public/
gabarits/{taches,ressources,contraintes}.csv` — jamais lue dynamiquement
depuis `docs/dsl/` (le frontend peut être déployé sans le dépôt Python à côté).
Recopier manuellement après régénération, ce script ne le fait pas lui-même.

    uv run python -m scripts.generer_gabarit_csv
"""

from __future__ import annotations

import csv
from pathlib import Path

DOSSIER_SORTIE = Path(__file__).resolve().parent.parent / "docs" / "dsl" / "gabarit_csv"


def construire(dossier_sortie: Path) -> None:
    dossier_sortie.mkdir(parents=True, exist_ok=True)

    # `duree_estimee_minutes` : nécessaire pour toute tâche dont la
    # compatibilité est dérivée par compétence — c'est le cas de T1 et T2 ici,
    # aucune des deux ne déclare de compatibilite_ressource_tache directement.
    with (dossier_sortie / "taches.csv").open("w", newline="", encoding="utf-8") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["id", "nom", "duree_estimee_minutes"])
        ecrivain.writerow(["T1", "Decoupe", "30"])
        ecrivain.writerow(["T2", "Assemblage", "20"])

    # `competences` : liste séparée par `;` (la virgule est déjà le
    # délimiteur CSV) — R1 sait faire les deux, utilisé pour dériver sa
    # compatibilité avec T1 et T2 sans la saisir à la main.
    with (dossier_sortie / "ressources.csv").open("w", newline="", encoding="utf-8") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["id", "nom", "competences"])
        ecrivain.writerow(["R1", "Decoupeuse", "decoupe;assemblage"])

    # Compatibilité entièrement dérivée par compétence, aucune saisie
    # directe de compatibilite_ressource_tache dans cet exemple (ce type de
    # ligne reste supporté par l'adaptateur, juste pas illustré ici).
    with (dossier_sortie / "contraintes.csv").open("w", newline="", encoding="utf-8") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(
            ["type", "tache_avant", "tache_apres", "tache", "ressource", "duree_minutes", "competence"]
        )
        ecrivain.writerow(["precedence", "T1", "T2", "", "", "", ""])
        ecrivain.writerow(["competence_requise", "", "", "T1", "", "", "decoupe"])
        ecrivain.writerow(["competence_requise", "", "", "T2", "", "", "assemblage"])


def main() -> None:
    construire(DOSSIER_SORTIE)
    print("écrit :", DOSSIER_SORTIE)


if __name__ == "__main__":
    main()
