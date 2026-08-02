# Organisation du Répertoire CSV - Vue Détaillée

## 📊 Structure Hiérarchique

```
csv/
│
├── 🏭 industrie_manufacturiere/          [4 secteurs, 8 CSV]
│   │
│   ├── atelier_mecanique/
│   │   ├── atelier_mecanique_operations.csv       (8 opérations)
│   │   ├── atelier_mecanique_postes.csv           (8 postes)
│   │   └── README.md
│   │
│   ├── assemblage_electronique/
│   │   ├── assemblage_electronique_operations.csv (10 opérations)
│   │   ├── assemblage_electronique_postes.csv     (9 postes)
│   │   └── README.md
│   │
│   ├── imprimerie/
│   │   ├── imprimerie_operations.csv              (9 opérations)
│   │   └── imprimerie_postes.csv                  (7 postes)
│   │
│   ├── production_agroalimentaire/
│   │   ├── production_agroalimentaire_operations.csv (9 opérations)
│   │   └── production_agroalimentaire_postes.csv     (9 postes)
│   │
│   └── README.md (documentation secteur)
│
├── 🛠️ services/                         [2 secteurs, 4 CSV]
│   │
│   ├── centre_appels/
│   │   ├── centre_appels_operations.csv           (8 opérations)
│   │   ├── centre_appels_postes.csv               (4 postes)
│   │   └── README.md
│   │
│   ├── maintenance_industrielle/
│   │   ├── maintenance_industrielle_operations.csv (7 opérations)
│   │   └── maintenance_industrielle_postes.csv     (5 postes)
│   │
│   └── README.md (documentation secteur)
│
├── 💻 informatique/                      [1 secteur, 1 CSV]
│   │
│   ├── informatique_jira_export.csv               (format spécial JIRA)
│   └── README.md (documentation secteur)
│
└── 📚 Documentation/
    ├── README.md         (guide principal)
    ├── INDEX.md          (navigation rapide)
    └── ORGANISATION.md   (ce fichier)
```

## 📈 Statistiques

### Par secteur

| Secteur | Sous-dossiers | Fichiers CSV | Opérations | Postes | README |
|---------|--------------|--------------|------------|--------|--------|
| **Industrie Manufacturière** | 4 | 8 | 36 | 33 | ✅ 5 |
| **Services** | 2 | 4 | 15 | 9 | ✅ 3 |
| **Informatique** | 1 | 1 | Variable | Variable | ✅ 1 |
| **TOTAL** | **7** | **13** | **51** | **42** | **9** |

### Répartition des fichiers

```
Fichiers CSV:        13
Fichiers README:      9
Sous-dossiers:        7
Niveaux hiérarchie:   3
```

## 🗂️ Niveaux d'organisation

### Niveau 1 - Secteur principal (3)
```
csv/
├── industrie_manufacturiere/
├── services/
└── informatique/
```

### Niveau 2 - Sous-secteur métier (7)
```
industrie_manufacturiere/
├── atelier_mecanique/
├── assemblage_electronique/
├── imprimerie/
└── production_agroalimentaire/

services/
├── centre_appels/
└── maintenance_industrielle/

informatique/
└── (fichier direct, pas de sous-dossier)
```

### Niveau 3 - Fichiers de données
```
[sous-secteur]/
├── [nom]_operations.csv  ← Opérations avec durées et précédences
├── [nom]_postes.csv      ← Liste des postes/ressources
└── README.md (optionnel) ← Documentation spécifique
```

## 📖 Documentation créée

### README principaux (3)

1. **csv/README.md** - Guide général
   - Vue d'ensemble structure
   - Format des fichiers
   - Comparaison avec autres formats
   - Guide d'utilisation

2. **csv/INDEX.md** - Navigation rapide
   - Tableaux par secteur
   - Sélection par critère
   - Démarrage rapide
   - Statistiques

3. **csv/ORGANISATION.md** - Ce fichier
   - Structure détaillée
   - Statistiques complètes
   - Convention de nommage

### README sectoriels (3)

4. **industrie_manufacturiere/README.md**
   - 4 secteurs industriels
   - Caractéristiques techniques
   - Cas d'usage par secteur

5. **services/README.md**
   - 2 secteurs de services
   - Spécificités services vs industrie
   - Notes sur durées fractionnaires

6. **informatique/README.md**
   - Format JIRA spécial
   - Mapping vers TRCO
   - Comparaison avec format standard

### README sous-sectoriels (3)

7. **atelier_mecanique/README.md**
   - Détail des 8 opérations
   - Alternatives de soudure
   - Durée totale 12j

8. **assemblage_electronique/README.md**
   - Production PCB double face
   - AOI automatique
   - Tests fonctionnels

