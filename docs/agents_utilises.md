# Agents Utilisés pour Générer le Code

## 🎯 Réponse Courte

**NON**, le système a utilisé **un seul agent** (mode simple).

Mais il existe **9 agents disponibles** (mode pipeline multi-agents) que vous pouvez utiliser à la place !

---

## 📊 Ce qui s'est RÉELLEMENT passé

### Mode Utilisé : **Single-Shot (Étape 4)**

```
Votre instance
      ↓
┌────────────────────────────────────┐
│  UN SEUL AGENT : Générateur        │
│                                     │
│  generation/agents/generateur.py   │
│  - Construit le prompt             │
│  - Appelle Mistral AI              │
│  - Extrait le code                 │
│  → Code généré directement         │
└────────────────────────────────────┘
      ↓
Validation statique
      ↓
Exécution
      ↓
solveur_genere.py
```

**Code appelé** :
```python
# generation/tentative_unique.py, ligne 42
brut = generer_code_solveur(appel_llm)
#      ^^^^^^^^^^^^^^^^^^^^
#      UN SEUL AGENT
```

**Caractéristiques** :
- ✅ **Rapide** : 1 appel LLM (~10-30s)
- ✅ **Économique** : ~$0.01-0.05
- ⚠️ **Qualité variable** : 70-85% de succès
- ❌ **Pas de plan technique** : génère directement
- ❌ **Pas de revue de code** : pas de vérification
- ❌ **Pas d'optimisation** : premier jet uniquement

---

## 🚀 Ce qui EXISTE (mais pas utilisé)

### Mode Disponible : **Pipeline Multi-Agents**

```
Votre instance
      ↓
┌────────────────────────────────────────────────────────────────┐
│  PIPELINE DE 9 AGENTS                                           │
│                                                                 │
│  1. ORCHESTRATEUR                                               │
│     → Planifie les étapes                                      │
│                                                                 │
│  2. ANALYSTE                                                    │
│     → Analyse l'instance T-R-C-O                               │
│     → Identifie les contraintes critiques                      │
│                                                                 │
│  3. ARCHITECTE                                                  │
│     → Conçoit le plan technique                                │
│     → "Utiliser IntervalVar pour...", "NoOverlap sur..."       │
│                                                                 │
│  4. DÉVELOPPEUR (Générateur)                                    │
│     → Génère le code selon le plan                             │
│                                                                 │
│  5. TESTEUR                                                     │
│     → Génère des tests unitaires                               │
│                                                                 │
│  6. REVIEWER                                                    │
│     → Revoit le code, identifie les bugs potentiels            │
│                                                                 │
│  7. DEBUGGER (si besoin)                                        │
│     → Corrige les erreurs détectées                            │
│                                                                 │
│  8. OPTIMISEUR                                                  │
│     → Améliore les performances                                │
│                                                                 │
│  9. DOCUMENTATION                                               │
│     → Génère la documentation du code                          │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
      ↓
Code optimisé + tests + documentation
```

**Code disponible** :
```python
# generation/pipeline_multi_agents.py
from generation.agents import (
    orchestrateur,
    analyste,
    architecte,
    debugger,
    optimiseur,
    reviewer,
    testeur,
)
from generation.agents.generateur import generer_code_depuis_plan
from generation.agents.documentation import generer_documentation

# Fonction : executer_pipeline_multi_agents(...)
```

**Caractéristiques** :
- ⏱️ **Plus lent** : 9 appels LLM (~2-5 minutes)
- 💰 **Plus cher** : ~$0.50-1.00
- ✅ **Meilleure qualité** : 85-95% de succès
- ✅ **Plan technique** : architecture réfléchie
- ✅ **Revue de code** : bugs détectés avant exécution
- ✅ **Optimisation** : performances améliorées
- ✅ **Tests** : tests unitaires générés
- ✅ **Documentation** : code documenté

---

## 📋 Comparaison : Single-Shot vs Multi-Agents

