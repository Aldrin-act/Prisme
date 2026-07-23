# Index : Système de Génération de Données PRISME

Navigation centralisée pour toute la documentation du système de génération.

## 📖 Documentation Principale

| Document | Description | Audience |
|----------|-------------|----------|
| **[GUIDE_COMPLET_GENERATION.md](GUIDE_COMPLET_GENERATION.md)** | Guide complet du système | Développeurs |
| **[SECTEURS_DISPONIBLES.md](SECTEURS_DISPONIBLES.md)** | Référence rapide des 9 secteurs | Tous |
| **[GUIDE_DONNEES.md](GUIDE_DONNEES.md)** | Workflow données brutes → TRCO | Utilisateurs |
| **[README.md](README.md)** | Quick start | Nouveaux utilisateurs |

## 🗂️ Documentation par Composant

### Configurations Sectorielles

**Emplacement :** `data/configurations_secteurs/`

- [README.md](configurations_secteurs/README.md) - Guide des configurations YAML
- 9 fichiers YAML (un par secteur)

**Secteurs industriels :**
- `atelier_mecanique.yaml` - Usinage de précision
- `assemblage_electronique.yaml` - Assemblage de circuits
- `production_agroalimentaire.yaml` - Production alimentaire

**Secteurs de services :**
- `gestion_espaces_verts.yaml` - Entretien paysager (GreenSIG)
- `hopital_bloc_operatoire.yaml` - Planification chirurgicale
- `logistique_transport.yaml` - Supply chain
- `services_nettoyage.yaml` - Nettoyage professionnel
- `education_planification_cours.yaml` - Emplois du temps
- `restauration_collective.yaml` - Cuisine collective

### Données Générées

**Données brutes (ERP):**
- `data/donnees_brutes/README.md` - Format et structure
- `data/donnees_brutes/json_erp/` - Payloads JSON
- `data/donnees_brutes/csv/` - Export CSV

**Instances TRCO:**
- `data/instances_trco/` - Instances canoniques

**Instances enrichies:**
- `data/instances_trco_enrichies/README.md` - Guide des objectifs
- 6 configurations par instance : makespan, equilibrage, retards, utilisation, changements, multi

### Exemples DSL

**Emplacement :** `dsl/examples/`

- `objectifs_varies/README.md` - Instances pré-configurées
- `objectifs_varies/GUIDE_UTILISATION.md` - Mode d'emploi
- `objectifs_varies/OBJECTIFS_DISPONIBLES.md` - Référence des objectifs
- `objectifs_varies/INDEX.md` - Navigation

## 🛠️ Scripts

**Emplacement :** `scripts/`

### Scripts de Génération

| Script | Rôle | Usage Principal |
|--------|------|----------------|
| `generer_donnees_depuis_config.py` | Génère données brutes depuis YAML | `--secteur <nom> --taille <n>` |
| `transformer_donnees_brutes.py` | ERP → TRCO | `--entree <json> --sortie <json>` |
| `configurer_objectifs.py` | Enrichit avec objectifs | `--instance <json> [--config <type>]` |

### Scripts d'Analyse

| Script | Rôle |
|--------|------|
| `analyser_instances.py` | Statistiques instances TRCO |
| `analyser_objectifs.py` | Distribution objectifs |
| `valider_instances_objectifs_varies.py` | Validation structure |

### Scripts de Démonstration

| Script | Rôle |
|--------|------|
| `demo_donnees_brutes.py` | Workflow complet |
| `demo_bout_en_bout.py` | Pipeline PRISME end-to-end |

### Scripts Hérités (Ancienne Approche)

| Script | Rôle | Statut |
|--------|------|--------|
| `generer_donnees_brutes.py` | 5 secteurs hardcodés | ⚠️ Remplacé par config YAML |
| `generer_donnees_brutes_grande_echelle.py` | 3 secteurs large | ⚠️ Remplacé par `--taille` |
| `generer_instances_objectifs_varies.py` | 6 instances pré-faites | ✅ Conservé pour exemples |
| `generer_banc_synthetique.py` | Bench validation (construction inverse) | ✅ Conservé (cascade) |

## 🎯 Guides par Cas d'Usage

### Démarrage Rapide

