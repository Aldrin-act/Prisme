# Données Brutes au Format Simplifié

Ce répertoire contient des données brutes au format simplifié, utilisant directement
la structure taches/ressources/contraintes du T-R-C-O canonique.

## Différence avec les autres formats

**Format ERP** (`data/donnees_brutes/json_erp/`):
- Vocabulaire propriétaire: `operations` / `postes`
- Structure linéaire avec `operation_precedente`
- Nécessite un adaptateur (translator) pour conversion en TRCO

**Format Simplifié** (ce répertoire):
- Vocabulaire canonique: `taches` / `ressources`
- Compatibilité ressource-tâche déjà explicite (durée comprise)
- Instances T-R-C-O prêtes à l'emploi, ingérables directement sans transformation

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
    {"id": "T1", "nom": "Nom de la tâche"}
  ],
  "ressources": [
    {"id": "R1", "nom": "Nom de la ressource"}
  ],
  "contraintes": [
    {"type": "precedence", "avant": "T1", "apres": "T2"},
    {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 3}
  ],
  "objectifs": [
    {"type": "minimiser_makespan"}
  ]
}
```

## Utilisation

Ces données brutes peuvent être utilisées pour:

1. **Ingestion directe**: Import via l'API, aucune transformation nécessaire
2. **Prototypage**: Tests rapides sans adapter depuis un format ERP
3. **Exemples**: Documentation et démonstrations
4. **Tests**: Validation de la chaîne de traitement

## Regénération

```bash
uv run python -m scripts.generer_donnees_brutes_format_simplifie
```
