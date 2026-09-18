"""Génère le gabarit CSV d'ingestion T-R-C-O — trois fichiers séparés
(Tâches, Ressources, Contraintes), la version CSV de
`scripts/generer_gabarit_ingestion.py` (xlsx) pour qui préfère exporter/
remplir des CSV plutôt qu'un classeur Excel. Chaque fichier est ingéré tel
quel via `POST /adapters/csv/{client_id}` (`adapters/csv_import/`), qui lit
exactement les colonnes produites ici.

À relancer si les règles du DSL (`dsl/schema/`) changent — et si les noms de
colonnes changent, mettre à jour `adapters/csv_import/traducteur.py` en même
temps, les deux doivent rester en accord.

Aucun gabarit ne porte de durée : elle se fixe à la commande, tâche par tâche
(`durees_taches`). Seul `commandes.csv` (`date_limite`) porte un nombre de
jours ou d'heures, d'où sa variante `commandes_heures.csv`, à ingérer avec
`unite_temps=heures` ; `contraintes.csv` existe en deux variantes par simple
cohérence de nommage, son contenu étant identique. `taches.csv` et
`ressources.csv` servent les deux unités tels quels.

Le frontend (page Données, formulaire d'ingestion) sert sa propre copie de
ces gabarits en téléchargement direct — `Front/prismatron-solver-forge/public/
gabarits/` — jamais lue dynamiquement depuis `docs/dsl/` (le frontend peut être
déployé sans le dépôt Python à côté). Recopier manuellement après
régénération, ce script ne le fait pas lui-même.

    uv run python -m scripts.generer_gabarit_csv
"""

from __future__ import annotations

import csv
from pathlib import Path

DOSSIER_SORTIE = Path(__file__).resolve().parent.parent / "docs" / "dsl" / "gabarit_csv"

# Seule la date limite d'une commande dépend de l'unité — la variante heures n'est pas la
# variante jours ×24, juste un ordre de grandeur plausible en heures.
EXEMPLES_PAR_UNITE = {
    "jours": {"date_limite": "10"},
    "heures": {"date_limite": "24"},
}


def construire(dossier_sortie: Path) -> None:
    dossier_sortie.mkdir(parents=True, exist_ok=True)

    # `competences` optionnel, laissé vide ici : une compatibilité dérivée par compétence reprend
    # la durée déclarée sur la tâche (l'estimation automatique a été retirée de l'ingestion), d'où
    # la compatibilité explicite plus bas plutôt qu'une dérivation dans ce gabarit.
    # `heures_par_jour` optionnel : durée de travail quotidienne (1 à 24 h). Vide = ressource
    # disponible en continu ; renseignée, l'ingestion en dérive une indisponibilité récurrente
    # (`adapters/heures_travail.py`), uniquement pour une instance en heures.
    with (dossier_sortie / "ressources.csv").open("w", newline="", encoding="utf-8") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["id", "nom", "competences", "heures_par_jour"])
        # Valeur laissée vide : un gabarit de départ documente la colonne sans imposer un horaire
        # (renseignée, elle dériverait aussitôt une indisponibilité et un avertissement).
        ecrivain.writerow(["R1", "Decoupeuse", "", ""])

    # Aucune durée sur la tâche : l'atelier décrit ce qui peut s'exécuter où, la commande dit
    # combien de temps ça prend.
    with (dossier_sortie / "taches.csv").open("w", newline="", encoding="utf-8") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["id", "nom"])
        ecrivain.writerow(["T1", "Decoupe"])
        ecrivain.writerow(["T2", "Assemblage"])

    for unite, suffixe in (("jours", ""), ("heures", "_heures")):
        exemple = EXEMPLES_PAR_UNITE[unite]

        # Compatibilité déclarée sans durée : aucun fichier d'ingestion n'en porte, elle se fixe
        # à la commande, tâche par tâche (voir `adapters/csv_import/traducteur.py`).
        with (dossier_sortie / f"contraintes{suffixe}.csv").open("w", newline="", encoding="utf-8") as f:
            ecrivain = csv.writer(f)
            ecrivain.writerow(["type", "tache_avant", "tache_apres", "tache", "ressource", "competence"])
            ecrivain.writerow(["precedence", "T1", "T2", "", "", ""])
            ecrivain.writerow(["compatibilite_ressource_tache", "", "", "T1", "R1", ""])
            ecrivain.writerow(["compatibilite_ressource_tache", "", "", "T2", "R1", ""])

        # `taches` : liste de tâches liées séparée par `;`, même convention que
        # `competences` sur ressources.csv. `date_limite` relative, dans l'unité de
        # l'instance (jamais une date calendaire, voir CLAUDE.md) — dérive une
        # Echeance par tâche liée, sauf si déjà explicite dans contraintes.csv.
        with (dossier_sortie / f"commandes{suffixe}.csv").open("w", newline="", encoding="utf-8") as f:
            ecrivain = csv.writer(f)
            ecrivain.writerow(["id", "taches", "client", "date_limite"])
            ecrivain.writerow(["CMD1", "T1;T2", "Client A", exemple["date_limite"]])


def main() -> None:
    construire(DOSSIER_SORTIE)
    print("écrit :", DOSSIER_SORTIE)


if __name__ == "__main__":
    main()
