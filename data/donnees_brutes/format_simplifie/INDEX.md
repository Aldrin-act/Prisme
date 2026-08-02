# Index des Données Format Simplifié

## Vue d'ensemble

Le répertoire `format_simplifie` contient **22 scénarios réalistes** couvrant 8 secteurs d'activité différents, du cas trivial (2 tâches) aux instances complexes (16 tâches).

**Format**: JSON avec structure `taches` / `ressources` / `contraintes` / `objectifs`
**Validation**: 100% des fichiers validés par `scripts/valider_format_simplifie.py`
**Total contraintes**: 288 contraintes (précédence + compétences)

## Documentation

| Fichier | Description |
|---------|-------------|
| **README.md** | Guide complet du format, structure, conversion TRCO, cas d'usage |
| **CATALOGUE.md** | Tableau comparatif de tous les scénarios avec filtres par besoin |
| **INDEX.md** | Ce fichier - point d'entrée de la documentation |

## Démarrage rapide

### Pour un test simple
```bash
# Charger le cas minimal
cat format_simplifie/exemple_minimal.json
```

### Pour une démonstration
```bash
# Boulangerie: visuel, compréhensible
cat format_simplifie/boulangerie.json

# Centre d'appels: secteur services
cat format_simplifie/centre_appels.json
```

### Pour du benchmarking
```bash
# Instance large (15 tâches)
cat format_simplifie/assemblage_electronique_large.json

# Instance très large (16 tâches)
cat format_simplifie/imprimerie_large.json
```

## Validation

```bash
# Valider tous les fichiers
uv run python -m scripts.valider_format_simplifie

# Sortie attendue:
# OK: Fichiers valides: 22/22
# Tous les fichiers sont valides!
```

## Structure type

Chaque fichier JSON respecte ce schéma:

```json
{
  "taches": [
    {
      "id": "T1",
      "nom": "Nom descriptif",
      "duree_estimee_jours": 2.5
    }
  ],
  "ressources": [
    {
      "id": "R1",
      "nom": "Nom ressource",
      "competences": ["comp1", "comp2"]
    }
  ],
  "contraintes": [
    {
      "type": "precedence",
      "avant": "T1",
      "apres": "T2"
    },
    {
      "type": "competence_requise",
      "tache": "T1",
      "competence": "comp1"
    }
  ],
  "objectifs": [
    {
      "type": "minimiser_makespan"
    }
  ]
}
```

## Sélection par critère

### Par secteur
- **Industrie** (9 fichiers): assemblage_electronique*, atelier_mecanique*, textile_confection, boulangerie, production_agroalimentaire, imprimerie*, pharmacie_production
- **Services** (6 fichiers): centre_appels, maintenance, data_center_maintenance, garage_automobile, laboratoire_analyses, restauration
- **BTP** (1 fichier): construction_batiment
- **Formation/Édition** (2 fichiers): formation_professionnelle, edition_livre
- **Santé** (1 fichier): hopital
- **Logistique** (1 fichier): logistique
- **Démo** (2 fichiers): exemple_minimal, atelier_mecanique_petit

### Par taille (nombre de tâches)
- **Petit** (2-5 tâches): exemple_minimal, atelier_mecanique_petit, hopital, imprimerie_petit, restauration, logistique, maintenance, assemblage_electronique, production_agroalimentaire
- **Moyen** (6-10 tâches): atelier_mecanique_moyen, boulangerie, centre_appels, textile_confection, formation_professionnelle, laboratoire_analyses, garage_automobile, construction_batiment
- **Grand** (11+ tâches): pharmacie_production (11), data_center_maintenance (12), edition_livre (12), assemblage_electronique_large (15), imprimerie_large (16)

### Par complexité du graphe
- **Linéaire**: exemple_minimal, atelier_mecanique_petit, boulangerie, centre_appels, pharmacie_production
- **Avec branches**: atelier_mecanique_moyen, assemblage_electronique, garage_automobile, laboratoire_analyses
- **Complexe**: construction_batiment, assemblage_electronique_large, imprimerie_large, edition_livre, data_center_maintenance

### Par durée du projet
- **< 1 jour**: centre_appels (0.67j)
- **1-5 jours**: boulangerie (1.5j), textile_confection (3j), restauration (3j), atelier_mecanique_petit (5j), garage_automobile (5.5j), logistique (5j)
- **5-15 jours**: assemblage_electronique (6.3j), assemblage_electronique_large (6.8j), laboratoire_analyses (6.6j), maintenance (7j), atelier_mecanique_moyen (8j), production_agroalimentaire (9j), imprimerie_large (9j), formation_professionnelle (10.3j), pharmacie_production (14.6j)
- **> 15 jours**: construction_batiment (51j), edition_livre (48j)

## Propriétés garanties

Tous les fichiers ont été validés pour:

✅ **Schéma complet**: taches, ressources, contraintes, objectifs présents
✅ **IDs uniques**: Pas de doublons dans les identifiants
✅ **Références valides**: Toutes les contraintes référencent des tâches/ressources existantes
✅ **Compétences cohérentes**: Chaque compétence requise existe dans au moins une ressource
✅ **Durées positives**: Toutes les durées sont > 0
✅ **Graphe acyclique**: Aucun cycle dans les précédences

## Statistiques

| Métrique | Min | Médiane | Max | Total |
|----------|-----|---------|-----|-------|
| Tâches | 2 | 6.5 | 16 | 166 |
| Ressources | 1 | 5 | 13 | 122 |
| Contraintes | 3 | 11 | 31 | 288 |

**Distribution des contraintes:**
- Précédence: ~50%
- Compétence requise: ~50%

## Utilisation dans PRISME

### Conversion vers TRCO
Les fichiers de ce répertoire nécessitent une conversion légère avant utilisation dans PRISME:

1. Dériver `compatibilite_ressource_tache` depuis `competence_requise`
2. Extraire les durées vers les contraintes de compatibilité
3. Ajouter les métadonnées (priorité, statut, type_ressource)

Voir `adapters/competence_derivation.py` pour la logique.

### Intégration API
```python
# Via l'adaptateur JSON import
from adapters.json_import.adapter import AdapterJSON

with open("format_simplifie/boulangerie.json") as f:
    instance_trco = AdapterJSON().adapter(json.load(f))
```

## Extension future

Pour ajouter un nouveau scénario:

1. Créer le fichier JSON selon le schéma
2. Valider: `uv run python -m scripts.valider_format_simplifie`
3. Mettre à jour CATALOGUE.md avec les caractéristiques
4. Ajouter dans la section appropriée du README

**Contraintes actuellement non utilisées** (disponibles dans format TRCO complet):
- `echeance`: deadline sur tâche
- `contrainte_capacite`: ressource multi-tâches simultanées
- `contrainte_incompatibilite`: exclusion mutuelle tâches/ressources

## Références croisées

- Format ERP: `../json_erp/README.md` - Format propriétaire avec translator
- Format CSV: `../csv/README.md` - Import tableur simplifié
- Format TRCO: `../../instances_trco/README.md` - Format canonique complet
- Script de validation: `../../../scripts/valider_format_simplifie.py`

---

**Dernière mise à jour**: 2026-08-02
**Version**: 1.0
**Contributeurs**: Développement initial pour PRISME PFE
