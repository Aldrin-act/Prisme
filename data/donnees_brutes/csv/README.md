# Données Brutes au Format CSV

Ce répertoire contient des données brutes au format CSV, organisées par secteur d'activité.

## Structure

```
csv/
├── industrie_manufacturiere/
│   ├── atelier_mecanique/
│   │   ├── taches.csv
│   │   ├── ressources.csv
│   │   └── contraintes.csv
│   ├── assemblage_electronique/
│   │   ├── taches.csv
│   │   ├── ressources.csv
│   │   └── contraintes.csv
│   ├── imprimerie/
│   │   ├── taches.csv
│   │   ├── ressources.csv
│   │   └── contraintes.csv
│   └── production_agroalimentaire/
│       ├── taches.csv
│       ├── ressources.csv
│       └── contraintes.csv
├── services/
│   ├── centre_appels/
│   │   ├── taches.csv
│   │   ├── ressources.csv
│   │   └── contraintes.csv
│   └── maintenance_industrielle/
│       ├── taches.csv
│       ├── ressources.csv
│       └── contraintes.csv
├── informatique/
│   └── informatique_jira_export.csv
└── README.md (ce fichier)
```

## Format des fichiers

### Format standard (3 fichiers CSV par secteur)

Chaque secteur contient **3 fichiers CSV séparés**, suivant le format standard de l'adaptateur CSV :

#### 1. **taches.csv**

```csv
id,nom
T001,Découpe
T002,Assemblage
```

| Colonne | Requis | Description | Exemple |
|---------|--------|-------------|---------|
| `id` | ✅ Oui | Identifiant unique de la tâche | T001 |
| `nom` | Non | Nom descriptif | Découpe laser |

#### 2. **ressources.csv**

```csv
id,nom,competences
R001,Découpeuse,decoupe;usinage
R002,Assembleuse,assemblage
```

| Colonne | Requis | Description | Exemple |
|---------|--------|-------------|---------|
| `id` | ✅ Oui | Identifiant unique de la ressource | R001 |
| `nom` | Non | Nom descriptif | Découpeuse laser |
| `competences` | Non | Compétences (séparées par `;`) | decoupe;usinage |

#### 3. **contraintes.csv**

```csv
type,tache_avant,tache_apres,tache,ressource,duree_jours,competence
precedence,T001,T002,,,,
compatibilite_ressource_tache,,,T001,R001,1,
competence_requise,,,T001,,,decoupe
```

| Colonne | Description | Utilisée pour |
|---------|-------------|---------------|
| `type` | ✅ **Requis** : `precedence`, `compatibilite_ressource_tache`, ou `competence_requise` | Tous |
| `tache_avant` | Tâche précédente | `precedence` |
| `tache_apres` | Tâche suivante | `precedence` |
| `tache` | ID de la tâche | `compatibilite_ressource_tache`, `competence_requise` |
| `ressource` | ID de la ressource | `compatibilite_ressource_tache` |
| `duree_jours` | Durée en jours | `compatibilite_ressource_tache` |
| `competence` | Nom de la compétence | `competence_requise` |

**Types de contraintes supportés** :
- `precedence` : Tâche A doit précéder tâche B
- `compatibilite_ressource_tache` : Une ressource peut exécuter une tâche en N jours
- `competence_requise` : Une tâche nécessite une compétence spécifique

### Dérivation automatique des compatibilités par compétence

Au lieu de saisir manuellement chaque couple `(tache, ressource, duree)` dans `contraintes.csv`, vous pouvez :

1. Déclarer les **compétences** d'une ressource dans `ressources.csv` (colonne `competences`)
2. Déclarer qu'une tâche **exige** une compétence dans `contraintes.csv` (ligne `competence_requise`)
3. Fournir un estimateur de durée (`estimateur_duree`, apprentissage automatique — voir `estimation/`)
   à l'ingestion, pour combler la durée des tâches sans compatibilité déjà explicite

L'adaptateur crée alors automatiquement une `compatibilite_ressource_tache` pour chaque ressource possédant la compétence requise, avec la durée comblée par l'estimateur.

**Exemple** :

