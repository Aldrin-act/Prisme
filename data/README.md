# Data - Jeux de Données pour PRISME

Ce répertoire contient tous les jeux de données utilisés dans la pipeline PRISME,
depuis les données brutes sources jusqu'aux instances TRCO validées.

## Structure

```
data/
├── donnees_brutes/           # DONNÉES BRUTES (format ERP)
│   ├── json_erp/            # Format JSON ERP de référence
│   │   ├── atelier_mecanique.json
│   │   ├── assemblage_electronique.json
│   │   ├── production_agroalimentaire.json
│   │   ├── maintenance_industrielle.json
│   │   ├── imprimerie.json
│   │   └── centre_appels.json
│   ├── csv/                 # Format CSV simple
│   │   ├── *_operations.csv (6 fichiers)
│   │   └── *_postes.csv (6 fichiers)
│   └── README.md
│
├── instances_trco/           # INSTANCES TRCO (format canonique)
│   ├── atelier_mecanique.json
│   ├── assemblage_electronique.json
│   ├── production_agroalimentaire.json
│   ├── maintenance_industrielle.json
│   ├── imprimerie.json
│   └── centre_appels.json
│
├── README.md                 # Ce fichier
└── GUIDE_DONNEES.md          # Guide complet du workflow
```

## Quick Start

### 1. Générer les Données Brutes

```bash
# Génère 6 jeux de données en formats JSON + CSV
python -m scripts.generer_donnees_brutes
```

**Résultat**: 6 fichiers JSON + 12 fichiers CSV dans `donnees_brutes/`

### 2. Transformer en Instances TRCO

```bash
# Transforme toutes les données brutes en instances TRCO
python -m scripts.transformer_donnees_brutes
```

**Résultat**: 6 fichiers JSON TRCO dans `instances_trco/`

### 3. Utiliser dans la Pipeline

```python
from dsl.validation.charger_instance import charger_instance_depuis_json

# Charger une instance TRCO
instance = charger_instance_depuis_json("data/instances_trco/atelier_mecanique.json")

# L'instance est prête pour la génération de solveur
from generation.tentative_unique import generer_et_tester_solveur
resultat = generer_et_tester_solveur(instance)
```

## Jeux de Données Disponibles

| Nom | Secteur | Operations | Postes | Complexité |
|-----|---------|------------|--------|------------|
| `atelier_mecanique` | Fabrication métallique | 8 | 8 | Moyenne |
| `assemblage_electronique` | PCB manufacturing | 10 | 9 | Élevée |
| `production_agroalimentaire` | Transformation alim. | 9 | 9 | Moyenne |
| `maintenance_industrielle` | Gestion de pannes | 7 | 5 | Simple |
| `imprimerie` | Impression offset | 9 | 7 | Moyenne |
| `centre_appels` | Support client / helpdesk | 8 | 4 | Moyenne (compétences) |

## Formats de Données

### Données Brutes (ERP)

**Format JSON** - `donnees_brutes/json_erp/*.json`

```json
{
  "operations": [
    {
      "code_operation": "OP_001",
      "duree_jours": 2,
      "poste_id": "MACHINE_A",
      "operation_precedente": null
    }
  ],
  "postes": [
    {"code_poste": "MACHINE_A"}
  ]
}
```

**Format CSV** - `donnees_brutes/csv/*_operations.csv` + `*_postes.csv`

Fichiers séparés pour operations et postes, importables dans Excel/LibreOffice.

### Instances TRCO (Canonique)

**Format JSON** - `instances_trco/*.json`

```json
{
  "taches": [...],
  "ressources": [...],
  "contraintes": [
    {"type": "precedence", "avant": "T1", "apres": "T2"},
    {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 45}
  ],
  "objectifs": [
    {"type": "minimiser_makespan"}
  ]
}
```

## Scripts Disponibles

### Génération

```bash
# Générer les données brutes
python -m scripts.generer_donnees_brutes
```

### Transformation

```bash
# Transformer toutes les données brutes (défaut : json_erp/)
python -m scripts.transformer_donnees_brutes

# Transformer un fichier spécifique
python -m scripts.transformer_donnees_brutes --input data/donnees_brutes/json_erp/atelier_mecanique.json

# Depuis CSV
python -m scripts.transformer_donnees_brutes \
    --csv-operations data/donnees_brutes/csv/atelier_mecanique_operations.csv \
    --csv-postes data/donnees_brutes/csv/atelier_mecanique_postes.csv

# Transformer un répertoire entier
python -m scripts.transformer_donnees_brutes --input-dir data/donnees_brutes/json_erp
```

