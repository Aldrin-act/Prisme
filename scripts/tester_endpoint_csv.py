"""Script de test pour l'endpoint backend CSV local.

Ce script teste l'endpoint POST /adapters/csv-local/ingerer qui permet
de convertir des fichiers CSV locaux en instances TRCO via l'API.

Usage:
    # Démarrer l'API d'abord dans un autre terminal
    uv run uvicorn api.app:app --reload

    # Puis exécuter ce script
    uv run python -m scripts.tester_endpoint_csv
"""

from __future__ import annotations

import requests

# Configuration
API_BASE_URL = "http://localhost:8000"
CLIENT_ID = "test_client"

# Chemins relatifs depuis la racine du projet
DOSSIERS_TEST = [
    "data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique",
    "data/donnees_brutes/csv/industrie_manufacturiere/atelier_mecanique",
    "data/donnees_brutes/csv/services/centre_appels",
]


def obtenir_token() -> str:
    """Obtient un token JWT pour l'authentification (en mode dev)."""
    # En mode dev, créer un utilisateur de test ou utiliser les credentials existants
    # Pour ce test, on suppose que l'auth est désactivée (PRISME_AUTH_DESACTIVEE=1)
    # ou qu'on a un token valide

    # Si l'auth est activée, décommenter et adapter :
    # response = requests.post(
    #     f"{API_BASE_URL}/auth/login",
    #     json={"username": "admin", "password": "admin"}
    # )
    # return response.json()["access_token"]

    return "dummy_token"  # Pour tests avec auth désactivée


def tester_endpoint_csv_local(chemin_dossier: str, token: str) -> dict | None:
    """Teste l'endpoint CSV local avec un dossier spécifique."""
    print(f"\n{'=' * 80}")
    print(f"Test du dossier: {chemin_dossier}")
    print(f"{'=' * 80}")

    headers = {"Authorization": f"Bearer {token}"} if token != "dummy_token" else {}

    payload = {"chemin_dossier": chemin_dossier, "client_id": CLIENT_ID}

    try:
        response = requests.post(f"{API_BASE_URL}/adapters/csv-local/ingerer", json=payload, headers=headers)

        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            resultat = response.json()
            print("\n[OK] Conversion reussie!")
            print(f"\nInstance ID: {resultat['instance_id']}")
            print(f"Structure contraintes: {resultat['structure_contraintes']}")
            print("\nStatistiques:")
            stats = resultat["statistiques"]
            print(f"  - Taches:      {stats['taches']}")
            print(f"  - Ressources:  {stats['ressources']}")
            print(f"  - Contraintes: {stats['contraintes']}")
            print(f"  - Objectifs:   {stats['objectifs']}")
            return resultat
        else:
            print(f"\n[ERREUR] Status {response.status_code}")
            print(f"Detail: {response.json().get('detail', 'Aucun detail')}")
            return None

    except requests.exceptions.ConnectionError:
        print("\n[ERREUR] Impossible de se connecter a l'API")
        print("Verifiez que l'API est demarree avec: uv run uvicorn api.app:app --reload")
        return None
    except Exception as e:
        print(f"\n[ERREUR] Exception: {e}")
        return None


def tester_recuperation_instance(instance_id: str, token: str) -> None:
    """Teste la récupération d'une instance créée."""
    print(f"\n{'=' * 80}")
    print(f"Test de recuperation de l'instance: {instance_id}")
    print(f"{'=' * 80}")

    headers = {"Authorization": f"Bearer {token}"} if token != "dummy_token" else {}

    try:
        response = requests.get(f"{API_BASE_URL}/ingestion/{instance_id}", headers=headers)

        if response.status_code == 200:
            instance = response.json()
            print("\n[OK] Instance recuperee!")
            print(f"\nClient ID: {instance['client_id']}")
            print(f"Nombre de taches: {len(instance['taches'])}")
            print(f"Nombre de ressources: {len(instance['ressources'])}")

            # Afficher les premières tâches
            print("\nPremieres taches:")
            for tache in instance["taches"][:3]:
                print(f"  - {tache['id']}: {tache.get('nom', 'Sans nom')}")

        else:
            print(f"[ERREUR] Status {response.status_code}: {response.json()}")

    except Exception as e:
        print(f"[ERREUR] {e}")


def main():
    """Test principal."""
    print("Test de l'endpoint POST /adapters/csv-local/ingerer")
    print("=" * 80)

    # Vérifier que l'API est accessible
    try:
        response = requests.get(f"{API_BASE_URL}/docs")
        if response.status_code != 200:
            print("[AVERTISSEMENT] L'API ne semble pas repondre correctement")
    except requests.exceptions.ConnectionError:
        print("[ERREUR] L'API n'est pas accessible.")
        print("Veuillez d'abord demarrer l'API avec:")
        print("  uv run uvicorn api.app:app --reload")
        return

    token = obtenir_token()

    resultats = []
    for dossier in DOSSIERS_TEST:
        resultat = tester_endpoint_csv_local(dossier, token)
        if resultat:
            resultats.append(resultat)

    # Tester la récupération de la première instance créée
    if resultats:
        print("\n" + "=" * 80)
        print("Test de recuperation d'instance")
        tester_recuperation_instance(resultats[0]["instance_id"], token)

    # Résumé
    print("\n" + "=" * 80)
    print("Resume des tests")
    print("=" * 80)
    print(f"Reussites: {len(resultats)}/{len(DOSSIERS_TEST)}")

    if len(resultats) == len(DOSSIERS_TEST):
        print("\n[OK] Tous les tests ont reussi!")
    else:
        print(f"\n[ATTENTION] {len(DOSSIERS_TEST) - len(resultats)} test(s) ont echoue")


if __name__ == "__main__":
    main()
