# Timeline des Validations : Quand utilise-t-on quoi ?

## ❓ La Question

> "Quand est-ce qu'on utilise le feasibility checker ? Avant ou après ? Là on n'a pas de solveur..."

**Réponse** : Il y a **2 moments distincts** dans PRISME, avec des validations différentes à chaque moment.

---

## ⏱️ Timeline Complète

```
═══════════════════════════════════════════════════════════════════════
MOMENT 1 : GÉNÉRATION (Une seule fois, offline)
═══════════════════════════════════════════════════════════════════════

Trigger : Nouveau client OU nouvelle signature de contraintes

┌─────────────────────────────────────────────────────────────────┐
│ 1. INGESTION                                                     │
│    ERP → Adaptateur → InstanceTRCO                              │
│    Validation : Pydantic (§6.7 upstream guardrail)              │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. GÉNÉRATION DU CODE                                           │
│    Benchmarker choisit l'algorithme (cp_sat, ou une heuristique │
│    genetic/aco/tabu/... pour les grandes instances), puis le    │
│    LLM génère le code Python pour cet algorithme                │
│    Validation : AST allowlist (pas d'eval, exec, etc.)         │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. CASCADE DE VALIDATION (Étape 5)                              │
│                                                                  │
│    a) Exécution test sur l'instance source                      │
│       Code → Planning de test                                   │
│                                                                  │
│    b) ✅ FEASIBILITY (1ère utilisation !)                      │
│       Vérifie le planning de test                               │
│       → Si invalide : solveur REJETÉ                            │
│                                                                  │
│    c) Optimalité (synthetic bench)                              │
│       → Makespan = optimum connu ?                              │
│                                                                  │
│    d) Fidélité (reference cases)                                │
│       → Reproduit les cas attendus ?                            │
│                                                                  │
│    Verdict : VERT / ORANGE / ROUGE                              │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. STOCKAGE (seulement si VERT)                                 │
│    solver_store/artifacts/<sha256>.py                           │
│    + métadonnées dans PostgreSQL                                │
│                                                                  │
│    ⚠️  Si pas VERT : Solveur REFUSÉ, alerte humain            │
└─────────────────────────────────────────────────────────────────┘

Durée totale : ~1 minute
Coût : ~$0.10 (appel LLM)
Fréquence : RARE (nouvelle signature seulement)


═══════════════════════════════════════════════════════════════════════
MOMENT 2 : EXÉCUTION (À chaque fois, en production)
═══════════════════════════════════════════════════════════════════════

Trigger : Nouvelles données (planning à calculer)

┌─────────────────────────────────────────────────────────────────┐
│ 1. INGESTION (encore)                                           │
│    Nouvelles données ERP → InstanceTRCO                         │
│    Validation : Pydantic                                        │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. LOOKUP SOLVEUR                                               │
│    Cherche dans solver_store/ par :                             │
│      - client_id                                                │
│      - signature contraintes                                    │
│                                                                  │
│    Résultat : Récupère le code frozen (déjà validé à Moment 1) │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. EXÉCUTION SANDBOX                                            │
│    Docker exécute le code avec la nouvelle instance             │
│    → Planning brut retourné                                     │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. ✅ FEASIBILITY CHECKER (2ème utilisation !)                 │
│                                                                  │
│    Vérifie le planning sur les NOUVELLES données               │
│                                                                  │
│    Pourquoi encore ? Car :                                      │
│      - Les données ont changé depuis Moment 1                   │
│      - Peuvent être corrompues                                  │
│      - Edge case non testé par la cascade                       │
│      - Bug subtil qui apparaît sur cette config                 │
│                                                                  │
│    Si invalide : Planning BLOQUÉ, alerte, diagnostic            │
└──────────────────────┬──────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────────────────┐
│ 5. OUTPUT                                                        │
│    Planning JSON envoyé au client                               │
└─────────────────────────────────────────────────────────────────┘

Durée totale : ~2-3 secondes
Coût : $0 (pas d'appel LLM)
Fréquence : FRÉQUENTE (à chaque nouveau besoin de planning)
```

---

## 🎯 Réponse Directe à la Question

### Quand utilise-t-on le feasibility checker ?

**Il est utilisé 2 FOIS** :

1. **Moment 1 (Génération)** : Dans la CASCADE
   - Pour valider le code généré
   - Sur l'instance de test
   - Partie de la brique "Faisabilité" de la cascade

2. **Moment 2 (Exécution)** : Après le SANDBOX
   - Pour valider le planning produit
   - Sur les nouvelles données
   - Garde-fou final avant le client

### Pourquoi 2 fois ?

