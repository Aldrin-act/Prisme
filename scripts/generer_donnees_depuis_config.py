"""
Générateur de données brutes à partir de configurations YAML de secteurs.

Ce script lit une configuration de secteur depuis data/configurations_secteurs/
et génère des données brutes au format ERP (JSON et/ou CSV) en utilisant
les paramètres définis dans la configuration.

Usage:
    uv run python -m scripts.generer_donnees_depuis_config --secteur gestion_espaces_verts
    uv run python -m scripts.generer_donnees_depuis_config --secteur hopital_bloc_operatoire --taille 100
    uv run python -m scripts.generer_donnees_depuis_config --secteur restauration_collective --format json
    uv run python -m scripts.generer_donnees_depuis_config --tous --taille 50
"""

import argparse
import json
import random
from pathlib import Path
from typing import Any

import yaml


def charger_configuration(nom_secteur: str) -> dict[str, Any]:
    """Charge la configuration YAML d'un secteur."""
    chemin_config = Path("data/configurations_secteurs") / f"{nom_secteur}.yaml"

    if not chemin_config.exists():
        raise FileNotFoundError(
            f"Configuration introuvable: {chemin_config}\n"
            f"Vérifiez que le fichier existe dans data/configurations_secteurs/"
        )

    with open(chemin_config, encoding="utf-8") as f:
        return yaml.safe_load(f)


def lister_configurations_disponibles() -> list[str]:
    """Liste toutes les configurations de secteurs disponibles."""
    repertoire = Path("data/configurations_secteurs")
    if not repertoire.exists():
        return []

    return [
        fichier.stem
        for fichier in repertoire.glob("*.yaml")
    ]


def generer_donnees_depuis_config(
    config: dict[str, Any],
    n_operations: int = 20,
) -> dict[str, Any]:
    """
    Génère des données brutes au format ERP à partir d'une configuration.

    Args:
        config: Configuration du secteur chargée depuis YAML
        n_operations: Nombre d'opérations à générer

    Returns:
        Payload ERP au format JSON
    """
    nom_secteur = config["nom"]
    types_postes = config["types_postes"]
    phases = config["phases_production"]
    generation = config.get("generation", {})

    prefix_lot = generation.get("prefix_lot", "LOT")
    ops_par_lot_min = generation.get("operations_par_lot_min", 4)
    ops_par_lot_max = generation.get("operations_par_lot_max", 8)

    # Calcul du nombre de lots nécessaires
    ops_par_lot_moyen = (ops_par_lot_min + ops_par_lot_max) / 2
    n_lots = max(1, int(n_operations / ops_par_lot_moyen))

    operations = []
    postes_crees = {}
    op_id = 1

    # Génération par lots
    for i_lot in range(n_lots):
        id_lot = f"{prefix_lot}_{i_lot + 1:03d}"

        # Nombre d'opérations dans ce lot
        n_ops_lot = random.randint(ops_par_lot_min, ops_par_lot_max)

        # Sélectionner des phases pour ce lot
        phases_lot = random.sample(phases, min(len(phases), n_ops_lot))

        for i_op, phase in enumerate(phases_lot):
            # Choisir un type de poste compatible avec la phase
            type_poste_nom = random.choice(phase["types_poste"])
            type_poste_config = types_postes[type_poste_nom]

            # Créer le poste s'il n'existe pas encore
            if type_poste_nom not in postes_crees:
                postes_crees[type_poste_nom] = {
                    "nom": type_poste_nom,
                    "capacite": type_poste_config["capacite"],
                }

            # Générer l'opération
            duree = random.randint(
                type_poste_config["duree_min"],
                type_poste_config["duree_max"],
            )

            operation = {
                "id": f"OP_{op_id:04d}",
                "nom": f"{phase['nom']}_{i_op + 1}",
                "lot": id_lot,
                "phase": phase["nom"],
                "poste_requis": type_poste_nom,
                "duree_estimee": duree,
                "priorite": random.randint(1, 5),
            }

            # Ajouter des précédences dans le lot
            if i_op > 0 and random.random() < 0.6:  # 60% de chance
                operation["predecesseurs"] = [f"OP_{op_id - 1:04d}"]

            operations.append(operation)
            op_id += 1

            if len(operations) >= n_operations:
                break

        if len(operations) >= n_operations:
            break

    # Construire le payload
    payload = {
        "metadata": {
            "secteur": nom_secteur,
            "description": config.get("description", ""),
            "source": "generer_donnees_depuis_config.py",
            "n_operations": len(operations),
            "n_postes": len(postes_crees),
        },
        "postes": list(postes_crees.values()),
        "operations": operations,
    }

    return payload


def sauvegarder_json(payload: dict[str, Any], nom_secteur: str, taille: str) -> Path:
    """Sauvegarde le payload au format JSON."""
    repertoire = Path("data/donnees_brutes/json_erp")
    repertoire.mkdir(parents=True, exist_ok=True)

    nom_fichier = f"{nom_secteur}_{taille}.json"
    chemin = repertoire / nom_fichier

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    return chemin


