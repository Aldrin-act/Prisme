# Référence Rapide : Secteurs Disponibles

Guide rapide des 9 secteurs configurés pour la génération de données PRISME.

## 🏭 Secteurs Industriels

### 1. Atelier Mécanique
**Fichier :** `atelier_mecanique.yaml`
**Description :** Usinage de précision et fabrication mécanique
**Postes :** 15 types (découpe laser, tournage CNC, fraisage, soudure, etc.)
**Phases :** 9 (découpe, usinage, assemblage, finition, contrôle, etc.)
**Prefix :** PIECE
**Durées :** 10-360 min
**Capacité moyenne :** 7.5 machines/poste

**Exemple :**
```bash
uv run python -m scripts.generer_donnees_depuis_config --secteur atelier_mecanique --taille 50
```

---

### 2. Assemblage Électronique
**Fichier :** `assemblage_electronique.yaml`
**Description :** Ligne d'assemblage de circuits imprimés
**Postes :** 12 types (insertion, soudure, inspection, test, etc.)
**Phases :** 8 (préparation, insertion, soudure, inspection, test, etc.)
**Prefix :** PCB
**Durées :** 5-180 min
**Capacité moyenne :** 11.8 machines/poste

**Cas d'usage :** Production de cartes électroniques, assemblage de composants SMD/THT

---

### 3. Production Agroalimentaire
**Fichier :** `production_agroalimentaire.yaml`
**Description :** Transformation alimentaire industrielle
**Postes :** 11 types (préparation, cuisson, pasteurisation, conditionnement, etc.)
**Phases :** 8 (réception, préparation, transformation, conditionnement, etc.)
**Prefix :** LOT
**Durées :** 10-240 min
**Capacité moyenne :** 10.5 équipements/poste

**Cas d'usage :** Transformation alimentaire, chaîne de production, traçabilité

---

## 🌳 Secteurs de Services

### 4. Gestion Espaces Verts (GreenSIG)
**Fichier :** `gestion_espaces_verts.yaml`
**Description :** Entretien paysager et gestion d'espaces verts
**Postes :** 9 types (tonte, taille, désherbage, arrosage, etc.)
**Phases :** 9 (tonte, taille, désherbage, plantation, etc.)
**Prefix :** SITE
**Durées :** 30-360 min
**Capacité moyenne :** 9.1 équipes/type

**Cas d'usage :** Planification d'interventions paysagères, tournées d'entretien

**Exemple :**
```bash
uv run python -m scripts.generer_donnees_depuis_config --secteur gestion_espaces_verts --taille 40
```

---

