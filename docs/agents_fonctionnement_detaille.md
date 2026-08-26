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
    │ 5. TESTEUR                │  Génère les tests pytest (exécutés pour de vrai, voir ci-dessous)
    │    Durée : ~17s           │
    └───────────┬───────────────┘
                │ Code candidat + tests
                ▼
    ┌─────────────────────────────────────────────────────────────┐
    │ BOUCLE DE RÉPARATION BORNÉE (max 10 tentatives, §6.6bis)     │
    │                                                               │
    │  TEST_SANDBOX : exécute pour de vrai le module pytest        │
    │  généré par le Testeur, dans le conteneur Docker éphémère    │
    │      │ Échec ─────────────────────► DEBUGGER corrige         │
    │      │ Succès                             │                  │
    │      ▼                                    │                  │
    │  VALIDATION (statique → exécution → cascade déterministe)    │
    │      │ Échec ─────────────────────► DEBUGGER corrige         │
    │      │ Succès                             │                  │
    │      │                     DEBUGGER ──► retour à TEST_SANDBOX│
    └──────┼────────────────────────────────────────────────────────┘
           │                (tentatives épuisées → échec honnête, STOP)
           ▼
    ┌───────────────────────────┐
    │ 6. DOCUMENTATION          │  Best-effort, ne fait jamais échouer un solveur validé
    └───────────┬───────────────┘
                ▼
           RÉSULTAT FINAL