| Aspect | Single-Shot (utilisé) | Multi-Agents (disponible) |
|--------|----------------------|---------------------------|
| **Agents** | 1 (Générateur) | 9 (pipeline complet) |
| **Appels LLM** | 1 | 9 |
| **Durée** | 10-30 secondes | 2-5 minutes |
| **Coût** | ~$0.01-0.05 | ~$0.50-1.00 |
| **Taux de succès** | 70-85% | 85-95% |
| **Plan technique** | ❌ Non | ✅ Oui (Architecte) |
| **Revue de code** | ❌ Non | ✅ Oui (Reviewer) |
| **Débogage** | ❌ Non | ✅ Oui (Debugger) |
| **Optimisation** | ❌ Non | ✅ Oui (Optimiseur) |
| **Tests générés** | ❌ Non | ✅ Oui (Testeur) |
| **Documentation** | ❌ Non | ✅ Oui (Documentation) |

---

## 🔍 Détail des 9 Agents

### 1. Orchestrateur (`orchestrateur.py`)

**Rôle** : Planifie les étapes de génération

**Input** : Instance T-R-C-O
**Output** : Liste des étapes à suivre

```python
plan = [
    EtapePlan(agent="analyste", description="Analyser contraintes"),
    EtapePlan(agent="architecte", description="Concevoir architecture"),
    EtapePlan(agent="developpeur", description="Générer code"),
    ...
]
```

### 2. Analyste (`analyste.py`)

**Rôle** : Analyse l'instance pour identifier les défis

**Input** : Instance T-R-C-O
**Output** : Spécification détaillée

```
Analyse :
- 3 tâches avec précédences en chaîne (T1 → T2 → T3)
- Contrainte critique : T1 et T3 partagent R1 → risque de conflit
- Flexibilité limitée : 1 ressource/tâche
- Objectif : makespan minimal
Recommandation : Utiliser NoOverlap strict sur R1
```

### 3. Architecte (`architecte.py`)

**Rôle** : Conçoit le plan technique détaillé

**Input** : Spécification de l'Analyste
**Output** : Plan technique

```
Plan Technique :

1. Variables :
   - IntervalVar pour chaque (tâche, ressource) compatible
   - BoolVar pour affectations

2. Contraintes :
   - AddExactlyOne : une seule ressource/tâche
   - Précédences : end[pred] <= start[succ]
   - NoOverlap par ressource

3. Objectif :
   - Makespan = max(end_times)
   - Minimize(makespan)
```

### 4. Développeur (`generateur.py`)

**Rôle** : Génère le code selon le plan

**Input** : Plan technique de l'Architecte
**Output** : Code Python

```python
def resoudre(instance: InstanceTRCO) -> Planning | None:
    model = cp_model.CpModel()
    # ... suit le plan de l'Architecte ...
```

### 5. Testeur (`testeur.py`)

**Rôle** : Génère des tests unitaires

**Input** : Code du Développeur
**Output** : Tests pytest

```python
def test_resoudre_instance_simple():
    instance = InstanceTRCO(...)
    planning = resoudre(instance)
    assert planning is not None
    assert len(planning.operations) == 3

def test_respect_precedences():
    planning = resoudre(instance)
    t1 = find_operation(planning, "T1")
    t2 = find_operation(planning, "T2")
    assert t1.fin <= t2.debut
```

### 6. Reviewer (`reviewer.py`)

**Rôle** : Revoit le code et identifie les bugs

**Input** : Code du Développeur
**Output** : Liste de problèmes détectés

```
Revue de Code :

✅ Structure générale : OK
✅ Imports : OK
✅ Contraintes encodées : OK

❌ BUGS DÉTECTÉS :
1. Ligne 87 : OperationPlanifiee(tache=tache, ...) 
   → Devrait être tache.id (string)
2. Ligne 88 : ressource=ressources[r]
   → Devrait être r (string)
3. Ligne 89 : Champ "fin" manquant

Sévérité : CRITIQUE (empêchera l'exécution)
```

### 7. Debugger (`debugger.py`)

**Rôle** : Corrige les bugs détectés par le Reviewer

**Input** : Code + Rapport du Reviewer
**Output** : Code corrigé

