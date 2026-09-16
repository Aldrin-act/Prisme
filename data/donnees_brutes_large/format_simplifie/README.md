# Données Brutes Large au Format Simplifié

Ce répertoire contient des données brutes de **grande taille** (50-360+ tâches) au format simplifié,
avec compatibilité ressource-tâche déjà explicite (durée comprise).

## Fichiers générés

- **atelier_mecanique_large**: 160 tâches, 76 ressources
- **assemblage_electronique_large**: 360 tâches, 57 ressources
- **production_agroalimentaire_large**: 250 tâches, 58 ressources
- **imprimerie_large**: 145 tâches, 43 ressources

## Format

Identique au format simplifié standard (voir `instance_exemple.json`):

```json
{
  "taches": [
    {"id": "T0001", "nom": "Lot001_PREPARATION"}
  ],
  "ressources": [
    {"id": "R0001", "nom": "Decoupe Laser #1"}
  ],
  "contraintes": [
    {"type": "precedence", "avant": "T0001", "apres": "T0002"},
    {"type": "compatibilite_ressource_tache", "tache": "T0001", "ressource": "R0001", "duree": 2}
  ],
  "objectifs": [
    {"type": "minimiser_makespan"}
  ]
}
```

## Différences avec les données brutes "normales"

**Données normales** (`data/donnees_brutes/format_simplifie/`):
- Instances petites à moyennes (2-10 tâches)
- Pour tests rapides, prototypage, démonstrations

**Données large** (ce répertoire):
- Instances volumineuses (50-360+ tâches)
- Pour tests de performance, benchmarks, algorithmes heuristiques
- Générées procéduralement avec seed aléatoire (seed=42 pour reproductibilité)

## Utilisation

Ces données permettent de tester:
1. **Scalabilité** du système de génération de solveur
2. **Choix d'algorithme** (CP-SAT vs heuristiques) par le Benchmarker
3. **Performance** des solveurs générés sur problèmes réalistes
4. **Limites** du sandbox et timeouts

## Regénération

```bash
uv run python -m scripts.generer_donnees_brutes_large_format_simplifie
```

La génération utilise un seed fixe (42) pour garantir la reproductibilité des instances.