```

Le **Reviewer** (revue de code par un second LLM) n'apparaît **pas** dans ce flux : présent dans le code
(`generation/agents/reviewer.py`, `_noeud_reviewer`/`_route_apres_reviewer` dans `generation/graph.py`) mais
jamais câblé dans `_construire_graphe` — son avis consultatif est devenu redondant une fois que
`test_sandbox` exécute réellement les tests du Testeur et que la cascade déterministe tranche derrière.
Réactivable en deux lignes si besoin (voir CLAUDE.md, Étape 6). Pas d'Optimiseur non plus : agent retiré
(réponse JSON trop fragile pour embarquer du code Python complet). `generation/agents/optimiseur.py` a
été supprimé, resté orphelin trop longtemps sans jamais être recâblé — contrairement à `reviewer.py`,
gardé intentionnellement pour une réactivation potentielle.

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

**Rôle** : Concevoir la structure interne du solveur — algorithme-agnostique : reçoit
`algorithme`/`parametres` du Benchmarker (`concevoir_modele(modele, analyse, algorithme="cp_sat",
parametres=None)`), et adapte son plan en conséquence (variables/contraintes CP-SAT pour un
algorithme exact, ou encodage de solution/opérateurs pour une heuristique génétique/ACO/tabu/recuit
simulé/dispatching). Prompt système réel : *« Tu es un architecte logiciel spécialisé en
optimisation combinatoire (CP-SAT/OR-Tools et métaheuristiques d'ordonnancement) »*.

**Input** :
- Spécification (output de l'Analyste) + algorithme et paramètres recommandés par le Benchmarker

**Output** : `ResultatConception` — champs volontairement génériques (pas « CP-SAT » en dur, car le
contenu peut décrire un algorithme alternatif) :
- `variables` : représentation de la solution (variables CP-SAT, ou encodage chromosomique pour un
  GA, structure de solution pour ACO/tabu...)
- `contraintes_modele` : contraintes métier à respecter dans le modèle
- `objectif` : objectif à optimiser
- `fonctions_internes` : fonctions internes éventuelles

Exemple pour `algorithme="cp_sat"` :
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

Pour `algorithme="genetic"` (ou une autre heuristique), le contenu décrit à la place l'encodage
chromosomique, les opérateurs de croisement/mutation, la fonction de fitness, etc. — la structure
`ResultatConception` reste la même, seul son contenu textuel change.

**Durée moyenne** : ~15s

**Fichier** : `generation/agents/architecte.py`

---

### 4️⃣ DÉVELOPPEUR (Générateur)

**Rôle** : Générer le code Python implémentant le plan de l'Architecte — algorithme-agnostique,
prompt système réel : *« Tu es un générateur de code Python expert en optimisation combinatoire »*
(`generation/agents/generateur.py`, pas de « CP-SAT » en dur). Le code produit importe
`ortools.sat.python.cp_model` seulement quand l'algorithme choisi par le Benchmarker est `cp_sat` ;
pour une heuristique, il implémente plutôt l'algorithme décrit par l'Architecte (boucle génétique,
ACO, tabu search...) sans dépendre d'OR-Tools.

**Input** :
- Plan technique (output de l'Architecte) + algorithme recommandé par le Benchmarker

**Output** : `CodeGenere`
- Code source Python (~100-200 lignes)
- Fonction `resoudre(instance: InstanceTRCO) -> Planning | None` implémentée, quel que soit
  l'algorithme
- Exemple pour `algorithme="cp_sat"` (extrait) :
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

**Note** : Contrairement à une version antérieure de ce document, ces tests **sont bien exécutés**
pour de vrai — voir TEST_SANDBOX ci-dessous (§6.6bis). Le Testeur ne fait que les *générer* ; c'est
`test_sandbox` qui les fait tourner dans le conteneur Docker éphémère à chaque tentative.

---

### TEST_SANDBOX (pas un agent LLM — exécution réelle, §6.6bis)

**Rôle** : Exécuter pour de vrai le module pytest généré par le Testeur, dans le même conteneur
Docker éphémère durci que celui utilisé en production (`sandbox/runner.py::executer_tests_dans_sandbox`)
— premier vrai filtre de chaque tentative, avant même la cascade déterministe.

**Input** : Code source candidat (du Développeur ou du Debugger) + module de tests (du Testeur)

**Comportement** : Un échec route directement vers le Debugger, sans passer par la validation
cascade — inutile de faire tourner une cascade sur un code dont on sait déjà, par exécution réelle,
qu'il ne passe pas ses propres tests. Si le sandbox lui-même est injoignable, ça ne bloque jamais le
pipeline (traité comme un échec de cette tentative, pas une panne fatale).

**Fichier** : `generation/graph.py` (`_noeud_test_sandbox`/`_route_apres_test_sandbox`), `sandbox/runner.py`

---

### 6️⃣ REVIEWER — présent dans le code, **jamais appelé** par le pipeline

**Rôle prévu** : Relire le code et détecter les bugs potentiels avant validation — un second avis
LLM en plus de la validation déterministe.

**État réel** : `generation/agents/reviewer.py`, `_noeud_reviewer` et `_route_apres_reviewer`
(`generation/graph.py`) existent et fonctionnent, mais ne sont **pas** enregistrés dans
`_construire_graphe` — son avis consultatif est devenu redondant une fois que `test_sandbox`
exécute réellement les tests du Testeur et que la cascade déterministe tranche derrière. Réactivable
en deux lignes (`graphe.add_node("reviewer", ...)` + reprise des arêtes) si un besoin réapparaît —
voir CLAUDE.md, Étape 6.

**Fichier** : `generation/agents/reviewer.py`

---

### 7️⃣ DEBUGGER

**Rôle** : Corriger le code après un échec de `test_sandbox` ou de la validation cascade — jamais
après un rejet du Reviewer (désactivé, voir ci-dessus).

**Condition d'exécution** : Après un échec de `test_sandbox` (tests réels en échec) ou de
`validation` (cascade déterministe en échec).

**Input** :
- Code source bugué (output du Développeur ou d'une tentative précédente)
- Message d'erreur : sortie des tests réels en sandbox, ou verdict de la cascade

**Output** : `ResultatCorrection`
- Code source Python corrigé
- `cause: str | None` — cause identifiée (aide au diagnostic, jamais bloquant si absente)

**Durée moyenne** : ~15s

**Fichier** : `generation/agents/debugger.py`

**Note importante** : Le Debugger peut intervenir **jusqu'à 10 fois** (`MAX_TENTATIVES_REPARATION`,
§6.6bis) — boucle bornée `test_sandbox` ⇄ `debugger`, avec passage par `validation` entre les deux.
Toute correction repasse par `test_sandbox` en premier (jamais directement par `validation`). Si les
tentatives s'épuisent sans validation réussie, c'est un échec final honnête (jamais masqué).

---

### VALIDATION (pas un agent LLM, mais une fonction — appelée à chaque tentative, après un succès de test_sandbox)

**Rôle** : Valider le code en 3 passes déterministes, une fois `test_sandbox` déjà passé.

**Input** :
- Code source (du Développeur ou du Debugger), déjà vert sur `test_sandbox`

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

**Durée totale** : ~0.5s par tentative (hors temps de `test_sandbox`, qui tourne un vrai conteneur Docker)

**Fichier** : `generation/graph.py` (fonction `_valider_completement`, nœud `validation`)

**Point clé** : Appelée à chaque tentative de la boucle (jusqu'à 10 fois), seulement après un succès
de `test_sandbox` — jamais sur du code d'Optimiseur, cet agent ayant été supprimé du dépôt.

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
         TESTEUR ───► Module pytest généré
              │
              ▼
    ┌─── BOUCLE (max 10 tentatives, §6.6bis) ─────────────────────┐
    │                                                              │
    │   TEST_SANDBOX ───► exécution réelle des tests, en Docker   │
    │       │                                                      │
    │       ├─ ÉCHEC ──► DEBUGGER ──► Code corrigé ──► retour TEST_SANDBOX
    │       │                                                      │
    │       └─ SUCCÈS ──► VALIDATION (statique → exécution → cascade)
    │                             │                                │
    │                             ├─ ÉCHEC ──► DEBUGGER ──► retour TEST_SANDBOX
    │                             └─ SUCCÈS ──► sort de la boucle  │
    └──────────────────────────────────────────────────────────────┘
              │ (tentatives épuisées → échec honnête, STOP)
              ▼ (succès)
         DOCUMENTATION (best-effort)
              │
              ▼
       RÉSULTAT FINAL
```

