# Guide Complet du Système de Génération de Données

Ce guide présente le système complet de génération de données pour PRISME, depuis les configurations sectorielles jusqu'aux instances TRCO enrichies avec objectifs.

## 📋 Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Architecture du système](#architecture-du-système)
3. [Configurations sectorielles](#configurations-sectorielles)
4. [Génération de données](#génération-de-données)
5. [Pipeline complet](#pipeline-complet)
6. [Cas d'usage](#cas-dusage)

## 🎯 Vue d'ensemble

Le système de génération permet de créer des jeux de données réalistes pour **9 secteurs différents** (industriels et services) avec **6 configurations d'objectifs** différentes.

### Principaux Composants

```
configurations_secteurs/     ← Configurations YAML (9 secteurs)
         ↓
scripts/generer_donnees_depuis_config.py  ← Génère données brutes ERP
         ↓
donnees_brutes/             ← JSON et CSV (format ERP)
         ↓
scripts/transformer_donnees_brutes.py     ← Transforme en TRCO
         ↓
instances_trco/             ← Instances canoniques
         ↓
scripts/configurer_objectifs.py          ← Enrichit avec objectifs
         ↓
instances_trco_enrichies/   ← Instances prêtes pour pipeline
```

## 🏗️ Architecture du Système

### 1. Configurations Sectorielles (YAML)

**Emplacement :** `data/configurations_secteurs/`

Chaque secteur est défini par un fichier YAML contenant :
- Types de postes/équipements avec durées et capacités
- Phases de production/intervention
- Paramètres de génération

**Secteurs disponibles :**

**Industriels :**
- `atelier_mecanique.yaml` - Usinage de précision
- `assemblage_electronique.yaml` - Assemblage de circuits
- `production_agroalimentaire.yaml` - Production alimentaire

**Services :**
- `gestion_espaces_verts.yaml` - Entretien paysager (GreenSIG)
- `hopital_bloc_operatoire.yaml` - Planification chirurgicale
- `logistique_transport.yaml` - Supply chain
- `services_nettoyage.yaml` - Nettoyage professionnel
- `education_planification_cours.yaml` - Emplois du temps
- `restauration_collective.yaml` - Cuisine collective

### 2. Génération de Données Brutes

**Script :** `scripts/generer_donnees_depuis_config.py`

Génère des données au **format ERP** (propriétaire) à partir des configurations YAML.

**Formats de sortie :**
- **JSON** : Payload complet avec métadonnées
- **CSV** : Deux fichiers (postes + opérations)

**Tailles disponibles :**
- Small : < 50 opérations
- Medium : 50-149 opérations
- Large : ≥ 150 opérations

### 3. Transformation TRCO

**Script :** `scripts/transformer_donnees_brutes.py`

Traduit le format ERP → format canonique **T-R-C-O** (Tâches, Ressources, Contraintes, Objectifs).

Utilise l'adaptateur : `adapters.erp_reference.translator`

### 4. Configuration des Objectifs

**Script :** `scripts/configurer_objectifs.py`

Enrichit les instances TRCO avec **6 configurations d'objectifs** :

1. **makespan** - Minimiser le temps total
2. **equilibrage** - Équilibrer la charge entre ressources
3. **retards** - Minimiser les retards (+ échéances auto-générées)
4. **utilisation** - Maximiser le taux d'utilisation
5. **changements** - Minimiser les changements de configuration
6. **multi** - Configuration multi-objectifs complète

## 🚀 Pipeline Complet

### Workflow Standard

```bash
# 1. Installer les dépendances
uv sync

# 2. Générer données brutes pour un secteur
uv run python -m scripts.generer_donnees_depuis_config \
    --secteur gestion_espaces_verts \
    --taille 50

# 3. Transformer en TRCO
uv run python -m scripts.transformer_donnees_brutes \
    --entree data/donnees_brutes/json_erp/gestion_espaces_verts_medium.json \
    --sortie data/instances_trco/gestion_espaces_verts_medium.json

# 4. Enrichir avec objectifs (génère 6 variantes)
uv run python -m scripts.configurer_objectifs \
    --instance data/instances_trco/gestion_espaces_verts_medium.json

# 5. Résultat : 6 instances enrichies
# - gestion_espaces_verts_medium_makespan.json
# - gestion_espaces_verts_medium_equilibrage.json
# - gestion_espaces_verts_medium_retards.json
# - gestion_espaces_verts_medium_utilisation.json
# - gestion_espaces_verts_medium_changements.json
# - gestion_espaces_verts_medium_multi.json
```

### Workflow Masse (Tous les Secteurs)

```bash
# Générer pour TOUS les secteurs (9 × 6 = 54 instances enrichies)
uv run python -m scripts.generer_donnees_depuis_config --tous --taille 50
uv run python -m scripts.transformer_donnees_brutes --tous
uv run python -m scripts.configurer_objectifs --tous
```

### Workflow Démonstration

```bash
# Script de démo complet
uv run python -m scripts.demo_donnees_brutes
```

## 💡 Cas d'Usage

### Cas 1 : Tester un Nouveau Secteur

**Objectif :** Créer un secteur "transport_urbain"

```bash
# 1. Créer la configuration
cat > data/configurations_secteurs/transport_urbain.yaml << EOF
nom: transport_urbain
description: Planification transport en commun
types_postes:
  BUS_LIGNE_A:
    duree_min: 45
    duree_max: 90
    capacite: 10
  METRO_LIGNE_1:
    duree_min: 60
    duree_max: 120
    capacite: 5
phases_production:
  - nom: SERVICE_MATIN
    types_poste: [BUS_LIGNE_A, METRO_LIGNE_1]
  - nom: SERVICE_SOIR
    types_poste: [BUS_LIGNE_A]
generation:
  operations_par_lot_min: 4
  operations_par_lot_max: 8
  prefix_lot: "COURSE"
EOF

# 2. Générer et tester
uv run python -m scripts.generer_donnees_depuis_config --secteur transport_urbain --taille 30
uv run python -m scripts.transformer_donnees_brutes \
    --entree data/donnees_brutes/json_erp/transport_urbain_small.json \
    --sortie data/instances_trco/transport_urbain_small.json
```

### Cas 2 : Benchmark Multi-Objectifs

**Objectif :** Comparer les performances sur différents objectifs

```bash
# Générer un secteur avec toutes les variantes d'objectifs
uv run python -m scripts.generer_donnees_depuis_config --secteur hopital_bloc_operatoire --taille 100
uv run python -m scripts.transformer_donnees_brutes \
    --entree data/donnees_brutes/json_erp/hopital_bloc_operatoire_medium.json \
    --sortie data/instances_trco/hopital_bloc_operatoire_medium.json
uv run python -m scripts.configurer_objectifs \
    --instance data/instances_trco/hopital_bloc_operatoire_medium.json

# Résultat : 6 instances pour benchmark
ls data/instances_trco_enrichies/hopital_bloc_operatoire_medium_*.json
```

### Cas 3 : Scalabilité

**Objectif :** Tester avec un grand volume de données

```bash
# Générer un jeu de données large (200 opérations)
uv run python -m scripts.generer_donnees_depuis_config \
    --secteur restauration_collective \
    --taille 200 \
    --format json

# Pipeline complet
uv run python -m scripts.transformer_donnees_brutes \
    --entree data/donnees_brutes/json_erp/restauration_collective_large.json \
    --sortie data/instances_trco/restauration_collective_large.json

uv run python -m scripts.configurer_objectifs \
    --instance data/instances_trco/restauration_collective_large.json \
    --config multi
```

### Cas 4 : Secteur Personnalisé avec Compétences

**Objectif :** Générer des données avec contraintes de compétences

```bash
# Enrichir avec compétences pour objectif "changements"
uv run python -m scripts.configurer_objectifs \
    --instance data/instances_trco/atelier_mecanique_medium.json \
    --config changements \
    --avec-competences
```

## 📊 Statistiques des Données Générées

### Volume par Configuration

| Config | Secteurs | Tailles | Instances | Total |
|--------|----------|---------|-----------|-------|
| Base (YAML) | 9 | - | 9 | 9 configs |
| Données brutes | 9 | 3 (S/M/L) | 27 | 54 fichiers (JSON+CSV) |
| Instances TRCO | 9 | 3 | 27 | 27 instances |
| Enrichies (6 objectifs) | 9 | 3 | 27×6 | 162 instances |

### Répartition par Secteur

```
Industriels (3)     : 33% des configurations
Services (6)        : 67% des configurations

Opérations/instance :
  Small   : 15-40 opérations
  Medium  : 40-100 opérations
  Large   : 100-250 opérations
```

## 🔧 Commandes de Maintenance

### Lister les Secteurs Disponibles

```bash
uv run python -m scripts.generer_donnees_depuis_config --lister
```

### Analyser les Instances Existantes

```bash
uv run python -m scripts.analyser_instances.py
uv run python -m scripts.analyser_objectifs.py
```

### Valider les Instances

```bash
uv run python -m scripts.valider_instances_objectifs_varies.py
```

### Nettoyer les Données Générées

```bash
# Supprimer toutes les données brutes
rm -rf data/donnees_brutes/json_erp/*
rm -rf data/donnees_brutes/csv/*

# Supprimer les instances TRCO
rm -rf data/instances_trco/*.json

# Supprimer les instances enrichies
rm -rf data/instances_trco_enrichies/*.json
```

## 📁 Structure des Répertoires

```
data/
├── configurations_secteurs/          ← YAML des secteurs
│   ├── README.md
│   ├── atelier_mecanique.yaml
│   ├── gestion_espaces_verts.yaml
│   └── ... (9 fichiers)
│
├── donnees_brutes/                   ← Données ERP générées
│   ├── json_erp/                     ← Format JSON
│   └── csv/                          ← Format CSV
│
├── instances_trco/                   ← Instances canoniques
│   └── *.json
│
└── instances_trco_enrichies/         ← Instances avec objectifs
    ├── README.md
    └── *_{makespan,equilibrage,...}.json
```

## 🎓 Exemples d'Utilisation

### Exemple 1 : GreenSIG (Espaces Verts)

```bash
# Générer un planning d'entretien paysager
uv run python -m scripts.generer_donnees_depuis_config \
    --secteur gestion_espaces_verts \
    --taille 40

# Transformer en TRCO
uv run python -m scripts.transformer_donnees_brutes \
    --entree data/donnees_brutes/json_erp/gestion_espaces_verts_small.json \
    --sortie data/instances_trco/greensig_planning.json

# Optimiser pour minimiser les déplacements (changements)
uv run python -m scripts.configurer_objectifs \
    --instance data/instances_trco/greensig_planning.json \
    --config changements
```

### Exemple 2 : Bloc Opératoire

```bash
# Planning chirurgical avec contraintes de délais
uv run python -m scripts.generer_donnees_depuis_config \
    --secteur hopital_bloc_operatoire \
    --taille 30

uv run python -m scripts.transformer_donnees_brutes \
    --entree data/donnees_brutes/json_erp/hopital_bloc_operatoire_small.json \
    --sortie data/instances_trco/bloc_planning.json

# Minimiser les retards (échéances auto-générées)
uv run python -m scripts.configurer_objectifs \
    --instance data/instances_trco/bloc_planning.json \
    --config retards
```

## 🆘 Dépannage

### Erreur : Module 'yaml' introuvable

```bash
# Installer les dépendances
uv sync
```

### Erreur : Configuration introuvable

```bash
# Vérifier que le fichier YAML existe
ls data/configurations_secteurs/

# Lister les secteurs valides
uv run python -m scripts.generer_donnees_depuis_config --lister
```

### Performances lentes pour grandes instances

```bash
# Pour > 200 opérations, générer en plusieurs petites instances
# puis combiner au niveau TRCO
```

## 📚 Références

- **Configurations secteurs** : `data/configurations_secteurs/README.md`
- **Objectifs disponibles** : `data/instances_trco_enrichies/README.md`
- **Format TRCO** : `dsl/schema/instance.py`
- **Adaptateurs** : `adapters/erp_reference/`

## ✅ Checklist de Validation

Avant de générer des données en production :

- [ ] Configuration YAML validée (structure correcte)
- [ ] Types de postes cohérents avec les phases
- [ ] Durées réalistes (min < max)
- [ ] Capacités > 0
- [ ] Prefix_lot unique par secteur
- [ ] Tests de génération sur petit jeu de données
- [ ] Transformation TRCO sans erreur
- [ ] Validation des contraintes TRCO

## 🔄 Prochaines Étapes

1. **Générer le jeu de données de référence** pour tous les secteurs
2. **Exécuter la cascade de validation** sur les instances enrichies
3. **Intégrer au pipeline PRISME** pour génération de solveurs
4. **Benchmarker** les performances par secteur/objectif
