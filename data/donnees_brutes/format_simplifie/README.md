# Données Brutes au Format Simplifié

Ce répertoire contient des données brutes au format simplifié, utilisant directement
la structure taches/ressources/contraintes avec compétences.

## Différence avec les autres formats

**Format ERP** (`data/donnees_brutes/json_erp/`):
- Vocabulaire propriétaire: `operations` / `postes`
- Structure linéaire avec `operation_precedente`
- Nécessite un adaptateur (translator) pour conversion en TRCO

**Format Simplifié** (ce répertoire):
- Vocabulaire canonique: `taches` / `ressources`
- Contraintes typées avec compétences
- Prêt à l'emploi ou conversion légère vers TRCO complet

## Fichiers disponibles

### Exemples de base
- **exemple_minimal**: 2 tâches, 1 ressource - Cas trivial pour démarrage rapide

### Industrie manufacturière

#### Atelier mécanique
- **atelier_mecanique_petit**: 4 tâches, 4 ressources - Flux linéaire simple
- **atelier_mecanique_moyen**: 6 tâches, 6 ressources - Flux avec alternatives

#### Électronique
- **assemblage_electronique**: 5 tâches, 5 ressources - Production PCB basique
- **assemblage_electronique_large**: 15 tâches, 13 ressources - Production PCB double face complète avec tests

#### Textile
- **textile_confection**: 8 tâches, 6 ressources - Chaîne de confection vêtement

#### Agroalimentaire
- **production_agroalimentaire**: 5 tâches, 5 ressources - Transformation alimentaire
- **boulangerie**: 8 tâches, 6 ressources - Production pain artisanale avec pousses

#### Imprimerie
- **imprimerie_petit**: 4 tâches, 4 ressources - Impression simple
- **imprimerie_large**: 16 tâches, 11 ressources - Impression offset recto/verso avec finitions

#### Pharmacie
- **pharmacie_production**: 11 tâches, 9 ressources - Fabrication comprimés (pesée → conditionnement)

### Services

#### Maintenance & Support
- **maintenance**: 5 tâches, 2 ressources - Gestion pannes industrielles
- **data_center_maintenance**: 12 tâches, 6 ressources - Maintenance serveurs avec redondance
- **garage_automobile**: 9 tâches, 5 ressources - Réparation véhicule complète

#### Support client
- **centre_appels**: 6 tâches, 4 ressources - Support N1/N2 avec escalade

#### Santé & social
- **hopital**: 3 tâches, 3 ressources - Parcours patient simplifié

### BTP & Construction
- **construction_batiment**: 9 tâches, 7 ressources - Construction bâtiment (fondations → finitions)

### Services B2B

#### Logistique
- **logistique**: 4 tâches, 4 ressources - Chaîne logistique basique

#### Restauration
- **restauration**: 4 tâches, 4 ressources - Service restauration

#### Formation
- **formation_professionnelle**: 8 tâches, 5 ressources - Parcours formation certifiant

#### Laboratoire
- **laboratoire_analyses**: 8 tâches, 6 ressources - Analyses chimiques/physiques/microbiologiques

#### Édition
- **edition_livre**: 12 tâches, 9 ressources - Publication livre (manuscrit → distribution)

## Statistiques globales

- **Total fichiers**: 22 scénarios différents
- **Taille instances**: De 2 à 16 tâches
- **Secteurs couverts**: 8 (Industrie, Services, BTP, B2B, Santé, Formation, Édition, Logistique)
- **Complexité**: Flux linéaires simples → graphes de précédence complexes avec branches parallèles

## Caractéristiques des scénarios

### Par complexité de graphe de précédence

**Linéaire simple** (une seule chaîne):
- exemple_minimal, atelier_mecanique_petit, boulangerie, centre_appels

**Avec embranchements** (quelques branches parallèles):
- atelier_mecanique_moyen, assemblage_electronique, garage_automobile, laboratoire_analyses

**Complexe** (multiples branches + convergences):
- construction_batiment, assemblage_electronique_large, imprimerie_large, edition_livre

**Avec convergence critique** (plusieurs tâches → une seule):
- data_center_maintenance (T5 + T6 → T7), pharmacie_production

### Par durée temporelle

**Ultra-rapide** (< 1 jour):
- centre_appels (0.67 jours si séquentiel)
- data_center_maintenance (2.43 jours avec urgence pièce)

**Rapide** (1-5 jours):
- atelier_mecanique_petit (5 jours), garage_automobile (5.5 jours)
- textile_confection (3 jours), boulangerie (1.5 jours)