Le Reviewer n'apparaît pas dans ce flux (présent dans le code, jamais câblé — voir la section 6️⃣
ci-dessus).

---

## 📊 Métriques Typiques

Sur une instance de **12 tâches, 5 ressources, 10 contraintes** :

| Agent / étape | Durée (s) | Tokens Input | Tokens Output | Coût ($) |
|-------|-----------|--------------|---------------|----------|
| Analyste | 10.6 | 600 | 300 | 0.038 |
| Benchmarker | variable | 700 | 300 | 0.040 |
| Architecte | 14.9 | 900 | 400 | 0.051 |
| Développeur | 21.0 | 1200 | 800 | 0.075 |
| Testeur | 17.5 | 1000 | 500 | 0.058 |
| Test_sandbox (Docker) | variable, ~qq secondes | 0 | 0 | 0.000 |
| Debugger* | 15.0 | 1300 | 700 | 0.068 |
| Validation | 0.5 | 0 | 0 | 0.000 |
| Documentation | 8.0 | 900 | 400 | 0.048 |

*Conditionnel — seulement si `test_sandbox` ou `validation` échoue à une tentative donnée.
Reviewer absent de ce tableau : jamais appelé par le pipeline actuel (voir section dédiée
ci-dessus). Optimiseur aussi absent, pour une raison différente : supprimé, il n'existe plus du
tout. Les coûts réels dépendent aussi du fournisseur LLM effectivement
utilisé par agent (voir §Configuration ci-dessous) — nettement plus disparate qu'un fournisseur
unique pour tous les agents.

---

## 🎯 Points Clés du Pipeline

### ✅ Avantages Multi-Agents

