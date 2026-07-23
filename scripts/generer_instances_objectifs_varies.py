"""Génération d'instances TRCO avec objectifs variés pour tester la pipeline.

Ce script crée un ensemble d'instances de test couvrant différents types
d'objectifs : makespan, équilibrage de charge, minimisation des retards,
maximisation de l'utilisation, et combinaisons multi-objectifs.

Usage:
    uv run python -m scripts.generer_instances_objectifs_varies
"""

from __future__ import annotations

import json
from pathlib import Path


def creer_instance_makespan_simple() -> dict:
    """Instance simple - minimiser le makespan uniquement."""
    return {
        "taches": [
            {"id": "T1", "nom": "Préparation"},
            {"id": "T2", "nom": "Fabrication"},
            {"id": "T3", "nom": "Assemblage"},
            {"id": "T4", "nom": "Contrôle qualité"},
        ],
        "ressources": [
            {"id": "R1", "nom": "Poste de préparation"},
            {"id": "R2", "nom": "Machine de fabrication"},
            {"id": "R3", "nom": "Poste d'assemblage"},
        ],
        "contraintes": [
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "precedence", "avant": "T3", "apres": "T4"},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 20},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R2", "duree": 45},
            {"type": "compatibilite_ressource_tache", "tache": "T3", "ressource": "R2", "duree": 30},
            {"type": "compatibilite_ressource_tache", "tache": "T3", "ressource": "R3", "duree": 25},
            {"type": "compatibilite_ressource_tache", "tache": "T4", "ressource": "R3", "duree": 15},
        ],
        "objectifs": [{"type": "minimiser_makespan", "poids": 1.0}],
    }


def creer_instance_equilibrage_charge() -> dict:
    """Instance focalisée sur l'équilibrage de charge entre ressources."""
    return {
        "taches": [
            {"id": "T1", "nom": "Tâche A"},
            {"id": "T2", "nom": "Tâche B"},
            {"id": "T3", "nom": "Tâche C"},
            {"id": "T4", "nom": "Tâche D"},
            {"id": "T5", "nom": "Tâche E"},
            {"id": "T6", "nom": "Tâche F"},
        ],
        "ressources": [
            {"id": "R1", "nom": "Machine A"},
            {"id": "R2", "nom": "Machine B"},
            {"id": "R3", "nom": "Machine C"},
        ],
        "contraintes": [
            # Toutes les tâches peuvent s'exécuter sur toutes les ressources (flexibilité maximale)
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 30},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R2", "duree": 35},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R3", "duree": 28},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 40},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R2", "duree": 38},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R3", "duree": 42},
            {"type": "compatibilite_ressource_tache", "tache": "T3", "ressource": "R1", "duree": 25},
            {"type": "compatibilite_ressource_tache", "tache": "T3", "ressource": "R2", "duree": 25},
            {"type": "compatibilite_ressource_tache", "tache": "T3", "ressource": "R3", "duree": 25},
            {"type": "compatibilite_ressource_tache", "tache": "T4", "ressource": "R1", "duree": 35},
            {"type": "compatibilite_ressource_tache", "tache": "T4", "ressource": "R2", "duree": 33},
            {"type": "compatibilite_ressource_tache", "tache": "T4", "ressource": "R3", "duree": 37},
            {"type": "compatibilite_ressource_tache", "tache": "T5", "ressource": "R1", "duree": 20},
            {"type": "compatibilite_ressource_tache", "tache": "T5", "ressource": "R2", "duree": 22},
            {"type": "compatibilite_ressource_tache", "tache": "T5", "ressource": "R3", "duree": 20},
            {"type": "compatibilite_ressource_tache", "tache": "T6", "ressource": "R1", "duree": 45},
            {"type": "compatibilite_ressource_tache", "tache": "T6", "ressource": "R2", "duree": 40},
            {"type": "compatibilite_ressource_tache", "tache": "T6", "ressource": "R3", "duree": 43},
        ],
        "objectifs": [
            {"type": "equilibrer_charge", "poids": 0.7, "methode": "ecart_max"},
            {"type": "minimiser_makespan", "poids": 0.3},
        ],
    }


