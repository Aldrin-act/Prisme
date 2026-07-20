# Comment le Code du Solveur s'est Généré

## 📋 Vue d'ensemble du processus

```
Instance T-R-C-O (JSON)
       ↓
   [1. Prompt système]
       ↓
   [2. Prompt utilisateur avec l'instance]
       ↓
   Mistral AI 🤖
       ↓
   Code Python généré
       ↓
   [3. Validation + Exécution]
```

---

## 🎯 Étape 1 : L'Instance d'entrée

Vous avez fourni `atelier_trois_taches.json` :

```json
{
  "taches": [
    {"id": "T1", "nom": "Découpe"},
    {"id": "T2", "nom": "Soudure"},
    {"id": "T3", "nom": "Peinture"}
  ],
  "ressources": [
    {"id": "R1", "nom": "Machine laser"},
    {"id": "R2", "nom": "Poste de soudure"}
  ],
  "contraintes": [
    {"type": "precedence", "avant": "T1", "apres": "T2"},
    {"type": "precedence", "avant": "T2", "apres": "T3"},
    {"type": "compatibilite_ressource_tache", "tache": "T1", "ressource": "R1", "duree": 60},
    {"type": "compatibilite_ressource_tache", "tache": "T2", "ressource": "R2", "duree": 90},
    {"type": "compatibilite_ressource_tache", "tache": "T3", "ressource": "R1", "duree": 90}
  ],
  "objectifs": [
    {"type": "minimiser_makespan"}
  ]
}
```

---

## 🤖 Étape 2 : Construction du Prompt pour le LLM

### 2.1 Prompt Système (instructions générales)

Le code dans `generation/agents/generateur.py` construit un prompt système qui ressemble à :

```
Tu es un expert en optimisation avec OR-Tools CP-SAT.

Ta tâche : Générer du code Python qui résout un problème de scheduling FJSP 
(Flexible Job-Shop Scheduling Problem).

CONTRAINTES IMPORTANTES :
- Utilise UNIQUEMENT : ortools.sat.python, dsl.schema, collections, typing, dataclasses
- INTERDIT : eval, exec, __import__, open, os, sys, subprocess, file I/O
- Signature EXACTE : def resoudre(instance: InstanceTRCO) -> Planning | None
- Retourne Planning avec OperationPlanifiee(tache: str, ressource: str, debut: int, fin: int)
- Retourne None si problème infeasible

STRUCTURE DU CODE :
1. Importer ortools.sat.python.cp_model
2. Créer le modèle CP-SAT
3. Définir les variables (intervalles, affectations)
4. Encoder les contraintes
5. Définir l'objectif
6. Résoudre
7. Construire et retourner Planning

RAPPEL : OperationPlanifiee attend tache.id (string), pas l'objet tache !
```

### 2.2 Prompt Utilisateur (instance spécifique)

Le code transforme votre instance JSON en description pour le LLM :

```
Génère un solveur CP-SAT pour cette instance :

TÂCHES (3) :
- T1 (Découpe)
- T2 (Soudure)
- T3 (Peinture)

RESSOURCES (2) :
- R1 (Machine laser)
- R2 (Poste de soudure)

CONTRAINTES (5) :

1. PRECEDENCE : T1 doit finir avant T2
2. PRECEDENCE : T2 doit finir avant T3

3. COMPATIBILITE : T1 peut s'exécuter sur R1 en 60 minutes
4. COMPATIBILITE : T2 peut s'exécuter sur R2 en 90 minutes
5. COMPATIBILITE : T3 peut s'exécuter sur R1 en 90 minutes

OBJECTIF :
- Minimiser le makespan (durée totale)

CODE ATTENDU :
- Variables : intervalles pour chaque (tâche, ressource) compatible
- Contrainte : une seule ressource par tâche (ExactlyOne)
- Contrainte : précédences (end_T1 <= start_T2, end_T2 <= start_T3)
- Contrainte : pas de chevauchement sur chaque ressource (NoOverlap)
- Objectif : Minimize(makespan)

Génère le code Python complet maintenant.
```

---

## 🧠 Étape 3 : Le LLM génère le code

Mistral AI reçoit ces deux prompts et **génère** le code en analysant :

### Ce que Mistral a compris :

1. **3 tâches** à planifier
2. **2 ressources** disponibles
3. **Précédences** : chaîne T1 → T2 → T3
4. **Flexibilité** : T1 et T3 utilisent R1 (conflit potentiel)
5. **Objectif** : Makespan minimal

### Comment il a structuré le code :

