# Index des Données CSV

## Vue d'ensemble

Le répertoire `csv` contient **7 jeux de données** au format CSV, organisés par **3 secteurs** d'activité.

**Format**: CSV (paires operations + postes) ou CSV enrichi (JIRA)
**Organisation**: Structure hiérarchique par secteur
**Total fichiers CSV**: 13 fichiers

## Structure

```
csv/
├── industrie_manufacturiere/          (4 jeux, 8 fichiers)
│   ├── atelier_mecanique/
│   ├── assemblage_electronique/
│   ├── imprimerie/
│   └── production_agroalimentaire/
├── services/                          (2 jeux, 4 fichiers)
│   ├── centre_appels/
│   └── maintenance_industrielle/
├── informatique/                      (1 jeu, 1 fichier)
│   └── informatique_jira_export.csv
└── [Documentation]
    ├── README.md (ce fichier)
    ├── INDEX.md (navigation)
    └── [README par secteur]
```

## Navigation rapide

### 🏭 Industrie Manufacturière

| Secteur | Dossier | Opérations | Postes | Durée | README |
|---------|---------|------------|--------|-------|--------|
| **Atelier Mécanique** | `industrie_manufacturiere/atelier_mecanique/` | 8 | 8 | 12j | [Voir](industrie_manufacturiere/atelier_mecanique/README.md) |
| **Assemblage Électronique** | `industrie_manufacturiere/assemblage_electronique/` | 10 | 9 | 6j | [Voir](industrie_manufacturiere/assemblage_electronique/README.md) |
| **Imprimerie** | `industrie_manufacturiere/imprimerie/` | 9 | 7 | 5j | [Voir](industrie_manufacturiere/README.md) |
| **Production Agroalimentaire** | `industrie_manufacturiere/production_agroalimentaire/` | 9 | 9 | 9j | [Voir](industrie_manufacturiere/README.md) |

### 🛠️ Services

| Secteur | Dossier | Opérations | Postes | Durée | README |
|---------|---------|------------|--------|-------|--------|
| **Centre d'Appels** | `services/centre_appels/` | 8 | 4 | 0.67j | [Voir](services/centre_appels/README.md) |
| **Maintenance Industrielle** | `services/maintenance_industrielle/` | 7 | 5 | 7j | [Voir](services/README.md) |

### 💻 Informatique

| Secteur | Fichier | Format | README |
|---------|---------|--------|--------|
| **JIRA Export** | `informatique/informatique_jira_export.csv` | CSV enrichi | [Voir](informatique/README.md) |

## Démarrage rapide

### Lecture d'un fichier CSV

```bash
# Opérations
cat csv/industrie_manufacturiere/atelier_mecanique/atelier_mecanique_operations.csv

# Postes
cat csv/industrie_manufacturiere/atelier_mecanique/atelier_mecanique_postes.csv
```

### Import dans PRISME

```python
from adapters.csv_import.adapter import AdapterCSV

adapter = AdapterCSV()

# Import standard (paire operations + postes)
instance = adapter.adapter_depuis_fichiers(
    "csv/industrie_manufacturiere/atelier_mecanique/atelier_mecanique_operations.csv",
    "csv/industrie_manufacturiere/atelier_mecanique/atelier_mecanique_postes.csv"
)

# Import JIRA
from adapters.csv_import.adapter_jira import AdapterJIRA
adapter_jira = AdapterJIRA()
instance_jira = adapter_jira.adapter_depuis_jira_csv(
    "csv/informatique/informatique_jira_export.csv"
)
```

## Sélection par critère

### Par secteur d'activité

**Industrie (4 jeux)**:
- Métallurgie → `atelier_mecanique`
- Électronique → `assemblage_electronique`
- Impression → `imprimerie`
- Alimentaire → `production_agroalimentaire`

**Services (2 jeux)**:
- Support client → `centre_appels`
- GMAO → `maintenance_industrielle`

**IT (1 jeu)**:
- Développement logiciel → `informatique`

### Par durée de projet

**Ultra-rapide (< 1 jour)**:
- Centre d'Appels: 0.67j (~16h)

**Rapide (1-7 jours)**:
- Imprimerie: 5j
- Assemblage Électronique: 6j
- Maintenance Industrielle: 7j

**Moyen (7-15 jours)**:
- Production Agroalimentaire: 9j
- Atelier Mécanique: 12j

### Par nombre d'opérations

**Petit (< 8 opérations)**:
- Maintenance Industrielle: 7

**Moyen (8-9 opérations)**:
- Atelier Mécanique: 8
- Centre d'Appels: 8
- Imprimerie: 9
- Production Agroalimentaire: 9

**Grand (10+ opérations)**:
- Assemblage Électronique: 10

### Par type de ressources

**Machines uniquement**:
- Assemblage Électronique (automatisé)
- Imprimerie (presses, tunnel)

**Humain + Machine**:
- Atelier Mécanique (opérateurs + machines)
- Production Agroalimentaire (techniciens + équipements)

