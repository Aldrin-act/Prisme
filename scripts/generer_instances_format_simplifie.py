#!/usr/bin/env python
"""Génère des instances d'exemple au format simplifié (instance_exemple.json).

Ce format simplifié diffère du format TRCO complet:
- La durée est attachée directement à la tâche (duree_estimee_jours)
- Les compétences sont utilisées pour dériver la compatibilité ressource-tâche
- Utilise des contraintes competence_requise au lieu de compatibilite_ressource_tache

Usage:
    uv run python -m scripts.generer_instances_format_simplifie
"""

import json
from pathlib import Path
from typing import Any


def creer_instance_atelier_mecanique() -> dict[str, Any]:
    """Atelier de fabrication métallique - 6 tâches."""
    return {
        "taches": [
            {"id": "T1", "nom": "Découpe laser", "duree_estimee_jours": 2},
            {"id": "T2", "nom": "Perçage CNC", "duree_estimee_jours": 1},
            {"id": "T3", "nom": "Pliage", "duree_estimee_jours": 2},
            {"id": "T4", "nom": "Soudure", "duree_estimee_jours": 3},
            {"id": "T5", "nom": "Peinture", "duree_estimee_jours": 2},
            {"id": "T6", "nom": "Assemblage final", "duree_estimee_jours": 2},
        ],
        "ressources": [
            {"id": "R1", "nom": "Découpeuse laser", "competences": ["decoupe"]},
            {"id": "R2", "nom": "Perceuse CNC", "competences": ["percage", "usinage"]},
            {"id": "R3", "nom": "Presse de pliage", "competences": ["pliage", "formage"]},
            {"id": "R4", "nom": "Poste de soudure", "competences": ["soudure"]},
            {"id": "R5", "nom": "Cabine de peinture", "competences": ["peinture", "finition"]},
            {"id": "R6", "nom": "Station d'assemblage", "competences": ["assemblage"]},
        ],
        "contraintes": [
            # Précédences (workflow linéaire)
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "precedence", "avant": "T3", "apres": "T4"},
            {"type": "precedence", "avant": "T4", "apres": "T5"},
            {"type": "precedence", "avant": "T5", "apres": "T6"},
            # Compétences requises
            {"type": "competence_requise", "tache": "T1", "competence": "decoupe"},
            {"type": "competence_requise", "tache": "T2", "competence": "percage"},
            {"type": "competence_requise", "tache": "T3", "competence": "pliage"},
            {"type": "competence_requise", "tache": "T4", "competence": "soudure"},
            {"type": "competence_requise", "tache": "T5", "competence": "peinture"},
            {"type": "competence_requise", "tache": "T6", "competence": "assemblage"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def creer_instance_assemblage_electronique() -> dict[str, Any]:
    """Fabrication de cartes électroniques - 8 tâches."""
    return {
        "taches": [
            {"id": "T1", "nom": "Préparation PCB", "duree_estimee_jours": 1},
            {"id": "T2", "nom": "Pose composants face A", "duree_estimee_jours": 3},
            {"id": "T3", "nom": "Refusion face A", "duree_estimee_jours": 1},
            {"id": "T4", "nom": "Inspection AOI face A", "duree_estimee_jours": 1},
            {"id": "T5", "nom": "Pose composants face B", "duree_estimee_jours": 3},
            {"id": "T6", "nom": "Refusion face B", "duree_estimee_jours": 1},
            {"id": "T7", "nom": "Soudure manuelle THT", "duree_estimee_jours": 2},
            {"id": "T8", "nom": "Test fonctionnel", "duree_estimee_jours": 2},
        ],
        "ressources": [
            {"id": "R1", "nom": "Station prep", "competences": ["preparation"]},
            {"id": "R2", "nom": "Pick&Place #1", "competences": ["pick_place"]},
            {"id": "R3", "nom": "Pick&Place #2", "competences": ["pick_place"]},
            {"id": "R4", "nom": "Four réfusion", "competences": ["refusion"]},
            {"id": "R5", "nom": "AOI", "competences": ["inspection"]},
            {"id": "R6", "nom": "Poste soudure", "competences": ["soudure_manuelle"]},
            {"id": "R7", "nom": "Banc de test", "competences": ["test"]},
        ],
        "contraintes": [
            # Workflow PCB double face
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "precedence", "avant": "T3", "apres": "T4"},
            {"type": "precedence", "avant": "T4", "apres": "T5"},
            {"type": "precedence", "avant": "T5", "apres": "T6"},
            {"type": "precedence", "avant": "T6", "apres": "T7"},
            {"type": "precedence", "avant": "T7", "apres": "T8"},
            # Compétences
            {"type": "competence_requise", "tache": "T1", "competence": "preparation"},
            {"type": "competence_requise", "tache": "T2", "competence": "pick_place"},
            {"type": "competence_requise", "tache": "T3", "competence": "refusion"},
            {"type": "competence_requise", "tache": "T4", "competence": "inspection"},
            {"type": "competence_requise", "tache": "T5", "competence": "pick_place"},
            {"type": "competence_requise", "tache": "T6", "competence": "refusion"},
            {"type": "competence_requise", "tache": "T7", "competence": "soudure_manuelle"},
            {"type": "competence_requise", "tache": "T8", "competence": "test"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def creer_instance_production_agroalimentaire() -> dict[str, Any]:
    """Production agroalimentaire - 7 tâches."""
    return {
        "taches": [
            {"id": "T1", "nom": "Réception matières premières", "duree_estimee_jours": 1},
            {"id": "T2", "nom": "Lavage et préparation", "duree_estimee_jours": 2},
            {"id": "T3", "nom": "Découpe et transformation", "duree_estimee_jours": 3},
            {"id": "T4", "nom": "Cuisson/Traitement thermique", "duree_estimee_jours": 4},
            {"id": "T5", "nom": "Refroidissement", "duree_estimee_jours": 2},
            {"id": "T6", "nom": "Conditionnement", "duree_estimee_jours": 2},
            {"id": "T7", "nom": "Contrôle qualité", "duree_estimee_jours": 1},
        ],
        "ressources": [
            {"id": "R1", "nom": "Quai de réception", "competences": ["reception"]},
            {"id": "R2", "nom": "Station de lavage", "competences": ["lavage", "preparation"]},
            {"id": "R3", "nom": "Machine de découpe", "competences": ["decoupe", "transformation"]},
            {"id": "R4", "nom": "Four industriel", "competences": ["cuisson", "traitement"]},
            {"id": "R5", "nom": "Tunnel de refroidissement", "competences": ["refroidissement"]},
            {"id": "R6", "nom": "Ligne de conditionnement", "competences": ["conditionnement"]},
            {"id": "R7", "nom": "Laboratoire contrôle", "competences": ["controle_qualite"]},
        ],
        "contraintes": [
            # Workflow linéaire production
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "precedence", "avant": "T3", "apres": "T4"},
            {"type": "precedence", "avant": "T4", "apres": "T5"},
            {"type": "precedence", "avant": "T5", "apres": "T6"},
            {"type": "precedence", "avant": "T6", "apres": "T7"},
            # Compétences
            {"type": "competence_requise", "tache": "T1", "competence": "reception"},
            {"type": "competence_requise", "tache": "T2", "competence": "lavage"},
            {"type": "competence_requise", "tache": "T3", "competence": "decoupe"},
            {"type": "competence_requise", "tache": "T4", "competence": "cuisson"},
            {"type": "competence_requise", "tache": "T5", "competence": "refroidissement"},
            {"type": "competence_requise", "tache": "T6", "competence": "conditionnement"},
            {"type": "competence_requise", "tache": "T7", "competence": "controle_qualite"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def creer_instance_maintenance_industrielle() -> dict[str, Any]:
    """Maintenance d'équipements industriels - 5 tâches avec parallélisme."""
    return {
        "taches": [
            {"id": "T1", "nom": "Diagnostic initial", "duree_estimee_jours": 1},
            {"id": "T2", "nom": "Démontage mécanique", "duree_estimee_jours": 2},
            {"id": "T3", "nom": "Révision électrique", "duree_estimee_jours": 3},
            {"id": "T4", "nom": "Remplacement pièces", "duree_estimee_jours": 2},
            {"id": "T5", "nom": "Tests et mise en service", "duree_estimee_jours": 2},
        ],
        "ressources": [
            {"id": "R1", "nom": "Technicien diagnostic", "competences": ["diagnostic", "test"]},
            {"id": "R2", "nom": "Mécanicien", "competences": ["mecanique", "demontage"]},
            {"id": "R3", "nom": "Électricien", "competences": ["electrique", "revision"]},
            {"id": "R4", "nom": "Magasinier", "competences": ["pieces"]},
        ],
        "contraintes": [
            # Workflow avec parallélisme (T2 et T3 en parallèle après T1)
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T1", "apres": "T3"},
            {"type": "precedence", "avant": "T2", "apres": "T4"},
            {"type": "precedence", "avant": "T3", "apres": "T4"},
            {"type": "precedence", "avant": "T4", "apres": "T5"},
            # Compétences
            {"type": "competence_requise", "tache": "T1", "competence": "diagnostic"},
            {"type": "competence_requise", "tache": "T2", "competence": "mecanique"},
            {"type": "competence_requise", "tache": "T3", "competence": "electrique"},
            {"type": "competence_requise", "tache": "T4", "competence": "pieces"},
            {"type": "competence_requise", "tache": "T5", "competence": "test"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def creer_instance_imprimerie() -> dict[str, Any]:
    """Imprimerie offset - 9 tâches."""
    return {
        "taches": [
            {"id": "T1", "nom": "Prépresse (PAO)", "duree_estimee_jours": 2},
            {"id": "T2", "nom": "Gravure plaques", "duree_estimee_jours": 1},
            {"id": "T3", "nom": "Calage presse", "duree_estimee_jours": 1},
            {"id": "T4", "nom": "Impression recto", "duree_estimee_jours": 3},
            {"id": "T5", "nom": "Séchage recto", "duree_estimee_jours": 1},
            {"id": "T6", "nom": "Impression verso", "duree_estimee_jours": 3},
            {"id": "T7", "nom": "Séchage verso", "duree_estimee_jours": 1},
            {"id": "T8", "nom": "Découpe et façonnage", "duree_estimee_jours": 2},
            {"id": "T9", "nom": "Reliure et finition", "duree_estimee_jours": 2},
        ],
        "ressources": [
            {"id": "R1", "nom": "Station PAO", "competences": ["prepresse", "pao"]},
            {"id": "R2", "nom": "CTP (Computer To Plate)", "competences": ["gravure"]},
            {"id": "R3", "nom": "Presse offset 4 couleurs", "competences": ["calage", "impression"]},
            {"id": "R4", "nom": "Séchoir UV", "competences": ["sechage"]},
            {"id": "R5", "nom": "Massicot", "competences": ["decoupe", "faconnage"]},
            {"id": "R6", "nom": "Plieuse-piqueuse", "competences": ["reliure", "finition"]},
        ],
        "contraintes": [
            # Workflow impression recto-verso
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "precedence", "avant": "T3", "apres": "T4"},
            {"type": "precedence", "avant": "T4", "apres": "T5"},
            {"type": "precedence", "avant": "T5", "apres": "T6"},
            {"type": "precedence", "avant": "T6", "apres": "T7"},
            {"type": "precedence", "avant": "T7", "apres": "T8"},
            {"type": "precedence", "avant": "T8", "apres": "T9"},
            # Compétences
            {"type": "competence_requise", "tache": "T1", "competence": "prepresse"},
            {"type": "competence_requise", "tache": "T2", "competence": "gravure"},
            {"type": "competence_requise", "tache": "T3", "competence": "calage"},
            {"type": "competence_requise", "tache": "T4", "competence": "impression"},
            {"type": "competence_requise", "tache": "T5", "competence": "sechage"},
            {"type": "competence_requise", "tache": "T6", "competence": "impression"},
            {"type": "competence_requise", "tache": "T7", "competence": "sechage"},
            {"type": "competence_requise", "tache": "T8", "competence": "decoupe"},
            {"type": "competence_requise", "tache": "T9", "competence": "reliure"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def creer_instance_hopital_bloc_operatoire() -> dict[str, Any]:
    """Planification bloc opératoire - 5 tâches."""
    return {
        "taches": [
            {"id": "T1", "nom": "Préparation patient", "duree_estimee_jours": 1},
            {"id": "T2", "nom": "Installation en salle", "duree_estimee_jours": 1},
            {"id": "T3", "nom": "Intervention chirurgicale", "duree_estimee_jours": 3},
            {"id": "T4", "nom": "Surveillance post-op", "duree_estimee_jours": 2},
            {"id": "T5", "nom": "Désinfection salle", "duree_estimee_jours": 1},
        ],
        "ressources": [
            {"id": "R1", "nom": "Salle de préparation", "competences": ["preparation_patient"]},
            {
                "id": "R2",
                "nom": "Bloc opératoire 1",
                "competences": ["installation", "intervention", "desinfection"],
            },
            {"id": "R3", "nom": "Salle de réveil", "competences": ["surveillance_post_op"]},
            {"id": "R4", "nom": "Équipe stérilisation", "competences": ["desinfection"]},
        ],
        "contraintes": [
            # Workflow chirurgical
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "precedence", "avant": "T3", "apres": "T4"},
            {"type": "precedence", "avant": "T3", "apres": "T5"},  # Désinfection après opération
            # Compétences
            {"type": "competence_requise", "tache": "T1", "competence": "preparation_patient"},
            {"type": "competence_requise", "tache": "T2", "competence": "installation"},
            {"type": "competence_requise", "tache": "T3", "competence": "intervention"},
            {"type": "competence_requise", "tache": "T4", "competence": "surveillance_post_op"},
            {"type": "competence_requise", "tache": "T5", "competence": "desinfection"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def creer_instance_logistique_transport() -> dict[str, Any]:
    """Logistique et transport - 6 tâches."""
    return {
        "taches": [
            {"id": "T1", "nom": "Réception commande", "duree_estimee_jours": 1},
            {"id": "T2", "nom": "Préparation colis", "duree_estimee_jours": 2},
            {"id": "T3", "nom": "Contrôle et étiquetage", "duree_estimee_jours": 1},
            {"id": "T4", "nom": "Palettisation", "duree_estimee_jours": 1},
            {"id": "T5", "nom": "Chargement camion", "duree_estimee_jours": 1},
            {"id": "T6", "nom": "Livraison", "duree_estimee_jours": 3},
        ],
        "ressources": [
            {"id": "R1", "nom": "Plateforme réception", "competences": ["reception"]},
            {"id": "R2", "nom": "Zone préparation", "competences": ["preparation"]},
            {"id": "R3", "nom": "Poste contrôle", "competences": ["controle", "etiquetage"]},
            {"id": "R4", "nom": "Zone expédition", "competences": ["palettisation", "chargement"]},
            {"id": "R5", "nom": "Camion livraison", "competences": ["livraison"]},
        ],
        "contraintes": [
            # Workflow logistique
            {"type": "precedence", "avant": "T1", "apres": "T2"},
            {"type": "precedence", "avant": "T2", "apres": "T3"},
            {"type": "precedence", "avant": "T3", "apres": "T4"},
            {"type": "precedence", "avant": "T4", "apres": "T5"},
            {"type": "precedence", "avant": "T5", "apres": "T6"},
            # Compétences
            {"type": "competence_requise", "tache": "T1", "competence": "reception"},
            {"type": "competence_requise", "tache": "T2", "competence": "preparation"},
            {"type": "competence_requise", "tache": "T3", "competence": "controle"},
            {"type": "competence_requise", "tache": "T4", "competence": "palettisation"},
            {"type": "competence_requise", "tache": "T5", "competence": "chargement"},
            {"type": "competence_requise", "tache": "T6", "competence": "livraison"},
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }


def main() -> None:
    """Génère tous les exemples dans data/instances_format_simplifie/."""
    instances = {
        "atelier_mecanique": creer_instance_atelier_mecanique(),
        "assemblage_electronique": creer_instance_assemblage_electronique(),
        "production_agroalimentaire": creer_instance_production_agroalimentaire(),
        "maintenance_industrielle": creer_instance_maintenance_industrielle(),
        "imprimerie": creer_instance_imprimerie(),
        "hopital_bloc_operatoire": creer_instance_hopital_bloc_operatoire(),
        "logistique_transport": creer_instance_logistique_transport(),
    }

    # Créer le répertoire de destination
    output_dir = Path("data/instances_format_simplifie")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Générer chaque instance
    for nom, instance in instances.items():
        output_path = output_dir / f"{nom}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(instance, f, indent=2, ensure_ascii=False)
        print(f"[OK] {output_path}")

    # Créer un README
    readme_path = output_dir / "README.md"
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(
            """# Instances au Format Simplifié

Ce répertoire contient des instances d'exemple au format simplifié, similaire à `instance_exemple.json`.

## Format

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

## Différences avec le format TRCO complet

- **Durée sur la tâche**: `duree_estimee_jours` directement dans la tâche, pas dans une contrainte
- **Compétences**: utilise `competence_requise` pour lier tâches et ressources
- **Compatibilité**: pas de contrainte `compatibilite_ressource_tache` explicite

## Instances disponibles

"""
        )

        for nom, instance in instances.items():
            nb_taches = len(instance["taches"])
            nb_ressources = len(instance["ressources"])
            f.write(f"- **{nom}**: {nb_taches} tâches, {nb_ressources} ressources\n")

        f.write(
            """
## Utilisation

Ces instances peuvent être utilisées pour:
1. Tester des adaptateurs d'ingestion
2. Valider le format simplifié
3. Prototypage rapide de scénarios métier
4. Documentation et exemples

## Conversion vers TRCO

Pour convertir ces instances au format TRCO complet, vous pouvez utiliser un adaptateur qui:
1. Dérive les contraintes `compatibilite_ressource_tache` à partir des compétences
2. Extrait la durée de la tâche vers les contraintes de compatibilité
3. Ajoute les métadonnées manquantes (priorite, statut, etc.)

Voir `adapters/competence_derivation.py` pour la logique de dérivation.
"""
        )

    print(f"\n[OK] {len(instances)} instances générées dans {output_dir}")
    print(f"[OK] README créé: {readme_path}")


if __name__ == "__main__":
    main()
