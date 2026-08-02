# Données Brutes à Grande Échelle

Ce répertoire contient des jeux de données volumineux (~200 opérations par fichier)
pour tester la scalabilité de la pipeline PRISME.

## Jeux de Données

- **atelier_mecanique_large** : 200+ opérations, fabrication métallique
- **assemblage_electronique_large** : 200+ opérations, assemblage PCB
- **production_agroalimentaire_large** : 200+ opérations, transformation alimentaire
- **hopital_bloc_operatoire_large** : 200+ opérations, planification hospitalière
- **logistique_transport_large** : 200+ opérations, logistique et transport
- **restauration_collective_large** : 200+ opérations, restauration collective
- **services_nettoyage_large** : 200+ opérations, services de nettoyage
- **gestion_espaces_verts_large** : 200+ opérations, gestion d'espaces verts
- **education_planification_cours_large** : 200+ opérations, planification de cours

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

Génération : 200 opérations/fichier
Date : 2026-07-23
