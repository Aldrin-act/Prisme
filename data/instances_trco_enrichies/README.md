# Instances TRCO Enrichies avec Objectifs Configurables

Ce répertoire contient des instances TRCO enrichies avec différentes configurations
d'objectifs d'optimisation. Chaque instance de base a été déclinée en 6 variantes,
permettant de tester différentes stratégies d'optimisation.

## Vue d'ensemble

**49 instances enrichies** générées à partir de 8 instances de base :
- 5 instances standard (7-10 tâches)
- 3 instances à grande échelle (100 tâches)

Chaque instance déclinée en **6 configurations d'objectifs** :
1. `makespan` - Minimiser uniquement le makespan
2. `equilibrage` - Équilibrage de charge + makespan
3. `retards` - Minimiser les retards (avec échéances)
4. `utilisation` - Maximiser l'utilisation des ressources
5. `changements` - Minimiser les changements de ressources
6. `multi` - Configuration multi-objectifs complète (5 objectifs)

## Nomenclature des Fichiers

```
{instance_base}_{configuration}.json

Exemples:
  atelier_mecanique_makespan.json
  atelier_mecanique_large_equilibrage.json
  assemblage_electronique_multi.json
```

## Configurations Disponibles

### 1. makespan (Simple)
**Objectif** : Minimiser uniquement le makespan (durée totale)

```json
{
  "objectifs": [
    {"type": "minimiser_makespan", "poids": 1.0, "makespan_cible": <estimé>}
  ]
}
```

**Cas d'usage** :
- Production avec contrainte de livraison stricte
- Minimisation du temps total de fabrication
- Baseline pour comparaison

**Instances** : 8 (toutes les instances de base)

---

### 2. equilibrage (Ressources)
**Objectif** : Équilibrer la charge + makespan

```json
{
  "objectifs": [
    {"type": "equilibrer_charge", "poids": 0.6, "methode": "ecart_max"},
    {"type": "minimiser_makespan", "poids": 0.4}
  ]
}
```

**Cas d'usage** :
- Distribution équitable du travail
- Éviter la surcharge de certaines ressources
- Optimisation de la durée de vie des équipements

**Instances** : 8

---

### 3. retards (Délais)
**Objectif** : Minimiser les retards + makespan + **échéances générées**

```json
{
  "objectifs": [
    {
      "type": "minimiser_retards",
      "poids": 0.7,
      "fonction_penalite": "quadratique",
      "seuil_grace": 10
    },
    {"type": "minimiser_makespan", "poids": 0.3}
  ],
  "contraintes": [
    ...
    {"type": "echeance", "tache": "T_xxx", "echeance": <valeur>}
  ]
}
```

**Particularité** : Échéances ajoutées automatiquement (~50% des tâches)

**Cas d'usage** :
- Gestion de commandes avec SLA
- Production avec délais contractuels
- Minimisation des pénalités de retard

**Instances** : 8 (+ échéances)

---

### 4. utilisation (ROI)
**Objectif** : Maximiser l'utilisation + makespan

```json
{
  "objectifs": [
    {"type": "maximiser_utilisation", "poids": 0.6},
    {"type": "minimiser_makespan", "poids": 0.4}
  ]
}
```

**Cas d'usage** :
- Amortissement d'équipements coûteux
- Maximisation du ROI
- Réduction des temps morts

**Instances** : 8

---

### 5. changements (Efficacité)
**Objectif** : Minimiser les changements + makespan + équilibrage

```json
{
  "objectifs": [
    {"type": "minimiser_changements", "poids": 0.5},
    {"type": "minimiser_makespan", "poids": 0.3},
    {"type": "equilibrer_charge", "poids": 0.2, "methode": "variance"}
  ]
}
```

**Cas d'usage** :
- Réduction des temps de setup
- Production par lots/séries
- Minimisation des changements d'outils

**Instances** : 8

---

### 6. multi (Complet)
**Objectif** : **5 objectifs combinés** + échéances

```json
{
  "objectifs": [
    {"type": "minimiser_makespan", "poids": 0.25, "makespan_cible": <estimé>},
    {"type": "equilibrer_charge", "poids": 0.25, "methode": "gini"},
    {"type": "minimiser_retards", "poids": 0.2, "fonction_penalite": "lineaire"},
    {"type": "maximiser_utilisation", "poids": 0.15},
    {"type": "minimiser_changements", "poids": 0.15}
  ]
}
```

**Particularité** : Échéances ajoutées automatiquement

**Cas d'usage** :
- Scénario réaliste de production industrielle
- Optimisation multi-critères
- Tests de performance avancés

**Instances** : 9 (8 de base + 1 avec compétences)

---

## Statistiques

