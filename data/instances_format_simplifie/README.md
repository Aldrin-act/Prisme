# Instances au Format Simplifié

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

- **atelier_mecanique**: 6 tâches, 6 ressources
- **assemblage_electronique**: 8 tâches, 7 ressources
- **production_agroalimentaire**: 7 tâches, 7 ressources
- **maintenance_industrielle**: 5 tâches, 4 ressources
- **imprimerie**: 9 tâches, 6 ressources
- **hopital_bloc_operatoire**: 5 tâches, 4 ressources
- **logistique_transport**: 6 tâches, 5 ressources

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
