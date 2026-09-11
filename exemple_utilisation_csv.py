"""Exemple d'utilisation de la fonction csv_vers_instance.

Ce script montre comment convertir facilement des fichiers CSV en instances TRCO
en utilisant la fonction csv_vers_instance.
"""

from __future__ import annotations

import json

from scripts.convertir_csv_vers_instance import csv_vers_instance


def exemple_simple():
    """Exemple simple: convertir un dossier CSV en instance TRCO."""
    print("=" * 80)
    print("Exemple 1: Conversion simple d'un dossier CSV")
    print("=" * 80)

    # Chemin vers le dossier contenant les CSV
    dossier = "data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique"

    # Convertir en instance TRCO
    instance = csv_vers_instance(dossier)

    # Afficher les statistiques
    print(f"\nDossier: {dossier}")
    print(f"  - Taches: {len(instance.taches)}")
    print(f"  - Ressources: {len(instance.ressources)}")
    print(f"  - Contraintes: {len(instance.contraintes)}")
    print(f"  - Objectifs: {len(instance.objectifs)}")

    # Afficher le détail des tâches
    print("\nTaches:")
    for tache in instance.taches:
        print(f"  - {tache.id}: {tache.nom}")

    # Afficher le détail des ressources
    print("\nRessources:")
    for ressource in instance.ressources:
        competences_str = ", ".join(ressource.competences) if ressource.competences else "aucune"
        print(f"  - {ressource.id}: {ressource.nom} (competences: {competences_str})")

    # Compter les types de contraintes
    types_contraintes = {}
    for contrainte in instance.contraintes:
        type_contrainte = contrainte.__class__.__name__
        types_contraintes[type_contrainte] = types_contraintes.get(type_contrainte, 0) + 1

    print("\nTypes de contraintes:")
    for type_c, count in sorted(types_contraintes.items()):
        print(f"  - {type_c}: {count}")


def exemple_tous_les_dossiers():
    """Exemple: convertir plusieurs dossiers et comparer."""
    print("\n" + "=" * 80)
    print("Exemple 2: Conversion de plusieurs dossiers")
    print("=" * 80)

    dossiers = [
        "data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique",
        "data/donnees_brutes/csv/industrie_manufacturiere/atelier_mecanique",
        "data/donnees_brutes/csv/services/centre_appels",
    ]

    resultats = []

    for dossier in dossiers:
        try:
            instance = csv_vers_instance(dossier)
            resultats.append(
                {
                    "dossier": dossier.split("/")[-1],
                    "taches": len(instance.taches),
                    "ressources": len(instance.ressources),
                    "contraintes": len(instance.contraintes),
                }
            )
        except Exception as e:
            print(f"Erreur pour {dossier}: {e}")

    # Afficher un tableau comparatif
    print("\nTableau comparatif:")
    print(f"{'Dossier':<30} {'Taches':>10} {'Ressources':>12} {'Contraintes':>13}")
    print("-" * 80)
    for r in resultats:
        print(f"{r['dossier']:<30} {r['taches']:>10} {r['ressources']:>12} {r['contraintes']:>13}")


def exemple_export_json():
    """Exemple: exporter une instance en JSON."""
    print("\n" + "=" * 80)
    print("Exemple 3: Export JSON")
    print("=" * 80)

    dossier = "data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique"
    instance = csv_vers_instance(dossier)

    # Convertir en dictionnaire JSON
    instance_dict = instance.model_dump(mode="json")

    # Afficher le JSON (tronqué pour l'exemple)
    json_str = json.dumps(instance_dict, indent=2, ensure_ascii=False)
    print("\nPremiers 800 caracteres du JSON:")
    print(json_str[:800] + "...")

    # Pour sauvegarder dans un fichier:
    # with open("instance.json", "w", encoding="utf-8") as f:
    #     json.dump(instance_dict, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    # Exécuter tous les exemples
    exemple_simple()
    exemple_tous_les_dossiers()
    exemple_export_json()

    print("\n" + "=" * 80)
    print("Tous les exemples ont ete executes avec succes!")
    print("=" * 80)
