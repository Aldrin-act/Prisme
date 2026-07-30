# Guide : Génération du Solveur (Étape 4, mode single-shot legacy)

> Ce guide décrit `generation/tentative_unique.py` (un seul appel LLM, sans boucle de réparation
> ni choix d'algorithme) — utile pour l'itération rapide/économique en dev, mais **pas** le chemin
> de production : voir `generation/graph.py` (Étape 6, LangGraph) pour le pipeline réel, où un
> agent Benchmarker choisit l'algorithme par instance (`cp_sat` exact, ou une heuristique pour les
> grandes instances) avant la génération.

## 🎯 Objectif

Faire générer par un LLM (fournisseur configuré via `PRISME_LLM_PROVIDER` — Mistral par défaut,
voir `generation/agents/client_llm.py`) du code Python utilisant OR-Tools CP-SAT qui résout votre problème de scheduling.

**Innovation PRISME** : Le code est généré **UNE FOIS**, puis **ré-exécuté des milliers de fois** sur des données changeantes sans jamais rappeler le LLM.

---

## 📋 Vue d'ensemble

```
InstanceTRCO (JSON)
      ↓
┌─────────────────────────────────────┐
│  LLM (Claude/GPT)                   │
│  Prompt : "Génère un solveur        │
│            CP-SAT pour cette        │
│            instance T-R-C-O"        │
└──────────────┬──────────────────────┘
               ↓
Code Python généré (~150-300 lignes)
      ↓
Validation statique (AST allowlist)
      ↓
Exécution test
      ↓
Cascade de validation
      ↓
✅ Stockage (si VERT)
❌ Rejet (si ROUGE)
```

---

## 🚀 Étape 1 : Setup de l'environnement

### 1.1 Installer les dépendances LLM

```bash
# Dans le dossier du projet
cd C:\Users\ASUS\Desktop\PFE\Prisme\Prisme

# Installer uv si pas déjà fait
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Installer les extras LLM (anthropic, openai, mistralai)
uv sync --extra llm
```

**Ce qui est installé** :
- `anthropic` - SDK Anthropic Claude
- `openai` - SDK OpenAI GPT
- `mistralai` - SDK Mistral AI
- Leurs dépendances

### 1.2 Obtenir une clé API

Vous devez choisir **UN provider** :

#### Option A : Anthropic Claude (Recommandé ⭐)

**Pourquoi Claude ?**
- Meilleur pour la génération de code
- 5$ de crédit gratuit
- Modèle Sonnet 4.5 performant et économique

**Obtenir la clé** :
1. Aller sur https://console.anthropic.com/
2. Créer un compte (si pas déjà fait)
3. Aller dans "API Keys"
4. Créer une nouvelle clé
5. Copier la clé (commence par `sk-ant-...`)

**Configurer** :
```powershell
# PowerShell
$env:PRISME_LLM_PROVIDER = "anthropic"
$env:ANTHROPIC_API_KEY = "sk-ant-api03-VOTRE_CLE_ICI"
```

**Prix** : ~$0.003/1K tokens (input), ~$0.015/1K tokens (output)
- 1 génération ≈ 10K tokens ≈ **$0.05-0.10**

#### Option B : OpenAI GPT

**Obtenir la clé** :
1. Aller sur https://platform.openai.com/api-keys
2. Créer une clé API
3. Copier la clé (commence par `sk-...`)

**Configurer** :
```powershell
$env:PRISME_LLM_PROVIDER = "openai"
$env:OPENAI_API_KEY = "sk-VOTRE_CLE_ICI"
```

**Prix** : GPT-4 ~$0.03/1K tokens
- 1 génération ≈ **$0.30-0.50** (plus cher que Claude)

#### Option C : Mistral AI

**Obtenir la clé** :
1. Aller sur https://console.mistral.ai/
2. API Keys
3. Créer une clé

**Configurer** :
```powershell
$env:PRISME_LLM_PROVIDER = "mistralai"
$env:MISTRAL_API_KEY = "VOTRE_CLE_ICI"
```

---

## 🎬 Étape 2 : Première Génération

### 2.1 Vérifier la configuration

```bash
# Vérifier que les variables sont bien définies
echo $env:PRISME_LLM_PROVIDER
echo $env:ANTHROPIC_API_KEY  # (ou OPENAI_API_KEY, MISTRAL_API_KEY)
```

### 2.2 Lancer la génération

