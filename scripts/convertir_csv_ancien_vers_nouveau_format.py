#!/usr/bin/env python3
"""
Script de conversion des fichiers CSV de l'ancien format (2 fichiers)
vers le nouveau format (3 fichiers) compatible avec l'adaptateur csv_import.

Ancien format:
- <nom>_operations.csv (code_operation, duree_jours, poste_id, operation_precedente)
- <nom>_postes.csv (code_poste)

Nouveau format:
- taches.csv (id, nom)
- ressources.csv (id, nom, competences)
- contraintes.csv (type, tache_avant, tache_apres, tache, ressource, duree_jours, competence)
"""

import csv
from pathlib import Path


def convertir_secteur(dossier: Path, nom_base: str):
    """Convertit un secteur de l'ancien vers le nouveau format."""
    print(f"Conversion de {nom_base}...")

    # Lire l'ancien format
    ancien_operations = dossier / f"{nom_base}_operations.csv"
    ancien_postes = dossier / f"{nom_base}_postes.csv"

    if not ancien_operations.exists() or not ancien_postes.exists():
        print("  SKIP: Fichiers anciens introuvables")
        return

    # Lire operations
    with open(ancien_operations, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        operations = list(reader)

    # Lire postes
    with open(ancien_postes, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        postes = list(reader)

    # Créer taches.csv
    with open(dossier / "taches.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "nom"])
        for op in operations:
            code = op["code_operation"]
            nom = op.get("nom", code.replace("_", " ").title())
            writer.writerow([code, nom])

    # Créer ressources.csv (avec compétences déduites du nom)
    with open(dossier / "ressources.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "nom", "competences"])
        for poste in postes:
            code = poste["code_poste"]
            # Déduire nom et compétence du code
            nom = code.replace("_", " ").title()
            # Compétence = première partie du code en minuscules
            competence = code.split("_")[0].lower()
            writer.writerow([code, nom, competence])

    # Créer contraintes.csv
    with open(dossier / "contraintes.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["type", "tache_avant", "tache_apres", "tache", "ressource", "duree_jours", "competence"])

        # Contraintes de précédence
        for op in operations:
            if op["operation_precedente"]:
                writer.writerow(["precedence", op["operation_precedente"], op["code_operation"], "", "", "", ""])

        # Contraintes de compatibilité
        for op in operations:
            writer.writerow(
                [
                    "compatibilite_ressource_tache",
                    "",
                    "",
                    op["code_operation"],
                    op["poste_id"],
                    op["duree_jours"],
                    "",
                ]
            )

    # Supprimer anciens fichiers
    ancien_operations.unlink()
    ancien_postes.unlink()

    print(f"  OK: {nom_base} converti")


def main():
    """Point d'entrée."""
    base = Path(__file__).parent.parent / "data" / "donnees_brutes" / "csv"

    conversions = [
        (base / "industrie_manufacturiere" / "assemblage_electronique", "assemblage_electronique"),
        (base / "industrie_manufacturiere" / "imprimerie", "imprimerie"),
        (base / "industrie_manufacturiere" / "production_agroalimentaire", "production_agroalimentaire"),
        (base / "services" / "centre_appels", "centre_appels"),
        (base / "services" / "maintenance_industrielle", "maintenance_industrielle"),
    ]

    print("Conversion des fichiers CSV vers le nouveau format...\n")

    for dossier, nom in conversions:
        if dossier.exists():
            convertir_secteur(dossier, nom)
        else:
            print(f"SKIP: {nom} (dossier inexistant)")

    print("\nConversion terminée!")


if __name__ == "__main__":
    main()
