"""Analyse les configurations d'objectifs dans les instances enrichies.

Usage:
    python -m scripts.analyser_objectifs
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def analyser_instance_enrichie(chemin: Path) -> dict:
    """Analyse une instance enrichie."""
    with open(chemin, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Compter les types de contraintes
    types_contraintes = Counter()
    for contrainte in data.get("contraintes", []):
        types_contraintes[contrainte.get("type", "inconnu")] += 1

    # Analyser les objectifs
    objectifs_info = []
    for objectif in data.get("objectifs", []):
        objectifs_info.append({
            "type": objectif.get("type"),
            "poids": objectif.get("poids", 1.0),
        })

    return {
        "nom": chemin.stem,
        "taches": len(data.get("taches", [])),
        "ressources": len(data.get("ressources", [])),
        "contraintes": len(data.get("contraintes", [])),
        "objectifs": objectifs_info,
        "types_contraintes": dict(types_contraintes),
        "a_echeances": types_contraintes.get("echeance", 0) > 0,
        "a_competences": types_contraintes.get("competence_requise", 0) > 0,
    }


def main():
    """Point d'entrée principal."""
    enrichies_dir = Path(__file__).parent.parent / "data" / "instances_trco_enrichies"

    if not enrichies_dir.exists():
        print(f"ERREUR: Le repertoire {enrichies_dir} n'existe pas")
        print("Executez d'abord: python -m scripts.configurer_objectifs --all")
        return

    # Chercher toutes les instances enrichies
    fichiers = sorted(enrichies_dir.glob("**/*.json"))

    if not fichiers:
        print(f"ERREUR: Aucune instance enrichie trouvee dans {enrichies_dir}")
        return

    print("=" * 100)
    print(" " * 35 + "ANALYSE DES OBJECTIFS")
    print("=" * 100)
    print()

    # Grouper par configuration
    par_config = {}
    for fichier in fichiers:
        stats = analyser_instance_enrichie(fichier)

        # Extraire le type de configuration
        config_type = "inconnu"
        for conf in ["makespan", "equilibrage", "retards", "utilisation", "changements", "multi"]:
            if conf in stats["nom"]:
                config_type = conf
                break

        if config_type not in par_config:
            par_config[config_type] = []

        par_config[config_type].append(stats)

    # Afficher par configuration
    for config_type, instances in sorted(par_config.items()):
        print(f"CONFIGURATION: {config_type.upper()}")
        print("-" * 100)

        # Statistiques de la configuration
        total_taches = sum(i["taches"] for i in instances)
        total_contraintes = sum(i["contraintes"] for i in instances)
        avec_echeances = sum(1 for i in instances if i["a_echeances"])
        avec_competences = sum(1 for i in instances if i["a_competences"])

        # Nombre d'objectifs (prendre le premier comme référence)
        n_objectifs = len(instances[0]["objectifs"]) if instances else 0

        print(f"  Instances: {len(instances)}")
        print(f"  Objectifs par instance: {n_objectifs}")

        if instances:
            print(f"  Types d'objectifs:")
            for obj in instances[0]["objectifs"]:
                print(f"    - {obj['type']:<30} (poids: {obj['poids']})")

        print(f"  Total taches: {total_taches}")
        print(f"  Total contraintes: {total_contraintes}")
        print(f"  Avec echeances: {avec_echeances}/{len(instances)}")
        print(f"  Avec competences: {avec_competences}/{len(instances)}")
        print()

    # Statistiques globales
    print("=" * 100)
    print("STATISTIQUES GLOBALES")
    print("=" * 100)

    total_instances = len(fichiers)
    total_taches = sum(analyser_instance_enrichie(f)["taches"] for f in fichiers)
    total_contraintes = sum(analyser_instance_enrichie(f)["contraintes"] for f in fichiers)

    # Compter les types d'objectifs utilisés
    tous_objectifs = Counter()
    for fichier in fichiers:
        stats = analyser_instance_enrichie(fichier)
        for obj in stats["objectifs"]:
            tous_objectifs[obj["type"]] += 1

    print(f"Total instances enrichies    : {total_instances}")
    print(f"Total taches                 : {total_taches}")
    print(f"Total contraintes            : {total_contraintes}")
    print()

    print("REPARTITION DES TYPES D'OBJECTIFS:")
    for type_obj, count in tous_objectifs.most_common():
        pourcent = (count / total_instances) * 100
        print(f"  {type_obj:<35} : {count:>3} ({pourcent:>5.1f}%)")

    print()
    print("=" * 100)

    # Exemples détaillés
    print()
    print("EXEMPLES DETAILLES (3 premiers fichiers)")
    print("-" * 100)

    for fichier in fichiers[:3]:
        stats = analyser_instance_enrichie(fichier)
        print(f"\n{stats['nom']}")
        print(f"  Taches: {stats['taches']}, Ressources: {stats['ressources']}, Contraintes: {stats['contraintes']}")
        print(f"  Objectifs ({len(stats['objectifs'])}):")
        for obj in stats['objectifs']:
            print(f"    - {obj['type']} (poids: {obj['poids']})")

        print(f"  Types de contraintes:")
        for type_c, count in stats['types_contraintes'].items():
            print(f"    - {type_c}: {count}")

    print()


if __name__ == "__main__":
    main()
