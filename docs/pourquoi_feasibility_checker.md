# Pourquoi le Feasibility Checker ? 🔒

## ❓ La Question

> "Le solveur OR-Tools génère déjà un planning qui respecte les contraintes. Pourquoi le vérifier à nouveau avec un feasibility checker ?"

**Réponse courte** : Parce que le code du solveur est **généré par un LLM** et peut contenir des bugs, même s'il compile et s'exécute.

---

## 🎯 Le Problème Fondamental

### Rappel : PRISME génère du CODE, pas des plannings

```
┌──────────────────────────────────────────────────────────┐
│  ⚠️  LE SOLVEUR EST ÉCRIT PAR UNE IA, PAS PAR UN HUMAIN │
└──────────────────────────────────────────────────────────┘

Flux classique (code hand-written) :
  Développeur écrit code → Tests → Production
  ✅ Code vérifié, debuggé, validé

Flux PRISME (code généré) :
  LLM génère code → ??? → Production
  ❌ Code non testé unitairement
  ❌ Peut contenir des bugs subtils
  ❌ Peut mal interpréter les contraintes
```

### Le code généré PEUT avoir des bugs

**Même si** :
- ✅ Le code compile (Python valide)
- ✅ Le code s'exécute sans crash
- ✅ Le code utilise OR-Tools correctement

**Il peut quand même** :
- ❌ Oublier une contrainte
- ❌ Mal encoder une contrainte
- ❌ Retourner un planning invalide

---

## 📋 Exemples Réels de Bugs

### Exemple 1 : Contrainte de précédence oubliée

**Instance** :
```json
{
  "taches": [
    {"id": "T1", "nom": "Découpe"},
    {"id": "T2", "nom": "Assemblage"},
    {"id": "T3", "nom": "Peinture"}
  ],
  "contraintes": [
    {"type": "precedence", "avant": "T1", "apres": "T2"},
    {"type": "precedence", "avant": "T2", "apres": "T3"}
  ]
}
```

**Code généré par le LLM (bugué)** :
```python
def resoudre(instance: InstanceTRCO) -> Planning:
    model = cp_model.CpModel()
    
    # ... variables ...
    
    # ❌ BUG : Le LLM a oublié d'encoder la précédence T2 → T3
    model.Add(fin_T1 <= debut_T2)  # T1 → T2 ✅
    # model.Add(fin_T2 <= debut_T3)  # T2 → T3 ❌ OUBLIÉE !
    
    solver = cp_model.CpSolver()
    solver.Solve(model)
    
    # OR-Tools trouve une "solution" qui viole T2 → T3
    return Planning(operations=[
        OperationPlanifiee(tache="T1", debut=0, fin=60),
        OperationPlanifiee(tache="T3", debut=10, fin=70),  # ❌ Commence avant T2 !
        OperationPlanifiee(tache="T2", debut=60, fin=120),
    ])
```

**Sans feasibility checker** :
```
Client reçoit un planning INVALIDE
  → T3 (Peinture) commence avant T2 (Assemblage)
  → 🔥 Désastre en production !
```

**Avec feasibility checker** :
```python
resultat = verifier_faisabilite(instance, planning)

# → ResultatFaisabilite:
#     valide = False
#     violations = [
#       "Précédence violée : T2 doit finir avant T3, "
#       "or T2 finit à 120 et T3 commence à 10"
#     ]

# ✅ Système détecte le bug
# ✅ Alerte l'humain
# ✅ NE RETOURNE PAS le planning au client
```

---

### Exemple 2 : Durée incorrecte

**Instance** :
```json
{
  "contraintes": [
    {
      "type": "compatibilite_ressource_tache",
      "tache": "T1",
      "ressource": "R1",
      "duree": 60  // 60 minutes
    }
  ]
}
```

**Code généré (bugué)** :
```python
# ❌ BUG : Le LLM a mal interprété la durée
duree_T1_sur_R1 = 6  # Il pense que c'est en heures !

model.Add(fin_T1 == debut_T1 + duree_T1_sur_R1)
```

