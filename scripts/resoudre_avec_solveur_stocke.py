"""
Résout une instance avec un solveur stocké dans le registry.

Ce script charge un solveur depuis solver_store/artifacts/ et l'utilise
pour résoudre une instance TRCO.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dsl.schema import InstanceTRCO
from solver_store.registry import Registre


def lister_solveurs():
    """Liste tous les solveurs disponibles dans le store."""
    artifacts_dir = Path("solver_store/artifacts")

    solveurs = []
    for dir_path in artifacts_dir.iterdir():
        if dir_path.is_dir() and dir_path.name != ".gitkeep":
            solveur_path = dir_path / "solveur.py"
            if solveur_path.exists():
                taille = solveur_path.stat().st_size
                lignes = len(solveur_path.read_text(encoding="utf-8").splitlines())
                solveurs.append({
                    "id": dir_path.name,
                    "path": solveur_path,
                    "taille": taille,
                    "lignes": lignes
                })

    return solveurs


def main():
    parser = argparse.ArgumentParser(
        description="Résout une instance avec un solveur stocké"
    )
    parser.add_argument(
        "--instance",
        type=Path,
        required=True,
        help="Chemin vers l'instance TRCO (JSON)"
    )
    parser.add_argument(
        "--solveur-id",
        type=str,
        help="ID du solveur à utiliser (optionnel, utilise le premier disponible sinon)"
    )
    parser.add_argument(
        "--lister",
        action="store_true",
        help="Lister les solveurs disponibles et quitter"
    )

    args = parser.parse_args()

    # Lister les solveurs si demandé
    if args.lister:
        solveurs = lister_solveurs()
        print(f"\nSolveurs disponibles : {len(solveurs)}")
        print("-" * 80)
        for s in solveurs:
            print(f"\nID     : {s['id']}")
            print(f"Taille : {s['taille']} octets ({s['lignes']} lignes)")
            print(f"Path   : {s['path']}")
        print()
        return

    print("=" * 80)
    print("RESOLUTION AVEC SOLVEUR STOCKE (IA)")
    print("=" * 80)

    # Charger l'instance
    print(f"\n[1/4] Chargement de l'instance : {args.instance.name}")
    try:
        with open(args.instance, encoding="utf-8") as f:
            data = json.load(f)
        instance = InstanceTRCO(**data)
        print(f"      [OK] {len(instance.taches)} taches, {len(instance.ressources)} ressources")
    except Exception as e:
        print(f"      [ERREUR] Impossible de charger l'instance : {e}")
        sys.exit(1)

    # Sélectionner un solveur
    print(f"\n[2/4] Selection du solveur...")
    solveurs = lister_solveurs()

    if not solveurs:
        print(f"      [ERREUR] Aucun solveur trouve dans solver_store/artifacts/")
        sys.exit(1)

    if args.solveur_id:
        solveur = next((s for s in solveurs if s["id"] == args.solveur_id), None)
        if not solveur:
            print(f"      [ERREUR] Solveur {args.solveur_id} introuvable")
            print(f"\n      Solveurs disponibles:")
            for s in solveurs:
                print(f"        - {s['id']}")
            sys.exit(1)
    else:
        solveur = solveurs[0]

    print(f"      [OK] Solveur selectionne : {solveur['id']}")
    print(f"           Taille : {solveur['lignes']} lignes")

    # Charger le solveur
    print(f"\n[3/4] Chargement et execution du solveur...")
    try:
        # Lire le code
        code_source = solveur['path'].read_text(encoding="utf-8")

        # Executer le code pour obtenir la fonction resoudre
        namespace = {}
        exec(code_source, namespace)

        if "resoudre" not in namespace:
            print(f"      [ERREUR] Le solveur ne contient pas de fonction 'resoudre'")
            sys.exit(1)

        fonction_resoudre = namespace["resoudre"]

        # Résoudre
        planning = fonction_resoudre(instance)

        if planning is None:
            print(f"      [ECHEC] Le solveur n'a pas trouve de solution")
            sys.exit(1)

        print(f"      [OK] Solution trouvee avec {len(planning.operations)} operations")

    except Exception as e:
        print(f"      [ERREUR] Execution echouee : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Analyser le planning
    print(f"\n[4/4] Analyse du planning...")

    # Créer un dictionnaire pour récupérer les durées
    durees = {}
    for contrainte in instance.contraintes:
        if contrainte.type == "compatibilite_ressource_tache":
            durees[(contrainte.tache, contrainte.ressource)] = contrainte.duree

    # Analyser chaque opération
    details_operations = []
    max_fin = 0

    for op in planning.operations:
        debut = op.debut
        tache_id = op.tache
        ressource_id = op.ressource
        duree = durees.get((tache_id, ressource_id), 0)
        fin = debut + duree
        max_fin = max(max_fin, fin)

        details_operations.append({
            "tache": tache_id,
            "ressource": ressource_id,
            "debut": debut,
            "duree": duree,
            "fin": fin
        })

    # Afficher le résumé
    print("\n" + "=" * 80)
    print("PLANNING OBTENU (SOLVEUR IA)")
    print("=" * 80)
    print(f"\nMakespan total: {max_fin} minutes ({max_fin / 60:.2f} heures)")
    print(f"Nombre d'operations: {len(planning.operations)}")
    print(f"Solveur utilise: {solveur['id']}")

    print("\nOrdre d'execution:")
    print("-" * 80)
    print(f"{'Operation':<25} {'Ressource':<25} {'Debut':>8} {'Duree':>8} {'Fin':>8}")
    print("-" * 80)

    # Trier par début
    details_operations.sort(key=lambda x: x["debut"])

    for detail in details_operations:
        print(f"{detail['tache']:<25} {detail['ressource']:<25} "
              f"{detail['debut']:>8} {detail['duree']:>8} {detail['fin']:>8}")

    # Sauvegarder
    output_dir = Path("data/plannings_generes")
    output_dir.mkdir(parents=True, exist_ok=True)
    planning_path = output_dir / f"production_agro_solveur_ia_{solveur['id'][:8]}.json"

    planning_data = {
        "instance": str(args.instance),
        "solveur_id": solveur["id"],
        "makespan": max_fin,
        "nb_operations": len(planning.operations),
        "operations": [
            {
                "tache": detail["tache"],
                "ressource": detail["ressource"],
                "debut": detail["debut"],
                "duree": detail["duree"],
                "fin": detail["fin"]
            }
            for detail in details_operations
        ]
    }

    with open(planning_path, "w", encoding="utf-8") as f:
        json.dump(planning_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 80)
    print(f"Planning sauvegarde : {planning_path}")
    print("=" * 80)
    print("\nCe planning a ete genere par un SOLVEUR IA, pas par le solveur minimal.")
    print()


if __name__ == "__main__":
    main()
