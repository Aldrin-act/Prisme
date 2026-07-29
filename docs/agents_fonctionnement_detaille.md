# Fonctionnement Détaillé des 8 Agents PRISME

Ce document explique le rôle, l'input, l'output et le fonctionnement de chaque agent du pipeline multi-agents (`generation/graph.py`, StateGraph LangGraph — Étape 6).

---

## 🎯 Vue d'Ensemble

Le pipeline multi-agents est une **chaîne de responsabilité** où chaque agent a un rôle précis. Pas d'Orchestrateur : il ne faisait que produire un plan JSON jamais lu par personne, l'ordre d'exécution ci-dessous a toujours été câblé en Python (`_construire_graphe`), jamais décidé dynamiquement par sa réponse — le fichier a été supprimé.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     PIPELINE MULTI-AGENTS (8 agents)                 │
└─────────────────────────────────────────────────────────────────────┘

Instance T-R-C-O  ──┐
                    │
                    ▼
    ┌───────────────────────────┐
    │ 1. ANALYSTE               │  Analyse le problème (tâches, ressources, contraintes)
    │    Durée : ~10s           │
    └───────────┬───────────────┘
                │ Spécification détaillée
                ▼
    ┌───────────────────────────┐
    │ 2. BENCHMARKER            │  Choisit l'algorithme (cp_sat, genetic, aco, ...)
    │    Durée : variable       │
    └───────────┬───────────────┘
                │ Algorithme + paramètres
                ▼
    ┌───────────────────────────┐
    │ 3. ARCHITECTE             │  Conçoit le modèle (variables, contraintes)
    │    Durée : ~15s           │
    └───────────┬───────────────┘
                │ Plan technique (architecture)
                ▼
    ┌───────────────────────────┐
    │ 4. DÉVELOPPEUR            │  Génère le code Python + OR-Tools
    │    Durée : ~21s           │
    └───────────┬───────────────┘
                │ Code source (~100-200 lignes)
                ▼
    ┌───────────────────────────┐
    │ 5. TESTEUR                │  Génère les tests unitaires
    │    Durée : ~17s           │
    └───────────┬───────────────┘
                │ Code candidat + tests
                ▼
    ┌─────────────────────────────────────────────────────────────┐
    │ BOUCLE DE RÉPARATION BORNÉE (max 10 tentatives)              │
    │                                                               │
    │  6. REVIEWER relit le code                                   │
    │      │ Rejeté ──────────► 7. DEBUGGER corrige, retour Reviewer│
    │      │ Approuvé                                              │
    │      ▼                                                       │
    │  VALIDATION (statique → exécution → cascade)                 │
    │      │ Échec ────────────► 7. DEBUGGER corrige, retour Reviewer│
    │      │ Succès                                                │
    └──────┼────────────────────────────────────────────────────────┘
           │                (tentatives épuisées → échec honnête, STOP)
           ▼
    ┌───────────────────────────┐
    │ 8. DOCUMENTATION          │  Best-effort, ne fait jamais échouer un solveur validé
    └───────────┬───────────────┘
                ▼
           RÉSULTAT FINAL
```

Pas d'Optimiseur non plus dans ce pipeline : agent retiré (réponse JSON trop fragile pour embarquer du code Python complet). `generation/agents/optimiseur.py` existe toujours mais n'est plus appelé — orphelin.

---

## 📋 Détail Agent par Agent

### 1️⃣ ANALYSTE

**Rôle** : Analyser le problème en profondeur (tâches, ressources, contraintes).

**Input** :
- Instance T-R-C-O

**Prompt** :
```
Analyse cette instance TRCO. Liste :
- Les tâches (IDs, dépendances)
- Les ressources (IDs, types)
- Les contraintes (précédence, compatibilité ressource-tâche)
- Les objectifs (minimiser makespan)