**Moyen** (5-15 jours):
- assemblage_electronique (6.3 jours), imprimerie_large (9 jours)
- laboratoire_analyses (6.6 jours), pharmacie_production (14.6 jours)

**Long** (> 15 jours):
- construction_batiment (51 jours), edition_livre (48 jours)

### Par type de ressources

**Humaines uniquement**:
- formation_professionnelle, edition_livre, hopital

**Machines uniquement**:
- assemblage_electronique_large, imprimerie_large

**Mixte humain/machine**:
- garage_automobile, boulangerie, textile_confection, laboratoire_analyses

**Avec ressources partagées** (plusieurs tâches → même ressource):
- boulangerie (chambre fermentation pour T3 et T5)
- imprimerie_large (tunnel séchage pour T7, T9, T11)
- assemblage_electronique_large (Pick&Place 1/2, Four 1/2 — redondance)

## Structure du format

```json
{
  "taches": [
    {"id": "T1", "nom": "Nom de la tâche", "duree_estimee_jours": 3}
  ],
  "ressources": [
    {"id": "R1", "nom": "Nom de la ressource", "competences": ["comp1", "comp2"]}
  ],
  "contraintes": [
    {"type": "precedence", "avant": "T1", "apres": "T2"},
    {"type": "competence_requise", "tache": "T1", "competence": "comp1"}
  ],
  "objectifs": [
    {"type": "minimiser_makespan"}
  ]
}
```

## Utilisation

Ces données brutes peuvent être utilisées pour:

1. **Ingestion directe**: Import via l'API avec conversion minimale
2. **Prototypage**: Tests rapides sans adapter depuis un format ERP
3. **Exemples**: Documentation et démonstrations
4. **Tests**: Validation de la chaîne de traitement

## Conversion vers TRCO complet

Pour utiliser ces données dans PRISME, un adaptateur léger doit:

1. Dériver les contraintes `compatibilite_ressource_tache` depuis les compétences
2. Extraire les durées des tâches vers les contraintes de compatibilité
3. Ajouter les métadonnées (priorite, statut, type_ressource)

Voir `adapters/competence_derivation.py` pour la logique de dérivation.

## Cas d'usage recommandés

### Tests unitaires
- **exemple_minimal**: Tests basiques, sanity checks
- **atelier_mecanique_petit**: Tests de régression standards

### Validation des algorithmes
- **assemblage_electronique_large**: Test de performance (15 tâches)
- **imprimerie_large**: Test ressources partagées multiples
- **construction_batiment**: Test graphe complexe avec embranchements

### Démonstrations clients
- **boulangerie**: Secteur familier, visuel
- **garage_automobile**: Flux métier évident
- **centre_appels**: Secteur services

### Benchmarking
- **pharmacie_production**: Chaîne linéaire longue (11 tâches)
- **edition_livre**: Projet long terme (48 jours)
- **data_center_maintenance**: Urgence + parallélisme (commande pièce ∥ diagnostic)

## Notes d'implémentation

### Compétences multiples
Certaines ressources possèdent plusieurs compétences, permettant de tester la flexibilité :
- **Boulanger** (`boulangerie`): pesee, faconnage, scarification
- **Responsable qualité** (`laboratoire_analyses`): validation, compilation, redaction
- **Mécanicien** (`garage_automobile`): demontage, reparation_mecanique, remontage

### Durées fractionnaires
Les secteurs services utilisent des durées < 1 jour pour simuler des opérations horaires :
- **centre_appels**: de 0.02 (30min) à 0.2 jour (5h)
- **data_center_maintenance**: de 0.01 à 1 jour

### Contraintes implicites
Tous les fichiers utilisent uniquement des contraintes de **précédence** et **compétence_requise**.
Pour tester d'autres types de contraintes (échéances, capacité, incompatibilité),
ajouter manuellement ou utiliser le format TRCO complet.

## Regénération

```bash
uv run python -m scripts.generer_donnees_brutes_format_simplifie
```

## Évolution future

Contraintes à ajouter dans les prochaines versions :
- **Échéances** (`echeance`): deadline sur certaines tâches critiques
- **Capacité** (`contrainte_capacite`): ressources multi-opérations simultanées
- **Incompatibilité** (`contrainte_incompatibilite`): tâches mutuellement exclusives sur ressources

Secteurs manquants à couvrir :
- Transport/Logistique maritime
- Télécommunications
- Énergie/Utilities
- Événementiel
- Recherche & Développement
