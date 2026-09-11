#!/usr/bin/env python
"""Enrichit les fichiers JSON ERP avec des compétences explicites.

Ajoute automatiquement :
- competences[] sur chaque poste
- competence_requise sur chaque opération

Pour permettre à l'agent de compréhension de fonctionner correctement.

Usage:
    uv run python -m scripts.enrichir_competences_erp
"""

from __future__ import annotations

import json
import re
from pathlib import Path


def extraire_competence_depuis_poste(code_poste: str) -> str:
    """Extrait une compétence depuis un code de poste.

    Exemples:
        DECOUPEUSE_LASER_1 -> decoupe_laser
        POSTE_SOUDURE -> soudure
        BLOC_CHIRURGIE_GENERALE -> chirurgie_generale
    """
    # Retirer les suffixes numériques (_1, _2, etc.)
    code_sans_numero = re.sub(r"_\d+$", "", code_poste)

    # Mapping de préfixes connus vers compétences
    prefixes_a_retirer = [
        "POSTE_",
        "STATION_",
        "LIGNE_",
        "ZONE_",
        "ROBOT_",
        "MACHINE_",
        "BANC_",
        "TUNNEL_",
        "CABINE_",
        "FOUR_",
        "EQUIPE_",
        "BLOC_",
        "SALLE_",
        "UNITE_",
        "LABORATOIRE_",
        "QUAI_",
        "CAMION_",
        "CAMIONNETTE_",
        "CHARIOT_",
        "CENTRE_",
        "ATELIER_",
    ]

    competence = code_sans_numero
    for prefix in prefixes_a_retirer:
        if competence.startswith(prefix):
            competence = competence[len(prefix) :]
            break

    # Convertir en minuscules pour uniformité
    competence = competence.lower()

    return competence


def enrichir_fichier_erp(fichier_path: Path) -> dict[str, int]:
    """Enrichit un fichier JSON ERP avec des compétences.

    Returns:
        dict avec statistiques : postes_enrichis, operations_enrichies
    """
    print(f"[ENRICHISSEMENT] {fichier_path.name}...")

    with open(fichier_path, encoding="utf-8") as f:
        data = json.load(f)

    # Construire le mapping poste -> compétence
    mapping_competences = {}
    for poste in data.get("postes", []):
        code_poste = poste["code_poste"]
        competence = extraire_competence_depuis_poste(code_poste)
        mapping_competences[code_poste] = competence

    # Enrichir les postes avec competences
    postes_enrichis = 0
    for poste in data.get("postes", []):
        code_poste = poste["code_poste"]
        competence = mapping_competences[code_poste]

        # Ajouter le champ competences (liste pour compatibilité)
        poste["competences"] = [competence]
        postes_enrichis += 1

    # Enrichir les opérations avec competence_requise
    operations_enrichies = 0
    for operation in data.get("operations", []):
        poste_id = operation.get("poste_id")
        if poste_id and poste_id in mapping_competences:
            # Ajouter la compétence requise
            operation["competence_requise"] = mapping_competences[poste_id]
            operations_enrichies += 1

    # Sauvegarder le fichier enrichi
    with open(fichier_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"  [OK] {postes_enrichis} postes enrichis")
    print(f"  [OK] {operations_enrichies} operations enrichies")

    return {
        "postes_enrichis": postes_enrichis,
        "operations_enrichies": operations_enrichies,
    }


def main():
    """Enrichit tous les fichiers JSON ERP dans les deux répertoires."""

    repertoires = [
        Path("data/donnees_brutes/json_erp"),
        Path("data/donnees_brutes_large/json_erp"),
    ]

    print("=" * 60)
    print("Enrichissement des fichiers JSON ERP avec competences")
    print("=" * 60)
    print()

    total_fichiers = 0
    total_postes = 0
    total_operations = 0

    for repertoire in repertoires:
        if not repertoire.exists():
            print(f"[SKIP] {repertoire} n'existe pas\n")
            continue

        print(f"=== {repertoire} ===\n")

        fichiers = sorted(repertoire.glob("*.json"))
        for fichier in fichiers:
            stats = enrichir_fichier_erp(fichier)
            total_fichiers += 1
            total_postes += stats["postes_enrichis"]
            total_operations += stats["operations_enrichies"]
            print()

    print("=" * 60)
    print(f"Fichiers enrichis : {total_fichiers}")
    print(f"Postes enrichis : {total_postes}")
    print(f"Operations enrichies : {total_operations}")
    print("=" * 60)
    print()
    print("[OK] Enrichissement termine !")
    print()
    print("Les fichiers peuvent maintenant etre utilises avec l'agent de comprehension.")


if __name__ == "__main__":
    main()
