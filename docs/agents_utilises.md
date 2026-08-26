# Agents Utilisés pour Générer le Code

## 🎯 Réponse Courte

**NON**, le système a utilisé **un seul agent** (mode simple).

Mais il existe **8 agents** (mode pipeline multi-agents, `generation/graph.py`) que vous pouvez utiliser à la place !

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
# generation/tentative_unique.py, fonction tenter_generation_unique
brut = generer_code_solveur(modele)  # modele: BaseChatModel (LangChain), pas l'ancien AppelLLM
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
│  PIPELINE DE 8 AGENTS (generation/graph.py, StateGraph LangGraph)│
│                                                                 │
│  1. ANALYSTE                                                    │
│     → Analyse l'instance T-R-C-O                               │
│     → Identifie les contraintes critiques                      │
│                                                                 │
│  2. BENCHMARKER                                                 │
│     → Choisit l'algorithme (cp_sat, genetic, aco, ...)          │
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
│  6. TEST_SANDBOX ⇄ DEBUGGER (boucle bornée, max 10 tentatives)  │
│     → Exécute réellement les tests du Testeur en Docker         │
│       (§6.6bis), puis la cascade déterministe ; le Debugger     │
│       corrige si l'un des deux échoue, jusqu'à validation       │
│                                                                 │
│  7. DOCUMENTATION (si succès)                                   │
│     → Génère la documentation du code                          │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
      ↓
Code validé (tests réels + cascade au vert) + documentation
```

Pas d'Orchestrateur ni d'Optimiseur dans ce pipeline : le premier ne faisait
que produire un plan JSON jamais lu par personne (l'ordre d'exécution a
toujours été câblé en Python), le second a été retiré car sa réponse JSON
(code Python complet en valeur de chaîne) était trop fragile à faire produire
par un LLM de façon fiable. Les deux fichiers ont été supprimés (`orchestrateur.py`)
ou laissés orphelins (`optimiseur.py`, toujours présent mais plus appelé).

**Le Reviewer aussi est orphelin**, pour une troisième raison différente :
`generation/agents/reviewer.py` fonctionne et reste appelable isolément, mais
`generation/graph.py::_construire_graphe` ne l'enregistre jamais comme nœud du
pipeline — son avis LLM consultatif est devenu redondant une fois que
`test_sandbox` exécute réellement les tests du Testeur et que la cascade
déterministe tranche derrière. Réactivable en deux lignes si besoin.

**Code disponible** :
```python
# generation/graph.py — seul pipeline branché sur l'API (api/routes/generation.py)
from generation.graph import tenter_generation_avec_boucle, tenter_generation_avec_boucle_stream

# Version bloquante :
resultat = tenter_generation_avec_boucle()
# Version streaming (SSE, un évènement par agent) :
for evenement in tenter_generation_avec_boucle_stream():
    ...
```

**Caractéristiques** :
- ⏱️ **Plus lent** : 7-8 appels LLM + jusqu'à 10 tentatives de réparation (~2-5 minutes)
- 💰 **Plus cher** : ~$0.50-1.00
- ✅ **Meilleure qualité** : boucle de réparation bornée, pas un seul essai
- ✅ **Plan technique** : architecture réfléchie
- ✅ **Choix d'algorithme** : Benchmarker sélectionne cp_sat ou une heuristique
- ✅ **Tests réels** : le module pytest du Testeur est exécuté pour de vrai en sandbox Docker (§6.6bis),
  pas juste généré comme livrable documentaire
- ✅ **Documentation** : code documenté (best-effort)

---

## 📋 Comparaison : Single-Shot vs Multi-Agents

| Aspect | Single-Shot (utilisé) | Multi-Agents (disponible) |
|--------|----------------------|---------------------------|
| **Agents** | 1 (Générateur) | 7 réellement câblés (Reviewer présent mais inactif) |
| **Appels LLM** | 1 | 6-7 + jusqu'à 10 tentatives de réparation |
| **Durée** | 10-30 secondes | 2-5 minutes |
| **Coût** | ~$0.01-0.05 | ~$0.35-1.00 |
| **Taux de succès** | 70-85% | plus élevé (boucle bornée, pas un seul essai) |
| **Plan technique** | ❌ Non | ✅ Oui (Architecte) |
| **Choix d'algorithme** | ❌ Non (CP-SAT fixe) | ✅ Oui (Benchmarker) |
| **Tests réellement exécutés** | ❌ Non | ✅ Oui (`test_sandbox`, Docker, §6.6bis) |
| **Revue de code par un second LLM** | ❌ Non | ❌ Non plus (Reviewer présent mais désactivé, jamais appelé) |
| **Débogage** | ❌ Non | ✅ Oui (Debugger, boucle bornée sur échec de test_sandbox/validation) |
| **Documentation** | ❌ Non | ✅ Oui (Documentation) |

---

## 🔍 Détail des 8 Agents

### 1. Analyste (`analyste.py`)

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

### 2. Benchmarker (`benchmarker.py`)

**Rôle** : Choisit l'algorithme le mieux adapté à l'instance

**Input** : Instance T-R-C-O (ou une instance d'exemple par défaut)
**Output** : Algorithme recommandé + justification + paramètres

```python
recommandation = Recommandation(
    algorithme="cp_sat",  # ou genetic/aco/tabu_search/simulated_annealing/dispatching/greedy_local
    raison="petite instance, solution optimale garantie possible",
    parametres_suggeres={...},
)
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