Produis une spécification détaillée.
```

**Output** : `Specification`
- Texte structuré décrivant :
  - Nombre de tâches, jobs
  - Ressources disponibles
  - Contraintes à respecter
  - Objectif
- Exemple :
  ```
  Spécification :
  - 12 tâches réparties en 4 jobs
  - 5 ressources (3 machines, 2 opérateurs)
  - Contraintes de précédence : tâche_2 après tâche_1
  - Compatibilité : tâche_1 peut utiliser ressource_A (5min) ou ressource_B (7min)
  - Objectif : Minimiser le makespan total
  ```

**Durée moyenne** : ~10s

**Fichier** : `generation/agents/analyste.py`

---

### 2️⃣ BENCHMARKER

**Rôle** : Choisir l'algorithme le mieux adapté à l'instance — toujours appelé, avant l'Architecte.

**Input** :
- Instance T-R-C-O (ou une petite instance d'exemple par défaut si aucune n'est fournie)

**Output** : `Recommandation`
- Algorithme choisi (`cp_sat` — seul traité comme *exact* — ou une heuristique : `genetic`/`aco`/`tabu_search`/`simulated_annealing`/`dispatching`/`greedy_local`, pour les très grandes instances)
- Justification + paramètres suggérés (ex. `limite_temps_s`, `population_size`...)

**Fichier** : `generation/agents/benchmarker.py`

**Note** : détermine aussi la tolérance de la cascade de validation qui suit (§5 — un algorithme heuristique n'est pas comparé au strict optimum du banc synthétique comme `cp_sat`).

---

### 3️⃣ ARCHITECTE

**Rôle** : Concevoir l'architecture du modèle CP-SAT.

**Input** :
- Spécification (output de l'Analyste)

**Prompt** :
```
À partir de cette spécification, conçois l'architecture du modèle OR-Tools :
- Quelles variables (start_times, durations, assigned_resources) ?
- Quelles contraintes (precedence, no_overlap, compatibility) ?
- Comment modéliser l'objectif (makespan) ?
```

**Output** : `PlanTechnique`
- Architecture détaillée :
  - Variables à créer
  - Contraintes à ajouter
  - Objectif à minimiser
- Exemple :
  ```
  Variables :
  - start[t] : IntVar(0, 1000) pour chaque tâche t
  - resource[t] : IntVar(ressources compatibles) pour chaque tâche t
  - makespan : IntVar(0, 1000)

  Contraintes :
  - Précédence : start[t2] >= start[t1] + duration[t1]
  - No-overlap : si 2 tâches sur même ressource → AddNoOverlap(intervals)
  - Makespan : makespan >= start[t] + duration[t] pour tout t

  Objectif :
  - Minimize(makespan)
  ```

**Durée moyenne** : ~15s

**Fichier** : `generation/agents/architecte.py`

---

### 4️⃣ DÉVELOPPEUR (Générateur)

**Rôle** : Générer le code Python implémentant le modèle CP-SAT.

**Input** :
- Plan technique (output de l'Architecte)

**Prompt** :
```
Génère le code Python complet d'un solveur OR-Tools CP-SAT qui :
- Prend en entrée une InstanceTRCO
- Retourne un Planning ou None
- Utilise la signature : def resoudre(instance: InstanceTRCO) -> Planning | None
- Respecte l'architecture décrite dans le plan technique
```

**Output** : `CodeGenere`
- Code source Python (~100-200 lignes)
- Imports : `from ortools.sat.python import cp_model`, `from dsl.schema import *`
- Fonction `resoudre(instance)` implémentée
- Exemple (extrait) :
  ```python
  from ortools.sat.python import cp_model
  from dsl.schema.instance import InstanceTRCO
  from dsl.schema.planning import Planning, OperationPlanifiee

  def resoudre(instance: InstanceTRCO) -> Planning | None:
      model = cp_model.CpModel()
      
      # Variables
      start_times = {}
      for tache in instance.taches:
          start_times[tache.id] = model.NewIntVar(0, 1000, f"start_{tache.id}")
      
      # Contraintes de précédence
      for contrainte in instance.contraintes:
          if contrainte.type == "precedence":
              # ...
      
      # Résolution
      solver = cp_model.CpSolver()
      status = solver.Solve(model)
      
      if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
          return Planning(operations=[...])
      return None
  ```

**Durée moyenne** : ~21s (agent le plus lent du pipeline)

**Fichier** : `generation/agents/generateur.py`

---

### 5️⃣ TESTEUR

**Rôle** : Générer des tests unitaires pour le code.

**Input** :
- Code source (output du Développeur)

**Prompt** :
```
Génère des tests pytest pour ce solveur :
- Test avec instance vide
- Test avec une tâche simple
- Test avec précédence
- Test que le Planning retourné est valide
```

**Output** : `CodeTests`
- Code pytest (~50-100 lignes)
- Exemple :
  ```python
  import pytest
  from dsl.schema import *
  
  def test_instance_vide():
      instance = InstanceTRCO(taches=[], ressources=[], contraintes=[], objectifs=[])
      from solveur import resoudre
      planning = resoudre(instance)
      assert planning is not None
      assert len(planning.operations) == 0
  
  def test_une_tache_simple():
      # ...
  ```

**Durée moyenne** : ~17s

**Fichier** : `generation/agents/testeur.py`

**Note** : Ces tests ne sont **jamais exécutés** par le pipeline. Seule la validation cascade fait autorité. Les tests sont un livrable documentaire.

---

### 6️⃣ REVIEWER

**Rôle** : Relire le code et détecter les bugs potentiels.

**Input** :
- Code source (output du Développeur)

**Prompt** :
```
Relis ce code solveur OR-Tools. Détecte les bugs potentiels :
- Variables mal nommées
- Contraintes manquantes
- Utilisation incorrecte de l'API OR-Tools
- Incompatibilité avec le DSL (OperationPlanifiee, Planning)
- Erreurs de logique

