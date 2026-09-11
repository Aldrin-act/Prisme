"""Analyse et affiche les statistiques des instances TRCO générées.

Usage:
    python -m scripts.analyser_instances
"""

from __future__ import annotations

import json
from pathlib import Path


def analyser_instance(chemin: Path) -> dict:
    """Analyse une instance TRCO et retourne ses statistiques."""
    with open(chemin, encoding="utf-8") as f:
        data = json.load(f)

    stats = {
        "nom": chemin.stem,
        "taches": len(data.get("taches", [])),
        "ressources": len(data.get("ressources", [])),
        "contraintes": len(data.get("contraintes", [])),
        "objectifs": len(data.get("objectifs", [])),
    }

    # Compter les types de contraintes
    types_contraintes = {}
    for contrainte in data.get("contraintes", []):
        type_c = contrainte.get("type", "inconnu")
        types_contraintes[type_c] = types_contraintes.get(type_c, 0) + 1

    stats["types_contraintes"] = types_contraintes

    # Calculer la taille du fichier
    stats["taille_ko"] = chemin.stat().st_size / 1024

    return stats


def main():
    """Point d'entrée principal."""
    instances_dir = Path(__file__).parent.parent / "data" / "instances_trco"

    if not instances_dir.exists():
        print(f"ERREUR: Le repertoire {instances_dir} n'existe pas")
        return

    fichiers = sorted(instances_dir.glob("*.json"))

    if not fichiers:
        print(f"ERREUR: Aucun fichier JSON trouve dans {instances_dir}")
        return

    print("=" * 90)
    print(" " * 25 + "ANALYSE DES INSTANCES TRCO")
    print("=" * 90)
    print()

    # Séparer instances normales et grandes
    instances_normales = []
    instances_larges = []

    for fichier in fichiers:
        stats = analyser_instance(fichier)
        if "_large" in stats["nom"]:
            instances_larges.append(stats)
        else:
            instances_normales.append(stats)

    # Afficher instances normales
    if instances_normales:
        print("INSTANCES STANDARD (petite/moyenne échelle)")
        print("-" * 90)
        print(f"{'Nom':<40} {'Taches':>8} {'Ressources':>12} {'Contraintes':>13} {'Taille (KB)':>12}")
        print("-" * 90)

        for stats in instances_normales:
            print(
                f"{stats['nom']:<40} {stats['taches']:>8} {stats['ressources']:>12} "
                f"{stats['contraintes']:>13} {stats['taille_ko']:>11.1f}"
            )

        print()
        total_taches = sum(s["taches"] for s in instances_normales)
        total_ressources = sum(s["ressources"] for s in instances_normales)
        total_contraintes = sum(s["contraintes"] for s in instances_normales)

        print(f"{'TOTAL STANDARD':<40} {total_taches:>8} {total_ressources:>12} {total_contraintes:>13}")
        print()

    # Afficher instances larges
    if instances_larges:
        print("INSTANCES A GRANDE ECHELLE (100+ operations)")
        print("-" * 90)
        print(f"{'Nom':<40} {'Taches':>8} {'Ressources':>12} {'Contraintes':>13} {'Taille (KB)':>12}")
        print("-" * 90)

        for stats in instances_larges:
            print(
                f"{stats['nom']:<40} {stats['taches']:>8} {stats['ressources']:>12} "
                f"{stats['contraintes']:>13} {stats['taille_ko']:>11.1f}"
            )

        print()
        total_taches = sum(s["taches"] for s in instances_larges)
        total_ressources = sum(s["ressources"] for s in instances_larges)
        total_contraintes = sum(s["contraintes"] for s in instances_larges)

        print(f"{'TOTAL GRANDE ECHELLE':<40} {total_taches:>8} {total_ressources:>12} {total_contraintes:>13}")
        print()

    # Statistiques globales
    print("=" * 90)
    print("STATISTIQUES GLOBALES")
    print("=" * 90)

    toutes_stats = instances_normales + instances_larges
    total_instances = len(toutes_stats)
    total_taches_global = sum(s["taches"] for s in toutes_stats)
    total_ressources_global = sum(s["ressources"] for s in toutes_stats)
    total_contraintes_global = sum(s["contraintes"] for s in toutes_stats)
    total_taille = sum(s["taille_ko"] for s in toutes_stats)

    print(f"Nombre total d'instances      : {total_instances}")
    print(f"  - Standard                   : {len(instances_normales)}")
    print(f"  - Grande echelle             : {len(instances_larges)}")
    print()
    print(f"Total taches                   : {total_taches_global}")
    print(f"Total ressources               : {total_ressources_global}")
    print(f"Total contraintes              : {total_contraintes_global}")
    print(f"Taille totale                  : {total_taille:.1f} KB")
    print()

    if toutes_stats:
        print(f"Moyenne taches/instance        : {total_taches_global / total_instances:.1f}")
        print(f"Moyenne ressources/instance    : {total_ressources_global / total_instances:.1f}")
        print(f"Moyenne contraintes/instance   : {total_contraintes_global / total_instances:.1f}")

    print()
    print("=" * 90)

    # Détails par type de contrainte
    print()
    print("REPARTITION DES TYPES DE CONTRAINTES")
    print("-" * 90)

    types_globaux = {}
    for stats in toutes_stats:
        for type_c, count in stats["types_contraintes"].items():
            types_globaux[type_c] = types_globaux.get(type_c, 0) + count

    for type_c, count in sorted(types_globaux.items(), key=lambda x: x[1], reverse=True):
        pourcent = (count / total_contraintes_global) * 100
        print(f"  {type_c:<40} : {count:>6} ({pourcent:>5.1f}%)")

    print()
    print("=" * 90)


if __name__ == "__main__":
    main()