def creer_instance_minimiser_retards() -> dict:
    """Instance avec échéances strictes - minimiser les retards."""
    return {
        "taches": [
            {"id": "T1", "nom": "Commande urgente client A"},
            {"id": "T2", "nom": "Commande standard client B"},
            {"id": "T3", "nom": "Commande prioritaire client C"},
            {"id": "T4", "nom": "Maintenance préventive"},
            {"id": "T5", "nom": "Commande urgente client D"},
        ],
        "ressources": [
            {"id": "R1", "nom": "Ligne de production 1"},
            {"id": "R2", "nom": "Ligne de production 2"},
        ],
        "contraintes": [
            {"type": "precedence", "avant": "T2", "apres": "T4"},
            # Compatibilités
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 60},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R2", "duree": 65},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 90},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R2", "duree": 85},
            {"type": "compatibilite_ressource_tache", "tache": "T3", "ressource": "R1", "duree": 45},
            {"type": "compatibilite_ressource_tache", "tache": "T3", "ressource": "R2", "duree": 50},
            {"type": "compatibilite_ressource_tache", "tache": "T4", "ressource": "R1", "duree": 30},
            {"type": "compatibilite_ressource_tache", "tache": "T4", "ressource": "R2", "duree": 30},
            {"type": "compatibilite_ressource_tache", "tache": "T5", "ressource": "R1", "duree": 55},
            {"type": "compatibilite_ressource_tache", "tache": "T5", "ressource": "R2", "duree": 52},
            # Échéances critiques
            {"type": "echeance", "tache": "T1", "echeance": 120},  # Très urgente
            {"type": "echeance", "tache": "T3", "echeance": 180},  # Urgente
            {"type": "echeance", "tache": "T5", "echeance": 150},  # Urgente
            {"type": "echeance", "tache": "T2", "echeance": 300},  # Standard
        ],
        "objectifs": [
            {
                "type": "minimiser_retards",
                "poids": 0.8,
                "fonction_penalite": "quadratique",
                "priorite_par_tache": {"T1": 10.0, "T5": 8.0, "T3": 5.0, "T2": 1.0},
                "seuil_grace": 10,
            },
            {"type": "minimiser_makespan", "poids": 0.2},
        ],
    }


def creer_instance_maximiser_utilisation() -> dict:
    """Instance focalisée sur la maximisation de l'utilisation des ressources."""
    return {
        "taches": [
            {"id": "T1", "nom": "Opération courte 1"},
            {"id": "T2", "nom": "Opération longue"},
            {"id": "T3", "nom": "Opération courte 2"},
            {"id": "T4", "nom": "Opération moyenne 1"},
            {"id": "T5", "nom": "Opération moyenne 2"},
            {"id": "T6", "nom": "Opération courte 3"},
        ],
        "ressources": [
            {"id": "R1", "nom": "Machine premium", "competences": ["standard", "precision"]},
            {"id": "R2", "nom": "Machine standard", "competences": ["standard"]},
            {"id": "R3", "nom": "Machine polyvalente", "competences": ["standard", "precision", "rapide"]},
        ],
        "contraintes": [
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T4", "apres": "T5"},
            # Compatibilités - certaines tâches limitées
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 15},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R2", "duree": 20},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R3", "duree": 12},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 80},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R3", "duree": 75},
            {"type": "compatibilite_ressource_tache", "tache": "T3", "ressource": "R2", "duree": 18},
            {"type": "compatibilite_ressource_tache", "tache": "T3", "ressource": "R3", "duree": 15},
            {"type": "compatibilite_ressource_tache", "tache": "T4", "ressource": "R1", "duree": 40},
            {"type": "compatibilite_ressource_tache", "tache": "T4", "ressource": "R2", "duree": 45},
            {"type": "compatibilite_ressource_tache", "tache": "T4", "ressource": "R3", "duree": 38},
            {"type": "compatibilite_ressource_tache", "tache": "T5", "ressource": "R1", "duree": 35},
            {"type": "compatibilite_ressource_tache", "tache": "T5", "ressource": "R2", "duree": 40},
            {"type": "compatibilite_ressource_tache", "tache": "T6", "ressource": "R2", "duree": 10},
            {"type": "compatibilite_ressource_tache", "tache": "T6", "ressource": "R3", "duree": 8},
        ],
        "objectifs": [
            {
                "type": "maximiser_utilisation",
                "poids": 0.6,
                "ressources_prioritaires": ["R1"],  # Machine premium doit être bien utilisée
            },
            {"type": "minimiser_makespan", "poids": 0.4},
        ],
    }