```python
# Code corrigé :
operations.append(OperationPlanifiee(
    tache=tache.id,  # ✅ Corrigé
    ressource=r,     # ✅ Corrigé
    debut=debut,
    fin=debut + compatibilites[tache.id][r]  # ✅ Ajouté
))
```

### 8. Optimiseur (`optimiseur.py`)

**Rôle** : Améliore les performances du code

**Input** : Code fonctionnel
**Output** : Code optimisé

```python
# AVANT (lent)
for tache in instance.taches:
    for ressource in instance.ressources:
        if est_compatible(tache, ressource):  # ❌ O(n²)
            ...

# APRÈS (rapide)
compatibilites = construire_index(instance)  # ✅ O(n), une fois
for tache_id, ressources_compatibles in compatibilites.items():
    ...
```

### 9. Documentation (`documentation.py`)

**Rôle** : Génère la documentation du code

**Input** : Code final
**Output** : Docstrings + commentaires

```python
def resoudre(instance: InstanceTRCO) -> Planning | None:
    """Résout le problème de scheduling FJSP avec OR-Tools CP-SAT.
    
    Args:
        instance: Instance T-R-C-O contenant tâches, ressources, contraintes
        
    Returns:
        Planning optimisé ou None si infeasible
        
    Approche:
        - Variables : IntervalVar pour chaque affectation possible
        - Contraintes : Précédences + NoOverlap + ExactlyOne
        - Objectif : Minimiser le makespan
    """
    # Création du modèle CP-SAT
    model = cp_model.CpModel()
    ...
```

---

## 🎯 Comment Utiliser le Pipeline Multi-Agents

### Option 1 : Créer un script

```python
# scripts/generer_avec_pipeline.py

from generation.pipeline_multi_agents import executer_pipeline_multi_agents
from generation.agents.client_llm import construire_appel_llm
from dsl.validation.validator import charger_instance
import json

# Charger instance
with open("dsl/examples/valid/atelier_trois_taches.json") as f:
    instance = charger_instance(json.load(f))

# Client LLM
appel_llm = construire_appel_llm()

# Pipeline complet
print("🚀 Lancement du pipeline multi-agents...")
resultat = executer_pipeline_multi_agents(appel_llm, instance)

# Résultats
print(f"✅ Code généré : {len(resultat.code_final)} caractères")
print(f"✅ Tests générés : {len(resultat.tests_generes)} lignes")
print(f"✅ Documentation : {resultat.documentation}")
print(f"📊 Verdict : {resultat.verdict_cascade}")
```

### Option 2 : Modifier le script existant

```python
# Dans generer_solveur_simple.py, remplacer :
from generation.tentative_unique import tenter_generation_unique
resultat = tenter_generation_unique(appel_llm)

# Par :
from generation.pipeline_multi_agents import executer_pipeline_multi_agents
resultat = executer_pipeline_multi_agents(appel_llm, instance)
```

---

## 💡 Quand Utiliser Quel Mode ?

### Utilisez **Single-Shot** (ce qui a été fait) si :
- ✅ Vous testez/expérimentez rapidement
- ✅ Budget limité ($0.01 vs $1)
- ✅ Instance simple (< 10 tâches)
- ✅ Prototypage initial

### Utilisez **Multi-Agents** si :
- ✅ Production / client réel
- ✅ Instance complexe (> 20 tâches)
- ✅ Qualité critique (> 95% de succès)
- ✅ Besoin de documentation/tests
- ✅ Optimisation des performances importante

---

## 🎓 Résumé

### Ce qui s'est passé :
```
Instance → 1 AGENT (Générateur) → Code (avec bug) → solveur_genere.py
           ⏱️  10-30s
           💰 $0.01
```

### Ce qui existe (non utilisé) :
```
Instance → 9 AGENTS (Orchestrateur → ... → Documentation) → Code optimisé + tests + doc
           ⏱️  2-5 minutes
           💰 $0.50-1.00
           ✅ 85-95% succès
```

---

**Voulez-vous tester le pipeline multi-agents pour voir la différence ?** 🚀

Il corrigerait probablement le bug automatiquement (Reviewer + Debugger) et générerait des tests + documentation !