```csv
# taches.csv
id,nom
T001,Soudure

# ressources.csv
id,nom,competences
R001,Poste MIG,soudure
R002,Poste TIG,soudure

# contraintes.csv
type,tache_avant,tache_apres,tache,ressource,duree_jours,competence
competence_requise,,,T001,,,soudure
```

→ Génère automatiquement (durée comblée par l'estimateur, ici 2 jours) :
- `CompatibiliteRessourceTache(tache=T001, ressource=R001, duree=2)`
- `CompatibiliteRessourceTache(tache=T001, ressource=R002, duree=2)`

## Utilisation

### Import via l'API

```python
from adapters.csv_import.traducteur import traduire

# Charger les 3 fichiers CSV
with open("taches.csv", "rb") as f_t, \
     open("ressources.csv", "rb") as f_r, \
     open("contraintes.csv", "rb") as f_c:
    instance_trco = traduire(f_t.read(), f_r.read(), f_c.read())
```

### Conversion automatique

Les 3 fichiers CSV sont automatiquement convertis en instance TRCO lors de l'ingestion :
- Validation du schéma (colonnes requises)
- Validation des types (durées numériques)
- Dérivation des compatibilités par compétence (si applicable)
- Validation DSL complète (références, unicité...)

## Secteurs disponibles

### 🏭 Industrie Manufacturière (4 jeux)
- **Atelier Mécanique** - 8 tâches, 8 ressources
- **Assemblage Électronique** - 10 tâches, 9 ressources
- **Imprimerie** - 9 tâches, 7 ressources
- **Production Agroalimentaire** - 9 tâches, 9 ressources

### 🛠️ Services (2 jeux)
- **Centre d'Appels** - 8 tâches, 4 ressources (durées fractionnaires)
- **Maintenance Industrielle** - 7 tâches, 5 ressources

### 💻 Informatique (1 jeu)
- **JIRA Export** - Format spécial (1 seul fichier CSV enrichi)

## Avantages du format CSV

✅ **Simplicité** - Format texte lisible, éditable dans tout tableur
✅ **Compatibilité** - Standard universel (LibreOffice, Google Sheets, etc.)
✅ **Versionnable** - Compatible avec Git (diffs clairs)
✅ **Familier** - Format connu des utilisateurs métier
✅ **Flexible** - Compatibilités explicites OU dérivées par compétence

## Caractéristiques techniques

- **Encodage** : UTF-8 (avec BOM toléré pour exports Excel)
- **Séparateur** : Virgule (`,`)
- **Séparateur compétences** : Point-virgule (`;`)
- **En-têtes** : Présents sur la première ligne
- **Valeurs vides** : Chaînes vides
- **Format durées** : Jours (entier ou décimal)

## Limitations

⚠️ **Contraintes simples** - Seulement précédence, compatibilité, compétence
⚠️ **Pas d'échéances** - Pour dates limites, utiliser format TRCO complet
⚠️ **Pas de capacités** - Pour ressources multi-tâches, utiliser format TRCO
⚠️ **Pas d'incompatibilités** - Pour exclusions, utiliser format TRCO

## Différences avec autres formats

| Aspect | CSV (3 fichiers) | Format Simplifié (JSON) |
|--------|------------------|-------------------------|
| **Édition** | ✅ Tableur standard | ⚠️ Éditeur texte |
| **Structure** | ✅ 3 fichiers séparés | ✅ 1 fichier structuré |
| **Validation** | ⚠️ À l'import | ⚠️ À l'import |
| **Compétences** | ✅ Supportées | ✅ Supportées |
| **Dérivation auto** | ✅ Oui | ❌ Non |
| **Familiarité** | ✅ Très familier | ⚠️ Dev/tech |

## Pour aller plus loin

- **Format Simplifié (JSON)** : Structure JSON avec compétences → `../format_simplifie/`
- **Format TRCO complet** : Format canonique avec toutes contraintes → `../../instances_trco/`
- **Format ERP (JSON)** : Format propriétaire avec traducteur → `../json_erp/`

## Notes

- Les fichiers CSV sont des **données de test et démonstration**
- Le séparateur de compétences (`;`) évite la confusion avec le délimiteur CSV (`,`)
- Les durées fractionnaires sont supportées (ex: `0.5` = demi-journée)
- Les lignes vides et lignes d'exemple sont ignorées automatiquement
