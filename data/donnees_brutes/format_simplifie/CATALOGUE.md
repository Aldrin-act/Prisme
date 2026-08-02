# Catalogue des Scénarios - Format Simplifié

## Tableau comparatif

| Fichier | Tâches | Ressources | Contraintes | Durée totale | Secteur | Complexité | Type ressources |
|---------|--------|------------|-------------|--------------|---------|------------|-----------------|
| **exemple_minimal** | 2 | 1 | 3 | 5j | Demo | ⭐ Simple | Mixte |
| **atelier_mecanique_petit** | 4 | 4 | 7 | 5j | Industrie | ⭐ Simple | Machine |
| **atelier_mecanique_moyen** | 6 | 6 | 11 | 8j | Industrie | ⭐⭐ Moyen | Machine |
| **assemblage_electronique** | 5 | 5 | 9 | 6.3j | Industrie | ⭐⭐ Moyen | Machine |
| **assemblage_electronique_large** | 15 | 13 | 29 | 6.8j | Industrie | ⭐⭐⭐ Complexe | Machine |
| **production_agroalimentaire** | 5 | 5 | 9 | 9j | Industrie | ⭐⭐ Moyen | Machine |
| **textile_confection** | 8 | 6 | 15 | 3j | Industrie | ⭐⭐ Moyen | Machine |
| **boulangerie** | 8 | 6 | 15 | 1.5j | Industrie | ⭐⭐ Moyen | Mixte |
| **imprimerie_petit** | 4 | 4 | 7 | 4j | Industrie | ⭐ Simple | Machine |
| **imprimerie_large** | 16 | 11 | 31 | 9j | Industrie | ⭐⭐⭐ Complexe | Machine |
| **pharmacie_production** | 11 | 9 | 21 | 14.6j | Industrie | ⭐⭐⭐ Complexe | Machine |
| **maintenance** | 5 | 2 | 9 | 7j | Services | ⭐⭐ Moyen | Humain |
| **data_center_maintenance** | 12 | 6 | 23 | 2.43j | Services | ⭐⭐⭐ Complexe | Mixte |
| **garage_automobile** | 9 | 5 | 17 | 5.5j | Services | ⭐⭐ Moyen | Mixte |
| **centre_appels** | 6 | 4 | 11 | 0.67j | Services | ⭐ Simple | Humain |
| **hopital** | 3 | 3 | 5 | 4j | Santé | ⭐ Simple | Humain |
| **construction_batiment** | 9 | 7 | 17 | 51j | BTP | ⭐⭐⭐ Complexe | Mixte |
| **logistique** | 4 | 4 | 7 | 5j | Logistique | ⭐⭐ Moyen | Mixte |
| **restauration** | 4 | 4 | 7 | 3j | Services | ⭐ Simple | Mixte |
| **formation_professionnelle** | 8 | 5 | 15 | 10.3j | Formation | ⭐⭐ Moyen | Humain |
| **laboratoire_analyses** | 8 | 6 | 16 | 6.6j | Services | ⭐⭐⭐ Complexe | Mixte |
| **edition_livre** | 12 | 9 | 23 | 48j | Édition | ⭐⭐⭐ Complexe | Humain |

## Légende

### Complexité
- ⭐ **Simple**: Flux linéaire, peu de contraintes
- ⭐⭐ **Moyen**: Quelques embranchements, ressources multiples
- ⭐⭐⭐ **Complexe**: Graphe riche, convergences, ressources partagées

### Type ressources
- **Humain**: Uniquement des opérateurs/techniciens
- **Machine**: Uniquement des équipements/machines
- **Mixte**: Combinaison humain + machine

### Durée totale
Estimation du makespan si toutes les tâches sont exécutées séquentiellement (chemin critique).

## Sélection rapide par besoin

### Besoin: Test rapide / Proof of concept
→ `exemple_minimal`, `atelier_mecanique_petit`, `centre_appels`

### Besoin: Démonstration client secteur industriel
→ `boulangerie`, `assemblage_electronique`, `textile_confection`

### Besoin: Démonstration client secteur services
→ `garage_automobile`, `centre_appels`, `laboratoire_analyses`

### Besoin: Benchmark performance algorithme
→ `assemblage_electronique_large` (15 tâches), `imprimerie_large` (16 tâches), `pharmacie_production` (11 tâches)

### Besoin: Test ressources partagées
→ `boulangerie` (chambre fermentation), `imprimerie_large` (tunnel séchage), `assemblage_electronique_large` (redondance)

### Besoin: Test graphe complexe
→ `construction_batiment`, `data_center_maintenance`, `edition_livre`

### Besoin: Test durées courtes (< 1 jour)
→ `centre_appels` (0.67j), `boulangerie` (1.5j)

### Besoin: Test projets longs
→ `construction_batiment` (51j), `edition_livre` (48j)

### Besoin: Test parallélisme fort
→ `construction_batiment` (T2 → T4, T5, T6 en parallèle)
→ `laboratoire_analyses` (T2 → T3, T4, T5 en parallèle)

### Besoin: Test urgence / criticité
→ `data_center_maintenance` (redondance, basculement)

## Distribution par secteur

```
Industrie manufacturière: 9 fichiers (41%)
  └─ Électronique: 2, Mécanique: 2, Textile: 1, Agro: 1, Boulangerie: 1, Imprimerie: 2, Pharmacie: 1

Services: 6 fichiers (27%)
  └─ Maintenance: 2, Support: 1, Garage: 1, Restauration: 1, Laboratoire: 1

BTP: 1 fichier (5%)

Formation/Édition: 2 fichiers (9%)

Santé: 1 fichier (5%)

Logistique: 1 fichier (5%)

Démo: 2 fichiers (9%)
```

## Propriétés des graphes

### Graphes linéaires (chaîne simple)
`exemple_minimal`, `atelier_mecanique_petit`, `pharmacie_production`, `boulangerie`, `centre_appels`, `hopital`, `restauration`

**Propriété**: Aucun parallélisme possible, makespan = somme des durées

### Graphes avec fork (1 → N)
`atelier_mecanique_moyen` (T2 → T3a, T3b), `construction_batiment` (T2 → T4, T5), `laboratoire_analyses` (T2 → T3, T4, T5)

**Propriété**: Parallélisme limité, réduction makespan possible

### Graphes avec join (N → 1)
`data_center_maintenance` (T5 + T6 → T7), `garage_automobile` (T5 + T6 → T7), `edition_livre` (T6 + T7 → T8)

**Propriété**: Synchronisation requise, goulot d'étranglement

### Graphes complexes (fork + join multiples)
`assemblage_electronique_large`, `imprimerie_large`, `construction_batiment`

**Propriété**: Nombreux chemins critiques potentiels

## Notes de compatibilité

Tous les fichiers respectent le schéma:
```json
{
  "taches": [...],        // Obligatoire, min 1
  "ressources": [...],    // Obligatoire, min 1
  "contraintes": [...],   // Obligatoire, min 1 precedence + 1 competence_requise par tâche
  "objectifs": [...]      // Obligatoire, actuellement toujours minimiser_makespan
}
```

Contraintes utilisées:
- ✅ `precedence` (avant, apres)
- ✅ `competence_requise` (tache, competence)
- ❌ `echeance` (non utilisé dans format_simplifie)
- ❌ `contrainte_capacite` (non utilisé dans format_simplifie)
- ❌ `contrainte_incompatibilite` (non utilisé dans format_simplifie)

Pour utiliser les contraintes avancées, convertir vers le format TRCO complet.
