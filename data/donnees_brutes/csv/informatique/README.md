# Informatique - Données CSV

Ce répertoire contient un jeu de données spécifique au secteur informatique, simulant un export JIRA.

## Fichier disponible

### `informatique_jira_export.csv`

**Secteur**: Développement logiciel / Gestion de projet

**Source simulée**: Export de tickets depuis un système de suivi (JIRA, Redmine, Azure DevOps, etc.)

**Caractéristiques**:
- Format enrichi avec métadonnées projet
- Colonnes additionnelles (priorité, assigné, statut, labels)
- Workflow typique : Backlog → To Do → In Progress → In Review → Done
- Durée estimée en jours/homme

## Structure du fichier

Contrairement aux autres secteurs qui utilisent 2 fichiers (`operations` + `postes`),
ce fichier suit le **format d'export JIRA** avec toutes les informations dans un seul CSV.

### Colonnes

| Colonne | Type | Description | Exemple |
|---------|------|-------------|---------|
| `issue_key` | String | Identifiant unique du ticket | PROJ-123 |
| `summary` | String | Titre/résumé de la tâche | "Implémenter l'authentification" |
| `issue_type` | String | Type (Story, Task, Bug, Epic) | Story |
| `status` | String | Statut actuel | In Progress |
| `priority` | String | Priorité (High, Medium, Low) | High |
| `assignee` | String | Personne assignée | john.doe |
| `estimate_days` | Float | Estimation en jours/homme | 3.0 |
| `epic` | String | Epic parent (optionnel) | PROJ-100 |
| `labels` | String | Labels séparés par `;` | backend;security |
| `dependencies` | String | Clés des tickets bloquants (séparées par `;`) | PROJ-122;PROJ-118 |

## Différences avec le format standard

| Aspect | Format Standard | Format JIRA |
|--------|-----------------|-------------|
| **Fichiers** | 2 (operations + postes) | 1 (tout-en-un) |
| **Ressources** | Postes/Machines | Personnes (assignees) |
| **Précédences** | Colonne `operation_precedente` | Colonne `dependencies` |
| **Métadonnées** | Minimales | Riches (priorité, statut, labels) |
| **Workflow** | Linéaire | Agile (statuts multiples) |

## Exemple de contenu

```csv
issue_key,summary,issue_type,status,priority,assignee,estimate_days,epic,labels,dependencies
PROJ-101,Analyse des besoins,Task,Done,High,alice.martin,2,PROJ-100,analyse;specs,
PROJ-102,Maquettes UI,Task,Done,Medium,bob.dupont,3,PROJ-100,frontend;design,PROJ-101
PROJ-103,API REST authentification,Story,In Progress,High,charlie.bernard,5,PROJ-100,backend;security,PROJ-101
PROJ-104,Tests unitaires API,Task,To Do,High,charlie.bernard,2,PROJ-100,backend;tests,PROJ-103
PROJ-105,Intégration frontend,Story,To Do,Medium,bob.dupont,4,PROJ-100,frontend;integration,PROJ-102;PROJ-103
```

## Utilisation

### Import avec l'adaptateur JIRA

```python
from adapters.csv_import.adapter_jira import AdapterJIRA

adapter = AdapterJIRA()

# Import depuis le CSV JIRA
instance_trco = adapter.adapter_depuis_jira_csv(
    "informatique/informatique_jira_export.csv"
)
```

### Mapping vers TRCO

Le mapping est effectué comme suit:

```python
# Tâches
issue_key → Tache.id
summary → Tache.nom
estimate_days → durée

# Ressources
assignee → Ressource.id
assignee → Ressource.nom

# Contraintes
dependencies → ContraintePrecedence
  (chaque dépendance devient une contrainte avant/après)

# Métadonnées (si supportées)
priority → Tache.priorite
status → Tache.statut
labels → Tache.tags
```

## Cas d'usage

### Tests