def creer_instance_minimiser_changements() -> dict:
    """Instance pour minimiser les changements de ressources entre tâches."""
    return {
        "taches": [
            {"id": "T1", "nom": "Série A - pièce 1"},
            {"id": "T2", "nom": "Série A - pièce 2"},
            {"id": "T3", "nom": "Série A - pièce 3"},
            {"id": "T4", "nom": "Série B - pièce 1"},
            {"id": "T5", "nom": "Série B - pièce 2"},
            {"id": "T6", "nom": "Série C - pièce 1"},
            {"id": "T7", "nom": "Série C - pièce 2"},
        ],
        "ressources": [
            {"id": "R1", "nom": "Centre d'usinage 1"},
            {"id": "R2", "nom": "Centre d'usinage 2"},
            {"id": "R3", "nom": "Centre d'usinage 3"},
        ],
        "contraintes": [
            # Séries avec précédences
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "precedence", "avant": "T4", "apres": "T5"},
            {"type": "precedence", "avant": "T6", "apres": "T7"},
            # Toutes compatibles avec toutes (mais coûts de changement différents)
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 25},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R2", "duree": 28},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R3", "duree": 30},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R1", "duree": 25},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R2", "duree": 28},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R3", "duree": 30},
            {"type": "compatibilite_ressource_tache", "tache": "T3", "ressource": "R1", "duree": 25},
            {"type": "compatibilite_ressource_tache", "tache": "T3", "ressource": "R2", "duree": 28},
            {"type": "compatibilite_ressource_tache", "tache": "T3", "ressource": "R3", "duree": 30},
            {"type": "compatibilite_ressource_tache", "tache": "T4", "ressource": "R1", "duree": 35},
            {"type": "compatibilite_ressource_tache", "tache": "T4", "ressource": "R2", "duree": 32},
            {"type": "compatibilite_ressource_tache", "tache": "T4", "ressource": "R3", "duree": 38},
            {"type": "compatibilite_ressource_tache", "tache": "T5", "ressource": "R1", "duree": 35},
            {"type": "compatibilite_ressource_tache", "tache": "T5", "ressource": "R2", "duree": 32},
            {"type": "compatibilite_ressource_tache", "tache": "T5", "ressource": "R3", "duree": 38},
            {"type": "compatibilite_ressource_tache", "tache": "T6", "ressource": "R1", "duree": 40},
            {"type": "compatibilite_ressource_tache", "tache": "T6", "ressource": "R2", "duree": 42},
            {"type": "compatibilite_ressource_tache", "tache": "T6", "ressource": "R3", "duree": 38},
            {"type": "compatibilite_ressource_tache", "tache": "T7", "ressource": "R1", "duree": 40},
            {"type": "compatibilite_ressource_tache", "tache": "T7", "ressource": "R2", "duree": 42},
            {"type": "compatibilite_ressource_tache", "tache": "T7", "ressource": "R3", "duree": 38},
        ],
        "objectifs": [
            {
                "type": "minimiser_changements",
                "poids": 0.5,
                "cout_changement_par_ressource": {
                    "R1": 2.0,  # Centre moderne, changement rapide
                    "R2": 3.5,  # Centre ancien, changement lent
                    "R3": 1.5,  # Centre automatisé, changement très rapide
                },
            },
            {"type": "minimiser_makespan", "poids": 0.3},
            {"type": "equilibrer_charge", "poids": 0.2, "methode": "variance"},
        ],
    }