Si le code est parfait : approuve.
Sinon : liste les bugs précisément.
```

**Output** : `ResultatRevue`
- `approuve: bool`
- `commentaires: str` (liste de bugs si rejeté)
- Exemple (approbation) :
  ```
  approuve = True
  commentaires = "Code propre, bien structuré, respect du DSL."
  ```
- Exemple (rejet) :
  ```
  approuve = False
  commentaires = """
  Bug 1 : Ligne 42, vous passez l'objet `tache` au lieu de `tache.id`
  Bug 2 : Ligne 87, le champ `fin` manque dans OperationPlanifiee
  Bug 3 : Contrainte de no-overlap non implémentée
  """
  ```

**Durée moyenne** : ~10s

**Fichier** : `generation/agents/reviewer.py`

**Point clé** : Si `approuve = True`, on passe direct à la validation. Si `False`, on passe au Debugger.

---

### 7️⃣ DEBUGGER (Conditionnel)

**Rôle** : Corriger les bugs identifiés par le Reviewer.

**Condition d'exécution** : Seulement si `revue.approuve == False`

**Input** :
- Code source bugué (output du Développeur)
- Commentaires du Reviewer (liste des bugs)

**Prompt** :
```
Le reviewer a détecté ces bugs dans le code :

{commentaires}