```
Moment 1 : Valide que le CODE est bon
  "Ce solveur génère-t-il des plannings valides ?"
  
Moment 2 : Valide que le PLANNING est bon
  "Ce planning spécifique est-il valide pour ces données ?"
```

---

## 📍 Où vous êtes actuellement

```
✅ Étape 1 : DSL T-R-C-O               [Terminé]
✅ Étape 2 : Feasibility Checker       [Terminé - code existe]
✅ Étape 3 : Synthetic Bench           [Terminé]
✅ Étape 4 : Générateur                [Terminé - code existe]
✅ Étape 5 : Cascade                   [Terminé - code existe]
✅ Étape 7 : Store + Sandbox           [Terminé]

🔴 VOUS ÊTES ICI : Pas encore testé le flow complet avec un vrai solveur
```

**Ce que vous avez** :
- ✅ Le CODE du feasibility checker existe (`validation_engine/feasibility_checker.py`)
- ✅ Il est testé unitairement (`tests/unit/test_feasibility_checker.py`)
- ✅ Un solveur de référence (hand-written) existe dans `scripts/_solveur_minimal.py`

**Ce que vous N'AVEZ PAS encore fait** :
- ❌ Générer un solveur avec le LLM (Moment 1)
- ❌ Tester le flow complet end-to-end avec génération

---

## 🚀 Comment tester MAINTENANT (sans générer de code LLM)

### Option A : Flow complet avec solveur de référence

```bash
# 1. Enregistrer le solveur minimal (hand-written)
uv run python -m scripts.enregistrer_solveur_reference

# Ce script :
#   - Charge le solveur minimal
#   - Lance la cascade (incluant feasibility checker)
#   - Si VERT : enregistre dans solver_store/
```

**Ce qui se passe** :
```python
# Dans enregistrer_solveur_reference.py

# 1. Charge le solveur hand-written
from scripts._solveur_minimal import resoudre

# 2. Wrappe en callable pour la cascade
def solveur(instance):
    return resoudre(instance)

# 3. Lance la cascade (MOMENT 1)
verdict = evaluer_cascade(solveur)
#   ├─→ Faisabilité : exécute + feasibility checker ✅
#   ├─→ Optimalité : teste sur bench
#   └─→ Fidélité : teste sur reference cases

# 4. Si VERT : enregistre
if verdict.est_vert():
    registre.enregistrer(
        client_id="reference",
        code=get_source(resoudre),
        verdict=verdict
    )
```

### Option B : Tester juste le feasibility checker

```python
# test_feasibility_manuel.py

from dsl.validation.charger_instance import charger_instance_depuis_fichier
from dsl.schema.planning import Planning, OperationPlanifiee
from validation_engine.feasibility_checker import verifier_faisabilite

# 1. Charger une instance
instance = charger_instance_depuis_fichier(
    "dsl/examples/valid/atelier_trois_taches.json"
)

# 2. Créer un planning VALIDE
planning_valide = Planning(operations=[
    OperationPlanifiee(tache="T1", ressource="R1", debut=0, fin=60),
    OperationPlanifiee(tache="T2", ressource="R2", debut=60, fin=150),
    OperationPlanifiee(tache="T3", ressource="R1", debut=60, fin=150),
])

# 3. Vérifier (devrait passer)
resultat = verifier_faisabilite(instance, planning_valide)
print(f"Valide : {resultat.valide}")  # True
print(f"Violations : {resultat.violations}")  # []

# 4. Créer un planning INVALIDE (viole précédence)
planning_invalide = Planning(operations=[
    OperationPlanifiee(tache="T2", ressource="R2", debut=0, fin=90),   # T2 avant T1 !
    OperationPlanifiee(tache="T1", ressource="R1", debut=60, fin=120),
    OperationPlanifiee(tache="T3", ressource="R1", debut=120, fin=210),
])

# 5. Vérifier (devrait échouer)
resultat = verifier_faisabilite(instance, planning_invalide)
print(f"Valide : {resultat.valide}")  # False
print(f"Violations : {resultat.violations}")
# ["Précédence violée : T1 doit finir avant T2..."]
```

### Option C : Flow end-to-end complet

```bash
# 1. Enregistrer le solveur de référence
uv run python -m scripts.enregistrer_solveur_reference

# 2. Lancer la démo bout-en-bout
uv run python -m scripts.demo_bout_en_bout

# Ce script fait TOUT le flow :
#   - Charge instance
#   - Lookup solveur (trouve le référence)
#   - Exécute dans sandbox (MOMENT 2)
#   - Feasibility checker ✅ (vérifie le planning)
#   - Retourne Planning JSON
```

