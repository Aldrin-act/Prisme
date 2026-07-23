# Configurations des Secteurs

Ce répertoire contient les configurations YAML pour différents secteurs d'activité. Chaque fichier définit les caractéristiques spécifiques d'un secteur permettant de générer des données de planification réalistes.

## 📁 Structure d'une Configuration

Chaque fichier YAML suit cette structure :

```yaml
nom: nom_du_secteur
description: Description du secteur
types_postes:
  NOM_POSTE:
    duree_min: durée minimale (minutes)
    duree_max: durée maximale (minutes)
    capacite: nombre d'instances disponibles
phases_production:
  - nom: NOM_PHASE
    types_poste:
      - TYPE_POSTE_1
      - TYPE_POSTE_2
generation:
  operations_par_lot_min: nombre minimum d'opérations par lot
  operations_par_lot_max: nombre maximum d'opérations par lot
  prefix_lot: préfixe pour les identifiants de lots
```

## 🏭 Secteurs Industriels

### atelier_mecanique.yaml
**Atelier de mécanique de précision**
- 15 types de postes (découpe laser, tournage CNC, fraisage, etc.)
- Capacités variées (4-15 machines par type)
- Durées : 10-360 minutes
- 9 phases de production

### assemblage_electronique.yaml
**Ligne d'assemblage électronique**
- 12 types de postes (insertion, soudure, inspection, etc.)
- Focus sur les processus d'assemblage de circuits
- Durées : 5-180 minutes
- 8 phases de production

### production_agroalimentaire.yaml
**Production alimentaire industrielle**
- 11 types de postes (préparation, cuisson, conditionnement, etc.)
- Contraintes d'hygiène et de conservation
- Durées : 10-240 minutes
- 8 phases de production

## 🌳 Secteurs de Services

### gestion_espaces_verts.yaml
**Gestion d'espaces verts (type GreenSIG)**
- 9 équipes spécialisées (tonte, taille, arrosage, etc.)
- Équipements variés (débroussailleuse, élagueuse, tondeuse)
- Durées : 30-360 minutes
- 9 phases d'intervention
- Prefix: SITE

### services_nettoyage.yaml
**Services de nettoyage professionnel**
- 10 types d'équipes (nettoyage bureaux, industriel, vitres, etc.)
- Spécialisations techniques (décapage, désinfection, polissage)
- Durées : 10-360 minutes
- 9 phases de nettoyage
- Prefix: SITE

## 🏥 Secteur Santé

### hopital_bloc_operatoire.yaml
**Planification bloc opératoire**
- 9 types de salles et équipements
- Blocs spécialisés (chirurgie générale, orthopédique, cardiaque)
- Durées : 10-1440 minutes (jusqu'à 24h pour soins intensifs)
- 7 phases de prise en charge
- Prefix: PAT (Patient)

## 🎓 Secteur Éducation

### education_planification_cours.yaml
**Planification de cours et examens**
- 9 types de salles (cours standard, TP, amphi, laboratoire, etc.)
- Capacités variées selon le type de salle
- Durées : 60-300 minutes
- 7 phases pédagogiques
- Prefix: UE (Unité d'Enseignement)

## 🚚 Secteur Logistique

### logistique_transport.yaml
**Logistique et transport**
- 9 types d'équipements (camions, chariots, quais, zones)
- Véhicules de différentes capacités (camionnette, 10T, 20T)
- Durées : 5-480 minutes
- 8 phases logistiques
- Prefix: CMD (Commande)

## 🍽️ Secteur Restauration

### restauration_collective.yaml
**Restauration collective**
- 11 postes de cuisine (préparation, cuisson, dressage, etc.)
- Équipements spécialisés (four, marmite, cellule de refroidissement)
- Durées : 10-300 minutes
- 9 phases de production
- Prefix: MENU

## 🚀 Utilisation

### Installation

Assurez-vous que PyYAML est installé :
```bash
uv sync  # Installe toutes les dépendances, y compris pyyaml
```

### Lister les secteurs disponibles

```bash
uv run python -m scripts.generer_donnees_depuis_config --lister
```

### Générer des données pour un secteur

**Petit jeu de données (20 opérations, par défaut) :**
```bash
uv run python -m scripts.generer_donnees_depuis_config --secteur gestion_espaces_verts
```

**Jeu de données moyen (50 opérations) :**
```bash
uv run python -m scripts.generer_donnees_depuis_config --secteur hopital_bloc_operatoire --taille 50
```

**Grand jeu de données (100 opérations) :**
```bash
uv run python -m scripts.generer_donnees_depuis_config --secteur restauration_collective --taille 100
```

**Format spécifique (JSON ou CSV uniquement) :**
```bash
uv run python -m scripts.generer_donnees_depuis_config --secteur logistique_transport --format json
```

**Générer pour TOUS les secteurs :**
```bash
uv run python -m scripts.generer_donnees_depuis_config --tous --taille 30
```

### Fichiers de sortie

Les données générées sont sauvegardées dans :
- **JSON** : `data/donnees_brutes/json_erp/{secteur}_{taille}.json`
- **CSV** : `data/donnees_brutes/csv/{secteur}_{taille}_postes.csv`
            `data/donnees_brutes/csv/{secteur}_{taille}_operations.csv`

Catégories de taille :
- `small` : < 50 opérations
- `medium` : 50-149 opérations
- `large` : ≥ 150 opérations

## ➕ Ajouter un Nouveau Secteur

1. Créer un fichier `nouveau_secteur.yaml` dans ce répertoire
2. Suivre la structure décrite ci-dessus
3. Définir au minimum :
   - `nom` et `description`
   - 5-15 `types_postes` avec leurs caractéristiques
   - 4-10 `phases_production`
   - Paramètres de `generation`

4. Tester la génération :
```bash
uv run python -m scripts.generer_donnees_depuis_config --secteur nouveau_secteur --taille 20
```

## 📊 Caractéristiques par Secteur

| Secteur | Types Postes | Phases | Durée Min | Durée Max | Capacité Moy |
|---------|--------------|--------|-----------|-----------|--------------|
| Atelier mécanique | 15 | 9 | 10 min | 360 min | 7.5 |
| Assemblage électronique | 12 | 8 | 5 min | 180 min | 11.8 |
| Production agroalimentaire | 11 | 8 | 10 min | 240 min | 10.5 |
| Espaces verts | 9 | 9 | 30 min | 360 min | 9.1 |
| Bloc opératoire | 9 | 7 | 10 min | 1440 min | 7.7 |
| Logistique | 9 | 8 | 5 min | 480 min | 13.8 |
| Nettoyage | 10 | 9 | 10 min | 360 min | 8.0 |
| Éducation | 9 | 7 | 60 min | 300 min | 13.0 |
| Restauration | 11 | 9 | 10 min | 300 min | 8.5 |

## 🔄 Pipeline Complet

1. **Configuration** (ce répertoire) →
2. **Génération données brutes** (`scripts/generer_donnees_depuis_config.py`) →
3. **Transformation TRCO** (`scripts/transformer_donnees_brutes.py`) →
4. **Configuration objectifs** (`scripts/configurer_objectifs.py`) →
5. **Génération de solveur** (PRISME pipeline)

## 📝 Notes

- Les durées sont en **minutes**
- Les capacités représentent le nombre d'instances simultanées
- Chaque phase peut utiliser plusieurs types de postes
- Les lots permettent de grouper des opérations liées
- Les précédences entre opérations sont générées aléatoirement (60% de chance)

## 🆘 Support

Pour ajouter un secteur spécifique ou adapter une configuration existante, consultez les exemples dans ce répertoire et suivez la structure YAML.