### 5. Bloc Opératoire
**Fichier :** `hopital_bloc_operatoire.yaml`
**Description :** Planification chirurgicale et soins hospitaliers
**Postes :** 9 types (blocs chirurgicaux, salles réveil, USI, radiologie, etc.)
**Phases :** 7 (admission, examens préop, intervention, réveil, etc.)
**Prefix :** PAT (Patient)
**Durées :** 10-1440 min (jusqu'à 24h pour soins intensifs)
**Capacité moyenne :** 7.7 salles/type

**Cas d'usage :** Optimisation du planning chirurgical, gestion des urgences

**Exemple :**
```bash
# Planification avec contraintes de délais
uv run python -m scripts.generer_donnees_depuis_config --secteur hopital_bloc_operatoire --taille 30
```

---

### 6. Logistique et Transport
**Fichier :** `logistique_transport.yaml`
**Description :** Supply chain et opérations logistiques
**Postes :** 9 types (camions 20T/10T, camionnettes, chariots, quais, zones)
**Phases :** 8 (réception, contrôle, stockage, préparation, chargement, livraison)
**Prefix :** CMD (Commande)
**Durées :** 5-480 min
**Capacité moyenne :** 13.8 équipements/type

**Cas d'usage :** Optimisation de tournées, planification d'entrepôt

---

### 7. Services de Nettoyage
**Fichier :** `services_nettoyage.yaml`
**Description :** Nettoyage professionnel et entretien de bâtiments
**Postes :** 10 types (nettoyage bureaux/industriel, vitres, désinfection, etc.)
**Phases :** 9 (aspiration, lavage sols, désinfection, vitres, etc.)
**Prefix :** SITE
**Durées :** 10-360 min
**Capacité moyenne :** 8.0 équipes/type

**Cas d'usage :** Planification d'interventions de nettoyage, optimisation des tournées

---

### 8. Éducation - Planification de Cours
**Fichier :** `education_planification_cours.yaml`
**Description :** Emplois du temps et planification pédagogique
**Postes :** 9 types (salles cours, TP informatique/sciences, amphi, exam, etc.)
**Phases :** 7 (cours magistral, TD, TP, examens, conférences, projets)
**Prefix :** UE (Unité d'Enseignement)
**Durées :** 60-300 min
**Capacité moyenne :** 13.0 salles/type

**Cas d'usage :** Génération d'emplois du temps, optimisation de l'utilisation des salles

**Exemple :**
```bash
# Planning universitaire avec équilibrage de charge
uv run python -m scripts.generer_donnees_depuis_config --secteur education_planification_cours --taille 60
```

---

### 9. Restauration Collective
**Fichier :** `restauration_collective.yaml`
**Description :** Cuisine collective et préparation de repas
**Postes :** 11 types (préparation légumes/viandes, cuisson four/plaque/marmite, etc.)
**Phases :** 9 (préparation, cuisson principale, pâtisserie, dressage, etc.)
**Prefix :** MENU
**Durées :** 10-300 min
**Capacité moyenne :** 8.5 postes/type

**Cas d'usage :** Planification de production en cuisine centrale, optimisation des menus

---

## 📊 Comparaison Rapide

| Secteur | Code | Postes | Phases | Durée Moy | Use Case Principal |
|---------|------|--------|--------|-----------|-------------------|
| Atelier mécanique | `atelier_mecanique` | 15 | 9 | 120 min | Production industrielle |
| Assemblage électronique | `assemblage_electronique` | 12 | 8 | 60 min | Manufacturing électronique |
| Production agroalimentaire | `production_agroalimentaire` | 11 | 8 | 80 min | Transformation alimentaire |
| Espaces verts | `gestion_espaces_verts` | 9 | 9 | 150 min | Entretien paysager |
| Bloc opératoire | `hopital_bloc_operatoire` | 9 | 7 | 180 min | Planification chirurgicale |
| Logistique | `logistique_transport` | 9 | 8 | 120 min | Supply chain |
| Nettoyage | `services_nettoyage` | 10 | 9 | 90 min | Facility management |
| Éducation | `education_planification_cours` | 9 | 7 | 120 min | Emplois du temps |
| Restauration | `restauration_collective` | 11 | 9 | 90 min | Production culinaire |

## 🎯 Par Objectif d'Optimisation

### Minimiser Makespan (Temps Total)
**Recommandé pour :**
- Atelier mécanique
- Assemblage électronique
- Production agroalimentaire

### Équilibrer Charge
**Recommandé pour :**
- Éducation (répartition des salles)
- Restauration (équilibrage des postes)
- Bloc opératoire (utilisation des blocs)

### Minimiser Retards
**Recommandé pour :**
- Bloc opératoire (urgences)
- Logistique (livraisons)
- Espaces verts (contrats SLA)

### Maximiser Utilisation
**Recommandé pour :**
- Atelier mécanique (machines coûteuses)
- Bloc opératoire (optimisation ressources)

### Minimiser Changements
**Recommandé pour :**
- Espaces verts (réduction déplacements)
- Nettoyage (optimisation tournées)
- Logistique (groupage livraisons)

### Multi-Objectifs
**Recommandé pour :**
- Tous les secteurs pour benchmark complet

## 🚀 Commandes Rapides

### Lister tous les secteurs
```bash
uv run python -m scripts.generer_donnees_depuis_config --lister
```

### Générer un secteur spécifique
```bash
uv run python -m scripts.generer_donnees_depuis_config --secteur <nom> --taille <n>
```

### Générer tous les secteurs
```bash
uv run python -m scripts.generer_donnees_depuis_config --tous --taille 50
```

### Pipeline complet pour un secteur
```bash
# 1. Générer données brutes
uv run python -m scripts.generer_donnees_depuis_config --secteur <nom> --taille 50

# 2. Transformer en TRCO
uv run python -m scripts.transformer_donnees_brutes \
    --entree data/donnees_brutes/json_erp/<nom>_medium.json \
    --sortie data/instances_trco/<nom>_medium.json

# 3. Enrichir avec objectifs (génère 6 variantes)
uv run python -m scripts.configurer_objectifs \
    --instance data/instances_trco/<nom>_medium.json
```

## 📚 Documentation Complète

- **Guide complet** : `data/GUIDE_COMPLET_GENERATION.md`
- **Configurations** : `data/configurations_secteurs/README.md`
- **Objectifs** : `data/instances_trco_enrichies/README.md`
- **Workflow** : `data/GUIDE_DONNEES.md`

## ➕ Ajouter un Nouveau Secteur

1. Créer `nouveau_secteur.yaml` dans `data/configurations_secteurs/`
2. Suivre la structure des exemples existants
3. Tester avec :
```bash
uv run python -m scripts.generer_donnees_depuis_config --secteur nouveau_secteur --taille 20
```

## 🔍 Recherche Rapide

**Par type d'activité :**
- **Production :** atelier_mecanique, assemblage_electronique, production_agroalimentaire, restauration_collective
- **Services terrain :** gestion_espaces_verts, services_nettoyage
- **Services spécialisés :** hopital_bloc_operatoire, education_planification_cours
- **Logistique :** logistique_transport

**Par taille typique :**
- **Petit (< 50 ops) :** Tous secteurs
- **Moyen (50-100 ops) :** Tous secteurs
- **Grand (> 100 ops) :** Atelier mécanique, Assemblage électronique, Logistique, Restauration
