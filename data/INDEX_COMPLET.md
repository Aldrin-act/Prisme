# Index Complet - Données et Instances PRISME

## Vue d'Ensemble

Ce document indexe l'ensemble des jeux de données créés pour PRISME, incluant :
- **Données brutes** simulant des exports ERP réels
- **Instances TRCO** transformées et validées
- **Instances avec objectifs variés** pour tests avancés
- **Scripts de génération et transformation**
- **Documentation complète**

---

## 📁 Structure Complète

```
Prisme/
├── data/                                    # DONNÉES BRUTES ET INSTANCES
│   ├── donnees_brutes/
│   │   ├── json_erp/                       # 5 fichiers JSON (format ERP)
│   │   ├── csv/                            # 10 fichiers CSV (5 paires)
│   │   └── README.md
│   ├── instances_trco/                     # 5 instances TRCO transformées
│   ├── README.md
│   ├── GUIDE_DONNEES.md
│   └── INDEX_COMPLET.md                    # Ce fichier
│
├── dsl/examples/objectifs_varies/          # INSTANCES AVEC OBJECTIFS VARIÉS
│   ├── 01_makespan_simple.json
│   ├── 02_equilibrage_charge.json
│   ├── 03_minimiser_retards.json
│   ├── 04_maximiser_utilisation.json
│   ├── 05_minimiser_changements.json
│   ├── 06_multi_objectifs_complexe.json
│   ├── README.md
│   ├── GUIDE_UTILISATION.md
│   ├── OBJECTIFS_DISPONIBLES.md
│   └── INDEX.md
│
└── scripts/                                 # SCRIPTS UTILITAIRES
    ├── generer_donnees_brutes.py
    ├── transformer_donnees_brutes.py
    ├── demo_donnees_brutes.py
    ├── generer_instances_objectifs_varies.py
    └── valider_instances_objectifs_varies.py
```

---

## 📊 Jeux de Données Brutes (Format ERP)

### Sources Simulées - 5 Secteurs Industriels

| Fichier | Secteur | Ops | Postes | Format | Description |
|---------|---------|-----|--------|--------|-------------|
| `atelier_mecanique` | Métallurgie | 8 | 8 | JSON+CSV | Découpe, perçage, soudure, peinture |
| `assemblage_electronique` | Électronique | 10 | 9 | JSON+CSV | PCB, pick&place, refusion, AOI |
| `production_agroalimentaire` | Agro-alimentaire | 9 | 9 | JSON+CSV | Lavage, cuisson, conditionnement |
| `maintenance_industrielle` | Maintenance | 7 | 5 | JSON+CSV | Diagnostic, réparation, tests |
| `imprimerie` | Impression | 9 | 7 | JSON+CSV | Pré-presse, impression, finition |

**Total**: 5 fichiers JSON + 10 fichiers CSV = **15 fichiers**

### Emplacement
- **JSON**: `data/donnees_brutes/json_erp/*.json`
- **CSV**: `data/donnees_brutes/csv/*_operations.csv` + `*_postes.csv`

### Génération
```bash
python -m scripts.generer_donnees_brutes
```

---

## 🎯 Instances TRCO (Format Canonique)

### Instances Transformées - 5 Fichiers

| Fichier | Tâches | Ressources | Contraintes | Objectifs |
|---------|--------|------------|-------------|-----------|
| `atelier_mecanique.json` | 8 | 8 | 15 | 1 |
| `assemblage_electronique.json` | 10 | 9 | 19 | 1 |
| `production_agroalimentaire.json` | 9 | 9 | 17 | 1 |
| `maintenance_industrielle.json` | 7 | 5 | 13 | 1 |
| `imprimerie.json` | 9 | 7 | 17 | 1 |

**Total**: 5 instances TRCO validées

### Emplacement
`data/instances_trco/*.json`

### Transformation
```bash
# Transformer toutes les données brutes
python -m scripts.transformer_donnees_brutes

# Transformer un fichier spécifique
python -m scripts.transformer_donnees_brutes --input data/donnees_brutes/json_erp/atelier_mecanique.json
```

