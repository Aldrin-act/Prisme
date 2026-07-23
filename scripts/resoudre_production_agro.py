"""
Script simple pour résoudre l'instance production agroalimentaire.

Utilise directement le solveur minimal de référence sans passer par l'API.
"""

from __future__ import annotations

import json
from pathlib import Path

from dsl.schema import InstanceTRCO
from scripts._solveur_minimal import resoudre


def main() -> None:
    print("=" * 80)
    print("RESOLUTION : PRODUCTION AGROALIMENTAIRE")
    print("=" * 80)

    # Charger l'instance TRCO de base (sans enrichissement)
    chemin_instance = Path("data/instances_trco/production_agroalimentaire.json")

    print(f"\n1. Chargement de l'instance depuis {chemin_instance.name}...")
    with open(chemin_instance, encoding="utf-8") as f:
        data = json.load(f)
    instance = InstanceTRCO(**data)

    print(f"   [OK] Instance chargee:")
    print(f"        - {len(instance.taches)} taches")
    print(f"        - {len(instance.ressources)} ressources")
    print(f"        - {len(instance.contraintes)} contraintes")

    # Afficher les tâches
    print("\n   Taches de production:")
    for i, tache in enumerate(instance.taches, 1):
        print(f"      {i}. {tache.id}")

    # Résoudre avec le solveur minimal
    print(f"\n2. Resolution avec le solveur de reference...")
    try:
        planning = resoudre(instance)

        if planning is None:
            print("   [ERREUR] Aucune solution trouvee")
            return

        print(f"   [OK] Solution trouvee avec {len(planning.operations)} operations")

    except Exception as e:
        print(f"   [ERREUR] Echec de la resolution: {e}")
        import traceback
        traceback.print_exc()
        return

    # Analyser le planning
    print("\n3. Analyse du planning...")

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
    print("PLANNING OBTENU")
    print("=" * 80)
    print(f"\nMakespan total: {max_fin} minutes ({max_fin / 60:.2f} heures)")
    print(f"Nombre d'operations: {len(planning.operations)}")

    print("\nOrdre d'execution:")
    print("-" * 80)
    print(f"{'Operation':<25} {'Ressource':<25} {'Debut':>8} {'Duree':>8} {'Fin':>8}")
    print("-" * 80)

    # Trier par début
    details_operations.sort(key=lambda x: x["debut"])

    for detail in details_operations:
        print(f"{detail['tache']:<25} {detail['ressource']:<25} "
              f"{detail['debut']:>8} {detail['duree']:>8} {detail['fin']:>8}")

    # Utilisation des ressources
    print("\n" + "-" * 80)
    print("UTILISATION DES RESSOURCES")
    print("-" * 80)

    ressources_utilisees = {}
    for detail in details_operations:
        ressource = detail['ressource']
        if ressource not in ressources_utilisees:
            ressources_utilisees[ressource] = {
                'nombre_ops': 0,
                'temps_total': 0,
                'operations': []
            }
        ressources_utilisees[ressource]['nombre_ops'] += 1
        ressources_utilisees[ressource]['temps_total'] += detail['duree']
        ressources_utilisees[ressource]['operations'].append(detail['tache'])

    for ressource, stats in sorted(ressources_utilisees.items()):
        taux_utilisation = (stats['temps_total'] / max_fin) * 100 if max_fin > 0 else 0
        print(f"\n{ressource}:")
        print(f"  - Operations: {stats['nombre_ops']}")
        print(f"  - Temps total: {stats['temps_total']} minutes")
        print(f"  - Taux d'utilisation: {taux_utilisation:.1f}%")

    # Sauvegarder le planning en JSON
    output_dir = Path("data/plannings_generes")
    output_dir.mkdir(parents=True, exist_ok=True)
    planning_path = output_dir / "production_agroalimentaire_planning.json"

    planning_data = {
        "instance": str(chemin_instance),
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
    print(f"Planning sauvegarde dans: {planning_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
