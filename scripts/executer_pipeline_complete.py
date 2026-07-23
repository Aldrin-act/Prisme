"""
Script pour exécuter la pipeline complète PRISME sur une instance donnée.

Ce script prend une instance TRCO enrichie et exécute le workflow complet :
1. Enregistre un solveur de référence
2. Ingère l'instance via l'API
3. Exécute le solveur
4. Récupère et affiche le planning

Usage:
    python -m scripts.executer_pipeline_complete --instance <chemin_instance.json>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

from api.dependencies import obtenir_registre
from dsl.schema import InstanceTRCO
from scripts.enregistrer_solveur_reference import enregistrer


def charger_instance(chemin: Path) -> InstanceTRCO:
    """Charge une instance TRCO depuis un fichier JSON."""
    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)
    return InstanceTRCO(**data)


def executer_pipeline(chemin_instance: Path, client_id: str = "pipeline_user", api_url: str = "http://127.0.0.1:8000"):
    """Exécute la pipeline complète pour une instance donnée."""

    print("=" * 80)
    print("PIPELINE COMPLETE PRISME")
    print("=" * 80)

    # 1. Enregistrer un solveur de référence
    print("\n[1/5] Enregistrement du solveur de référence...")
    try:
        registre = obtenir_registre()
        id_solveur = enregistrer(registre, client_id=client_id)
        print(f"      [OK] Solveur enregistre avec l'ID: {id_solveur}")
    except Exception as e:
        print(f"      [ERREUR] Impossible d'enregistrer le solveur: {e}")
        return

    # 2. Charger l'instance
    print(f"\n[2/5] Chargement de l'instance depuis {chemin_instance.name}...")
    try:
        instance = charger_instance(chemin_instance)
        print(f"      [OK] Instance chargee:")
        print(f"           - {len(instance.taches)} taches")
        print(f"           - {len(instance.ressources)} ressources")
        print(f"           - {len(instance.contraintes)} contraintes")
        print(f"           - {len(instance.objectifs)} objectif(s)")
    except Exception as e:
        print(f"      [ERREUR] Impossible de charger l'instance: {e}")
        return

    # 3. Ingérer l'instance via l'API
    print(f"\n[3/5] Ingestion de l'instance via l'API ({api_url})...")
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{api_url}/ingestion/{client_id}",
                json=instance.model_dump(mode="json")
            )
            response.raise_for_status()
            result = response.json()
            instance_id = result["instance_id"]
            print(f"      [OK] Instance ingeree avec l'ID: {instance_id}")
    except Exception as e:
        print(f"      [ERREUR] Echec de l'ingestion: {e}")
        return

    # 4. Exécuter le solveur
    print(f"\n[4/5] Execution du solveur...")
    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{api_url}/execution/{instance_id}",
                params={"client_id": client_id}
            )
            response.raise_for_status()
            result = response.json()
            execution_id = result["execution_id"]
            reussi = result["reussi"]

            if reussi:
                print(f"      [OK] Execution reussie avec l'ID: {execution_id}")
            else:
                print(f"      [ECHEC] Execution echouee (ID: {execution_id})")
                if "erreur" in result:
                    print(f"              Erreur: {result['erreur']}")
                return
    except Exception as e:
        print(f"      [ERREUR] Echec de l'execution: {e}")
        return

    # 5. Récupérer le planning
    print(f"\n[5/5] Recuperation du planning...")
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{api_url}/planning/{execution_id}")
            response.raise_for_status()
            planning_data = response.json()

            print(f"      [OK] Planning recupere")
            print("\n" + "=" * 80)
            print("PLANNING OBTENU")
            print("=" * 80)
            print(json.dumps(planning_data, indent=2, ensure_ascii=False))

            # Calculer et afficher le makespan
            if "operations" in planning_data and planning_data["operations"]:
                operations = planning_data["operations"]
                # Trouver la fin maximale
                max_fin = 0
                for op in operations:
                    debut = op["debut"]
                    # Trouver la durée dans les contraintes
                    tache_id = op["tache"]
                    ressource_id = op["ressource"]

                    # Chercher la durée dans les contraintes de l'instance
                    duree = 0
                    for contrainte in instance.contraintes:
                        if (contrainte.type == "compatibilite_ressource_tache" and
                            contrainte.tache == tache_id and
                            contrainte.ressource == ressource_id):
                            duree = contrainte.duree
                            break

                    fin = debut + duree
                    max_fin = max(max_fin, fin)

                print("\n" + "=" * 80)
                print(f"MAKESPAN: {max_fin} minutes")
                print("=" * 80)

    except Exception as e:
        print(f"      [ERREUR] Impossible de recuperer le planning: {e}")
        return

    # 6. Bonus : récupérer le code source du solveur (audit)
    print(f"\n[BONUS] Code source du solveur (audit)...")
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{api_url}/audit/{execution_id}")
            response.raise_for_status()
            audit_data = response.json()

            code_source = audit_data.get("code_source", "")
            print(f"        Code source disponible: {len(code_source)} caracteres")

            # Sauvegarder le code source dans un fichier
            output_dir = Path("data/solveurs_generes")
            output_dir.mkdir(parents=True, exist_ok=True)
            code_path = output_dir / f"solveur_{execution_id}.py"

            with open(code_path, "w", encoding="utf-8") as f:
                f.write(code_source)

            print(f"        Code sauvegarde dans: {code_path}")
    except Exception as e:
        print(f"        [INFO] Code source non disponible: {e}")

    print("\n" + "=" * 80)
    print("PIPELINE COMPLETE TERMINEE AVEC SUCCES")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Execute la pipeline complete PRISME sur une instance TRCO"
    )
    parser.add_argument(
        "--instance",
        type=Path,
        required=True,
        help="Chemin vers l'instance TRCO enrichie (JSON)"
    )
    parser.add_argument(
        "--client-id",
        type=str,
        default="pipeline_user",
        help="Identifiant du client (defaut: pipeline_user)"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default="http://127.0.0.1:8000",
        help="URL de l'API PRISME (defaut: http://127.0.0.1:8000)"
    )

    args = parser.parse_args()

    if not args.instance.exists():
        print(f"ERREUR: Le fichier {args.instance} n'existe pas")
        return

    executer_pipeline(args.instance, args.client_id, args.api_url)


if __name__ == "__main__":
    main()
