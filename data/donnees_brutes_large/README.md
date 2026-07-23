# Données Brutes à Grande Échelle

Ce répertoire contient des jeux de données volumineux (~100 opérations par fichier)
pour tester la scalabilité de la pipeline PRISME.

## Jeux de Données

- **atelier_mecanique_large** : 100+ opérations, fabrication métallique
- **assemblage_electronique_large** : 100+ opérations, assemblage PCB
- **production_agroalimentaire_large** : 100+ opérations, transformation alimentaire

## Utilisation

### Transformation en instances TRCO

```bash
python -m scripts.transformer_donnees_brutes --input-dir data/donnees_brutes_large/json_erp
```

### Régénération

```bash
# Taille par défaut (100 opérations)
python -m scripts.generer_donnees_brutes_grande_echelle

# Taille personnalisée
python -m scripts.generer_donnees_brutes_grande_echelle --taille 150
python -m scripts.generer_donnees_brutes_grande_echelle --taille 200
```

## Caractéristiques

- Opérations organisées en lots de production réalistes
- Précédences entre opérations d'un même lot
- Multiples instances de chaque type de poste (haute capacité)
- Durées variables selon le type de poste
- Format compatible avec l'adaptateur ERP de référence

## Note

Ces instances volumineuses permettent de :
- Tester les performances du générateur LLM sur de grandes instances
- Valider la scalabilité du solveur CP-SAT
- Évaluer les temps d'exécution dans le sandbox
- Benchmarker la cascade de validation

Génération : 100 opérations/fichier
Date : 2026-07-23