## Workflow de Transformation

```
┌────────────────┐
│ Données Brutes │  Format ERP propriétaire (JSON/CSV)
└────────┬───────┘
         │
         │  scripts/transformer_donnees_brutes.py
         │  adapters/erp_reference/translator.py
         ▼
┌────────────────┐
│ Instance TRCO  │  Format canonique validé (DSL)
└────────┬───────┘
         │
         │  generation/tentative_unique.py (mode single-shot legacy)
         ▼
┌────────────────┐
│ Solveur CP-SAT │  Code Python généré par LLM (ce module ne choisit pas
└────────────────┘  d'algorithme — pas de Benchmarker sur ce chemin)
```

Chemin de production réel : `generation/graph.py`, où un agent Benchmarker choisit l'algorithme
(`cp_sat` exact, ou une heuristique genetic/aco/tabu/... pour les grandes instances) avant que le
code soit généré — voir [CLAUDE.md](../CLAUDE.md), section Étape 6.

## Documentation

- **[GUIDE_DONNEES.md](GUIDE_DONNEES.md)** - Guide complet du workflow (⭐ À LIRE)
- **[donnees_brutes/README.md](donnees_brutes/README.md)** - Détails sur les données brutes
- **[../CLAUDE.md](../CLAUDE.md)** - Documentation projet PRISME

## Exemples d'Utilisation

### Charger et Valider une Instance

```python
from dsl.validation.charger_instance import charger_instance_depuis_json

instance = charger_instance_depuis_json("data/instances_trco/atelier_mecanique.json")

print(f"Taches: {len(instance.taches)}")
print(f"Ressources: {len(instance.ressources)}")
print(f"Contraintes: {len(instance.contraintes)}")
```

### Pipeline Complète

```python
import json
from adapters.erp_reference.schema_erp import PayloadERP
from adapters.erp_reference.translator import traduire
from generation.tentative_unique import generer_et_tester_solveur

# 1. Charger données brutes
with open("data/donnees_brutes/json_erp/atelier_mecanique.json") as f:
    payload_erp = PayloadERP(**json.load(f))

# 2. Traduire en TRCO
instance = traduire(payload_erp)

# 3. Générer solveur
resultat = generer_et_tester_solveur(instance)

if resultat.solveur:
    # 4. Exécuter
    planning = resultat.solveur(instance)
    if planning:
        makespan = max(op.debut + op.duree for op in planning.operations)
        print(f"Makespan: {makespan} minutes")
```

### Enrichir une Instance

```python
from dsl.schema import Echeance

# Charger instance de base
instance = charger_instance_depuis_json("data/instances_trco/atelier_mecanique.json")

# Ajouter une échéance
instance.contraintes.append(
    Echeance(tache="CONTROLE_QUALITE", echeance=300)
)

# Sauvegarder
with open("data/instances_trco/atelier_mecanique_avec_echeances.json", "w") as f:
    json.dump(instance.model_dump(mode="json"), f, indent=2)
```

## Statistiques

| Métrique | Total |
|----------|-------|
| Jeux de données bruts | 6 |
| Fichiers JSON ERP | 6 |
| Fichiers CSV | 12 (6 paires) |
| Instances TRCO | 6 |
| Tâches totales (toutes instances) | 51 |
| Ressources totales | 42 |
| Secteurs industriels couverts | 6 |

## Prochaines Étapes

1. **Utiliser les instances** dans votre pipeline de tests
2. **Créer vos propres données brutes** basées sur ces exemples
3. **Développer un adaptateur personnalisé** pour votre ERP
4. **Enrichir les instances** avec des objectifs variés

## Support

- Questions sur le format des données → [GUIDE_DONNEES.md](GUIDE_DONNEES.md)
- Questions sur les adaptateurs → `adapters/README.md`
- Questions générales → `CLAUDE.md`

---

**Dernière mise à jour**: 2026-07-23
**Auteur**: Pipeline PRISME (EIGSI × BARAA Consult)
