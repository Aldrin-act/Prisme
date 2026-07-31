"""Transformation de données brutes (format ERP) en instances TRCO.

Ce script prend des données au format ERP de référence (JSON ou CSV) et les
transforme en instances TRCO canoniques prêtes à être utilisées par la pipeline.

Usage:
    # JSON unique
    python -m scripts.transformer_donnees_brutes --input data/donnees_brutes/json_erp/atelier_mecanique.json

    # Tous les fichiers JSON d'un répertoire
    python -m scripts.transformer_donnees_brutes --input-dir data/donnees_brutes/json_erp

    # CSV (paire operations + postes)
    python -m scripts.transformer_donnees_brutes \\
        --csv-operations data/donnees_brutes/csv/atelier_mecanique_operations.csv \\
        --csv-postes data/donnees_brutes/csv/atelier_mecanique_postes.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from adapters.erp_reference.schema_erp import PayloadERP
from adapters.erp_reference.translator import traduire
from dsl.schema import InstanceTRCO


def charger_depuis_json(chemin: Path) -> PayloadERP:
    """Charge un payload ERP depuis un fichier JSON."""
    with open(chemin, "r", encoding="utf-8") as f:
        data = json.load(f)
    return PayloadERP(**data)


def charger_depuis_csv(chemin_operations: Path, chemin_postes: Path) -> PayloadERP:
    """Charge un payload ERP depuis des fichiers CSV."""
    # Lire les opérations
    operations = []
    with open(chemin_operations, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            operations.append(
                {
                    "code_operation": row["code_operation"],
                    "duree_jours": int(row["duree_jours"]),
                    "poste_id": row["poste_id"],
                    "operation_precedente": row["operation_precedente"] if row["operation_precedente"] else None,
                }
            )

    # Lire les postes
    postes = []
    with open(chemin_postes, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            postes.append({"code_poste": row["code_poste"]})

    return PayloadERP(operations=operations, postes=postes)


def sauvegarder_instance_trco(instance: InstanceTRCO, chemin: Path) -> None:
    """Sauvegarde une instance TRCO en JSON."""
    chemin.parent.mkdir(parents=True, exist_ok=True)

    # Convertir en dict pour serialization JSON
    data = instance.model_dump(mode="json")

    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def transformer_fichier_json(chemin_entree: Path, chemin_sortie: Path | None = None) -> None:
    """Transforme un fichier JSON ERP en instance TRCO."""
    print(f"[TRANSFORMATION] {chemin_entree.name}")

    # Charger le payload ERP
    payload_erp = charger_depuis_json(chemin_entree)
    print(f"  Charge: {len(payload_erp.operations)} operations, {len(payload_erp.postes)} postes")

    # Traduire en TRCO
    instance_trco = traduire(payload_erp)
    print(f"  Traduit: {len(instance_trco.taches)} taches, {len(instance_trco.ressources)} ressources")
    print(f"  Contraintes: {len(instance_trco.contraintes)}")

    # Déterminer le chemin de sortie
    if chemin_sortie is None:
        output_dir = Path(__file__).parent.parent / "data" / "instances_trco"
        output_dir.mkdir(parents=True, exist_ok=True)
        chemin_sortie = output_dir / chemin_entree.name

    # Sauvegarder
    sauvegarder_instance_trco(instance_trco, chemin_sortie)
    print(f"  Sauvegarde: {chemin_sortie}")
    print()


def transformer_fichiers_csv(chemin_operations: Path, chemin_postes: Path, chemin_sortie: Path | None = None) -> None:
    """Transforme une paire de fichiers CSV en instance TRCO."""
    print(f"[TRANSFORMATION CSV] {chemin_operations.name} + {chemin_postes.name}")

    # Charger le payload ERP
    payload_erp = charger_depuis_csv(chemin_operations, chemin_postes)
    print(f"  Charge: {len(payload_erp.operations)} operations, {len(payload_erp.postes)} postes")

    # Traduire en TRCO
    instance_trco = traduire(payload_erp)
    print(f"  Traduit: {len(instance_trco.taches)} taches, {len(instance_trco.ressources)} ressources")

    # Déterminer le chemin de sortie
    if chemin_sortie is None:
        output_dir = Path(__file__).parent.parent / "data" / "instances_trco"
        output_dir.mkdir(parents=True, exist_ok=True)
        nom_base = chemin_operations.name.replace("_operations.csv", "")
        chemin_sortie = output_dir / f"{nom_base}.json"

    # Sauvegarder
    sauvegarder_instance_trco(instance_trco, chemin_sortie)
    print(f"  Sauvegarde: {chemin_sortie}")
    print()


def transformer_repertoire(chemin_repertoire: Path) -> None:
    """Transforme tous les fichiers JSON d'un répertoire."""
    fichiers_json = list(chemin_repertoire.glob("*.json"))

    if not fichiers_json:
        print(f"ATTENTION: Aucun fichier JSON trouve dans {chemin_repertoire}")
        return

    print(f"Transformation de {len(fichiers_json)} fichiers JSON...\n")

    for fichier in fichiers_json:
        transformer_fichier_json(fichier)

    print(f"Transformation terminee ! {len(fichiers_json)} instances TRCO generees")


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(description="Transforme des donnees brutes ERP en instances TRCO")

    # Options pour JSON
    parser.add_argument("--input", type=Path, help="Fichier JSON ERP a transformer")
    parser.add_argument("--input-dir", type=Path, help="Repertoire contenant des fichiers JSON ERP")

    # Options pour CSV
    parser.add_argument("--csv-operations", type=Path, help="Fichier CSV des operations")
    parser.add_argument("--csv-postes", type=Path, help="Fichier CSV des postes")

    # Option de sortie
    parser.add_argument("--output", type=Path, help="Chemin de sortie (optionnel)")

    args = parser.parse_args()

    # Vérifier les arguments
    if args.input:
        # Transformation d'un fichier JSON unique
        if not args.input.exists():
            print(f"ERREUR: Le fichier {args.input} n'existe pas")
            return

        transformer_fichier_json(args.input, args.output)

    elif args.input_dir:
        # Transformation d'un répertoire entier
        if not args.input_dir.exists():
            print(f"ERREUR: Le repertoire {args.input_dir} n'existe pas")
            return

        transformer_repertoire(args.input_dir)

    elif args.csv_operations and args.csv_postes:
        # Transformation depuis CSV
        if not args.csv_operations.exists():
            print(f"ERREUR: Le fichier {args.csv_operations} n'existe pas")
            return
        if not args.csv_postes.exists():
            print(f"ERREUR: Le fichier {args.csv_postes} n'existe pas")
            return

        transformer_fichiers_csv(args.csv_operations, args.csv_postes, args.output)

    else:
        # Par défaut, transformer tout le répertoire json_erp
        default_dir = Path(__file__).parent.parent / "data" / "donnees_brutes" / "json_erp"

        if default_dir.exists():
            print("Aucun argument fourni - transformation du repertoire par defaut")
            print(f"Repertoire: {default_dir}\n")
            transformer_repertoire(default_dir)
        else:
            print("ERREUR: Aucun argument fourni et le repertoire par defaut n'existe pas")
            print("\nUsage:")
            parser.print_help()


if __name__ == "__main__":
    main()