**Humain principalement**:
- Centre d'Appels (agents + CRM)
- Maintenance Industrielle (techniciens)

## Format des fichiers

### Format standard (industrie + services)

Chaque secteur = **2 fichiers CSV**:

**`*_operations.csv`**:
```csv
code_operation,duree_jours,poste_id,operation_precedente
OP_001,2,POSTE_A,
OP_002,1,POSTE_B,OP_001
```

**`*_postes.csv`**:
```csv
code_poste
POSTE_A
POSTE_B
```

### Format JIRA (informatique)

**`informatique_jira_export.csv`**:
```csv
issue_key,summary,issue_type,status,priority,assignee,estimate_days,epic,labels,dependencies
PROJ-101,Analyse besoins,Task,Done,High,alice,2,PROJ-100,analyse,
PROJ-102,API REST,Story,In Progress,High,bob,5,PROJ-100,backend,PROJ-101
```

## Statistiques

| Métrique | Valeur |
|----------|--------|
| **Jeux de données** | 7 |
| **Fichiers CSV** | 13 |
| **Secteurs** | 3 |
| **Opérations totales** | 60 |
| **Postes totaux** | 46 |
| **Durée min** | 0.67j (centre d'appels) |
| **Durée max** | 12j (atelier mécanique) |

## Cas d'usage

### Tests & Validation

| Besoin | Secteur recommandé |
|--------|-------------------|
| Import CSV basique | Atelier Mécanique (simple) |
| Durées fractionnaires | Centre d'Appels (heures) |
| Format JIRA | Informatique |
| Ressources partagées | Imprimerie (tunnel séchage) |
| Longues durées | Production Agroalimentaire (cuisson 3j) |

### Démonstrations

| Audience | Secteur recommandé |
|----------|-------------------|
| Industrie classique | Atelier Mécanique |
| High-tech | Assemblage Électronique |
| Services | Centre d'Appels |
| GMAO | Maintenance Industrielle |
| Équipes agile/dev | Informatique (JIRA) |

## Différences avec autres formats

| Aspect | CSV | Format Simplifié (JSON) | Format ERP (JSON) |
|--------|-----|-------------------------|-------------------|
| **Édition** | ✅ Excel/LibreOffice | ⚠️ Éditeur texte | ⚠️ Éditeur texte |
| **Validation** | ❌ Aucune | ⚠️ Schéma basique | ✅ Schéma strict |
| **Compétences** | ❌ Non supportées | ✅ Supportées | ❌ Non supportées |
| **Métadonnées** | ⚠️ Minimales (JIRA: riches) | ⚠️ Basiques | ✅ Complètes |
| **Familiarité** | ✅ Très familier | ⚠️ Dev/tech | ⚠️ Spécifique ERP |

## Conversion vers autres formats

### CSV → Format Simplifié (JSON)

```python
# Charger CSV
instance_csv = adapter_csv.adapter_depuis_fichiers(
    "csv/.../operations.csv",
    "csv/.../postes.csv"
)

# Exporter en JSON format simplifié
import json
with open("format_simplifie/nouveau.json", "w") as f:
    json.dump(instance_csv.dict(), f, indent=2)
```

### CSV → TRCO (format canonique)

```python
# L'adaptateur CSV produit déjà une instance TRCO
instance_trco = adapter_csv.adapter_depuis_fichiers(...)

# Valider avec le DSL
from dsl.schema.instance import InstanceTRCO
instance_validee = InstanceTRCO(**instance_trco.dict())
```

## Limitations du format CSV

⚠️ **Pas de compétences** - Utiliser format simplifié ou XLSX
⚠️ **Pas de contraintes avancées** - Échéances, capacités, incompatibilités absentes
⚠️ **Validation faible** - Schéma non enforced (risque d'erreurs)
⚠️ **Métadonnées limitées** - Sauf format JIRA

## Extension

### Ajout d'un nouveau secteur

1. Créer un sous-dossier dans le secteur approprié
2. Créer `<nom>_operations.csv` et `<nom>_postes.csv`
3. Respecter le format (colonnes requises)
4. Ajouter un README.md dans le sous-dossier
5. Mettre à jour cet INDEX

### Nouvelles colonnes optionnelles

On peut enrichir `operations.csv` avec:
- `priorite` (High, Medium, Low)
- `statut` (To Do, In Progress, Done)
- `competence_requise` (nom de compétence)

L'adaptateur CSV devra être étendu pour les supporter.

## Références

- [README général CSV](README.md) - Documentation complète
- [Industrie manufacturière](industrie_manufacturiere/README.md) - 4 secteurs industriels
- [Services](services/README.md) - Centre d'appels + Maintenance
- [Informatique](informatique/README.md) - Format JIRA
- [Format simplifié](../format_simplifie/INDEX.md) - Alternative JSON avec compétences
- [Format ERP](../json_erp/README.md) - Format propriétaire

---

**Dernière mise à jour**: 2026-08-02
**Version**: 1.0 (réorganisation par secteur)
**Organisation**: Hiérarchie à 3 niveaux (secteur/sous-secteur/fichiers)