```python
# 1. VARIABLES (lignes 20-38)
# Pour chaque (tâche, ressource) compatible :
starts[(T1, R1)] = variable "start"
ends[(T1, R1)] = variable "end"
intervals[(T1, R1)] = IntervalVar(start, 60, end)
ressource_assign[(T1, R1)] = BoolVar "est-ce T1 assigné à R1 ?"

# 2. CONTRAINTE : Une seule ressource par tâche (lignes 39-41)
# T1 a 1 ressource compatible (R1)
# T2 a 1 ressource compatible (R2)
# T3 a 1 ressource compatible (R1)
model.AddExactlyOne(ressource_assign[(tache, r)] for r in compatibles)

# 3. CONTRAINTE : Précédences (lignes 43-50)
# T1 doit finir avant T2 :
model.Add(ends[(T1, R1)] <= starts[(T2, R2)])
# T2 doit finir avant T3 :
model.Add(ends[(T2, R2)] <= starts[(T3, R1)])

# 4. CONTRAINTE : Pas de chevauchement (lignes 52-58)
# Sur R1 : T1 et T3 ne peuvent pas se chevaucher
intervals_R1 = [intervals[(T1, R1)], intervals[(T3, R1)]]
model.AddNoOverlap(intervals_R1)
# Sur R2 : seulement T2 (pas de conflit)
intervals_R2 = [intervals[(T2, R2)]]
model.AddNoOverlap(intervals_R2)

# 5. OBJECTIF : Minimiser makespan (lignes 68-74)
makespan = max(ends)
model.Minimize(makespan)

# 6. RÉSOLUTION (lignes 76-93)
solver.Solve(model)
# Construire Planning à partir de la solution
```

---

## 🔍 Étape 4 : Analyse du code généré

### ✅ Ce qui est CORRECT :

1. **Structure générale** : Suit le pattern CP-SAT classique
2. **Variables** : Intervalles pour chaque (tâche, ressource)
3. **Contrainte ExactlyOne** : Une seule ressource par tâche
4. **Précédences** : Bien encodées (end ≤ start)
5. **NoOverlap** : Pas de chevauchement par ressource
6. **Objectif** : Minimise le makespan

### ❌ Ce qui est INCORRECT (le bug détecté) :

```python
# Ligne 87 : ❌ BUG
operations.append(OperationPlanifiee(
    tache=tache,           # ❌ Objet Tache au lieu de tache.id
    ressource=ressources[r],  # ❌ Objet Ressource au lieu de r (string)
    debut=debut
))

# Devrait être :
operations.append(OperationPlanifiee(
    tache=tache.id,        # ✅ String
    ressource=r,           # ✅ String
    debut=debut,
    fin=debut + duree      # ✅ Manque aussi le champ "fin"
))
```

**Pourquoi ce bug ?**

Mistral a "oublié" que `OperationPlanifiee` attend des **strings** (IDs), pas des objets. C'est un bug logique classique dans du code généré par IA.

---

## 📊 Étape 5 : Schéma de génération complet