| Configuration | Instances | Objectifs/instance | Avec échéances | Contraintes totales |
|---------------|-----------|-------------------|----------------|---------------------|
| makespan | 8 | 1 | 0/8 | 622 |
| equilibrage | 8 | 2 | 0/8 | 622 |
| retards | 8 | 2 | 8/8 ✅ | 792 |
| utilisation | 8 | 2 | 0/8 | 622 |
| changements | 8 | 3 | 0/8 | 622 |
| multi | 9 | 5 | 9/9 ✅ | 1060 |
| **TOTAL** | **49** | - | **17** | **4340** |

## Utilisation

### Charger une Instance Enrichie

```python
from dsl.validation.charger_instance import charger_instance_depuis_json

# Charger une instance avec configuration multi-objectifs
instance = charger_instance_depuis_json(
    "data/instances_trco_enrichies/atelier_mecanique_large_multi.json"
)

print(f"Taches: {len(instance.taches)}")
print(f"Objectifs: {len(instance.objectifs)}")

for objectif in instance.objectifs:
    print(f"  - {objectif.type} (poids: {objectif.poids})")
```

### Générer vos Propres Variantes

```bash
# Générer toutes les variantes pour toutes les instances
python -m scripts.configurer_objectifs --all

# Appliquer une configuration spécifique
python -m scripts.configurer_objectifs \
    --input data/instances_trco/atelier_mecanique.json \
    --config multi

# Ajouter des compétences aux ressources
python -m scripts.configurer_objectifs \
    --input data/instances_trco/atelier_mecanique_large.json \
    --config multi \
    --add-competences
```

### Analyser les Objectifs

```bash
# Afficher les statistiques des configurations
python -m scripts.analyser_objectifs
```

## Variantes avec Compétences

Le sous-répertoire `avec_competences/` contient des instances enrichies avec :
- **Compétences** attribuées aux ressources
- **Exigences de compétences** sur les tâches
- **Contraintes supplémentaires** `competence_requise`

Exemple :
```json
{
  "ressources": [
    {
      "id": "R1",
      "competences": ["usinage_precision", "programmation_cnc"]
    }
  ],
  "contraintes": [
    ...
    {
      "type": "competence_requise",
      "tache": "T5",
      "competence": "usinage_precision"
    }
  ]
}
```

**Génération** :
```bash
python -m scripts.configurer_objectifs \
    --input data/instances_trco/atelier_mecanique_large.json \
    --config multi \
    --add-competences \
    --output-dir data/instances_trco_enrichies/avec_competences
```

## Exemples d'Utilisation dans la Pipeline

### Test de Scalabilité

```python
# Tester sur une petite instance
instance_small = charger_instance_depuis_json(
    "data/instances_trco_enrichies/atelier_mecanique_multi.json"
)
resultat_small = generer_et_tester_solveur(instance_small)

# Tester sur une grande instance
instance_large = charger_instance_depuis_json(
    "data/instances_trco_enrichies/atelier_mecanique_large_multi.json"
)
resultat_large = generer_et_tester_solveur(instance_large)

# Comparer les temps de génération
print(f"Petite: {resultat_small.temps_generation}s")
print(f"Grande: {resultat_large.temps_generation}s")
```

### Benchmark par Configuration

```python
import time
from pathlib import Path

configurations = ["makespan", "equilibrage", "retards", "utilisation", "changements", "multi"]

for config in configurations:
    instances = list(Path("data/instances_trco_enrichies").glob(f"*_{config}.json"))

    temps_total = 0
    for instance_path in instances:
        instance = charger_instance_depuis_json(str(instance_path))

        debut = time.time()
        resultat = generer_et_tester_solveur(instance)
        fin = time.time()

        temps_total += (fin - debut)

    print(f"{config}: {temps_total/len(instances):.2f}s en moyenne")
```

## Régénération

Pour régénérer toutes les variantes :

```bash
# Supprimer les anciennes variantes
rm -rf data/instances_trco_enrichies/*

# Régénérer
python -m scripts.configurer_objectifs --all
```

## Notes Techniques

### Génération des Échéances

Les échéances sont générées automatiquement selon une stratégie "uniforme" :
- Appliquée à ~50% des tâches
- Distribuées uniformément entre 50% et 100% du makespan estimé
- Makespan estimé = `durée_totale / nb_ressources * 1.5`

### Génération des Compétences

Lorsque `--add-competences` est utilisé :
- 8 compétences génériques disponibles
- Chaque ressource reçoit 1-3 compétences aléatoires
- ~30% des tâches nécessitent 1-2 compétences spécifiques

### Pondération des Objectifs

Les poids sont **relatifs** :
- Pas besoin que la somme = 1.0
- Un poids plus élevé = plus d'importance
- Le solveur interprétera les poids selon sa stratégie

## Support

- **Documentation des objectifs** → `dsl/examples/objectifs_varies/OBJECTIFS_DISPONIBLES.md`
- **Guide complet des données** → `data/GUIDE_DONNEES.md`
- **Code source du configurateur** → `scripts/configurer_objectifs.py`

---

**Dernière génération** : 2026-07-23
**Nombre d'instances** : 49
**Total de contraintes** : 4340
**Total de tâches** : 2158
