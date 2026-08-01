# Données Brutes au Format Simplifié

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

- **exemple_minimal**: 2 tâches, 1 ressources
- **atelier_mecanique_petit**: 4 tâches, 4 ressources
- **atelier_mecanique_moyen**: 6 tâches, 6 ressources
- **assemblage_electronique**: 5 tâches, 5 ressources
- **production_agroalimentaire**: 5 tâches, 5 ressources
- **imprimerie_petit**: 4 tâches, 4 ressources
- **maintenance**: 5 tâches, 2 ressources
- **logistique**: 4 tâches, 4 ressources
- **hopital**: 3 tâches, 3 ressources
- **restauration**: 4 tâches, 4 ressources

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