def creer_instance_multi_objectifs_complexe() -> dict:
    """Instance complexe combinant tous les objectifs."""
    return {
        "taches": [
            {"id": "T1", "nom": "Commande prioritaire A"},
            {"id": "T2", "nom": "Commande standard B"},
            {"id": "T3", "nom": "Commande urgente C"},
            {"id": "T4", "nom": "Opération préparatoire"},
            {"id": "T5", "nom": "Commande standard D"},
            {"id": "T6", "nom": "Finition A"},
            {"id": "T7", "nom": "Finition C"},
            {"id": "T8", "nom": "Contrôle qualité"},
        ],
        "ressources": [
            {"id": "R1", "nom": "Machine rapide premium", "competences": ["usinage", "finition"]},
            {"id": "R2", "nom": "Machine standard polyvalente", "competences": ["usinage", "preparation"]},
            {"id": "R3", "nom": "Machine contrôle", "competences": ["controle"]},
            {"id": "R4", "nom": "Machine finition", "competences": ["finition"]},
        ],
        "contraintes": [
            # Précédences
            {"type": "precedence", "avant": "T4", "apres": "T1"},
            {"type": "precedence", "avant": "T4", "apres": "T2"},
            {"type": "precedence", "avant": "T1", "apres": "T6"},
            {"type": "precedence", "avant": "T3", "apres": "T7"},
            {"type": "precedence", "avant": "T6", "apres": "T8"},
            {"type": "precedence", "avant": "T7", "apres": "T8"},
            # Compatibilités
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 40},
            {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R2", "duree": 50},
            {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R2", "duree": 60},
            {"type": "compatibilite_ressource_tache", "tache": "T3", "ressource": "R1", "duree": 35},
            {"type": "compatibilite_ressource_tache", "tache": "T3", "ressource": "R2", "duree": 45},
            {"type": "compatibilite_ressource_tache", "tache": "T4", "ressource": "R2", "duree": 20},
            {"type": "compatibilite_ressource_tache", "tache": "T5", "ressource": "R1", "duree": 55},
            {"type": "compatibilite_ressource_tache", "tache": "T5", "ressource": "R2", "duree": 65},
            {"type": "compatibilite_ressource_tache", "tache": "T6", "ressource": "R1", "duree": 25},
            {"type": "compatibilite_ressource_tache", "tache": "T6", "ressource": "R4", "duree": 30},
            {"type": "compatibilite_ressource_tache", "tache": "T7", "ressource": "R1", "duree": 20},
            {"type": "compatibilite_ressource_tache", "tache": "T7", "ressource": "R4", "duree": 25},
            {"type": "compatibilite_ressource_tache", "tache": "T8", "ressource": "R3", "duree": 15},
            # Échéances
            {"type": "echeance", "tache": "T3", "echeance": 150},  # Urgente
            {"type": "echeance", "tache": "T1", "echeance": 200},  # Prioritaire
            {"type": "echeance", "tache": "T8", "echeance": 280},  # Fin de journée
        ],
        "objectifs": [
            {"type": "minimiser_makespan", "poids": 0.25, "makespan_cible": 300, "penalite_depassement": 2.0},
            {"type": "minimiser_retards", "poids": 0.3, "fonction_penalite": "quadratique", "seuil_grace": 10},
            {"type": "equilibrer_charge", "poids": 0.2, "methode": "gini"},
            {"type": "maximiser_utilisation", "poids": 0.15, "ressources_prioritaires": ["R1"]},
            {"type": "minimiser_changements", "poids": 0.1},
        ],
    }


def generer_toutes_les_instances() -> None:
    """Génère toutes les instances et les sauvegarde."""
    # Répertoire de sortie
    output_dir = Path(__file__).parent.parent / "dsl" / "examples" / "objectifs_varies"
    output_dir.mkdir(parents=True, exist_ok=True)

    instances = {
        "01_makespan_simple.json": creer_instance_makespan_simple(),
        "02_equilibrage_charge.json": creer_instance_equilibrage_charge(),
        "03_minimiser_retards.json": creer_instance_minimiser_retards(),
        "04_maximiser_utilisation.json": creer_instance_maximiser_utilisation(),
        "05_minimiser_changements.json": creer_instance_minimiser_changements(),
        "06_multi_objectifs_complexe.json": creer_instance_multi_objectifs_complexe(),
    }

    print(f"Génération de {len(instances)} instances dans {output_dir}...\n")

    for filename, instance in instances.items():
        filepath = output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(instance, f, indent=2, ensure_ascii=False)
        print(f"[OK] {filename}")
        print(f"  - Taches: {len(instance['taches'])}")
        print(f"  - Ressources: {len(instance['ressources'])}")
        print(f"  - Contraintes: {len(instance['contraintes'])}")
        print(f"  - Objectifs: {len(instance['objectifs'])}")
        print()

    # Créer un README pour documenter les instances
    readme_path = output_dir / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write("""# Instances TRCO avec Objectifs Variés

Ce répertoire contient des instances de test couvrant différents types d'objectifs
pour valider la pipeline de génération et d'exécution de PRISME.

## Instances disponibles

### 01_makespan_simple.json
- **Objectif principal**: Minimiser le makespan
- **Complexité**: Simple (4 tâches, 3 ressources)
- **Cas d'usage**: Validation de base, planification simple

### 02_equilibrage_charge.json
- **Objectifs**: Équilibrage de charge (70%) + Makespan (30%)
- **Complexité**: Moyenne (6 tâches, 3 ressources)
- **Particularité**: Toutes les tâches compatibles avec toutes les ressources
- **Cas d'usage**: Optimisation de l'utilisation équitable des ressources

### 03_minimiser_retards.json
- **Objectifs**: Minimiser les retards (80%) + Makespan (20%)
- **Complexité**: Moyenne (5 tâches, 2 ressources)
- **Particularité**: Contraintes d'échéances strictes, priorités différenciées
- **Cas d'usage**: Gestion de commandes urgentes avec délais

### 04_maximiser_utilisation.json
- **Objectifs**: Maximiser l'utilisation (60%) + Makespan (40%)
- **Complexité**: Moyenne (6 tâches, 3 ressources)
- **Particularité**: Ressources avec compétences, focus sur machine premium
- **Cas d'usage**: Optimisation du ROI des équipements coûteux

### 05_minimiser_changements.json
- **Objectifs**: Minimiser changements (50%) + Makespan (30%) + Équilibrage (20%)
- **Complexité**: Moyenne (7 tâches en 3 séries, 3 ressources)
- **Particularité**: Coûts de changement différenciés par ressource
- **Cas d'usage**: Réduction des temps de setup/changement de série

### 06_multi_objectifs_complexe.json
- **Objectifs**: 5 objectifs pondérés (makespan, retards, équilibrage, utilisation, changements)
- **Complexité**: Élevée (8 tâches, 4 ressources)
- **Particularité**: Combine tous les types d'objectifs et contraintes
- **Cas d'usage**: Scénario réaliste de production industrielle

## Utilisation dans la pipeline

Ces instances peuvent être utilisées pour :

1. **Tests de génération** : Vérifier que le générateur LLM produit des solveurs corrects
   pour chaque type d'objectif

2. **Tests de validation** : Valider que la cascade de validation fonctionne avec des
   objectifs variés

3. **Benchmarking** : Comparer les performances de différentes stratégies de résolution

4. **Tests de régression** : Assurer la stabilité après modifications du code

## Exemple d'utilisation

```python
from dsl.validation.charger_instance import charger_instance_depuis_json

# Charger une instance
instance = charger_instance_depuis_json("dsl/examples/objectifs_varies/02_equilibrage_charge.json")

# Générer un solveur
from generation.tentative_unique import generer_et_tester_solveur
solveur = generer_et_tester_solveur(instance)

# Exécuter le solveur
planning = solveur(instance)
```

## Notes techniques

- Toutes les instances respectent le garde-fou amont (§6.7) de `InstanceTRCO`
- Les durées sont en minutes
- Les échéances sont relatives à un instant de référence implicite
- Les pondérations des objectifs sont normalisées (somme ≠ nécessairement 1.0,
  interprétation relative)
""")

    print(f"[OK] {readme_path.name}")
    print(f"\nGeneration terminee ! {len(instances)} instances creees dans {output_dir}")


if __name__ == "__main__":
    generer_toutes_les_instances()