9. **centre_appels/README.md**
   - Workflow N1/N2
   - Durées en heures
   - Utilisation CRM

## 🎯 Convention de nommage

### Fichiers CSV

**Format**: `<secteur>_<type>.csv`

**Exemples**:
- `atelier_mecanique_operations.csv`
- `atelier_mecanique_postes.csv`
- `centre_appels_operations.csv`
- `centre_appels_postes.csv`

**Exception**: `informatique_jira_export.csv` (format spécial, fichier unique)

### Dossiers

**Format**: `<nom_descriptif>/` (snake_case, minuscules)

**Exemples**:
- `industrie_manufacturiere/`
- `centre_appels/`
- `maintenance_industrielle/`

## 🔍 Navigation

### Par chemin direct

```bash
# Accès direct à un secteur
cd csv/industrie_manufacturiere/atelier_mecanique/

# Lecture fichier
cat atelier_mecanique_operations.csv
```

### Par recherche

```bash
# Trouver tous les fichiers operations
find csv/ -name "*_operations.csv"

# Trouver tous les README
find csv/ -name "README.md"

# Lister par secteur
ls csv/industrie_manufacturiere/
ls csv/services/
```

## 📦 Contenu par secteur

### 🏭 Industrie Manufacturière

| Sous-secteur | Fichiers | Description |
|--------------|----------|-------------|
| atelier_mecanique | 3 (2 CSV + README) | Fabrication métallique, 8 opérations |
| assemblage_electronique | 3 (2 CSV + README) | Production PCB, 10 opérations |
| imprimerie | 2 (2 CSV) | Impression offset, 9 opérations |
| production_agroalimentaire | 2 (2 CSV) | Transformation alimentaire, 9 opérations |

**Total**: 10 fichiers + 1 README sectoriel

### 🛠️ Services

| Sous-secteur | Fichiers | Description |
|--------------|----------|-------------|
| centre_appels | 3 (2 CSV + README) | Support N1/N2, 8 opérations, durées courtes |
| maintenance_industrielle | 2 (2 CSV) | GMAO, 7 opérations |

**Total**: 5 fichiers + 1 README sectoriel

### 💻 Informatique

| Fichier | Type | Description |
|---------|------|-------------|
| informatique_jira_export.csv | CSV enrichi | Export JIRA avec métadonnées |

**Total**: 1 fichier + 1 README sectoriel

## ✅ Checklist de conformité

Chaque sous-secteur respecte:

- ✅ Dossier nommé en snake_case
- ✅ Fichiers `*_operations.csv` et `*_postes.csv` (sauf JIRA)
- ✅ README.md présent ou dans le parent
- ✅ Format CSV valide (UTF-8, virgule)
- ✅ Colonnes requises présentes

## 🔄 Migration effectuée

### Avant (structure plate)
```
csv/
├── atelier_mecanique_operations.csv
├── atelier_mecanique_postes.csv
├── assemblage_electronique_operations.csv
├── assemblage_electronique_postes.csv
├── centre_appels_operations.csv
├── centre_appels_postes.csv
├── ... (tous mélangés)
└── README.md
```

### Après (structure hiérarchique)
```
csv/
├── industrie_manufacturiere/
│   ├── atelier_mecanique/
│   │   ├── atelier_mecanique_operations.csv
│   │   └── atelier_mecanique_postes.csv
│   └── ...
├── services/
│   └── ...
├── informatique/
│   └── ...
└── [Documentation complète]
```

## 📊 Métriques de qualité

| Critère | Statut |
|---------|--------|
| Organisation hiérarchique | ✅ 3 niveaux |
| Documentation complète | ✅ 9 README |
| Navigation facilitée | ✅ INDEX.md |
| Convention nommage | ✅ Cohérente |
| Accessibilité | ✅ Chemins clairs |
| Maintenabilité | ✅ Structure extensible |

## 🚀 Avantages de la nouvelle structure

### Pour les développeurs
✅ Séparation claire par domaine métier
✅ Facilité de recherche (secteur → sous-secteur → fichiers)
✅ Extensibilité (ajout de nouveaux secteurs sans pollution)

### Pour les utilisateurs
✅ Navigation intuitive
✅ Documentation accessible
✅ Exemples par métier

### Pour la maintenance
✅ Isolation des changements
✅ Tests par secteur possibles
✅ Documentation proche des données

---

**Date de réorganisation**: 2026-08-02
**Structure précédente**: Plate (tous fichiers au même niveau)
**Structure actuelle**: Hiérarchique (3 niveaux)
**Impact**: Amélioration de la navigabilité et de la maintenabilité
