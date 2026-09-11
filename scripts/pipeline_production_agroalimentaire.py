"""
Script de démonstration de la pipeline complète pour l'instance production agroalimentaire.

Ce script reprend le workflow de demo_bout_en_bout.py mais avec l'instance
production_agroalimentaire_makespan.json que nous venons de créer.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.app import app
from api.dependencies import obtenir_registre
from dsl.schema import InstanceTRCO
from scripts.enregistrer_solveur_reference import enregistrer

CLIENT_ID = "production_agro"


def main() -> None:
    print("=" * 80)
    print("PIPELINE COMPLETE : PRODUCTION AGROALIMENTAIRE")
    print("=" * 80)

    # Charger l'instance TRCO enrichie
    chemin_instance = Path("data/instances_trco_enrichies/production_agroalimentaire_makespan.json")

    print(f"\n1. Chargement de l'instance depuis {chemin_instance.name}...")
    with open(chemin_instance, encoding="utf-8") as f:
        data = json.load(f)
    instance = InstanceTRCO(**data)
    print(f"   -> {len(instance.taches)} taches, {len(instance.ressources)} ressources")
    print(f"   -> {len(instance.contraintes)} contraintes")
    print(f"   -> {len(instance.objectifs)} objectif(s)")

    # Afficher les tâches
    print("\n   Taches:")
    for tache in instance.taches:
        print(f"     - {tache.id}: {tache.nom}")

    # Enregistrer un solveur de référence
    print("\n2. Enregistrement du solveur de référence dans le store...")
    registre = obtenir_registre()
    id_solveur = enregistrer(registre, client_id=CLIENT_ID)
    print(f"   -> id_solveur = {id_solveur}")

    # Utiliser TestClient pour interagir avec l'API
    client = TestClient(app)

    # Ingestion
    print("\n3. POST /ingestion (validation amont)...")
    reponse = client.post(f"/ingestion/{CLIENT_ID}", json=instance.model_dump(mode="json"))
    reponse.raise_for_status()
    instance_id = reponse.json()["instance_id"]
    print(f"   -> instance_id = {instance_id}")

    # Exécution
    print("\n4. POST /execution (sandbox + solveur)...")
    reponse = client.post(f"/execution/{instance_id}", params={"client_id": CLIENT_ID})
    reponse.raise_for_status()
    corps_execution = reponse.json()
    execution_id = corps_execution["execution_id"]
    reussi = corps_execution["reussi"]
    print(f"   -> execution_id = {execution_id}, reussi = {reussi}")

    if not reussi:
        print("   ERREUR: L'execution a echoue")
        if "erreur" in corps_execution:
            print(f"   Details: {corps_execution['erreur']}")
        return

    # Récupération du planning
    print("\n5. GET /planning (canal opérationnel)...")
    reponse = client.get(f"/planning/{execution_id}")
    reponse.raise_for_status()
    planning_data = reponse.json()

    print("\n" + "=" * 80)
    print("PLANNING OBTENU")
    print("=" * 80)
    print(json.dumps(planning_data, indent=2, ensure_ascii=False))

    # Calculer le makespan
    if "operations" in planning_data and planning_data["operations"]:
        operations = planning_data["operations"]

        # Créer un dictionnaire pour récupérer les durées
        durees = {}
        for contrainte in instance.contraintes:
            if contrainte.type == "compatibilite_ressource_tache":
                durees[(contrainte.tache, contrainte.ressource)] = contrainte.duree

        # Calculer la fin de chaque opération
        max_fin = 0
        details_operations = []

        for op in operations:
            debut = op["debut"]
            tache_id = op["tache"]
            ressource_id = op["ressource"]
            duree = durees.get((tache_id, ressource_id), 0)
            fin = debut + duree
            max_fin = max(max_fin, fin)

            # Récupérer le nom de la tâche
            nom_tache = next((t.nom for t in instance.taches if t.id == tache_id), tache_id)

            details_operations.append(
                {"tache": nom_tache, "ressource": ressource_id, "debut": debut, "duree": duree, "fin": fin}
            )

        # Afficher le résumé
        print("\n" + "=" * 80)
        print("RESUME DU PLANNING")
        print("=" * 80)
        print(f"\nMakespan total: {max_fin} minutes ({max_fin / 60:.2f} heures)")
        print(f"Nombre d'operations: {len(operations)}")

        print("\nOrdre d'execution:")
        print("-" * 80)
        print(f"{'Operation':<25} {'Ressource':<20} {'Debut':>8} {'Duree':>8} {'Fin':>8}")
        print("-" * 80)

        # Trier par début
        details_operations.sort(key=lambda x: x["debut"])

        for detail in details_operations:
            print(
                f"{detail['tache']:<25} {detail['ressource']:<20} "
                f"{detail['debut']:>8} {detail['duree']:>8} {detail['fin']:>8}"
            )

    # Audit (code source)
    print("\n" + "=" * 80)
    print("6. GET /audit (canal d'audit, transparence)...")
    reponse = client.get(f"/audit/{execution_id}")
    reponse.raise_for_status()
    audit_data = reponse.json()
    code_source = audit_data.get("code_source", "")
    print(f"   -> Code source du solveur: {len(code_source)} caracteres")

    # Sauvegarder le code source
    output_dir = Path("data/solveurs_generes")
    output_dir.mkdir(parents=True, exist_ok=True)
    code_path = output_dir / f"solveur_production_agro_{execution_id}.py"

    with open(code_path, "w", encoding="utf-8") as f:
        f.write(code_source)

    print(f"   -> Code sauvegarde dans: {code_path}")

    print("\n" + "=" * 80)
    print("PIPELINE COMPLETE TERMINEE AVEC SUCCES")
    print("=" * 80)


if __name__ == "__main__":
    main()