✅ **Import export JIRA** - Validation du parsing format JIRA
✅ **Dépendances multiples** - Un ticket peut avoir plusieurs bloquants
✅ **Affectation personnes** - Ressources humaines nommées
✅ **Métadonnées riches** - Priorité, statut, labels

### Démonstrations

✅ **Projet agile** - Workflow Scrum/Kanban
✅ **Gestion sprint** - Planification d'itération
✅ **Suivi charge** - Répartition par développeur

## Particularités

### Dépendances multiples

Contrairement au format standard où une opération a **au plus 1 précédente**,
le format JIRA permet **plusieurs dépendances** :

```csv
issue_key,dependencies
PROJ-105,PROJ-102;PROJ-103;PROJ-104
```

→ `PROJ-105` nécessite que `PROJ-102`, `PROJ-103` **ET** `PROJ-104` soient terminés

### Ressources nommées

Les ressources sont des **personnes** avec des noms lisibles:
- `alice.martin`
- `bob.dupont`
- `charlie.bernard`

→ Plus naturel pour les équipes projet

### Epics et hiérarchie

Le champ `epic` permet de regrouper les tickets par fonctionnalité:

```csv
issue_key,epic,summary
PROJ-100,,Epic: Authentification utilisateur
PROJ-101,PROJ-100,Analyse besoins auth
PROJ-102,PROJ-100,Maquettes écrans login
PROJ-103,PROJ-100,API REST auth
```

→ Permet de filtrer par epic si besoin

## Workflow JIRA typique

Les statuts classiques dans un projet Scrum:

1. **Backlog** - Ticket créé, non priorisé
2. **To Do** - Priorisé, prêt pour le sprint
3. **In Progress** - En cours de développement
4. **In Review** - En revue de code
5. **Testing** - En phase de test QA
6. **Done** - Terminé et validé

**Note**: Le format CSV ne capture que l'état actuel, pas l'historique des transitions.

## Limitations

⚠️ **Pas de workflow complet** - Seul le statut actuel est exporté
⚠️ **Pas de dates** - Pas de date de début/fin réelle
⚠️ **Pas de sous-tâches** - Structure plate (epic → stories/tasks)
⚠️ **Estimations statiques** - Pas de suivi du temps passé réel

## Extension

### Ajout d'un nouveau projet

Pour ajouter un nouveau export JIRA:

1. Exporter depuis JIRA (CSV avec les colonnes ci-dessus)
2. Placer le fichier dans `informatique/`
3. S'assurer que les colonnes requises sont présentes
4. Valider avec l'adaptateur JIRA

### Colonnes optionnelles additionnelles

On peut enrichir le format avec:
- `reporter` - Créateur du ticket
- `created_date` - Date de création
- `due_date` - Date d'échéance
- `sprint` - Sprint assigné
- `story_points` - Complexité en points
- `time_spent_hours` - Temps passé réel

Ces colonnes additionnelles seront ignorées par l'adaptateur basique,
mais peuvent être exploitées par un adaptateur étendu.

## Comparaison avec format simplifié

| Aspect | CSV JIRA | Format Simplifié (JSON) |
|--------|----------|-------------------------|
| **Format** | CSV (1 fichier) | JSON (structure riche) |
| **Métadonnées** | Riches (priorité, statut) | Minimales |
| **Compétences** | ❌ Absentes | ✅ Supportées |
| **Dépendances** | Multiples (séparées `;`) | Simples (1 avant → 1 après) |
| **Validation** | ⚠️ Implicite | ✅ Schéma strict |
| **Cas d'usage** | Import JIRA | Tests variés |

## Recommandation

Utiliser le format JIRA CSV pour:
- ✅ Import depuis JIRA réel
- ✅ Prototypage rapide projet agile
- ✅ Démonstration workflow dev

Utiliser le format simplifié JSON pour:
- ✅ Tests avec compétences
- ✅ Validation stricte du schéma
- ✅ Scénarios industriels complexes

---

**Retour**: [../README.md](../README.md) - Documentation CSV générale