```bash
uv run python -m scripts.generer_premier_solveur
```

**Ce qui va se passer** :
```
1. Charge l'instance (atelier_trois_taches.json)
2. Envoie au LLM avec prompt structuré
3. LLM génère du code Python (~30-60 secondes)
4. Validation statique (AST allowlist)
5. Exécution test sur l'instance
6. Cascade de validation :
   - Feasibility checker ✅
   - Optimalité (synthetic bench) ✅
   - Fidélité (reference cases) ✅
7. Si tout est VERT : Code sauvegardé
```

**Output attendu** :
```
🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖
  GÉNÉRATION D'UN SOLVEUR AVEC LE LLM
🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖🤖

📋 Étape 1 : Chargement de l'instance
   ✅ Instance chargée :
      - 3 tâches
      - 2 ressources
      - 6 contraintes

🤖 Étape 2 : Génération du code par le LLM
   ⏱️  Cela peut prendre 30-60 secondes...
   💰 Coût estimé : ~$0.05-0.10

   [Appel LLM en cours...]

======================================================================
  RÉSULTATS DE LA GÉNÉRATION
======================================================================

✅ GÉNÉRATION RÉUSSIE !

📊 Verdict de la cascade : VerdictCascade(vert=True, ...)

💾 Code sauvegardé : solveur_genere.py
   2847 caractères

📄 Extrait (10 premières lignes) :
   ------------------------------------------------------------------
   from ortools.sat.python import cp_model
   from dsl.schema.instance import InstanceTRCO
   from dsl.schema.planning import Planning, OperationPlanifiee
   
   def resoudre(instance: InstanceTRCO) -> Planning | None:
       """Résout le problème de scheduling FJSP."""
       model = cp_model.CpModel()
       
       # Variables : intervalles pour chaque tâche
       ...
   ------------------------------------------------------------------

🔍 Détails de la validation :
   - Faisabilité : ✅ 100% (tous les plannings valides)
   - Optimalité : ✅ 34/34 optimaux (100%)
   - Fidélité : ✅ 3/3 fidèles

🎯 Prochaines étapes :
   1. Examinez le code généré : cat solveur_genere.py
   2. Enregistrez-le dans solver_store/
   3. Testez l'exécution dans le sandbox
```

---

## 📊 Étape 3 : Examiner le code généré

```bash
# Lire le code
cat solveur_genere.py

# Ou ouvrir dans VS Code
code solveur_genere.py
```

**Structure typique du code généré** :
```python
from ortools.sat.python import cp_model
from dsl.schema.instance import InstanceTRCO
from dsl.schema.planning import Planning, OperationPlanifiee

def resoudre(instance: InstanceTRCO) -> Planning | None:
    """Résout le problème de scheduling FJSP."""
    
    model = cp_model.CpModel()
    
    # 1. Variables : intervalles pour chaque tâche
    taches_intervals = {}
    for tache in instance.taches:
        # Pour chaque compatibilité ressource-tâche
        intervals_par_ressource = []
        for contrainte in instance.contraintes:
            if contrainte.type == "compatibilite_ressource_tache" \
               and contrainte.tache == tache.id:
                # Créer variable intervalle
                debut = model.NewIntVar(0, horizon, f"debut_{tache.id}_{contrainte.ressource}")
                fin = model.NewIntVar(0, horizon, f"fin_{tache.id}_{contrainte.ressource}")
                intervalle = model.NewIntervalVar(
                    debut, contrainte.duree, fin,
                    f"interval_{tache.id}_{contrainte.ressource}"
                )
                intervals_par_ressource.append(intervalle)
        
        taches_intervals[tache.id] = intervals_par_ressource
    
    # 2. Contraintes de précédence
    for contrainte in instance.contraintes:
        if contrainte.type == "precedence":
            # fin(avant) <= debut(apres)
            model.Add(...)
    
    # 3. Contraintes de non-chevauchement (par ressource)
    for ressource in instance.ressources:
        intervals_sur_ressource = [...]
        model.AddNoOverlap(intervals_sur_ressource)
    
    # 4. Objectif : minimiser makespan
    makespan = model.NewIntVar(0, horizon, "makespan")
    for tache in instance.taches:
        model.Add(makespan >= fin_tache)
    model.Minimize(makespan)
    
    # 5. Résolution
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    
    if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
        # Construire Planning
        operations = []
        for tache in instance.taches:
            operation = OperationPlanifiee(
                tache=tache.id,
                ressource=...,
                debut=solver.Value(debut_var),
                fin=solver.Value(fin_var),
            )
            operations.append(operation)
        
        return Planning(operations=operations)
    
    return None  # Infeasible
```