**Planning retourné** :
```json
{
  "tache": "T1",
  "ressource": "R1",
  "debut": 0,
  "fin": 6  // ❌ 6 minutes au lieu de 60 !
}
```

**Sans feasibility checker** :
```
Client planifie 6 minutes pour une tâche qui prend 60 minutes
  → Retard de 54 minutes
  → Cascade de retards sur toutes les tâches suivantes
```

**Avec feasibility checker** :
```python
# Vérification : fin - debut doit égaler duree
# 6 - 0 = 6 ≠ 60 (attendu)

violations = [
  "Durée incorrecte pour T1 sur R1 : planning dit 6, "
  "contrainte exige 60"
]

# ✅ Bug détecté
# ✅ Planning rejeté
```

---

### Exemple 3 : Chevauchement de ressources

**Code généré (bugué)** :
```python
# ❌ BUG : Le LLM a oublié la contrainte NoOverlap
# pour les tâches sur la même ressource

# Il encode juste les précédences entre jobs
# mais pas la non-simultanéité sur une ressource
```

**Planning retourné** :
```json
{
  "operations": [
    {"tache": "T1", "ressource": "R1", "debut": 0, "fin": 60},
    {"tache": "T2", "ressource": "R1", "debut": 30, "fin": 90}
    // ❌ T1 et T2 se chevauchent sur R1 !
  ]
}
```

**Sans feasibility checker** :
```
Une ressource (machine, opérateur) doit faire 2 tâches en même temps
  → Impossible physiquement
  → Planning inapplicable
```

**Avec feasibility checker** :
```python
# Vérifie qu'aucune ressource n'a 2 tâches simultanées

violations = [
  "Chevauchement sur R1 : T1 [0,60] et T2 [30,90] "
  "se superposent pendant [30,60]"
]

# ✅ Détecté et bloqué
```

---

## 🔒 Positionnement du Feasibility Checker (§6.7)

### C'est un "Garde-fou" (Guardrail)

```
┌─────────────────────────────────────────────────────────┐
│  SYSTÈME PRISME                                          │
│                                                          │
│  1. LLM génère code solveur                             │
│      └─→ Validation cascade (offline, une fois)         │
│                                                          │
│  2. Code stocké (frozen, immutable)                     │
│                                                          │
│  3. À chaque exécution :                                │
│      a) Données ERP → InstanceTRCO                      │
│      b) Sandbox exécute solveur → Planning brut         │
│      c) 🔒 FEASIBILITY CHECKER (garde-fou §6.7)        │
│          └─→ BLOQUE si planning invalide               │
│      d) Si OK → Retour au client                       │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

**Le feasibility checker est la DERNIÈRE ligne de défense** avant que le planning n'arrive au client.

---

## 🎯 Pourquoi c'est NÉCESSAIRE dans PRISME

### 1. Le code n'est PAS testé unitairement

**Code classique** :
```python
def calculer_planning():
    # ...
    pass

# Tests unitaires
def test_respect_precedences():
    assert ...

def test_pas_de_chevauchement():
    assert ...

def test_durees_correctes():
    assert ...
```

**Code généré par LLM** :
```python
# Généré à la volée par l'IA
def resoudre(instance):
    # Code jamais vu avant
    # ❌ Pas de tests unitaires
    # ❌ Pas de review humaine
    # ❌ Peut contenir n'importe quel bug
    pass
```

### 2. La cascade de validation n'est PAS suffisante

**Ce que la cascade vérifie (Étape 5)** :
- ✅ Le solveur fonctionne sur l'instance de test
- ✅ Le solveur trouve l'optimum sur le synthetic bench
- ✅ Le solveur reproduit les cas de référence

**Ce que la cascade NE vérifie PAS** :
- ❌ Toutes les instances futures possibles
- ❌ Données corrompues ou aberrantes
- ❌ Edge cases non couverts par le bench

**Exemple** :
```
Cascade teste avec 3 tâches → ✅ OK

Client envoie 50 tâches avec pattern complexe
  → Bug apparaît seulement sur cette configuration
  → Sans feasibility checker : planning invalide en prod