---

## 🎲 Instances avec Objectifs Variés

### 6 Instances de Test Avancées

| Instance | Objectifs | Tâches | Ressources | Complexité | Focus |
|----------|-----------|--------|------------|------------|-------|
| `01_makespan_simple` | 1 | 4 | 3 | ★☆☆☆☆ | Validation de base |
| `02_equilibrage_charge` | 2 | 6 | 3 | ★★★☆☆ | Distribution équitable |
| `03_minimiser_retards` | 2 | 5 | 2 | ★★★☆☆ | Respect des échéances |
| `04_maximiser_utilisation` | 2 | 6 | 3 | ★★★☆☆ | ROI équipements |
| `05_minimiser_changements` | 3 | 7 | 3 | ★★★☆☆ | Réduction setup |
| `06_multi_objectifs_complexe` | 5 | 8 | 4 | ★★★★★ | Scénario réaliste |

**Total**: 6 instances avec objectifs variés

### Emplacement
`dsl/examples/objectifs_varies/*.json`

### Génération
```bash
python -m scripts.generer_instances_objectifs_varies
```

### Validation
```bash
python -m scripts.valider_instances_objectifs_varies
```

---

## 📚 Documentation

### Guides Principaux

| Document | Emplacement | Contenu |
|----------|-------------|---------|
| **Guide Complet du Workflow** | `data/GUIDE_DONNEES.md` | Pipeline de transformation complète A→Z |
| **README Données** | `data/README.md` | Vue d'ensemble, quick start |
| **README Données Brutes** | `data/donnees_brutes/README.md` | Détails des formats sources |
| **Guide Objectifs Variés** | `dsl/examples/objectifs_varies/GUIDE_UTILISATION.md` | Usage avancé des objectifs |
| **Référence Objectifs** | `dsl/examples/objectifs_varies/OBJECTIFS_DISPONIBLES.md` | Documentation complète des 5 types |
| **Index Objectifs** | `dsl/examples/objectifs_varies/INDEX.md` | Navigation rapide |
| **Index Complet** | `data/INDEX_COMPLET.md` | Ce document |

**Total**: 7 fichiers de documentation

---

## 🛠️ Scripts Utilitaires

### Scripts de Génération

| Script | Fonction | Usage |
|--------|----------|-------|
| `generer_donnees_brutes.py` | Crée 5 jeux de données ERP | `python -m scripts.generer_donnees_brutes` |
| `generer_instances_objectifs_varies.py` | Crée 6 instances avec objectifs | `python -m scripts.generer_instances_objectifs_varies` |

### Scripts de Transformation

| Script | Fonction | Usage |
|--------|----------|-------|
| `transformer_donnees_brutes.py` | ERP → TRCO | `python -m scripts.transformer_donnees_brutes` |
| `valider_instances_objectifs_varies.py` | Valide les instances | `python -m scripts.valider_instances_objectifs_varies` |

### Scripts de Démonstration

| Script | Fonction | Usage |
|--------|----------|-------|
| `demo_donnees_brutes.py` | Workflow complet bout-en-bout | `python -m scripts.demo_donnees_brutes` |

**Total**: 5 scripts Python

---

## 📈 Statistiques Globales

### Données Brutes
- **Jeux de données**: 5 secteurs industriels
- **Fichiers JSON**: 5
- **Fichiers CSV**: 10 (5 paires)
- **Opérations totales**: 43
- **Postes totaux**: 38

### Instances TRCO
- **Instances de base**: 5
- **Instances avec objectifs variés**: 6
- **Total instances**: 11
- **Tâches totales**: 83
- **Ressources totales**: 56
- **Contraintes totales**: 185

### Documentation
- **Guides complets**: 7
- **Pages totales**: ~50 pages (équivalent)

### Scripts
- **Génération**: 2
- **Transformation**: 2
- **Démonstration**: 1
- **Total**: 5 scripts

