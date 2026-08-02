# Données Brutes au Format CSV

Ce répertoire contient des données brutes au format CSV, organisées par secteur d'activité.

## Structure

```
csv/
├── industrie_manufacturiere/
│   ├── atelier_mecanique/
│   │   ├── atelier_mecanique_operations.csv
│   │   └── atelier_mecanique_postes.csv
│   ├── assemblage_electronique/
│   │   ├── assemblage_electronique_operations.csv
│   │   └── assemblage_electronique_postes.csv
│   ├── imprimerie/
│   │   ├── imprimerie_operations.csv
│   │   └── imprimerie_postes.csv
│   └── production_agroalimentaire/
│       ├── production_agroalimentaire_operations.csv
│       └── production_agroalimentaire_postes.csv
├── services/
│   ├── centre_appels/
│   │   ├── centre_appels_operations.csv
│   │   └── centre_appels_postes.csv
│   └── maintenance_industrielle/
│       ├── maintenance_industrielle_operations.csv
│       └── maintenance_industrielle_postes.csv
├── informatique/
│   └── informatique_jira_export.csv
└── README.md (ce fichier)
```

## Secteurs disponibles

### 🏭 Industrie Manufacturière (4 jeux)
- **Atelier Mécanique** - Fabrication métallique (8 opérations, 8 postes)
- **Assemblage Électronique** - Production PCB (10 opérations, 9 postes)
- **Imprimerie** - Impression offset (9 opérations, 7 postes)
- **Production Agroalimentaire** - Transformation alimentaire (9 opérations, 9 postes)

### 🛠️ Services (2 jeux)
- **Centre d'Appels** - Support client N1/N2 (8 opérations, 4 postes)
- **Maintenance Industrielle** - Gestion pannes (7 opérations, 5 postes)

### 💻 Informatique (1 jeu)
- **Informatique (JIRA Export)** - Export de tickets JIRA (format spécifique)

## Format des fichiers

### Format standard (paires operations + postes)

Chaque secteur contient **deux fichiers CSV**:

**Fichier `*_operations.csv`**:
```csv
code_operation,duree_jours,poste_id,operation_precedente
OP_001,2,POSTE_A,
OP_002,1,POSTE_B,OP_001
OP_003,3,POSTE_C,OP_002
```

**Fichier `*_postes.csv`**:
```csv
code_poste
POSTE_A
POSTE_B
POSTE_C
```

### Format spécifique (informatique)

Le fichier `informatique_jira_export.csv` simule un export JIRA avec des champs supplémentaires (assigné, priorité, statut, etc.).

## Utilisation

### Import direct via l'API

```python
from adapters.csv_import.adapter import AdapterCSV

# Charger les opérations et postes
adapter = AdapterCSV()
instance_trco = adapter.adapter_depuis_fichiers(
    "csv/industrie_manufacturiere/atelier_mecanique/atelier_mecanique_operations.csv",
    "csv/industrie_manufacturiere/atelier_mecanique/atelier_mecanique_postes.csv"
)
```

### Conversion vers format TRCO

Les fichiers CSV sont automatiquement convertis en instances TRCO lors de l'ingestion:
- `code_operation` → `Tache.id`
- `duree_jours` → durée dans `CompatibiliteRessourceTache`
- `poste_id` → `Ressource.id`
- `operation_precedente` → `ContraintePrecedence`

## Navigation rapide

| Secteur | Dossier | Fichiers |
|---------|---------|----------|
| Atelier Mécanique | `industrie_manufacturiere/atelier_mecanique/` | 2 CSV |
| Assemblage Électronique | `industrie_manufacturiere/assemblage_electronique/` | 2 CSV |
| Imprimerie | `industrie_manufacturiere/imprimerie/` | 2 CSV |
| Production Agroalimentaire | `industrie_manufacturiere/production_agroalimentaire/` | 2 CSV |
| Centre d'Appels | `services/centre_appels/` | 2 CSV |
| Maintenance Industrielle | `services/maintenance_industrielle/` | 2 CSV |
| Informatique | `informatique/` | 1 CSV (JIRA) |

## Caractéristiques techniques

- **Encodage**: UTF-8
- **Séparateur**: virgule (`,`)
- **En-têtes**: Présents sur la première ligne
- **Valeurs vides**: Représentées par une chaîne vide
- **Format dates**: Jours (entier ou décimal)

## Avantages du format CSV

✅ **Simplicité**: Éditable dans Excel/LibreOffice/Google Sheets
✅ **Interopérabilité**: Standard universel, facile à importer/exporter
✅ **Légèreté**: Fichiers texte compacts
✅ **Versionnable**: Compatible avec Git
✅ **Familier**: Format connu des utilisateurs métier

## Limitations

⚠️ **Pas de validation native**: Le schéma n'est pas enforced (contrairement au JSON)
⚠️ **Types implicites**: Les types sont déduits lors de l'import
⚠️ **Contraintes simples**: Seulement précédence + compatibilité ressource-tâche
⚠️ **Pas de compétences**: Pour les compétences, utiliser `format_simplifie/` ou XLSX

## Pour aller plus loin

- **Format simplifié (JSON)**: `../format_simplifie/` - Structure taches/ressources/contraintes avec compétences
- **Format ERP (JSON)**: `../json_erp/` - Format propriétaire avec translator
- **Format XLSX**: Via `adapters/tableur/` - Gabarit Excel avec compétences
- **Format TRCO complet**: `../../instances_trco/` - Format canonique avec toutes les contraintes

## Ajout d'un nouveau secteur

1. Créer un sous-dossier dans le secteur approprié (industrie_manufacturiere, services, etc.)
2. Créer les fichiers `<nom>_operations.csv` et `<nom>_postes.csv`
3. Respecter le format standard (colonnes requises)
4. Ajouter un README dans le sous-dossier (optionnel)
5. Mettre à jour ce README principal

## Notes

- Les fichiers CSV sont des **exports simulés** pour prototypage et tests
- Pour une utilisation production, privilégier le format XLSX avec validation ou le format TRCO directement
- Les durées sont exprimées en jours (fraction possible pour les heures)
- Chaque opération ne peut être assignée qu'à un seul poste (pas de flexibilité FJSP)
