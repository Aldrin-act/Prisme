"""Exemple d'utilisation de l'API CSV local.

Ce script montre comment utiliser l'endpoint POST /adapters/csv-local/ingerer
pour convertir des fichiers CSV en instances TRCO via l'API backend.

Prérequis:
    1. Démarrer l'API : uv run uvicorn api.app:app --reload
    2. Avoir des fichiers CSV dans un dossier accessible

Usage:
    uv run python exemple_api_csv.py
"""

from __future__ import annotations

import json
from pathlib import Path

import requests

# Configuration de l'API
API_BASE_URL = "http://localhost:8000"
CLIENT_ID = "demo_client"


def verifier_api_disponible() -> bool:
    """Vérifie que l'API est accessible."""
    try:
        response = requests.get(f"{API_BASE_URL}/docs", timeout=2)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def ingerer_csv_local(chemin_dossier: str) -> dict | None:
    """Ingère un dossier CSV via l'API backend.

    Args:
        chemin_dossier: Chemin vers le dossier contenant les CSV

    Returns:
        Réponse de l'API avec instance_id et statistiques, ou None si erreur
    """
    url = f"{API_BASE_URL}/adapters/csv-local/ingerer"

    payload = {"chemin_dossier": chemin_dossier, "client_id": CLIENT_ID}

    try:
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erreur {response.status_code}: {response.json().get('detail')}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Erreur de connexion: {e}")
        return None


def recuperer_instance(instance_id: str) -> dict | None:
    """Récupère les détails complets d'une instance.

    Args:
        instance_id: ID de l'instance à récupérer

    Returns:
        Instance complète avec tâches, ressources, contraintes
    """
    url = f"{API_BASE_URL}/ingestion/{instance_id}"

    try:
        response = requests.get(url, timeout=10)

        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erreur {response.status_code}: {response.json().get('detail')}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"Erreur de connexion: {e}")
        return None


def exemple_simple():
    """Exemple 1: Ingestion simple d'un dossier CSV."""
    print("=" * 80)
    print("Exemple 1: Ingestion simple")
    print("=" * 80)

    chemin = "data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique"

    print(f"\nIngestion du dossier: {chemin}")

    resultat = ingerer_csv_local(chemin)

    if resultat:
        print("\n[OK] Instance creee avec succes!")
        print(f"\nInstance ID: {resultat['instance_id']}")
        print(f"Structure contraintes: {resultat['structure_contraintes']}")
        print("\nStatistiques:")
        stats = resultat["statistiques"]
        for cle, valeur in stats.items():
            print(f"  {cle:15s}: {valeur}")

        return resultat["instance_id"]
    else:
        print("\n[ERREUR] Echec de l'ingestion")
        return None


def exemple_batch():
    """Exemple 2: Ingestion en batch de plusieurs dossiers."""
    print("\n" + "=" * 80)
    print("Exemple 2: Ingestion en batch")
    print("=" * 80)

    dossiers = [
        "data/donnees_brutes/csv/industrie_manufacturiere/atelier_mecanique",
        "data/donnees_brutes/csv/services/centre_appels",
        "data/donnees_brutes/csv/industrie_manufacturiere/imprimerie",
    ]

    instances_creees = []

    for dossier in dossiers:
        nom_dossier = Path(dossier).name
        print(f"\n[{len(instances_creees)+1}/{len(dossiers)}] Traitement: {nom_dossier}")

        resultat = ingerer_csv_local(dossier)

        if resultat:
            instances_creees.append(
                {
                    "dossier": nom_dossier,
                    "instance_id": resultat["instance_id"],
                    "stats": resultat["statistiques"],
                }
            )
            print(f"  [OK] Instance: {resultat['instance_id'][:8]}...")
        else:
            print(f"  [ERREUR] Echec")

    # Résumé
    print(f"\n{'='*80}")
    print(f"Resume: {len(instances_creees)}/{len(dossiers)} reussies")
    print(f"{'='*80}")

    if instances_creees:
        print("\nInstances creees:")
        for item in instances_creees:
            print(f"  - {item['dossier']:<30} {item['instance_id'][:16]}...")

    return [item["instance_id"] for item in instances_creees]


def exemple_recuperation(instance_id: str):
    """Exemple 3: Récupération et exploration d'une instance."""
    print("\n" + "=" * 80)
    print("Exemple 3: Recuperation et exploration")
    print("=" * 80)

    print(f"\nRecuperation de l'instance: {instance_id[:16]}...")

    instance = recuperer_instance(instance_id)

    if not instance:
        print("[ERREUR] Impossible de recuperer l'instance")
        return

    print("\n[OK] Instance recuperee!")
    print(f"\nClient ID: {instance['client_id']}")
    print(f"Structure contraintes: {instance['structure_contraintes']}")

    # Explorer les tâches
    print(f"\nTaches ({len(instance['taches'])}):")
    for i, tache in enumerate(instance["taches"][:5], 1):
        nom = tache.get("nom") or "(sans nom)"
        print(f"  {i}. {tache['id']:20s} - {nom}")

    if len(instance["taches"]) > 5:
        print(f"  ... et {len(instance['taches']) - 5} autres")

    # Explorer les ressources
    print(f"\nRessources ({len(instance['ressources'])}):")
    for i, ressource in enumerate(instance["ressources"][:5], 1):
        nom = ressource.get("nom") or "(sans nom)"
        competences = ", ".join(ressource.get("competences", []))
        comp_str = f" [{competences}]" if competences else ""
        print(f"  {i}. {ressource['id']:20s} - {nom}{comp_str}")

    if len(instance["ressources"]) > 5:
        print(f"  ... et {len(instance['ressources']) - 5} autres")

    # Analyser les contraintes par type
    types_contraintes = {}
    for contrainte in instance["contraintes"]:
        type_c = contrainte["type"]
        types_contraintes[type_c] = types_contraintes.get(type_c, 0) + 1

    print(f"\nTypes de contraintes ({len(instance['contraintes'])}):")
    for type_c, count in sorted(types_contraintes.items()):
        print(f"  - {type_c:30s}: {count}")


def main():
    """Programme principal."""
    print("\nExemple d'utilisation de l'API CSV Local")
    print("=" * 80)

    # Vérifier que l'API est disponible
    print("\nVerification de l'API...")
    if not verifier_api_disponible():
        print("\n[ERREUR] L'API n'est pas accessible!")
        print("\nVeuillez d'abord demarrer l'API avec:")
        print("  uv run uvicorn api.app:app --reload\n")
        return

    print("[OK] API accessible")

    # Exemple 1: Ingestion simple
    instance_id = exemple_simple()

    # Exemple 2: Ingestion en batch
    autres_instances = exemple_batch()

    # Exemple 3: Récupération et exploration
    if instance_id:
        exemple_recuperation(instance_id)

    # Récapitulatif
    print("\n" + "=" * 80)
    print("Recapitulatif")
    print("=" * 80)

    total_instances = 1 + len(autres_instances) if instance_id else len(autres_instances)
    print(f"\nTotal d'instances creees: {total_instances}")

    print("\nProchaines etapes possibles:")
    if instance_id:
        print(f"  - Generer un solveur: POST /generation/{instance_id}")
        print(f"  - Executer: POST /execution/{instance_id}")
        print(f"  - Voir les plannings: GET /planning/{instance_id}")

    print("\n[OK] Tous les exemples executes!")


if __name__ == "__main__":
    main()