### 6. Reviewer (`reviewer.py`) — présent dans le code, **jamais appelé par le pipeline**

**Rôle prévu** : Revoit le code et identifie les bugs, avant tout test réel.

**État réel** : fonctionne isolément (`generation.agents.reviewer.relire_code`), mais
`generation/graph.py::_construire_graphe` ne l'enregistre jamais comme nœud du `StateGraph` — son
avis LLM consultatif est devenu redondant une fois que `test_sandbox` (ci-dessous) exécute
réellement les tests du Testeur et que la cascade déterministe tranche derrière. Réactivable en deux
lignes si un besoin réapparaît.

### TEST_SANDBOX — pas un agent LLM, la vraie étape à cette place du pipeline (§6.6bis)

**Rôle** : Exécute pour de vrai le module pytest généré par le Testeur, dans le même conteneur
Docker éphémère durci que la production (`sandbox/runner.py::executer_tests_dans_sandbox`).

**Input** : Code du Développeur (ou du Debugger) + tests du Testeur
**Output** : Succès/échec réel des tests — un échec route directement vers le Debugger, sans passer
par la revue LLM ni par la cascade déterministe (inutile de faire tourner une cascade sur un code
dont on sait déjà, par exécution réelle, qu'il échoue ses propres tests).

Si `test_sandbox` réussit, le code passe ensuite par la **validation cascade déterministe**
(statique → exécution → faisabilité/optimalité/fidélité) avant d'être accepté.

### 7. Debugger (`debugger.py`)

**Rôle** : Corrige le code après un échec de `test_sandbox` (tests réels) ou de la validation
cascade — jamais après un rejet du Reviewer (désactivé, voir ci-dessus).

**Input** : Code + message d'erreur (sortie des tests réels, ou verdict de la cascade)
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

`optimiseur.py` existe toujours mais n'est plus appelé par le pipeline
(réponse JSON trop fragile pour embarquer du code Python complet) — orphelin,
comme `orchestrateur.py` avant sa suppression.

### 8. Documentation (`documentation.py`)

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

C'est déjà ce que l'API appelle (`api/routes/generation.py`, canal
`POST /{instance_id}` ou `POST /{instance_id}/demarrer` + SSE). Pour
l'appeler directement en script :

```python
from generation.graph import tenter_generation_avec_boucle

resultat = tenter_generation_avec_boucle()

print(f"✅ Réussi : {resultat.reussi}")
print(f"✅ Code final : {len(resultat.code_final)} caractères")
print(f"✅ Tests générés : {len(resultat.tests_generes)} lignes")
print(f"✅ Documentation : {resultat.documentation}")
print(f"📊 Tentatives de réparation : {resultat.boucle_reparation.nombre_tentatives}")
print(f"📊 Verdict : {resultat.verdict_cascade}")
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
- ✅ Instance de grande taille où un algorithme alternatif (Benchmarker) peut valoir mieux que CP-SAT

---

## 🎓 Résumé

### Ce qui s'est passé :
```
Instance → 1 AGENT (Générateur) → Code (avec bug) → solveur_genere.py
           ⏱️  10-30s
           💰 $0.01
```

### Ce qui existe (pipeline de production, câblé sur l'API) :
```
Instance → 8 AGENTS (Analyste → ... → Documentation, boucle de réparation) → Code validé + tests + doc
           ⏱️  2-5 minutes
           💰 $0.50-1.00
```

---

**Voulez-vous tester le pipeline multi-agents pour voir la différence ?** 🚀

Il corrigerait probablement le bug automatiquement (tests réels en sandbox + Debugger, boucle bornée) et générerait une documentation !