Corrige ces bugs et retourne le code corrigé complet.
```

**Output** : `CodeCorrige`
- Code source Python corrigé

**Durée moyenne** : ~15s

**Fichier** : `generation/agents/debugger.py`

**Note importante** : Le Debugger peut intervenir **jusqu'à 10 fois** (`MAX_TENTATIVES_REPARATION`, §6.6) — boucle bornée Reviewer ⇄ Debugger, pas un essai unique. Si les tentatives s'épuisent sans validation réussie, c'est un échec final honnête (jamais masqué).

---

### VALIDATION (pas un agent LLM, mais une fonction — appelée à chaque tentative de la boucle)

**Rôle** : Valider le code en 3 passes.

**Input** :
- Code source (du Développeur ou du Debugger)

**Pipeline de validation** :

1. **Validation statique** (`validation_statique.py`)
   - AST allowlist : vérifie imports autorisés (`ortools`, `dsl`, `collections`, `dataclasses`)
   - Rejette : `eval`, `exec`, `__import__`, `open`, dunders
   - Durée : ~0.01s

2. **Exécution** (`executer.py`)
   - `exec()` du code dans un namespace isolé
   - Récupère la fonction `resoudre`
   - Durée : ~0.1s

3. **Validation cascade** (`validation_engine/cascade.py`)
   - Faisabilité : toutes les instances de test
   - Optimalité : banc synthétique (ground truth)
   - Fidélité : reference_cases (comparaison partielle)
   - Durée : ~0.4s

**Output** : `_ResultatValidationComplete`
- `validation_statique: ResultatValidationStatique`
- `erreur_execution: str | None`
- `verdict_cascade: VerdictCascade | None`
- `reussi: bool` (True seulement si les 3 passes OK)

**Durée totale** : ~0.5s par tentative

**Fichier** : `generation/graph.py` (fonction `_valider_completement`)

**Point clé** : Appelée à chaque tentative de la boucle (jusqu'à 10 fois) — jamais sur du code d'Optimiseur, cet agent n'est plus dans le pipeline (voir ci-dessous).

---

### OPTIMISEUR — orphelin, plus appelé par le pipeline

`generation/agents/optimiseur.py` existe toujours mais n'est plus invoqué
depuis `generation/graph.py` : sa réponse JSON devait embarquer un code
Python complet comme valeur de chaîne, un format que les LLM échouent
régulièrement à échapper correctement — et l'enjeu n'en valait pas la
fragilité, le code est déjà validé par la cascade à ce stade.

---

### 8️⃣ DOCUMENTATION (best-effort, après re-validation finale du code)

**Rôle** : Générer une documentation Markdown du code final.

**Input** :
- Code source final (validé, potentiellement optimisé)

**Prompt** :
```
Génère une documentation Markdown pour ce solveur :
- Description générale
- Fonction principale (signature, paramètres, retour)
- Algorithme (étapes)
- Exemple d'utilisation
```

**Output** : `Documentation`
- Markdown (~500-1000 mots)
- Exemple :
  ````markdown
  # Solveur FJSP OR-Tools

  ## Description
  Ce solveur résout le problème FJSP (Flexible Job-Shop Scheduling Problem) 
  en utilisant OR-Tools CP-SAT.

  ## Fonction principale
  ```python
  def resoudre(instance: InstanceTRCO) -> Planning | None
  ```

  ## Algorithme
  1. Crée les variables `start_times` et `assigned_resources`
  2. Ajoute les contraintes de précédence
  3. Ajoute les contraintes de no-overlap
  4. Minimise le makespan
  5. Résout avec CP-SAT
  6. Construit le Planning de sortie

  ## Exemple
  ```python
  from dsl.schema import *
  instance = InstanceTRCO(...)
  planning = resoudre(instance)
  ```
  ````

**Durée moyenne** : ~8s

**Fichier** : `generation/agents/documentation.py`

---

## 🔄 Flux de Données Complet

```
Instance T-R-C-O
    │
    ├───► ANALYSTE ───► Spécification (str)
    │
    ├───► BENCHMARKER ───► Algorithme + paramètres
    │
    └───► ARCHITECTE ───► Plan technique (str)
              │
              ▼
         DÉVELOPPEUR ───► Code candidat
              │
              ▼
         TESTEUR ───► Tests pytest générés (jamais exécutés automatiquement)
              │
              ▼
    ┌─── BOUCLE (max 10 tentatives) ──────────────────────────────┐
    │                                                              │
    │   REVIEWER ───► Approuvé (bool) + Commentaires (str)        │
    │       │                                                      │
    │       ├─ REJETÉ ──► DEBUGGER ──► Code corrigé ──► retour Reviewer
    │       │                                                      │
    │       └─ APPROUVÉ ──► VALIDATION (statique → exécution → cascade)
    │                             │                                │
    │                             ├─ ÉCHEC ──► DEBUGGER ──► retour Reviewer
    │                             └─ SUCCÈS ──► sort de la boucle  │
    └──────────────────────────────────────────────────────────────┘
              │ (tentatives épuisées → échec honnête, STOP)
              ▼ (succès)
         DOCUMENTATION (best-effort)
              │
              ▼
       RÉSULTAT FINAL
