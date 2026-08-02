#!/usr/bin/env python
"""Valide que tous les fichiers JSON ERP sont bien formés.

Vérifie que :
- Chaque opération a un poste_id
- Chaque poste_id référencé existe dans la liste des postes
- Il n'y a pas de postes orphelins

Usage:
    uv run python -m scripts.valider_donnees_brutes_erp
"""

import json
from pathlib import Path


def valider_fichier_erp(fichier_path: Path) -> tuple[bool, list[str]]:
    """Valide un fichier ERP et retourne (succès, liste d'erreurs)."""
    erreurs = []

    try:
        with open(fichier_path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, [f"Erreur de lecture JSON : {e}"]

    # Vérifier la structure
    if "operations" not in data:
        erreurs.append("Clé 'operations' manquante")
    if "postes" not in data:
        erreurs.append("Clé 'postes' manquante")

    if erreurs:
        return False, erreurs

    # Extraire les postes déclarés
    postes_declares = {poste["code_poste"] for poste in data["postes"]}

    # Vérifier chaque opération
    postes_references = set()
    for i, operation in enumerate(data["operations"]):
        if "code_operation" not in operation:
            erreurs.append(f"Opération {i} : clé 'code_operation' manquante")
            continue

        if "poste_id" not in operation:
            erreurs.append(
                f"Opération '{operation['code_operation']}' : clé 'poste_id' manquante"
            )
            continue

        poste_id = operation["poste_id"]
        postes_references.add(poste_id)

        if poste_id not in postes_declares:
            erreurs.append(
                f"Opération '{operation['code_operation']}' : "
                f"poste '{poste_id}' non déclaré dans la liste des postes"
            )

        if "duree_jours" not in operation:
            erreurs.append(
                f"Opération '{operation['code_operation']}' : clé 'duree_jours' manquante"
            )

    # Postes orphelins (déclarés mais jamais utilisés) - juste un warning
    postes_orphelins = postes_declares - postes_references
    if postes_orphelins:
        erreurs.append(
            f"WARNING : {len(postes_orphelins)} poste(s) déclaré(s) mais jamais utilisé(s) : "
            f"{sorted(list(postes_orphelins))[:5]}"
        )

    return len([e for e in erreurs if not e.startswith("WARNING")]) == 0, erreurs


def main():
    """Valide tous les fichiers JSON ERP."""
    # Dossiers à valider
    dossiers = [
        Path("data/donnees_brutes/json_erp"),
        Path("data/donnees_brutes_large/json_erp"),
    ]

    print("Validation des fichiers JSON ERP\n")

    total_fichiers = 0
    total_valides = 0
    total_erreurs = 0

    for dossier in dossiers:
        if not dossier.exists():
            print(f"[SKIP] {dossier} n'existe pas\n")
            continue

        print(f"=== {dossier} ===\n")

        fichiers = sorted(dossier.glob("*.json"))
        for fichier in fichiers:
            total_fichiers += 1
            valide, erreurs = valider_fichier_erp(fichier)

            if valide:
                total_valides += 1
                print(f"[OK] {fichier.name}")
            else:
                total_erreurs += len([e for e in erreurs if not e.startswith("WARNING")])
                print(f"[ERREUR] {fichier.name}")
                for erreur in erreurs:
                    symbole = "[!]" if not erreur.startswith("WARNING") else "[WARN]"
                    print(f"  {symbole} {erreur}")

        print()

    print("=" * 60)
    print(f"Fichiers validés : {total_fichiers}")
    print(f"Valides : {total_valides}")
    print(f"Invalides : {total_fichiers - total_valides}")
    print(f"Total erreurs : {total_erreurs}")

    if total_fichiers == total_valides:
        print("\n✓ Tous les fichiers sont valides !")
    else:
        print(f"\n✗ {total_fichiers - total_valides} fichier(s) invalide(s)")


if __name__ == "__main__":
    main()
