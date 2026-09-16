"""Génère le gabarit CSV d'ingestion T-R-C-O — trois fichiers séparés
(Tâches, Ressources, Contraintes), la version CSV de
`scripts/generer_gabarit_ingestion.py` (xlsx) pour qui préfère exporter/
remplir des CSV plutôt qu'un classeur Excel. Chaque fichier est ingéré tel
quel via `POST /adapters/csv/{client_id}` (`adapters/csv_import/`), qui lit
exactement les colonnes produites ici.

À relancer si les règles du DSL (`dsl/schema/`) changent — et si les noms de
colonnes changent, mettre à jour `adapters/csv_import/traducteur.py` en même
temps, les deux doivent rester en accord.

Deux variantes d'unité : seuls `contraintes.csv` (colonne de durée) et
`commandes.csv` (`date_limite`) portent un nombre de jours ou d'heures — les
variantes heures s'écrivent `contraintes_heures.csv`/`commandes_heures.csv`
(colonne `duree_heures`, valeurs d'exemple en heures), à ingérer avec
`unite_temps=heures`. Tâches et ressources n'ont aucune durée, une seule
version sert les deux unités.

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

# Valeurs d'exemple par unité : la variante heures n'est pas la variante jours ×24 (des tâches
# de 72 h n'aident personne à comprendre le format), juste un ordre de grandeur plausible en
# heures, avec la même logique — la date limite laisse de la marge après T1 puis T2.
EXEMPLES_PAR_UNITE = {
    "jours": {"duree_t1": "3", "duree_t2": "2", "date_limite": "10"},
    "heures": {"duree_t1": "6", "duree_t2": "4", "date_limite": "24"},
}


def construire(dossier_sortie: Path) -> None:
    dossier_sortie.mkdir(parents=True, exist_ok=True)

    # Aucune durée sur la tâche elle-même (`Tache` n'en a délibérément aucun
    # champ, §4.2 — la durée dépend de la ressource en vrai FJSP flexible) :
    # elle se déclare via compatibilite_ressource_tache, dans contraintes.csv.
    with (dossier_sortie / "taches.csv").open("w", newline="", encoding="utf-8") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["id", "nom"])
        ecrivain.writerow(["T1", "Decoupe"])
        ecrivain.writerow(["T2", "Assemblage"])

    # `competences` optionnel, laissé vide ici : la dérivation par compétence
    # (voir `adapters/csv_import/traducteur.py`) a besoin d'un estimateur ML
    # pour combler la durée d'une tâche sans compatibilité déjà explicite —
    # un gabarit de départ doit rester valide sans en fournir un, d'où la
    # compatibilité explicite ci-dessous plutôt qu'une dérivation ici.
    with (dossier_sortie / "ressources.csv").open("w", newline="", encoding="utf-8") as f:
        ecrivain = csv.writer(f)
        ecrivain.writerow(["id", "nom", "competences"])
        ecrivain.writerow(["R1", "Decoupeuse", ""])

    for unite, suffixe in (("jours", ""), ("heures", "_heures")):
        exemple = EXEMPLES_PAR_UNITE[unite]

        # Compatibilité déclarée explicitement (avec sa durée) pour T1 et T2 —
        # voie fiable et toujours valide, contrairement à la dérivation par
        # compétence qui dépend d'un estimateur ML fourni à l'ingestion. Le nom de
        # la colonne de durée suit l'unité (voir `adapters/csv_import/traducteur.py::
        # _colonne_duree`).
        with (dossier_sortie / f"contraintes{suffixe}.csv").open("w", newline="", encoding="utf-8") as f:
            ecrivain = csv.writer(f)
            ecrivain.writerow(
                ["type", "tache_avant", "tache_apres", "tache", "ressource", f"duree_{unite}", "competence"]
            )
            ecrivain.writerow(["precedence", "T1", "T2", "", "", "", ""])
            ecrivain.writerow(["compatibilite_ressource_tache", "", "", "T1", "R1", exemple["duree_t1"], ""])
            ecrivain.writerow(["compatibilite_ressource_tache", "", "", "T2", "R1", exemple["duree_t2"], ""])

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