**Points importants** :
- ✅ Utilise `ortools.sat.python.cp_model`
- ✅ Signature : `def resoudre(instance: InstanceTRCO) -> Planning | None`
- ✅ Encode toutes les contraintes (précédences, compatibilités, NoOverlap)
- ✅ Objectif : minimiser makespan
- ✅ Retourne `Planning` ou `None` (si infeasible)

---

## 🔍 Étape 4 : Comprendre la Cascade de Validation

Le code généré passe par **3 briques** de validation :

### Brique 1 : Faisabilité

**Teste** : Toutes les instances réelles (exemples + vos données)

**Critère** : Planning valide (contraintes respectées)

**Comment** : Feasibility checker vérifie :
- ✅ Précédences respectées
- ✅ Durées correctes
- ✅ Pas de chevauchement
- ✅ Ressources compatibles

**Si échec** : Solveur REJETÉ (code génère des plannings illégaux)

### Brique 2 : Optimalité

**Teste** : Synthetic bench (34 instances, 1→80 tâches)

**Critère** : Makespan = optimum connu

**Comment** : Chaque instance du bench a un optimum prouvable par construction

**Si échec** : Solveur ORANGE (sous-optimal, mais pas bloquant)

### Brique 3 : Fidélité

**Teste** : Reference cases (3 cas métier)

**Critère** : Même affectation tâche→ressource + même makespan

**Comment** : Compare avec des plannings attendus par le métier

**Si échec** : Solveur ORANGE (ne reproduit pas les cas métier)

### Verdict Final

| Verdict | Condition | Action |
|---------|-----------|--------|
| **VERT** ✅ | 3 briques OK | Solveur enregistré dans solver_store/ |
| **ORANGE** ⚠️ | Faisabilité OK, autres partielles | Alerte humain, décision manuelle |
| **ROUGE** ❌ | Faisabilité échouée | Solveur REFUSÉ |

---

## 🐛 Étape 5 : Que faire si ça échoue ?

### Cas 1 : Erreur de configuration

```
❌ Erreur : No API key provided
```

**Solution** :
```powershell
# Vérifier la variable
echo $env:ANTHROPIC_API_KEY

# Si vide, redéfinir
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

### Cas 2 : Génération échouée (ROUGE)

```
❌ GÉNÉRATION ÉCHOUÉE
Verdict : ROUGE
   ❌ Faisabilité : échec
      - instance_1 : Précédence violée
```

**Causes possibles** :
1. LLM a oublié d'encoder une contrainte
2. Bug dans le code généré
3. Modèle LLM pas assez performant

**Solutions** :
1. **Relancer** : Parfois ça passe au 2ème essai
2. **Changer de modèle** : Essayer Claude Opus ou GPT-4
3. **Simplifier l'instance** : Tester sur 2 tâches d'abord

### Cas 3 : Optimalité échouée (ORANGE)

```
⚠️  Verdict : ORANGE
   ✅ Faisabilité : OK
   ❌ Optimalité : 28/34 optimaux
```

**Cause** : Code génère des solutions sous-optimales

**Solution** :
- Accepter (le solveur fonctionne, juste pas optimal)
- Ou améliorer les prompts (Étape 6 : boucle de réparation)

---

## 📈 Étape 6 : Mesurer le Taux de Succès

Une fois que vous avez généré **UN** solveur avec succès, testez sur **toutes les instances** :

```bash
uv run python -m scripts.mesurer_taux_succes_generation
```

**Ce script** :
1. Charge les 34 instances du synthetic bench
2. Pour chaque instance : génère un solveur
3. Lance la cascade
4. Mesure : % VERT, % ORANGE, % ROUGE

**Output attendu** :
```
34 générations lancées...
⏱️  Durée estimée : 20-30 minutes
💰 Coût estimé : 34 × $0.08 = $2.72

Résultats :
  ✅ VERT : 24/34 (70.6%)
  ⚠️  ORANGE : 8/34 (23.5%)
  ❌ ROUGE : 2/34 (5.9%)