**Je veux :** Générer mes premières données
**Lire :** [README.md](README.md)
**Commandes :**
```bash
uv sync
uv run python -m scripts.generer_donnees_depuis_config --lister
uv run python -m scripts.generer_donnees_depuis_config --secteur gestion_espaces_verts --taille 30
```

### Comprendre le Système

**Je veux :** Comprendre l'architecture complète
**Lire :** [GUIDE_COMPLET_GENERATION.md](GUIDE_COMPLET_GENERATION.md)
**Sections clés :** Architecture, Pipeline complet, Cas d'usage

### Choisir un Secteur

**Je veux :** Voir tous les secteurs disponibles
**Lire :** [SECTEURS_DISPONIBLES.md](SECTEURS_DISPONIBLES.md)
**Contenu :** Fiches détaillées par secteur, comparaison

### Créer un Nouveau Secteur

**Je veux :** Ajouter mon propre secteur
**Lire :** [configurations_secteurs/README.md](configurations_secteurs/README.md) section "Ajouter un Nouveau Secteur"
**Étapes :**
1. Créer fichier YAML
2. Définir types_postes, phases_production
3. Tester génération

### Travailler avec les Objectifs

**Je veux :** Comprendre les différents objectifs d'optimisation
**Lire :** [instances_trco_enrichies/README.md](instances_trco_enrichies/README.md)
**Contenu :** 6 configurations, formules mathématiques, cas d'usage

### Workflow Données Brutes

**Je veux :** Comprendre le format ERP et la transformation
**Lire :** [GUIDE_DONNEES.md](GUIDE_DONNEES.md)
**Contenu :** Format ERP, transformation TRCO, validation

## 📋 Checklists

### Génération Standard

- [ ] Installer dépendances (`uv sync`)
- [ ] Choisir un secteur (`--lister`)
- [ ] Générer données brutes (`generer_donnees_depuis_config.py`)
- [ ] Transformer en TRCO (`transformer_donnees_brutes.py`)
- [ ] Enrichir avec objectifs (`configurer_objectifs.py`)
- [ ] Valider les instances générées

### Ajout de Secteur

- [ ] Créer fichier YAML dans `configurations_secteurs/`
- [ ] Définir au moins 5 types_postes
- [ ] Définir au moins 4 phases_production
- [ ] Configurer paramètres de génération
- [ ] Tester génération small (20 ops)
- [ ] Tester transformation TRCO
- [ ] Tester enrichissement objectifs
- [ ] Documenter le secteur dans README

### Validation Qualité

- [ ] Aucune erreur de génération
- [ ] Toutes les contraintes TRCO valides
- [ ] Précédences cohérentes
- [ ] Durées réalistes
- [ ] Capacités > 0
- [ ] Objectifs bien formés
- [ ] Échéances cohérentes (si applicable)

## 🔍 Index par Mot-Clé

**Configuration**
- [configurations_secteurs/README.md](configurations_secteurs/README.md)
- [GUIDE_COMPLET_GENERATION.md](GUIDE_COMPLET_GENERATION.md) § Architecture

**YAML**
- [configurations_secteurs/](configurations_secteurs/) - 9 fichiers

**Objectifs**
- [instances_trco_enrichies/README.md](instances_trco_enrichies/README.md)
- [SECTEURS_DISPONIBLES.md](SECTEURS_DISPONIBLES.md) § Par Objectif

**Format ERP**
- [donnees_brutes/README.md](donnees_brutes/README.md)
- [GUIDE_DONNEES.md](GUIDE_DONNEES.md)

**TRCO (Tâches, Ressources, Contraintes, Objectifs)**
- `dsl/schema/instance.py` (code source)
- [GUIDE_COMPLET_GENERATION.md](GUIDE_COMPLET_GENERATION.md) § Transformation TRCO

**Scripts**
- [GUIDE_COMPLET_GENERATION.md](GUIDE_COMPLET_GENERATION.md) § Pipeline
- Cette section "Scripts" ci-dessus

**Secteurs**
- [SECTEURS_DISPONIBLES.md](SECTEURS_DISPONIBLES.md) - Liste complète
- [configurations_secteurs/README.md](configurations_secteurs/README.md) - Détails techniques

**GreenSIG**
- [configurations_secteurs/gestion_espaces_verts.yaml](configurations_secteurs/gestion_espaces_verts.yaml)
- [SECTEURS_DISPONIBLES.md](SECTEURS_DISPONIBLES.md) § Espaces Verts

