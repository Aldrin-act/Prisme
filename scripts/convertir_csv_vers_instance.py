"""Script de conversion de fichiers CSV en instances TRCO.

Ce script scanne les dossiers de données brutes CSV et convertit chaque
ensemble de fichiers (taches.csv, ressources.csv, contraintes.csv) en une
instance TRCO valide.

Usage:
    uv run python -m scripts.convertir_csv_vers_instance <chemin_dossier>
    uv run python -m scripts.convertir_csv_vers_instance --tous
    uv run python -m scripts.convertir_csv_vers_instance --lister

Exemples:
    # Convertir un dossier spécifique
    uv run python -m scripts.convertir_csv_vers_instance data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique

    # Convertir tous les dossiers CSV
    uv run python -m scripts.convertir_csv_vers_instance --tous

    # Lister les dossiers disponibles
    uv run python -m scripts.convertir_csv_vers_instance --lister
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from adapters.csv_import.traducteur import ErreurFichierInvalide, traduire
from dsl.schema import InstanceTRCO


def _repertoire_racine_csv() -> Path:
    """Renvoie le chemin vers le répertoire racine des CSV."""
    return Path(__file__).parent.parent / "data" / "donnees_brutes" / "csv"


def _trouver_dossiers_avec_csv() -> list[Path]:
    """Trouve tous les dossiers contenant les trois fichiers CSV requis."""
    dossiers = []
    racine = _repertoire_racine_csv()

    if not racine.exists():
        return []

    # Parcourir récursivement tous les sous-dossiers
    for chemin in racine.rglob("*"):
        if chemin.is_dir():
            # Vérifier si les trois fichiers requis existent
            taches = chemin / "taches.csv"
            ressources = chemin / "ressources.csv"
            contraintes = chemin / "contraintes.csv"

            if taches.exists() and ressources.exists() and contraintes.exists():
                dossiers.append(chemin)

    return sorted(dossiers)


def _charger_fichiers_csv(dossier: Path) -> tuple[bytes, bytes, bytes]:
    """Charge les trois fichiers CSV requis d'un dossier."""
    taches_csv = (dossier / "taches.csv").read_bytes()
    ressources_csv = (dossier / "ressources.csv").read_bytes()
    contraintes_csv = (dossier / "contraintes.csv").read_bytes()

    return taches_csv, ressources_csv, contraintes_csv


def csv_vers_instance(chemin_dossier: str | Path) -> InstanceTRCO:
    """Fonction principale: convertit un dossier de fichiers CSV en instance TRCO.

    Cette fonction peut être importée et utilisée dans d'autres modules.

    Args:
        chemin_dossier: Chemin (absolu ou relatif) vers le dossier contenant
                       taches.csv, ressources.csv et contraintes.csv

    Returns:
        L'instance TRCO générée

    Raises:
        FileNotFoundError: Si le dossier ou un fichier requis n'existe pas
        ErreurFichierInvalide: Si un fichier CSV est mal formaté
        ValidationError: Si les données ne forment pas une instance TRCO valide

    Exemple:
        >>> from scripts.convertir_csv_vers_instance import csv_vers_instance
        >>> instance = csv_vers_instance("data/donnees_brutes/csv/industrie_manufacturiere/assemblage_electronique")
        >>> print(f"Taches: {len(instance.taches)}, Ressources: {len(instance.ressources)}")
    """
    dossier = Path(chemin_dossier).resolve()

    # Vérifier que le dossier existe
    if not dossier.exists():
        raise FileNotFoundError(f"Le dossier '{dossier}' n'existe pas")

    if not dossier.is_dir():
        raise FileNotFoundError(f"'{dossier}' n'est pas un dossier")

    # Vérifier que les trois fichiers requis existent
    fichiers_requis = ["taches.csv", "ressources.csv", "contraintes.csv"]
    fichiers_manquants = [f for f in fichiers_requis if not (dossier / f).exists()]

    if fichiers_manquants:
        raise FileNotFoundError(
            f"Fichier(s) manquant(s) dans '{dossier}': {', '.join(fichiers_manquants)}"
        )

    # Charger et convertir
    taches_csv, ressources_csv, contraintes_csv = _charger_fichiers_csv(dossier)
    instance = traduire(taches_csv, ressources_csv, contraintes_csv)

    return instance


