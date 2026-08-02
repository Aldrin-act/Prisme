# Industrie Manufacturière - Données CSV

Ce répertoire contient les données CSV pour 4 secteurs de l'industrie manufacturière.

## Secteurs disponibles

### 1. Atelier Mécanique (`atelier_mecanique/`)

**Secteur**: Fabrication métallique

**Processus**: Découpe → Perçage → Pliage → Soudure (2 alternatives) → Peinture → Contrôle

**Caractéristiques**:
- 8 opérations
- 8 postes de travail
- Chaîne de production linéaire avec alternatives de soudure
- Durée totale: ~12 jours

**Fichiers**:
- `atelier_mecanique_operations.csv` - Liste des opérations avec durées et précédences
- `atelier_mecanique_postes.csv` - Liste des postes/machines

**Cas d'usage**: Formation, démonstration flux industriel classique

---

### 2. Assemblage Électronique (`assemblage_electronique/`)

**Secteur**: Fabrication de cartes électroniques (PCB)

**Processus**: Pose CMS → Soudure refusion → Inspection AOI → Tests → Conditionnement

**Caractéristiques**:
- 10 opérations
- 9 postes de travail
- Double face PCB (face A puis face B)
- Inspection automatique optique (AOI)
- Durée totale: ~6 jours

**Fichiers**:
- `assemblage_electronique_operations.csv`
- `assemblage_electronique_postes.csv`

**Cas d'usage**: Benchmark performance, tests qualité, industrie 4.0

---

### 3. Imprimerie (`imprimerie/`)

**Secteur**: Impression offset

**Processus**: Pré-presse → Impression → Vernissage → Séchage → Reliure → Conditionnement

**Caractéristiques**:
- 9 opérations
- 7 postes de travail
- Impression recto/verso
- Ressource partagée (tunnel de séchage)
- Durée totale: ~5 jours

**Fichiers**:
- `imprimerie_operations.csv`
- `imprimerie_postes.csv`

**Cas d'usage**: Tests ressources partagées, goulots d'étranglement

---

### 4. Production Agroalimentaire (`production_agroalimentaire/`)

**Secteur**: Transformation alimentaire

**Processus**: Réception → Lavage → Cuisson → Pasteurisation → Conditionnement → Stockage

**Caractéristiques**:
- 9 opérations
- 9 postes de travail
- Longues durées (cuisson 3 jours)
- Séquence stricte (sécurité alimentaire)
- Durée totale: ~9 jours

**Fichiers**:
- `production_agroalimentaire_operations.csv`
- `production_agroalimentaire_postes.csv`

**Cas d'usage**: Tests longues durées, contraintes réglementaires

---

## Format des fichiers

Tous les secteurs utilisent le **même format CSV standard**:

### Fichier `*_operations.csv`

| Colonne | Type | Description | Exemple |
|---------|------|-------------|---------|
| `code_operation` | String | Identifiant unique de l'opération | OP_001 |
| `duree_jours` | Float | Durée en jours (décimal autorisé) | 2.5 |
| `poste_id` | String | Identifiant du poste assigné | POSTE_A |
| `operation_precedente` | String | Opération qui doit précéder (vide si première) | OP_000 |

### Fichier `*_postes.csv`

| Colonne | Type | Description | Exemple |
|---------|------|-------------|---------|
| `code_poste` | String | Identifiant unique du poste | POSTE_A |

## Statistiques

| Secteur | Opérations | Postes | Durée totale | Complexité |
|---------|------------|--------|--------------|------------|
| Atelier Mécanique | 8 | 8 | 12j | Moyenne |
| Assemblage Électronique | 10 | 9 | 6j | Élevée |
| Imprimerie | 9 | 7 | 5j | Moyenne |
| Production Agroalimentaire | 9 | 9 | 9j | Faible |

## Utilisation

### Import individuel

```python
from adapters.csv_import.adapter import AdapterCSV

adapter = AdapterCSV()

# Atelier mécanique
instance = adapter.adapter_depuis_fichiers(
    "industrie_manufacturiere/atelier_mecanique/atelier_mecanique_operations.csv",
    "industrie_manufacturiere/atelier_mecanique/atelier_mecanique_postes.csv"
)
```

### Import en lot

```python
secteurs = [
    "atelier_mecanique",
    "assemblage_electronique",
    "imprimerie",
    "production_agroalimentaire"
]

for secteur in secteurs:
    instance = adapter.adapter_depuis_fichiers(
        f"industrie_manufacturiere/{secteur}/{secteur}_operations.csv",
        f"industrie_manufacturiere/{secteur}/{secteur}_postes.csv"
    )
    # Traiter l'instance...
```

## Notes sectorielles

### Particularités techniques

**Atelier Mécanique**:
- Soudure avec 2 alternatives (MIG/TIG) → Test de choix de ressource

**Assemblage Électronique**:
- Double face → Séquence A puis B obligatoire
- AOI automatique → Pas d'intervention humaine

**Imprimerie**:
- Tunnel séchage partagé → Goulot d'étranglement potentiel
- Vernissage optionnel → Variante possible

**Production Agroalimentaire**:
- Cuisson longue (3j) → Impact fort sur makespan
- Contrôle qualité multiple → Sécurité sanitaire

## Extension

Pour ajouter un nouveau secteur industriel:

1. Créer un sous-dossier `nouveau_secteur/`
2. Créer les 2 fichiers CSV selon le format standard
3. Documenter les spécificités dans ce README
4. Tester l'import avec l'adaptateur CSV

---

**Retour**: [../README.md](../README.md) - Documentation CSV générale