**Benchmark**
- `scripts/generer_banc_synthetique.py` (synthetic bench)
- [GUIDE_COMPLET_GENERATION.md](GUIDE_COMPLET_GENERATION.md) § Cas 2: Benchmark

**Validation**
- `scripts/valider_instances_objectifs_varies.py`
- [GUIDE_COMPLET_GENERATION.md](GUIDE_COMPLET_GENERATION.md) § Checklist

## 📊 Arborescence Complète

```
data/
├── INDEX_GENERATION.md                 ← Vous êtes ici
├── GUIDE_COMPLET_GENERATION.md        ← Guide principal
├── SECTEURS_DISPONIBLES.md            ← Référence rapide
├── GUIDE_DONNEES.md                   ← Workflow données
├── README.md                          ← Quick start
│
├── configurations_secteurs/           ← YAML configs
│   ├── README.md
│   ├── atelier_mecanique.yaml
│   ├── assemblage_electronique.yaml
│   ├── production_agroalimentaire.yaml
│   ├── gestion_espaces_verts.yaml
│   ├── hopital_bloc_operatoire.yaml
│   ├── logistique_transport.yaml
│   ├── services_nettoyage.yaml
│   ├── education_planification_cours.yaml
│   └── restauration_collective.yaml
│
├── donnees_brutes/                    ← Données ERP générées
│   ├── README.md
│   ├── json_erp/                      ← Format JSON
│   │   └── {secteur}_{taille}.json
│   └── csv/                           ← Format CSV
│       ├── {secteur}_{taille}_postes.csv
│       └── {secteur}_{taille}_operations.csv
│
├── instances_trco/                    ← Instances canoniques
│   └── {secteur}_{taille}.json
│
└── instances_trco_enrichies/          ← Instances avec objectifs
    ├── README.md
    └── {secteur}_{taille}_{objectif}.json
```

## 🚀 Commandes Utiles

```bash
# Lister secteurs disponibles
uv run python -m scripts.generer_donnees_depuis_config --lister

# Générer un secteur
uv run python -m scripts.generer_donnees_depuis_config --secteur <nom> --taille <n>

# Générer tous les secteurs
uv run python -m scripts.generer_donnees_depuis_config --tous --taille 50

# Transformer en TRCO
uv run python -m scripts.transformer_donnees_brutes --tous

# Enrichir avec objectifs
uv run python -m scripts.configurer_objectifs --tous

# Analyser les données
uv run python -m scripts.analyser_instances
uv run python -m scripts.analyser_objectifs

# Valider
uv run python -m scripts.valider_instances_objectifs_varies

# Démo complète
uv run python -m scripts.demo_donnees_brutes
```

## 🆘 Support

**Problème de génération ?**
→ Vérifier [configurations_secteurs/README.md](configurations_secteurs/README.md)

**Erreur de transformation ?**
→ Consulter [GUIDE_DONNEES.md](GUIDE_DONNEES.md)

**Question sur les objectifs ?**
→ Lire [instances_trco_enrichies/README.md](instances_trco_enrichies/README.md)

**Nouveau secteur ?**
→ Suivre [GUIDE_COMPLET_GENERATION.md](GUIDE_COMPLET_GENERATION.md) § Cas 1

## 📚 Ressources Externes

- **Schéma TRCO** : `dsl/schema/`
- **Adaptateurs ERP** : `adapters/erp_reference/`
- **Documentation PRISME** : `CLAUDE.md`, `PRISME_Note_de_Cadrage (2).md`
- **Tests** : `tests/unit/`, `tests/integration/`

## ✅ Validation Finale

Avant de considérer le système prêt :

- [x] 9 configurations secteurs créées
- [x] Script générateur unifié (`generer_donnees_depuis_config.py`)
- [x] Documentation complète (5 fichiers MD)
- [ ] Tests unitaires pour le générateur
- [ ] Génération de référence tous secteurs (3 tailles × 6 objectifs)
- [ ] Validation cascade sur instances enrichies
- [ ] Intégration pipeline PRISME

## 🔄 Mise à Jour

**Dernière modification :** 2026-07-23
**Version système :** 2.0 (Configuration YAML, 9 secteurs)
**Auteur :** Claude Code (PRISME PFE)