def convertir_dossier(dossier: Path, afficher_json: bool = True, afficher_stats: bool = True) -> InstanceTRCO | None:
    """Convertit un dossier CSV en instance TRCO.

    Args:
        dossier: Chemin vers le dossier contenant les CSV
        afficher_json: Si True, affiche le JSON de l'instance
        afficher_stats: Si True, affiche les statistiques de l'instance

    Returns:
        L'instance TRCO générée, ou None en cas d'erreur
    """
    try:
        print(f"\n{'='*80}")
        print(f"[DOSSIER] Conversion: {dossier.relative_to(_repertoire_racine_csv())}")
        print(f"{'='*80}\n")

        # Charger les fichiers CSV
        taches_csv, ressources_csv, contraintes_csv = _charger_fichiers_csv(dossier)

        # Convertir en instance TRCO
        instance = traduire(taches_csv, ressources_csv, contraintes_csv)

        # Afficher les statistiques
        if afficher_stats:
            print("Statistiques de l'instance:")
            print(f"  - Taches: {len(instance.taches)}")
            print(f"  - Ressources: {len(instance.ressources)}")
            print(f"  - Contraintes: {len(instance.contraintes)}")

            # Compter les types de contraintes
            types_contraintes: dict[str, int] = {}
            for contrainte in instance.contraintes:
                type_contrainte = contrainte.__class__.__name__
                types_contraintes[type_contrainte] = types_contraintes.get(type_contrainte, 0) + 1

            print(f"  - Types de contraintes:")
            for type_c, count in sorted(types_contraintes.items()):
                print(f"      {type_c}: {count}")

            print(f"  - Objectifs: {len(instance.objectifs)}")
            print()

        # Afficher le JSON
        if afficher_json:
            print("Instance TRCO (JSON):")
            print("-" * 80)
            instance_dict = instance.model_dump(mode="json")
            print(json.dumps(instance_dict, indent=2, ensure_ascii=False))
            print("-" * 80)

        print("\n[OK] Conversion reussie!")
        return instance

    except ErreurFichierInvalide as e:
        print(f"\n[ERREUR] Erreur de fichier: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"\n[ERREUR] Erreur lors de la conversion: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def lister_dossiers_disponibles():
    """Liste tous les dossiers contenant des fichiers CSV convertibles."""
    dossiers = _trouver_dossiers_avec_csv()
    racine = _repertoire_racine_csv()

    print("\nDossiers CSV disponibles pour conversion:")
    print("=" * 80)

    if not dossiers:
        print("Aucun dossier trouve contenant les trois fichiers CSV requis.")
        return

    for i, dossier in enumerate(dossiers, 1):
        chemin_relatif = dossier.relative_to(racine)
        print(f"{i:2d}. {chemin_relatif}")

    print(f"\nTotal: {len(dossiers)} dossier(s)")


def convertir_tous_les_dossiers(afficher_json: bool = False):
    """Convertit tous les dossiers CSV trouvés."""
    dossiers = _trouver_dossiers_avec_csv()

    print(f"\nConversion de {len(dossiers)} dossier(s)...\n")

    resultats: dict[str, Any] = {
        "succes": [],
        "echecs": [],
    }

    for dossier in dossiers:
        instance = convertir_dossier(dossier, afficher_json=afficher_json, afficher_stats=True)

        chemin_relatif = str(dossier.relative_to(_repertoire_racine_csv()))

        if instance:
            resultats["succes"].append(chemin_relatif)
        else:
            resultats["echecs"].append(chemin_relatif)

    # Résumé final
    print("\n" + "=" * 80)
    print("Resume de la conversion")
    print("=" * 80)
    print(f"[OK] Reussies: {len(resultats['succes'])}")
    print(f"[ERREUR] Echouees: {len(resultats['echecs'])}")

    if resultats["echecs"]:
        print("\nDossiers en echec:")
        for echec in resultats["echecs"]:
            print(f"  - {echec}")


def main():
    parser = argparse.ArgumentParser(
        description="Convertit des fichiers CSV en instances TRCO",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "dossier",
        nargs="?",
        type=Path,
        help="Chemin vers le dossier contenant les fichiers CSV (taches.csv, ressources.csv, contraintes.csv)",
    )
    group.add_argument(
        "--tous",
        action="store_true",
        help="Convertir tous les dossiers CSV trouvés dans data/donnees_brutes/csv/",
    )
    group.add_argument(
        "--lister",
        action="store_true",
        help="Lister tous les dossiers CSV disponibles",
    )

    parser.add_argument(
        "--sans-json",
        action="store_true",
        help="Ne pas afficher le JSON de l'instance (seulement les statistiques)",
    )

    args = parser.parse_args()

    if args.lister:
        lister_dossiers_disponibles()
        return

    if args.tous:
        convertir_tous_les_dossiers(afficher_json=not args.sans_json)
        return

    if args.dossier:
        dossier = args.dossier.resolve()

        if not dossier.exists():
            print(f"[ERREUR] Le dossier '{dossier}' n'existe pas.", file=sys.stderr)
            sys.exit(1)

        if not dossier.is_dir():
            print(f"[ERREUR] '{dossier}' n'est pas un dossier.", file=sys.stderr)
            sys.exit(1)

        # Vérifier que les trois fichiers existent
        fichiers_requis = ["taches.csv", "ressources.csv", "contraintes.csv"]
        fichiers_manquants = [f for f in fichiers_requis if not (dossier / f).exists()]

        if fichiers_manquants:
            print(f"[ERREUR] Fichier(s) manquant(s) dans '{dossier}':", file=sys.stderr)
            for fichier in fichiers_manquants:
                print(f"  - {fichier}", file=sys.stderr)
            sys.exit(1)

        instance = convertir_dossier(dossier, afficher_json=not args.sans_json)

        if instance is None:
            sys.exit(1)


if __name__ == "__main__":
    main()