```

---

## 📊 Métriques Typiques

Sur une instance de **12 tâches, 5 ressources, 10 contraintes** :

| Agent | Durée (s) | Tokens Input | Tokens Output | Coût ($) |
|-------|-----------|--------------|---------------|----------|
| Analyste | 10.6 | 600 | 300 | 0.038 |
| Architecte | 14.9 | 900 | 400 | 0.051 |
| Développeur | 21.0 | 1200 | 800 | 0.075 |
| Testeur | 17.5 | 1000 | 500 | 0.058 |
| Reviewer | 9.8 | 1100 | 150 | 0.042 |
| Debugger | 15.0 | 1300 | 700 | 0.068 |
| Validation | 0.5 | 0 | 0 | 0.000 |
| Optimiseur | 12.0 | 1000 | 600 | 0.055 |
| Documentation | 8.0 | 900 | 400 | 0.048 |
| **TOTAL** | **95.3s** | **9,800** | **4,050** | **$0.48** |

*Estimation basée sur Mistral Large @ $3 input / $15 output par 1M tokens*

---

## 🎯 Points Clés du Pipeline

### ✅ Avantages Multi-Agents

1. **Séparation des préoccupations** : Chaque agent a un rôle clair
2. **Qualité accrue** : Reviewer détecte 70-80% des bugs avant exécution
3. **Correction automatique** : Debugger corrige les bugs identifiés
4. **Optimisation sûre** : L'optimiseur peut améliorer sans risquer la validité
5. **Documentation automatique** : Livrable prêt à l'emploi

### ⚠️ Limites

1. **Coût** : ~10x plus cher que le mode simple (1 agent)
2. **Durée** : ~3-5x plus lent (95s vs 30s)
3. **Pas de boucle** : Le Debugger n'intervient qu'une fois (§6.6, Étape 6 non construite)
4. **Tests non exécutés** : Le Testeur génère du code pytest mais il n'est jamais lancé

### 🔒 Garanties de Sécurité

1. **Validation statique** : AST allowlist AVANT exec()
2. **Sandbox** : Exécution dans conteneur Docker (production)
3. **Cascade obligatoire** : Jamais de code accepté sans validation cascade
4. **Double validation** : Code optimisé re-validé (l'agent n'est pas cru sur parole)

---

## 🚀 Cas d'Usage Recommandés

| Situation | Mode Recommandé |
|-----------|-----------------|
| Prototype rapide | Simple (1 agent) |
| Production critique | **Multi-agents** |
| Instance complexe (>20 tâches) | **Multi-agents** |
| Budget limité | Simple |
| Maximum de qualité | **Multi-agents** |
| Debugging d'échec | **Multi-agents** (logs détaillés) |

---

## 🔧 Configuration

Provider recommandé : **Anthropic Claude > Mistral Large > OpenAI GPT-4**

Fichier `.env` :
```bash
PRISME_LLM_PROVIDER=anthropic  # ou mistral, openai
ANTHROPIC_API_KEY=sk-ant-...
```

Script de génération :
```bash
uv run python scripts/generer_solveur.py        # Multi-agents (défaut)
uv run python scripts/generer_avec_metriques.py # Avec métriques Grafana
```

---

## 📚 Fichiers Liés

- **Pipeline + boucle** : `generation/graph.py` (StateGraph LangGraph, Étape 6)
- **Agents** : `generation/agents/{analyste,benchmarker,architecte,generateur,testeur,reviewer,debugger,documentation}.py` (`optimiseur.py` orphelin)
- **Client LLM** : `generation/agents/client_llm.py`
- **Validation** : `generation/validation_statique.py`, `generation/executer.py`, `validation_engine/cascade.py`
- **Script monitoring** : `scripts/generer_avec_metriques.py`
- **Dashboard Grafana** : `monitoring/grafana/dashboards/json/prisme-agents.json`