```

### 3. Défense en profondeur (Defense in Depth)

**Principe de sécurité** : plusieurs couches de protection indépendantes

```
Couche 1 : Validation statique (AST allowlist)
  └─→ Bloque code malveillant, mais pas les bugs logiques

Couche 2 : Cascade de validation (offline)
  └─→ Teste sur instances connues, mais pas exhaustif

Couche 3 : 🔒 FEASIBILITY CHECKER (runtime, chaque exécution)
  └─→ Vérifie CHAQUE planning avant sortie
  └─→ Indépendant du solveur
  └─→ Pure vérification, pas de confiance aveugle
```

**Analogie** :
- Aviation : pilote + co-pilote + tour de contrôle
- Médecine : diagnostic + second avis + vérification pharmacien
- Banque : signature + validation manager + audit interne

---

## 📊 Comparaison Avec/Sans Feasibility Checker

### Scénario : Bug dans le code généré

| Aspect | Sans Feasibility Checker | Avec Feasibility Checker |
|--------|--------------------------|--------------------------|
| **Détection bug** | ❌ En production (trop tard) | ✅ Avant envoi au client |
| **Impact client** | 🔥 Planning invalide appliqué | ✅ Erreur détectée, pas appliqué |
| **Diagnostic** | ⏱️ Enquête manuelle longue | ✅ Violation précise identifiée |
| **Action** | 🚨 Urgence, rollback, perte confiance | ✅ Alerte, régénération, 0 impact |
| **Coût** | 💰💰💰 Très élevé | 💰 Faible (quelques ms) |

### Exemple réel d'incident évité

**Contexte** : Atelier avec 20 tâches, 5 ressources, précédences complexes

**Sans feasibility checker** :
```
1. Solveur généré a un bug subtil (NoOverlap mal encodé)
2. Planning retourné au client : 2 tâches se chevauchent sur R3
3. Client applique le planning
4. À 14h30, R3 doit faire T12 et T15 en même temps
5. 🔥 Production bloquée
6. Client appelle en urgence
7. Investigation : 2h pour identifier le bug
8. Régénération du solveur : 30 min
9. Nouveau planning : 15 min
10. Reprise production : 16h45
    → 2h15 de production perdues
    → Coût : plusieurs milliers d'euros
    → Confiance client ébranlée
```

**Avec feasibility checker** :
```
1. Solveur généré a le même bug
2. Sandbox exécute, retourne planning
3. 🔒 Feasibility checker détecte :
   "Chevauchement sur R3 : T12 [840, 900] et T15 [870, 930]"
4. Planning BLOQUÉ, pas envoyé au client
5. Système alerte : "Planning invalide, solveur défaillant"
6. Régénération automatique du solveur : 30 min
7. Nouveau planning valide : 2 min
8. Client reçoit planning correct
    → 32 min de latence (au lieu de 2h15)
    → 0 impact production
    → Confiance maintenue
```

---

## 🧪 Que Vérifie le Feasibility Checker ?

### 1. Précédences respectées

```python
for contrainte in instance.contraintes:
    if contrainte.type == "precedence":
        tache_avant = find_operation(planning, contrainte.avant)
        tache_apres = find_operation(planning, contrainte.apres)
        
        if tache_avant.fin > tache_apres.debut:
            # ❌ VIOLATION
            violations.append(
                f"{contrainte.avant} doit finir avant que "
                f"{contrainte.apres} ne commence"
            )
```

### 2. Compatibilité ressource-tâche (durée exacte)

```python
for contrainte in instance.contraintes:
    if contrainte.type == "compatibilite_ressource_tache":
        operation = find_operation(planning, contrainte.tache)
        
        if operation.ressource != contrainte.ressource:
            # ❌ Mauvaise ressource
            violations.append(...)
        
        duree_planifiee = operation.fin - operation.debut
        if duree_planifiee != contrainte.duree:
            # ❌ Durée incorrecte
            violations.append(
                f"Durée de {contrainte.tache} sur {contrainte.ressource} "
                f"doit être {contrainte.duree}, mais le planning dit "
                f"{duree_planifiee}"
            )
```

### 3. Pas de chevauchement sur une ressource

```python
operations_par_ressource = group_by(planning.operations, key="ressource")

