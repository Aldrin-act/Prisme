# Index - Instances TRCO avec Objectifs Variés

## Fichiers d'Instances (JSON)

### 01_makespan_simple.json
- **Tâches**: 4 | **Ressources**: 3 | **Contraintes**: 8
- **Objectifs**: 1 (minimiser_makespan)
- **Complexité**: ★☆☆☆☆ (Simple)
- **Utilisation**: Tests de base, validation initiale

### 02_equilibrage_charge.json
- **Tâches**: 6 | **Ressources**: 3 | **Contraintes**: 18
- **Objectifs**: 2 (equilibrer_charge 70%, minimiser_makespan 30%)
- **Complexité**: ★★★☆☆ (Moyenne)
- **Particularité**: Flexibilité maximale (toutes tâches → toutes ressources)

### 03_minimiser_retards.json
- **Tâches**: 5 | **Ressources**: 2 | **Contraintes**: 15 (dont 4 échéances)
- **Objectifs**: 2 (minimiser_retards 80%, minimiser_makespan 20%)
- **Complexité**: ★★★☆☆ (Moyenne)
- **Particularité**: Échéances strictes, priorités différenciées

### 04_maximiser_utilisation.json
- **Tâches**: 6 | **Ressources**: 3 | **Contraintes**: 16
- **Objectifs**: 2 (maximiser_utilisation 60%, minimiser_makespan 40%)
- **Complexité**: ★★★☆☆ (Moyenne)
- **Particularité**: Ressources avec compétences, focus sur R1 (premium)

### 05_minimiser_changements.json
- **Tâches**: 7 | **Ressources**: 3 | **Contraintes**: 25
- **Objectifs**: 3 (minimiser_changements 50%, makespan 30%, equilibrage 20%)
- **Complexité**: ★★★☆☆ (Moyenne)
- **Particularité**: 3 séries de tâches, coûts de changement différenciés

### 06_multi_objectifs_complexe.json
- **Tâches**: 8 | **Ressources**: 4 | **Contraintes**: 22 (dont 3 échéances)
- **Objectifs**: 5 (tous les types combinés)
- **Complexité**: ★★★★★ (Élevée)
- **Particularité**: Scénario industriel réaliste, compétences, échéances

## Documentation

### README.md
Vue d'ensemble du répertoire, description de chaque instance, exemples d'utilisation de base

### GUIDE_UTILISATION.md
**Guide complet** avec :
- Code Python détaillé pour charger, générer, valider
- Pipeline complète bout-en-bout
- Tests automatisés (pytest)
- Benchmarking
- Notes de compatibilité

### OBJECTIFS_DISPONIBLES.md
**Référence complète** de tous les objectifs :
- 5 types d'objectifs de base
- Paramètres détaillés
- Exemples JSON
- Cas d'usage
- Objectifs multiples
- Extension avec objectifs personnalisés

### INDEX.md
Ce fichier - vue d'ensemble de tous les fichiers du répertoire

## Scripts (dans `scripts/`)

### generer_instances_objectifs_varies.py
**Script de génération** des 6 instances TRCO

**Usage**:
```bash
python -m scripts.generer_instances_objectifs_varies
```

**Fonctionnalités**:
- Génère 6 instances JSON variées
- Crée automatiquement le README.md
- Affiche un résumé de chaque instance générée

### valider_instances_objectifs_varies.py
**Script de validation** des instances générées

**Usage**:
```bash
python -m scripts.valider_instances_objectifs_varies
```

**Vérifications effectuées**:
- Structure JSON valide
- Clés obligatoires présentes
- IDs uniques
- Chaque tâche a au moins une compatibilité ressource
- Contraintes référencent des entités existantes
- Objectifs valides avec paramètres corrects
- Durées et échéances positives

## Arborescence Complète

```
dsl/examples/objectifs_varies/
├── 01_makespan_simple.json
├── 02_equilibrage_charge.json
├── 03_minimiser_retards.json
├── 04_maximiser_utilisation.json
├── 05_minimiser_changements.json
├── 06_multi_objectifs_complexe.json
├── README.md
├── GUIDE_UTILISATION.md
├── OBJECTIFS_DISPONIBLES.md
└── INDEX.md (ce fichier)

scripts/
├── generer_instances_objectifs_varies.py
└── valider_instances_objectifs_varies.py
```

## Workflow Recommandé

### 1. Découverte
Lire `README.md` pour une vue d'ensemble rapide

### 2. Apprentissage
Consulter `OBJECTIFS_DISPONIBLES.md` pour comprendre les types d'objectifs

### 3. Utilisation
Suivre `GUIDE_UTILISATION.md` pour intégrer les instances dans votre pipeline

### 4. Développement
- Modifier `generer_instances_objectifs_varies.py` pour créer de nouvelles instances
- Utiliser `valider_instances_objectifs_varies.py` pour vérifier la validité

## Statistiques Globales

| Métrique | Total |
|----------|-------|
| Instances | 6 |
| Tâches totales | 40 |
| Ressources totales | 18 |
| Contraintes totales | 104 |
| Types d'objectifs couverts | 5/5 (100%) |
| Pages de documentation | 4 |

## Prochaines Étapes

### Pour utiliser immédiatement
1. Charger une instance : `charger_instance_depuis_json("...")`
2. Générer un solveur : `generer_et_tester_solveur(instance)`
3. Exécuter et valider

### Pour étendre
1. **Ajouter de nouvelles instances** : Modifier `generer_instances_objectifs_varies.py`
2. **Créer des objectifs personnalisés** : Voir `OBJECTIFS_DISPONIBLES.md` § Extension
3. **Automatiser les tests** : Utiliser les exemples de `GUIDE_UTILISATION.md`

### Compatibilité actuelle

⚠️ **Important** : Pour utiliser les objectifs variés, mettre à jour `dsl/schema/instance.py` :

```python
# Ligne 34 - Remplacer
objectifs: list[MinimiserMakespan] = Field(min_length=1)

# Par
from .objectifs_parametrables import Objectif
objectifs: list[Objectif] = Field(min_length=1)
```

## Support

- Documentation projet : `CLAUDE.md`, `CONTRIBUTING.md`
- Note de cadrage : `PRISME_Note_de_Cadrage (2).md`
- Issues GitHub : (à créer selon votre workflow)

---

**Dernière mise à jour** : 2026-07-23
**Version** : 1.0
**Auteur** : Pipeline PRISME (EIGSI × BARAA Consult)
