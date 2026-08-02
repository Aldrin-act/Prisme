# Migration vers le Nouveau Format CSV

## 📋 Résumé

Les fichiers CSV ont été **migrés avec succès** de l'ancien format (2 fichiers) vers le nouveau format (3 fichiers) compatible avec l'adaptateur `csv_import`.

**Date de migration** : 2026-08-02

## 🔄 Changements effectués

### Ancien format (OBSOLÈTE)

```
secteur/
├── <nom>_operations.csv  (code_operation, duree_jours, poste_id, operation_precedente)
└── <nom>_postes.csv      (code_poste)
```

**Problèmes** :
- ❌ Non compatible avec l'adaptateur officiel `csv_import`
- ❌ Noms de colonnes non standardisés
- ❌ Pas de support natif pour les compétences
- ❌ Contraintes implicites (opération → poste fixe)

### Nouveau format (ACTUEL)

```
secteur/
├── taches.csv        (id, nom, duree_estimee_jours)
├── ressources.csv    (id, nom, competences)
└── contraintes.csv   (type, tache_avant, tache_apres, tache, ressource, duree_jours, competence)
```

**Avantages** :
- ✅ Compatible avec `adapters/csv_import/traducteur.py`
- ✅ Colonnes standardisées et documentées
- ✅ Support complet des compétences
- ✅ Dérivation automatique des compatibilités par compétence
- ✅ 3 types de contraintes (precedence, compatibilite_ressource_tache, competence_requise)

## 📊 Fichiers convertis

| Secteur | Ancien | Nouveau | Statut |
|---------|--------|---------|--------|
| **Atelier Mécanique** | 2 CSV | 3 CSV | ✅ Converti |
| **Assemblage Électronique** | 2 CSV | 3 CSV | ✅ Converti |
| **Imprimerie** | 2 CSV | 3 CSV | ✅ Converti |
| **Production Agroalimentaire** | 2 CSV | 3 CSV | ✅ Converti |
| **Centre d'Appels** | 2 CSV | 3 CSV | ✅ Converti |
| **Maintenance Industrielle** | 2 CSV | 3 CSV | ✅ Converti |
| **Informatique (JIRA)** | 1 CSV | 1 CSV | ➖ Inchangé (format spécial) |

**Total** : 6 secteurs convertis, 18 fichiers CSV créés (3 × 6)

## 🔧 Mapping des colonnes

### taches.csv

| Ancien | Nouveau | Notes |
|--------|---------|-------|
| `code_operation` | `id` | Identifiant unique |
| (nom déduit du code) | `nom` | Nom descriptif |
| `duree_jours` | `duree_estimee_jours` | Durée si dérivation par compétence |

### ressources.csv

| Ancien | Nouveau | Notes |
|--------|---------|-------|
| `code_poste` | `id` | Identifiant unique |
| (nom déduit du code) | `nom` | Nom descriptif |
| (absent) | `competences` | **NOUVEAU** : compétences séparées par `;` |

### contraintes.csv

| Ancien | Nouveau | Notes |
|--------|---------|-------|
| `operation_precedente` + `code_operation` | `type=precedence` + `tache_avant` + `tache_apres` | Contrainte explicite |
| `poste_id` + `duree_jours` | `type=compatibilite_ressource_tache` + `tache` + `ressource` + `duree_jours` | Affectation |
| (absent) | `type=competence_requise` + `tache` + `competence` | **NOUVEAU** : compétences |

## 📖 Exemple de conversion

### Avant

**operations.csv** :
```csv
code_operation,duree_jours,poste_id,operation_precedente
SOUDURE_001,2,POSTE_MIG,PLIAGE_001
```

**postes.csv** :
```csv
code_poste
POSTE_MIG
```

### Après

**taches.csv** :
```csv
id,nom,duree_estimee_jours
SOUDURE_001,Soudure,2
```

**ressources.csv** :
```csv
id,nom,competences
POSTE_MIG,Poste soudure MIG,soudure
```