Taux de succès : 70.6%
```

**Interprétation** :
- **> 70%** : Bon (acceptable pour démo)
- **> 85%** : Très bon (production envisageable)
- **< 50%** : Mauvais (changer de modèle ou améliorer prompts)

---

## 🎯 Étape 7 : Enregistrer le Solveur

Si votre solveur est **VERT**, enregistrez-le dans `solver_store/` :

```python
# enregistrer_solveur.py

from solver_store.registry import Registre
from pathlib import Path

# Charger le code généré
with open("solveur_genere.py", "r") as f:
    code = f.read()

# Créer le registre
registre = Registre()

# Enregistrer
registre.enregistrer(
    client_id="client_test_1",
    signature_contraintes="compatibilite_ressource_tache,precedence",
    code_bytes=code.encode("utf-8"),
    verdict=resultat.verdict,
)

print("✅ Solveur enregistré dans solver_store/")
```

**Ce qui se passe** :
- Code sauvegardé dans `solver_store/artifacts/<sha256>.py`
- Métadonnées dans PostgreSQL (ou in-memory si pas de DB)
- Indexé par `client_id` + `signature`

---

## 🚀 Étape 8 : Exécuter le Solveur (Sandbox)

Maintenant que le solveur est enregistré, exécutez-le sur de **nouvelles données** :

```bash
uv run python -m scripts.demo_bout_en_bout
```

**Flow** :
```
1. Charge nouvelle instance
2. Lookup solveur (trouve celui enregistré)
3. Sandbox Docker exécute le code
4. Feasibility checker vérifie le planning
5. Planning JSON retourné
```

**Output** :
```json
{
  "operations": [
    {"tache": "T1", "ressource": "R1", "debut": 0, "fin": 60},
    {"tache": "T2", "ressource": "R2", "debut": 60, "fin": 150},
    {"tache": "T3", "ressource": "R1", "debut": 150, "fin": 240}
  ],
  "makespan": 240
}
```

---

## 📊 Récapitulatif : Où vous en êtes

```
✅ Étape 1 : DSL T-R-C-O
✅ Étape 2 : Feasibility Checker
✅ Étape 3 : Synthetic Bench
🔄 Étape 4 : GÉNÉRATION (vous êtes ici)
⏳ Étape 5 : Cascade (automatique après génération)
❌ Étape 6 : Boucle réparation (skippée)
⏳ Étape 7 : Stockage (après génération réussie)
⏳ Étape 8 : Exécution (après stockage)
```

---

## 🎓 Checklist : Prêt pour la Génération

- [ ] `uv` installé
- [ ] `uv sync --extra llm` exécuté
- [ ] Clé API obtenue (Anthropic/OpenAI)
- [ ] Variables d'environnement définies (`PRISME_LLM_PROVIDER`, `*_API_KEY`)
- [ ] Instance test disponible (`dsl/examples/valid/atelier_trois_taches.json`)

**Si tout est coché, lancez** :
```bash
uv run python -m scripts.generer_premier_solveur
```

---

## 💡 Conseils

1. **Commencez petit** : 2-3 tâches d'abord
2. **Claude > GPT** : Meilleur pour le code, moins cher
3. **Budget** : Prévoyez $5-10 pour vos tests
4. **Patience** : Première génération = 30-60s
5. **Persistence** : Si échec, relancez (non-déterministe)

---

## 🆘 Besoin d'aide ?

**Erreur commune** | **Solution**
---|---
`No module named 'anthropic'` | `uv sync --extra llm`
`No API key provided` | Définir `$env:ANTHROPIC_API_KEY`
`Generation failed: ROUGE` | Relancer ou changer de modèle
`Timeout error` | Augmenter timeout (modèle surchargé)

---

## 📚 Prochaines étapes après génération

1. ✅ **Vous avez généré un solveur VERT**
   → Enregistrez-le dans `solver_store/`
   → Testez l'exécution dans le sandbox
   → Lancez l'API et le dashboard

2. ⚠️ **Vous avez ORANGE/ROUGE**
   → Analysez les diagnostics
   → Essayez un autre modèle
   → Simplifiez l'instance

3. 🚀 **Vous voulez aller plus loin**
   → Implémentez la boucle de réparation (Étape 6)
   → Mesurez le taux de succès sur tout le bench
   → Étendez le DSL (nouvelles contraintes)

---

**Prêt à générer votre premier solveur ?** 🤖

```bash
uv run python -m scripts.generer_premier_solveur
```