for ressource, ops in operations_par_ressource.items():
    ops_triees = sorted(ops, key=lambda o: o.debut)
    
    for i in range(len(ops_triees) - 1):
        op1 = ops_triees[i]
        op2 = ops_triees[i + 1]
        
        if op1.fin > op2.debut:
            # ❌ Chevauchement
            violations.append(
                f"Chevauchement sur {ressource} : "
                f"{op1.tache} [{op1.debut}, {op1.fin}] et "
                f"{op2.tache} [{op2.debut}, {op2.fin}]"
            )
```

### 4. Une seule affectation par tâche

```python
taches_vues = set()

for operation in planning.operations:
    if operation.tache in taches_vues:
        # ❌ Tâche affectée plusieurs fois
        violations.append(
            f"Tâche {operation.tache} apparaît plusieurs fois "
            f"dans le planning"
        )
    taches_vues.add(operation.tache)
```

### 5. Cohérence temporelle

```python
for operation in planning.operations:
    if operation.debut < 0:
        violations.append(f"{operation.tache} : debut < 0")
    
    if operation.fin <= operation.debut:
        violations.append(
            f"{operation.tache} : fin <= debut (impossible)"
        )
    
    duree_calculee = operation.fin - operation.debut
    if duree_calculee <= 0:
        violations.append(f"{operation.tache} : durée ≤ 0")
```

---

## 💡 Pourquoi c'est RAPIDE

**Complexité** : O(n) où n = nombre d'opérations

```python
# Vérifier un planning de 100 tâches :
#   - Précédences : ~200 vérifications (O(contraintes))
#   - Durées : ~100 vérifications (O(tâches))
#   - Chevauchements : ~100 comparaisons (O(tâches) après tri)
#   - Total : ~400 opérations simples
#   → < 1ms sur machine moderne
```

**Coût négligeable** comparé à :
- Exécution solveur OR-Tools : 1-5 secondes
- Appel LLM (génération) : 30-60 secondes

---

## 🎓 Résumé : Pourquoi le Feasibility Checker ?

### 1. Le code est généré par une IA
   → Peut contenir des bugs même s'il compile

### 2. Dernière ligne de défense (§6.7)
   → Bloque TOUT planning invalide avant le client

### 3. Indépendant du solveur
   → Ne fait pas confiance aveuglément à OR-Tools

### 4. Diagnostic précis
   → Dit EXACTEMENT quelle contrainte est violée

### 5. Coût négligeable
   → < 1ms, imperceptible dans le flow

### 6. Sécurité du système
   → Principe "Defense in Depth"

---

## 🔄 Analogie Finale

**Imaginez un restaurant** :

```
Sans feasibility checker :
  Chef (LLM) → Plat servi directement au client
  ❌ Si le chef se trompe (trop salé, allergène oublié)
     → Client malade, restaurant fermé

Avec feasibility checker :
  Chef (LLM) → 🔒 Contrôle qualité → Client
  ✅ Vérification systématique :
     - Température OK ?
     - Pas d'allergènes ?
     - Portions correctes ?
  ✅ Si problème détecté → Plat refait
  ✅ Client reçoit toujours un plat correct
```

**PRISME = même principe** :
- Le LLM est le "chef" (peut se tromper)
- Le feasibility checker est le "contrôle qualité" (vérifie avant envoi)
- Le client reçoit toujours un planning valide

---

## 📚 Références

- [CLAUDE.md](../CLAUDE.md) - Section §6.7 sur les garde-fous
- [validation_engine/feasibility_checker.py](../validation_engine/feasibility_checker.py) - Implémentation
- [tests/unit/test_feasibility_checker.py](../tests/unit/test_feasibility_checker.py) - Tests

---

**En résumé** : Le feasibility checker n'est PAS redondant, c'est la **sécurité finale** qui garantit qu'un planning bugué ne sort JAMAIS du système, même si le code généré contient une erreur.

Sans lui, PRISME serait **dangereux en production**. Avec lui, on peut avoir **confiance** dans les plannings générés, même si le code du solveur n'est pas parfait.