**contraintes.csv** :
```csv
type,tache_avant,tache_apres,tache,ressource,duree_jours,competence
precedence,PLIAGE_001,SOUDURE_001,,,,
compatibilite_ressource_tache,,,SOUDURE_001,POSTE_MIG,2,
```

## 🛠️ Script de conversion

Le script `scripts/convertir_csv_ancien_vers_nouveau_format.py` a été utilisé pour automatiser la conversion.

**Fonctionnalités** :
- Lecture des anciens fichiers `*_operations.csv` et `*_postes.csv`
- Extraction des tâches, ressources et contraintes
- Déduction des compétences depuis les codes de poste
- Création des 3 nouveaux fichiers CSV
- Suppression des anciens fichiers

**Usage** :
```bash
uv run python -m scripts.convertir_csv_ancien_vers_nouveau_format
```

## ✅ Validation post-migration

### Tests automatiques

```bash
# Import via l'adaptateur CSV
from adapters.csv_import.traducteur import traduire

with open("taches.csv", "rb") as f_t, \
     open("ressources.csv", "rb") as f_r, \
     open("contraintes.csv", "rb") as f_c:
    instance = traduire(f_t.read(), f_r.read(), f_c.read())

# ✅ Aucune erreur = format valide
```

### Vérifications manuelles

- ✅ Colonnes requises présentes
- ✅ Types de contraintes corrects
- ✅ Références tache/ressource valides
- ✅ Durées numériques
- ✅ Compétences déduites correctement

## 📚 Documentation mise à jour

| Fichier | Statut | Contenu |
|---------|--------|---------|
| `README.md` | ✅ Mis à jour | Format complet, exemples, dérivation compétences |
| `INDEX.md` | ⚠️ À mettre à jour | Navigation rapide |
| `ORGANISATION.md` | ⚠️ À mettre à jour | Structure détaillée |
| `industrie_manufacturiere/README.md` | ⚠️ À mettre à jour | Secteurs industriels |
| `services/README.md` | ⚠️ À mettre à jour | Secteurs services |
| `informatique/README.md` | ✅ Inchangé | Format JIRA spécial |

## 🔄 Migration des projets existants

Si vous avez des données au format ancien, utilisez le script de conversion :

```bash
# Placer les anciens fichiers dans un dossier temporaire
mkdir -p ancien_format/
cp <secteur>_operations.csv ancien_format/
cp <secteur>_postes.csv ancien_format/

# Adapter le script pour pointer vers ce dossier
# Exécuter la conversion
uv run python -m scripts.convertir_csv_ancien_vers_nouveau_format

# Résultat : taches.csv, ressources.csv, contraintes.csv
```

## ⚠️ Compatibilité ascendante

**IMPORTANT** : L'ancien format **n'est plus supporté** par l'adaptateur `csv_import`.

Si vous avez du code qui charge les anciens fichiers :
```python
# OBSOLÈTE - Ne fonctionne plus
adapter.adapter_depuis_fichiers(
    "secteur_operations.csv",
    "secteur_postes.csv"
)
```

Migrez vers :
```python
# NOUVEAU - Format actuel
traduire(taches_csv, ressources_csv, contraintes_csv)
```

## 🎯 Prochaines étapes

- [ ] Mettre à jour INDEX.md avec le nouveau format
- [ ] Mettre à jour ORGANISATION.md avec les nouvelles statistiques
- [ ] Mettre à jour les README sectoriels
- [ ] Créer des exemples d'utilisation dans la documentation
- [ ] Ajouter des tests unitaires pour le nouveau format

## 📞 Support

En cas de problème avec le nouveau format :
1. Vérifier que les 3 fichiers CSV sont présents
2. Vérifier les noms de colonnes (sensible à la casse)
3. Vérifier les types de contraintes (precedence, compatibilite_ressource_tache, competence_requise)
4. Consulter `adapters/csv_import/traducteur.py` pour les colonnes requises

---

**Migration effectuée le** : 2026-08-02
**Script utilisé** : `scripts/convertir_csv_ancien_vers_nouveau_format.py`
**Secteurs migrés** : 6/6 (100%)
**Statut** : ✅ **Terminé avec succès**