---

## 📊 Schéma : Les 2 Utilisations du Feasibility Checker

```
╔═══════════════════════════════════════════════════════════════╗
║  MOMENT 1 : GÉNÉRATION (offline, une fois)                    ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Instance Test                                                ║
║       ↓                                                       ║
║  Code généré par LLM                                          ║
║       ↓                                                       ║
║  Exécution                                                    ║
║       ↓                                                       ║
║  Planning Test                                                ║
║       ↓                                                       ║
║  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓                      ║
║  ┃ 🔒 FEASIBILITY CHECKER #1        ┃                      ║
║  ┃ (dans la cascade)                 ┃                      ║
║  ┃                                    ┃                      ║
║  ┃ Question : "Le CODE est-il bon ?" ┃                      ║
║  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛                      ║
║       ↓                                                       ║
║  Verdict : VERT → Stockage                                   ║
║  Verdict : ROUGE → Rejet                                     ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝

        (Temps passe... nouvelles données arrivent)

╔═══════════════════════════════════════════════════════════════╗
║  MOMENT 2 : EXÉCUTION (runtime, chaque fois)                 ║
╠═══════════════════════════════════════════════════════════════╣
║                                                               ║
║  Nouvelles Données                                            ║
║       ↓                                                       ║
║  Lookup Code (déjà validé)                                   ║
║       ↓                                                       ║
║  Sandbox exécute                                             ║
║       ↓                                                       ║
║  Planning Produit                                            ║
║       ↓                                                       ║
║  ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓            ║
║  ┃ 🔒 FEASIBILITY CHECKER #2               ┃            ║
║  ┃ (garde-fou opérationnel)                 ┃            ║
║  ┃                                           ┃            ║
║  ┃ Question : "Ce PLANNING spécifique       ┃            ║
║  ┃            est-il valide pour ces         ┃            ║
║  ┃            données ?"                     ┃            ║
║  ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛            ║
║       ↓                                                       ║
║  Valide → Client reçoit le planning                          ║
║  Invalide → Bloqué + Alerte                                  ║
║                                                               ║
╚═══════════════════════════════════════════════════════════════╝
```

---

## 💡 Pourquoi 2 fois ? Exemple Concret

### Scénario : Bug qui apparaît seulement sur certaines données

**Moment 1 (Génération)** :
```python
# Code généré par le LLM
def resoudre(instance):
    # Bug subtil : ne gère pas bien les instances > 20 tâches
    # Mais le test de la cascade utilise 3 tâches
    # → Passe la validation ✅
    pass

# Cascade teste sur :
#   - Instance source : 3 tâches → OK ✅
#   - Synthetic bench : 10-80 tâches → Makespan OK, mais...
#                        le bug n'affecte pas l'optimalité, juste la faisabilité
#                        sur un pattern spécifique ❌ non détecté

# Verdict : VERT (cascade incomplète)
# → Solveur enregistré
```

**Moment 2 (Exécution)** :
```python
# Client envoie 25 tâches avec un pattern qui trigger le bug
# (ex: beaucoup de précédences croisées)

# Sandbox exécute
planning = sandbox.executer(instance_25_taches)

# Planning contient une violation (le bug s'est manifesté)

# 🔒 Feasibility Checker #2 détecte :
violations = [
    "Précédence violée : T12 doit finir avant T18, "
    "or T12 finit à 350 et T18 commence à 300"
]

# ✅ Planning BLOQUÉ
# ✅ Alerte : "Solveur défaillant sur cette config"
# ✅ Diagnostic pour comprendre le pattern problématique
# ✅ Client ne reçoit PAS le planning bugué
```

**Sans le feasibility checker #2** :
```
Le planning bugué serait envoyé au client
  → Production cassée
  → Incident
```

---

## 🎓 Résumé

### Le feasibility checker est utilisé :

| Moment | Quand | Sur quoi | Pourquoi | Bloque si... |
|--------|-------|----------|----------|--------------|
| **#1 Génération** | Cascade de validation | Planning test (instance source) | Valider le CODE | Code génère des plannings invalides |
| **#2 Exécution** | Après sandbox | Planning produit (nouvelles données) | Valider le PLANNING | Planning spécifique invalide (données corrompues, edge case, bug subtil) |

### Pour tester maintenant (sans LLM) :

```bash
# Option la plus simple : flow complet avec solveur référence
uv run python -m scripts.enregistrer_solveur_reference  # Moment 1
uv run python -m scripts.demo_bout_en_bout              # Moment 2
```

**Est-ce plus clair maintenant ?** 🙂