---

## 🚀 Workflows

### 1. Workflow Standard : Données Brutes → Planning

```bash
# Étape 1 : Générer les données brutes
python -m scripts.generer_donnees_brutes

# Étape 2 : Transformer en TRCO
python -m scripts.transformer_donnees_brutes

# Étape 3 : Voir la démonstration complète
python -m scripts.demo_donnees_brutes

# Étape 4 : Utiliser dans votre code
# (voir data/GUIDE_DONNEES.md)
```

### 2. Workflow Tests Avancés : Objectifs Variés

```bash
# Étape 1 : Générer les instances avec objectifs
python -m scripts.generer_instances_objectifs_varies

# Étape 2 : Valider les instances
python -m scripts.valider_instances_objectifs_varies

# Étape 3 : Utiliser dans vos tests
# (voir dsl/examples/objectifs_varies/GUIDE_UTILISATION.md)
```

---

## 🎯 Cas d'Usage

### Pour les Tests

```python
# Charger une instance TRCO simple
from dsl.validation.charger_instance import charger_instance_depuis_json

instance = charger_instance_depuis_json("data/instances_trco/atelier_mecanique.json")
```

### Pour le Développement

```python
# Charger une instance avec objectifs variés
instance = charger_instance_depuis_json(
    "dsl/examples/objectifs_varies/06_multi_objectifs_complexe.json"
)
```

### Pour la Production

```python
# Transformer vos propres données ERP
from adapters.erp_reference.schema_erp import PayloadERP
from adapters.erp_reference.translator import traduire
import json

with open("mes_donnees.json") as f:
    payload = PayloadERP(**json.load(f))

instance = traduire(payload)
```

---

## 📋 Checklist de Vérification

### Données Générées ✅

- [x] 5 jeux de données brutes (JSON)
- [x] 10 fichiers CSV (5 paires)
- [x] 5 instances TRCO transformées
- [x] 6 instances avec objectifs variés
- [x] Toutes les instances validées

### Scripts Opérationnels ✅

- [x] Génération données brutes
- [x] Transformation ERP → TRCO
- [x] Génération instances objectifs variés
- [x] Validation des instances
- [x] Script de démonstration

### Documentation Complète ✅

- [x] Guide workflow complet
- [x] README données
- [x] README données brutes
- [x] Guide objectifs variés
- [x] Référence des objectifs
- [x] Index de navigation
- [x] Index complet (ce fichier)

---

## 🔗 Navigation Rapide

### Par Type de Données

- **Données ERP brutes** → `data/donnees_brutes/`
- **Instances TRCO** → `data/instances_trco/`
- **Objectifs variés** → `dsl/examples/objectifs_varies/`

### Par Type de Document

- **Guides pratiques** → `data/GUIDE_DONNEES.md`, `dsl/examples/objectifs_varies/GUIDE_UTILISATION.md`
- **Références** → `dsl/examples/objectifs_varies/OBJECTIFS_DISPONIBLES.md`
- **Quick start** → `data/README.md`

### Par Activité

- **Générer des données** → Scripts dans `scripts/`
- **Transformer des données** → `scripts/transformer_donnees_brutes.py`
- **Tester la pipeline** → `scripts/demo_donnees_brutes.py`

---

## 📞 Support

Pour toute question :

1. **Workflow de transformation** → Consultez `data/GUIDE_DONNEES.md`
2. **Objectifs d'optimisation** → Consultez `dsl/examples/objectifs_varies/OBJECTIFS_DISPONIBLES.md`
3. **Architecture générale** → Consultez `CLAUDE.md`
4. **Contribution** → Consultez `CONTRIBUTING.md`

---

**Dernière mise à jour**: 2026-07-23
**Version**: 1.0
**Auteur**: Pipeline PRISME (EIGSI Casablanca × BARAA Consult)

**Total des fichiers créés**: 38 fichiers (15 données brutes + 11 instances + 7 docs + 5 scripts)