def sauvegarder_csv(payload: dict[str, Any], nom_secteur: str, taille: str) -> tuple[Path, Path]:
    """Sauvegarde le payload au format CSV (2 fichiers: postes et operations)."""
    repertoire = Path("data/donnees_brutes/csv")
    repertoire.mkdir(parents=True, exist_ok=True)

    # Fichier postes
    nom_postes = f"{nom_secteur}_{taille}_postes.csv"
    chemin_postes = repertoire / nom_postes

    with open(chemin_postes, "w", encoding="utf-8") as f:
        f.write("nom,capacite\n")
        for poste in payload["postes"]:
            f.write(f"{poste['nom']},{poste['capacite']}\n")

    # Fichier opérations
    nom_ops = f"{nom_secteur}_{taille}_operations.csv"
    chemin_ops = repertoire / nom_ops

    with open(chemin_ops, "w", encoding="utf-8") as f:
        f.write("id,nom,lot,phase,poste_requis,duree_estimee,priorite,predecesseurs\n")
        for op in payload["operations"]:
            preds = ";".join(op.get("predecesseurs", []))
            f.write(
                f"{op['id']},{op['nom']},{op['lot']},{op['phase']},"
                f"{op['poste_requis']},{op['duree_estimee']},{op['priorite']},{preds}\n"
            )

    return chemin_postes, chemin_ops


def main():
    parser = argparse.ArgumentParser(
        description="Génère des données brutes à partir d'une configuration YAML de secteur"
    )
    parser.add_argument(
        "--secteur",
        type=str,
        help="Nom du secteur (nom du fichier YAML sans extension)",
    )
    parser.add_argument(
        "--taille",
        type=int,
        default=20,
        help="Nombre d'opérations à générer (défaut: 20)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv", "both"],
        default="both",
        help="Format de sortie (défaut: both)",
    )
    parser.add_argument(
        "--tous",
        action="store_true",
        help="Générer pour tous les secteurs configurés",
    )
    parser.add_argument(
        "--lister",
        action="store_true",
        help="Lister les secteurs disponibles et quitter",
    )

    args = parser.parse_args()

    # Lister les configurations disponibles
    if args.lister:
        configs = lister_configurations_disponibles()
        if configs:
            print("Configurations de secteurs disponibles:")
            for config in sorted(configs):
                print(f"  - {config}")
        else:
            print("Aucune configuration trouvée dans data/configurations_secteurs/")
        return

    # Vérifier les arguments
    if not args.tous and not args.secteur:
        parser.error("Vous devez spécifier --secteur <nom> ou --tous")

    # Déterminer la catégorie de taille
    if args.taille < 50:
        taille_str = "small"
    elif args.taille < 150:
        taille_str = "medium"
    else:
        taille_str = "large"

    # Liste des secteurs à traiter
    if args.tous:
        secteurs = lister_configurations_disponibles()
        if not secteurs:
            print("Erreur: Aucune configuration trouvée dans data/configurations_secteurs/")
            return
        print(f"Génération pour {len(secteurs)} secteurs...")
    else:
        secteurs = [args.secteur]

    # Génération pour chaque secteur
    resultats = []

    for nom_secteur in secteurs:
        try:
            print(f"\n[{nom_secteur}]")

            # Charger la configuration
            config = charger_configuration(nom_secteur)
            print(f"  Configuration chargée: {config.get('description', 'N/A')}")

            # Générer les données
            payload = generer_donnees_depuis_config(config, args.taille)
            n_ops = len(payload["operations"])
            n_postes = len(payload["postes"])
            print(f"  Données générées: {n_ops} opérations, {n_postes} postes")

            # Sauvegarder
            fichiers_crees = []

            if args.format in ["json", "both"]:
                chemin_json = sauvegarder_json(payload, nom_secteur, taille_str)
                fichiers_crees.append(chemin_json)
                print(f"  JSON: {chemin_json}")

            if args.format in ["csv", "both"]:
                chemin_postes, chemin_ops = sauvegarder_csv(payload, nom_secteur, taille_str)
                fichiers_crees.extend([chemin_postes, chemin_ops])
                print(f"  CSV: {chemin_postes}")
                print(f"       {chemin_ops}")

            resultats.append({
                "secteur": nom_secteur,
                "operations": n_ops,
                "postes": n_postes,
                "fichiers": fichiers_crees,
            })

        except Exception as e:
            print(f"  Erreur: {e}")
            continue

    # Résumé final
    print("\n" + "=" * 60)
    print(f"Génération terminée: {len(resultats)} secteur(s) traité(s)")
    print("=" * 60)

    for resultat in resultats:
        print(f"\n{resultat['secteur']}:")
        print(f"  - {resultat['operations']} opérations")
        print(f"  - {resultat['postes']} postes")
        print(f"  - {len(resultat['fichiers'])} fichier(s) créé(s)")


if __name__ == "__main__":
    main()