```
┌─────────────────────────────────────────────────────────────────┐
│ VOTRE INSTANCE (JSON)                                            │
│   3 tâches, 2 ressources, 5 contraintes, 1 objectif            │
└───────────────────┬─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ TRADUCTION EN PROMPT (generation/agents/generateur.py)          │
│   "Génère un solveur CP-SAT pour :                             │
│    - Tâches : T1, T2, T3                                       │
│    - Ressources : R1, R2                                       │
│    - Contraintes : précédences + compatibilités                │
│    - Objectif : minimiser makespan"                            │
└───────────────────┬─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ APPEL LLM (generation/agents/client_llm.py)                     │
│   POST https://api.mistral.ai/v1/chat/completions              │
│   {                                                             │
│     "model": "mistral-large-latest",                           │
│     "messages": [                                              │
│       {"role": "system", "content": "...prompt système..."},   │
│       {"role": "user", "content": "...prompt instance..."}     │
│     ],                                                          │
│     "temperature": 0.7                                         │
│   }                                                             │
└───────────────────┬─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ RÉPONSE MISTRAL AI (après ~10-30 secondes)                     │
│   Code Python complet (94 lignes)                              │
│   - Imports                                                     │
│   - def resoudre(instance: InstanceTRCO)                       │
│   - Modèle CP-SAT                                              │
│   - Variables + Contraintes + Objectif                         │
│   - Résolution + Construction Planning                         │
└───────────────────┬─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ VALIDATION STATIQUE (generation/validation_statique.py)         │
│   ✅ AST allowlist : seulement imports autorisés               │
│   ✅ Pas d'eval, exec, __import__, open                        │
│   ✅ Signature correcte : def resoudre(...)                    │
└───────────────────┬─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ EXÉCUTION TEST (generation/executer.py)                         │
│   exec(code_genere) dans namespace isolé                       │
│   resoudre(instance_test) → Planning brut                      │
│                                                                 │
│   ❌ ÉCHEC : OperationPlanifiee attend strings, pas objets    │
│   → Bug détecté AVANT d'atteindre le client                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 💡 Points Clés à Retenir

### 1. Le LLM ne "comprend" pas vraiment

Mistral AI n'a **pas de compréhension** du problème de scheduling. Il fait du **pattern matching** :
- Il a vu des milliers d'exemples de code CP-SAT dans ses données d'entraînement
- Il reproduit les patterns qu'il a appris
- Mais il peut faire des erreurs subtiles (comme oublier `.id`)

### 2. Le prompt est CRUCIAL

La qualité du code généré dépend **directement** de la qualité du prompt :
- Plus le prompt est précis → meilleur code
- Exemples dans le prompt → meilleur code
- Rappels explicites ("tache.id, pas tache") → moins d'erreurs

### 3. La validation est INDISPENSABLE

C'est pourquoi PRISME a **3 couches de validation** :
1. **Validation statique** : bloque code malveillant
2. **Exécution test** : détecte bugs runtime (celui-ci !)
3. **Cascade** : vérifie optimalité et fidélité

### 4. Non-déterminisme

Si vous relancez la génération, Mistral pourrait produire :
- Un code **différent** (variables nommées autrement)
- Peut-être **sans bug** (il "tombera juste" sur le bon pattern)
- Peut-être **avec d'autres bugs**

---

## 🔧 Comment améliorer la génération ?

### Option 1 : Enrichir le prompt

Ajouter dans le prompt système :

```python
IMPORTANT - CONSTRUCTION DU PLANNING :
❌ NE FAIS PAS : OperationPlanifiee(tache=tache_obj, ressource=ressource_obj, ...)
✅ FAIS : OperationPlanifiee(tache=tache.id, ressource=ressource_id, debut=..., fin=...)

EXEMPLE CORRECT :
operations.append(OperationPlanifiee(
    tache=tache_id,  # STRING, pas l'objet !
    ressource=r,     # STRING, pas l'objet !
    debut=solver.Value(starts[(tache_id, r)]),
    fin=solver.Value(ends[(tache_id, r)])
))
```

### Option 2 : Few-shot learning

Ajouter 1-2 exemples de code **correct** dans le prompt :

```python
EXEMPLE DE CODE ATTENDU :

```python
def resoudre(instance: InstanceTRCO) -> Planning | None:
    model = cp_model.CpModel()
    # ... variables ...
    solver.Solve(model)
    
    operations = []
    for tache_id in affectations:
        operations.append(OperationPlanifiee(
            tache=tache_id,  # ← STRING
            ressource=ressource_affectee,  # ← STRING
            debut=debut,
            fin=fin
        ))
    return Planning(operations=operations)
\```

Génère du code similaire pour l'instance fournie.
```

### Option 3 : Boucle de réparation (Étape 6)

Implémenter la boucle qui :
1. Détecte le bug (déjà fait !)
2. Envoie feedback au LLM : "Erreur : OperationPlanifiee attend strings, pas objets"
3. LLM régénère avec ce feedback
4. Retry jusqu'à succès (max 3 tentatives)

---

## 🎓 Résumé : Du JSON au Code

```
Instance JSON
  → Parsé en InstanceTRCO (Pydantic)
  → Traduit en prompt texte
  → Envoyé à Mistral AI
  → LLM génère code Python
  → Validé (AST)
  → Exécuté (détecte bugs)
  → Sauvegardé dans solveur_genere.py
```

**Temps total** : ~10-30 secondes
**Coût** : ~$0.01-0.05 (Mistral)
**Qualité** : 70-85% de taux de succès (selon modèle)

---

## 🚀 Prochaines étapes pour vous

1. **Examinez le code** : Comprenez la logique CP-SAT
2. **Corrigez le bug** : Lignes 87-90 (tache.id, ressource, fin)
3. **Relancez** : Voyez si ça fonctionne
4. **Cascade complète** : Testez optimalité et fidélité
5. **Enregistrez** : Si VERT, stockez dans solver_store/

---

**Le code généré est impressionnant, non ?** 🤖 Mistral a créé un vrai solveur OR-Tools en ~20 secondes !
