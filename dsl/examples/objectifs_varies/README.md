# Instances TRCO avec Objectifs Variés

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
