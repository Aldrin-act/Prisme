#!/usr/bin/env python
"""Génère des données brutes au format simplifié (similaire à instance_exemple.json).

Ce script crée des données brutes qui utilisent directement le format simplifié
avec compétences et durées sur les tâches, au lieu du format ERP operations/postes.

Usage:
    uv run python -m scripts.generer_donnees_brutes_format_simplifie
"""

import json
from pathlib import Path
from typing import Any


def generer_atelier_mecanique_petit() -> dict[str, Any]:
    """Atelier mécanique - cas simple avec 4 tâches."""
    return {
        "taches": [
            {"id": "T1", "nom": "Découpe", "duree_estimee_jours": 1},
            {"id": "T2", "nom": "Perçage", "duree_estimee_jours": 1},
            {"id": "T3", "nom": "Soudure", "duree_estimee_jours": 2},
            {"id": "T4", "nom": "Contrôle", "duree_estimee_jours": 1},
        ],
        "ressources": [
            {"id": "R1", "nom": "Découpeuse", "competences": ["decoupe"]},
            {"id": "R2", "nom": "Perceuse", "competences": ["percage"]},
            {"id": "R3", "nom": "Poste soudure", "competences": ["soudure"]},
            {"id": "R4", "nom": "Station contrôle", "competences": ["controle"]},
        ],
        "contraintes": [
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "precedence", "avant": "T3", "apres": "T4"},
            {"type": "competence_requise", "tache": "T1", "competence": "decoupe"},
            {"type": "competence_requise", "tache": "T2", "competence": "percage"},
            {"type": "competence_requise", "tache": "T3", "competence": "soudure"},
            {"type": "competence_requise", "tache": "T4", "competence": "controle"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def generer_atelier_mecanique_moyen() -> dict[str, Any]:
    """Atelier mécanique - taille moyenne avec ressources multiples."""
    return {
        "taches": [
            {"id": "T1", "nom": "Découpe pièce A", "duree_estimee_jours": 2},
            {"id": "T2", "nom": "Découpe pièce B", "duree_estimee_jours": 1},
            {"id": "T3", "nom": "Usinage pièce A", "duree_estimee_jours": 3},
            {"id": "T4", "nom": "Usinage pièce B", "duree_estimee_jours": 2},
            {"id": "T5", "nom": "Assemblage", "duree_estimee_jours": 2},
            {"id": "T6", "nom": "Finition", "duree_estimee_jours": 1},
        ],
        "ressources": [
            {"id": "R1", "nom": "Découpeuse laser", "competences": ["decoupe"]},
            {"id": "R2", "nom": "Découpeuse plasma", "competences": ["decoupe"]},
            {"id": "R3", "nom": "Fraiseuse CNC 1", "competences": ["usinage", "precision"]},
            {"id": "R4", "nom": "Fraiseuse CNC 2", "competences": ["usinage"]},
            {"id": "R5", "nom": "Poste assemblage", "competences": ["assemblage"]},
            {"id": "R6", "nom": "Poste finition", "competences": ["finition", "polissage"]},
        ],
        "contraintes": [
            # Précédences - deux branches parallèles
            {"type": "precedence", "avant": "T1", "apres": "T3"},
            {"type": "precedence", "avant": "T2", "apres": "T4"},
            {"type": "precedence", "avant": "T3", "apres": "T5"},
            {"type": "precedence", "avant": "T4", "apres": "T5"},
            {"type": "precedence", "avant": "T5", "apres": "T6"},
            # Compétences
            {"type": "competence_requise", "tache": "T1", "competence": "decoupe"},
            {"type": "competence_requise", "tache": "T2", "competence": "decoupe"},
            {"type": "competence_requise", "tache": "T3", "competence": "usinage"},
            {"type": "competence_requise", "tache": "T4", "competence": "usinage"},
            {"type": "competence_requise", "tache": "T5", "competence": "assemblage"},
            {"type": "competence_requise", "tache": "T6", "competence": "finition"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def generer_assemblage_electronique() -> dict[str, Any]:
    """Assemblage électronique - workflow PCB simple face."""
    return {
        "taches": [
            {"id": "T1", "nom": "Préparation", "duree_estimee_jours": 1},
            {"id": "T2", "nom": "Pose CMS", "duree_estimee_jours": 2},
            {"id": "T3", "nom": "Réfusion", "duree_estimee_jours": 1},
            {"id": "T4", "nom": "Inspection", "duree_estimee_jours": 1},
            {"id": "T5", "nom": "Test", "duree_estimee_jours": 1},
        ],
        "ressources": [
            {"id": "R1", "nom": "Station préparation", "competences": ["preparation"]},
            {"id": "R2", "nom": "Pick&Place", "competences": ["pick_place"]},
            {"id": "R3", "nom": "Four réfusion", "competences": ["refusion"]},
            {"id": "R4", "nom": "AOI", "competences": ["inspection"]},
            {"id": "R5", "nom": "Banc test", "competences": ["test"]},
        ],
        "contraintes": [
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "precedence", "avant": "T3", "apres": "T4"},
            {"type": "precedence", "avant": "T4", "apres": "T5"},
            {"type": "competence_requise", "tache": "T1", "competence": "preparation"},
            {"type": "competence_requise", "tache": "T2", "competence": "pick_place"},
            {"type": "competence_requise", "tache": "T3", "competence": "refusion"},
            {"type": "competence_requise", "tache": "T4", "competence": "inspection"},
            {"type": "competence_requise", "tache": "T5", "competence": "test"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def generer_production_agroalimentaire() -> dict[str, Any]:
    """Production agroalimentaire - transformation simple."""
    return {
        "taches": [
            {"id": "T1", "nom": "Réception", "duree_estimee_jours": 1},
            {"id": "T2", "nom": "Lavage", "duree_estimee_jours": 1},
            {"id": "T3", "nom": "Découpe", "duree_estimee_jours": 2},
            {"id": "T4", "nom": "Cuisson", "duree_estimee_jours": 3},
            {"id": "T5", "nom": "Conditionnement", "duree_estimee_jours": 2},
        ],
        "ressources": [
            {"id": "R1", "nom": "Quai réception", "competences": ["reception"]},
            {"id": "R2", "nom": "Station lavage", "competences": ["lavage"]},
            {"id": "R3", "nom": "Machine découpe", "competences": ["decoupe"]},
            {"id": "R4", "nom": "Four", "competences": ["cuisson"]},
            {"id": "R5", "nom": "Ligne conditionnement", "competences": ["conditionnement"]},
        ],
        "contraintes": [
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "precedence", "avant": "T3", "apres": "T4"},
            {"type": "precedence", "avant": "T4", "apres": "T5"},
            {"type": "competence_requise", "tache": "T1", "competence": "reception"},
            {"type": "competence_requise", "tache": "T2", "competence": "lavage"},
            {"type": "competence_requise", "tache": "T3", "competence": "decoupe"},
            {"type": "competence_requise", "tache": "T4", "competence": "cuisson"},
            {"type": "competence_requise", "tache": "T5", "competence": "conditionnement"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def generer_imprimerie_petit() -> dict[str, Any]:
    """Imprimerie - workflow simplifié."""
    return {
        "taches": [
            {"id": "T1", "nom": "Prépresse", "duree_estimee_jours": 2},
            {"id": "T2", "nom": "Impression", "duree_estimee_jours": 3},
            {"id": "T3", "nom": "Découpe", "duree_estimee_jours": 1},
            {"id": "T4", "nom": "Reliure", "duree_estimee_jours": 2},
        ],
        "ressources": [
            {"id": "R1", "nom": "Station PAO", "competences": ["prepresse"]},
            {"id": "R2", "nom": "Presse offset", "competences": ["impression"]},
            {"id": "R3", "nom": "Massicot", "competences": ["decoupe"]},
            {"id": "R4", "nom": "Plieuse", "competences": ["reliure"]},
        ],
        "contraintes": [
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "precedence", "avant": "T3", "apres": "T4"},
            {"type": "competence_requise", "tache": "T1", "competence": "prepresse"},
            {"type": "competence_requise", "tache": "T2", "competence": "impression"},
            {"type": "competence_requise", "tache": "T3", "competence": "decoupe"},
            {"type": "competence_requise", "tache": "T4", "competence": "reliure"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def generer_maintenance() -> dict[str, Any]:
    """Maintenance - intervention simple."""
    return {
        "taches": [
            {"id": "T1", "nom": "Diagnostic", "duree_estimee_jours": 1},
            {"id": "T2", "nom": "Démontage", "duree_estimee_jours": 1},
            {"id": "T3", "nom": "Réparation", "duree_estimee_jours": 2},
            {"id": "T4", "nom": "Remontage", "duree_estimee_jours": 1},
            {"id": "T5", "nom": "Test", "duree_estimee_jours": 1},
        ],
        "ressources": [
            {"id": "R1", "nom": "Technicien", "competences": ["diagnostic", "demontage", "remontage", "test"]},
            {"id": "R2", "nom": "Atelier réparation", "competences": ["reparation"]},
        ],
        "contraintes": [
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "precedence", "avant": "T3", "apres": "T4"},
            {"type": "precedence", "avant": "T4", "apres": "T5"},
            {"type": "competence_requise", "tache": "T1", "competence": "diagnostic"},
            {"type": "competence_requise", "tache": "T2", "competence": "demontage"},
            {"type": "competence_requise", "tache": "T3", "competence": "reparation"},
            {"type": "competence_requise", "tache": "T4", "competence": "remontage"},
            {"type": "competence_requise", "tache": "T5", "competence": "test"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def generer_logistique() -> dict[str, Any]:
    """Logistique - préparation commande."""
    return {
        "taches": [
            {"id": "T1", "nom": "Picking", "duree_estimee_jours": 1},
            {"id": "T2", "nom": "Emballage", "duree_estimee_jours": 1},
            {"id": "T3", "nom": "Étiquetage", "duree_estimee_jours": 1},
            {"id": "T4", "nom": "Chargement", "duree_estimee_jours": 1},
        ],
        "ressources": [
            {"id": "R1", "nom": "Zone picking", "competences": ["picking"]},
            {"id": "R2", "nom": "Poste emballage", "competences": ["emballage"]},
            {"id": "R3", "nom": "Station étiquetage", "competences": ["etiquetage"]},
            {"id": "R4", "nom": "Quai expédition", "competences": ["chargement"]},
        ],
        "contraintes": [
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "precedence", "avant": "T3", "apres": "T4"},
            {"type": "competence_requise", "tache": "T1", "competence": "picking"},
            {"type": "competence_requise", "tache": "T2", "competence": "emballage"},
            {"type": "competence_requise", "tache": "T3", "competence": "etiquetage"},
            {"type": "competence_requise", "tache": "T4", "competence": "chargement"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def generer_hopital() -> dict[str, Any]:
    """Hôpital - intervention chirurgicale simple."""
    return {
        "taches": [
            {"id": "T1", "nom": "Préparation patient", "duree_estimee_jours": 1},
            {"id": "T2", "nom": "Intervention", "duree_estimee_jours": 2},
            {"id": "T3", "nom": "Surveillance", "duree_estimee_jours": 2},
        ],
        "ressources": [
            {"id": "R1", "nom": "Salle préparation", "competences": ["preparation"]},
            {"id": "R2", "nom": "Bloc opératoire", "competences": ["intervention"]},
            {"id": "R3", "nom": "Salle réveil", "competences": ["surveillance"]},
        ],
        "contraintes": [
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "competence_requise", "tache": "T1", "competence": "preparation"},
            {"type": "competence_requise", "tache": "T2", "competence": "intervention"},
            {"type": "competence_requise", "tache": "T3", "competence": "surveillance"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def generer_restauration() -> dict[str, Any]:
    """Restauration collective - préparation repas."""
    return {
        "taches": [
            {"id": "T1", "nom": "Préparation ingrédients", "duree_estimee_jours": 1},
            {"id": "T2", "nom": "Cuisson", "duree_estimee_jours": 2},
            {"id": "T3", "nom": "Dressage", "duree_estimee_jours": 1},
            {"id": "T4", "nom": "Service", "duree_estimee_jours": 1},
        ],
        "ressources": [
            {"id": "R1", "nom": "Zone préparation", "competences": ["preparation"]},
            {"id": "R2", "nom": "Cuisines", "competences": ["cuisson"]},
            {"id": "R3", "nom": "Zone dressage", "competences": ["dressage"]},
            {"id": "R4", "nom": "Salle service", "competences": ["service"]},
        ],
        "contraintes": [
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "precedence", "avant": "T3", "apres": "T4"},
            {"type": "competence_requise", "tache": "T1", "competence": "preparation"},
            {"type": "competence_requise", "tache": "T2", "competence": "cuisson"},
            {"type": "competence_requise", "tache": "T3", "competence": "dressage"},
            {"type": "competence_requise", "tache": "T4", "competence": "service"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def generer_exemple_minimal() -> dict[str, Any]:
    """Exemple minimal - identique à instance_exemple.json."""
    return {
        "taches": [
            {"id": "T1", "nom": "Decoupe", "duree_estimee_jours": 3},
            {"id": "T2", "nom": "Assemblage", "duree_estimee_jours": 2},
        ],
        "ressources": [
            {"id": "R1", "nom": "Decoupeuse", "competences": ["decoupe", "assemblage"]},
        ],
        "contraintes": [
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "competence_requise", "tache": "T1", "competence": "decoupe"},
            {"type": "competence_requise", "tache": "T2", "competence": "assemblage"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def main() -> None:
    """Génère toutes les données brutes au format simplifié."""
    donnees = {
        "exemple_minimal": generer_exemple_minimal(),
        "atelier_mecanique_petit": generer_atelier_mecanique_petit(),
        "atelier_mecanique_moyen": generer_atelier_mecanique_moyen(),
        "assemblage_electronique": generer_assemblage_electronique(),
        "production_agroalimentaire": generer_production_agroalimentaire(),
        "imprimerie_petit": generer_imprimerie_petit(),
        "maintenance": generer_maintenance(),
        "logistique": generer_logistique(),
        "hopital": generer_hopital(),
        "restauration": generer_restauration(),
    }

    # Créer le répertoire de destination
    output_dir = Path("data/donnees_brutes/format_simplifie")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Générer chaque fichier
    for nom, donnee in donnees.items():
        output_path = output_dir / f"{nom}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(donnee, f, indent=2, ensure_ascii=False)
        print(f"[OK] {output_path}")

    # Créer un README
    readme_path = output_dir / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(
            """# Données Brutes au Format Simplifié

Ce répertoire contient des données brutes au format simplifié, utilisant directement
la structure taches/ressources/contraintes avec compétences.

## Différence avec les autres formats

**Format ERP** (`data/donnees_brutes/json_erp/`):
- Vocabulaire propriétaire: `operations` / `postes`
- Structure linéaire avec `operation_precedente`
- Nécessite un adaptateur (translator) pour conversion en TRCO

**Format Simplifié** (ce répertoire):
- Vocabulaire canonique: `taches` / `ressources`
- Contraintes typées avec compétences
- Prêt à l'emploi ou conversion légère vers TRCO complet

## Fichiers disponibles

"""
        )

        for nom, donnee in donnees.items():
            nb_taches = len(donnee["taches"])
            nb_ressources = len(donnee["ressources"])
            f.write(f"- **{nom}**: {nb_taches} tâches, {nb_ressources} ressources\n")

        f.write(
            """
## Structure du format

```json
{
  "taches": [
    {"id": "T1", "nom": "Nom de la tâche", "duree_estimee_jours": 3}
  ],
  "ressources": [
    {"id": "R1", "nom": "Nom de la ressource", "competences": ["comp1", "comp2"]}
  ],
  "contraintes": [
    {"type": "precedence", "avant": "T1", "apres": "T2"},
    {"type": "competence_requise", "tache": "T1", "competence": "comp1"}
  ],
  "objectifs": [
    {"type": "minimiser_makespan"}
  ]
}
```

## Utilisation

Ces données brutes peuvent être utilisées pour:

1. **Ingestion directe**: Import via l'API avec conversion minimale
2. **Prototypage**: Tests rapides sans adapter depuis un format ERP
3. **Exemples**: Documentation et démonstrations
4. **Tests**: Validation de la chaîne de traitement

## Conversion vers TRCO complet

Pour utiliser ces données dans PRISME, un adaptateur léger doit:

1. Dériver les contraintes `compatibilite_ressource_tache` depuis les compétences
2. Extraire les durées des tâches vers les contraintes de compatibilité
3. Ajouter les métadonnées (priorite, statut, type_ressource)

Voir `adapters/competence_derivation.py` pour la logique de dérivation.

## Regénération

```bash
uv run python -m scripts.generer_donnees_brutes_format_simplifie
```
"""
        )

    print(f"\n[OK] {len(donnees)} fichiers de données brutes générés dans {output_dir}")
    print(f"[OK] README créé: {readme_path}")


if __name__ == "__main__":
    main()