1. **Séparation des préoccupations** : Chaque agent a un rôle clair
2. **Qualité accrue** : les tests du Testeur sont réellement exécutés en sandbox (§6.6bis) avant
   toute cascade déterministe, pas juste générés comme livrable documentaire
3. **Correction automatique et bornée** : Debugger corrige jusqu'à 10 tentatives, jamais indéfiniment
4. **Documentation automatique** : Livrable prêt à l'emploi

### ⚠️ Limites

1. **Coût** : nettement plus cher que le mode simple (1 agent, `tentative_unique.py`)
2. **Durée** : plusieurs appels LLM + jusqu'à 10 tentatives de réparation, contre un seul appel en mode simple
3. **Complexité des instances riches en contraintes** : plus de contraintes à justifier peut
   consommer davantage le budget de tokens de sortie du fournisseur choisi (voir §Configuration) —
   pas de plafond dur documenté ici, dépend du modèle

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

**Anthropic et OpenAI ne sont pas des fournisseurs supportés par ce module** —
`generation/agents/client_llm.py::_CONSTRUCTEURS_MODELE` ne connaît que `mistral`, `together`,
`qwen` (alias de `together`), `nvidia`, `minimax`, `deepseek` et `nemotron` (tous deux hébergés via
le catalogue API NVIDIA NIM, `https://integrate.api.nvidia.com/v1`, sauf `mistral`/`together` qui
appellent leur API native).

Chaque agent est routé vers un fournisseur par défaut différent, pas un fournisseur unique pour tout
le pipeline (`generation/agents/config_fournisseurs.py`) :

| Agent(s) | Fournisseur par défaut | Modèle |
|---|---|---|
| Analyste, Architecte, Développeur, Testeur, Debugger, Reviewer (inactif), Compréhension ERP | `nemotron` | `nvidia/nemotron-3-super-120b-a12b` |
| Benchmarker | `minimax` | `minimaxai/minimax-m3` |
| Documentation | `nvidia` | `meta/llama-3.3-70b-instruct` |
| Supervision (MT7) | `mistral` | `mistral-large-latest` |

Surchargeable par variable d'environnement, agent par agent :
```bash
PRISME_LLM_PROVIDER_<AGENT>=mistral       # ex. PRISME_LLM_PROVIDER_DEVELOPPEUR=deepseek
PRISME_LLM_MODEL_<AGENT>=...
PRISME_LLM_TIMEOUT_SECONDES_<AGENT>=...
```
`PRISME_LLM_PROVIDER`/`PRISME_LLM_MODEL` (sans suffixe d'agent) restent le repli générique du mode
single-shot (`tentative_unique.py`), pas celui du pipeline multi-agents.

Appel direct du pipeline (pas de script `generer_solveur.py` — n'existe pas) :
```python
from generation.graph import tenter_generation_avec_boucle

resultat = tenter_generation_avec_boucle(instance_exemple=instance.model_dump(mode="json"))
```
Ou via l'API, déjà câblée dessus : `POST /generation/{instance_id}` (bloquant) ou
`POST /generation/{instance_id}/demarrer` + SSE `GET /generation/jobs/{job_id}/stream`
(`api/routes/generation.py`).

---

## 📚 Fichiers Liés

- **Pipeline + boucle** : `generation/graph.py` (StateGraph LangGraph, Étape 6, §6.6bis pour `test_sandbox`)
- **Agents** : `generation/agents/{analyste,benchmarker,architecte,generateur,testeur,debugger,documentation}.py`
  (`reviewer.py` présent, jamais câblé)
- **Client LLM** : `generation/agents/client_llm.py`, `generation/agents/config_fournisseurs.py` (routage par agent)
- **Validation** : `generation/validation_statique.py`, `generation/executer.py`, `validation_engine/cascade.py`
- **Sandbox** : `sandbox/runner.py` (`executer_tests_dans_sandbox`, exécution réelle du Testeur ; Étape 7 pour la production)
- **Observabilité** : LangSmith (tracing natif LangChain/LangGraph, aucune instrumentation maison)
