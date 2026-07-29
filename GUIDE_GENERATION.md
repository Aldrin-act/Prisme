# Guide de génération de solveur

Ce guide explique comment générer un nouveau solveur CP-SAT avec le pipeline multi-agents de PRISME.

## 🎯 Qu'est-ce qu'une génération ?

La génération est le **MOMENT 1** du cycle PRISME : un pipeline de 9 agents IA écrit le code d'un solveur CP-SAT qui résout le problème FJSP (Flexible Job-Shop Scheduling Problem).

**Une fois généré, ce code est :**
- ✅ Validé par la cascade (faisabilité + optimalité + fidélité)
- ✅ Persisté dans `solver_store/`
- ✅ Réexécutable à l'infini sans rappeler l'IA (MOMENT 2)

## 📋 Prérequis

### 1. Dépendances LLM installées

```bash
uv sync --extra llm
```

Cela installe :
- `mistralai` (Mistral AI)
- `anthropic` (Claude)
- `openai` (OpenAI GPT)

### 2. Clé API configurée

Vérifiez votre `.env` :

```bash
# Provider utilisé
PRISME_LLM_PROVIDER=mistral   # ou anthropic ou openai

# Clés API (remplir celle de votre provider)
MISTRAL_API_KEY=votre_cle_ici
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
```

**Votre configuration actuelle** :
- ✅ Provider : `mistral`
- ✅ Clé Mistral : Configurée

### 3. Mission définie

Le pipeline génère un solveur basé sur `generation/mission.md` (mission par défaut : résoudre FJSP avec précédence + compatibilité ressource-tâche).

## 🚀 Options de génération

Vous avez 3 scripts principaux :

### Option 1 : Pipeline standard (recommandé)

**Script** : `generer_multi_agents.py`

**Agents** : 8 agents séquentiels
1. Analyste → Spécification
2. Architecte → Conception
3. Développeur → Code
4. Testeur → Tests
5. Reviewer → Revue
6. Debugger → Corrections (si bugs)
7. Optimiseur → Optimisation
8. Documentation → Doc

**Durée** : 2-5 minutes

**Coût** : ~$0.50-1.00

**Commande** :
```bash
uv run python -m scripts.generer_multi_agents
```

### Option 2 : Pipeline avec boucle de réparation

**Script** : `generer_avec_boucle.py`

**Identique à Option 1, mais avec** :
- 🔁 Boucle de réparation si validation échoue
- 🐛 Debugger automatique (max 3 tentatives)
- 📊 Historique des tentatives

**Durée** : 3-10 minutes (selon nombre de tentatives)

**Coût** : ~$1.00-3.00

**Commande** :
```bash
uv run python -m scripts.generer_avec_boucle
```

### Option 3 : Génération + exécution GreenSig

**Script** : `generer_et_executer_greensig.py`

**Workflow complet** :
1. Génère le solveur (pipeline multi-agents)
2. Exécute sur une instance GreenSig de test (3 tâches)
3. Affiche le planning résultant

**Durée** : 2-5 minutes

**Coût** : ~$0.50-1.00

**Commande** :
```bash
uv run python -m scripts.generer_et_executer_greensig
```

## ⚙️ Étapes d'une génération

Quelle que soit l'option choisie, voici ce qui se passe :

```
┌─────────────────────────────────────────────────────────┐
│ 1. ANALYSTE                                             │
│    Analyse la mission → spécification technique         │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 2. ARCHITECTE                                           │
│    Conception du modèle CP-SAT                          │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 3. DÉVELOPPEUR                                          │
│    Génère le code Python (fonction resoudre)           │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 4. VALIDATION STATIQUE                                  │
│    Vérifie l'AST (allowlist : ortools, dsl, etc.)      │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 5. EXÉCUTION                                            │
│    Teste le code sur une instance simple               │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 6. CASCADE DE VALIDATION                                │
│    ✓ Faisabilité (toutes instances)                    │
│    ✓ Optimalité (banc synthétique)                     │
│    ✓ Fidélité (cas de référence)                       │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 7. TESTEUR (si cascade OK)                             │
│    Génère des tests pytest                             │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 8. REVIEWER                                             │
│    Revoit le code, suggère améliorations               │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 9. OPTIMISEUR (optionnel)                              │
│     Optimise le code si déjà fonctionnel               │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│ 10. DOCUMENTATION                                       │
│     Génère la documentation Markdown                    │
└─────────────────────────────────────────────────────────┘
```

## 📊 Résultats attendus

### Succès ✅

```
✅ GÉNÉRATION RÉUSSIE

📝 Fichiers générés :
   • solveur_genere.py (code du solveur)
   • test_solveur_genere.py (tests pytest)
   • solveur_genere_doc.md (documentation)

📊 Métriques :
   • Durée totale : 3.2 min
   • Coût estimé : $0.78
   • Tokens : 45,234
   • Cascade : ✅ VERT (faisabilité + optimalité + fidélité)

🎯 Prochaine étape :
   • Enregistrer dans solver_store/ : scripts/enregistrer_solveur_reference.py
   • Tester en sandbox : voir sandbox/README.md
```

### Échec ❌

```
❌ GÉNÉRATION ÉCHOUÉE

🔴 Raison : Cascade de validation ROUGE
   • Faisabilité : ✅ OK
   • Optimalité : ❌ ÉCHEC (3/10 instances optimales attendues)
   • Fidélité : ⚠️ PARTIEL

💡 Suggestions :
   • Relancer avec generer_avec_boucle.py (tentatives multiples)
   • Vérifier les logs du Debugger
   • Consulter generation/failures/ pour diagnostics
```

## 🛠️ Commandes rapides

### Génération simple (recommandé pour démarrer)

```bash
uv run python -m scripts.generer_multi_agents
```

### Génération robuste (boucle de réparation)

```bash
uv run python -m scripts.generer_avec_boucle
```

### Génération + test immédiat sur GreenSig

```bash
uv run python -m scripts.generer_et_executer_greensig
```

## 📁 Fichiers générés

Après une génération réussie :

```
.
├── solveur_genere.py              # Code du solveur
├── test_solveur_genere.py         # Tests pytest
├── solveur_genere_doc.md          # Documentation
└── generation/                    # Logs internes
    └── failures/                  # Diagnostics (si échecs)
```

## 🔍 Troubleshooting

### Erreur : "No API key found"

➡️ **Solution** : Vérifiez votre `.env`

```bash
# Vérifier
cat .env | grep MISTRAL_API_KEY

# Configurer
# Éditez .env et ajoutez votre clé
MISTRAL_API_KEY=votre_cle_ici
```

### Erreur : "Module 'mistralai' not found"

➡️ **Solution** : Installez les dépendances LLM

```bash
uv sync --extra llm
```

### Génération très lente (>10 min)

➡️ **Causes possibles** :
- Provider saturé (retry automatiques)
- Rate limiting API
- Connexion lente

➡️ **Solution** : Patience ou changez de provider

### Cascade ROUGE (échec validation)

➡️ **Solution** : Utilisez `generer_avec_boucle.py` qui retentera automatiquement

## 💰 Coûts estimés par provider

| Provider | Coût/génération | Modèle par défaut |
|----------|-----------------|-------------------|
| Mistral | $0.50-1.00 | Mistral Large |
| Anthropic | $0.50-1.00 | Claude Sonnet 4.5 |
| OpenAI | $2.00-5.00 | GPT-4 |

**Note** : Coûts indicatifs, varient selon la complexité de la mission.

## 🎯 Que faire après une génération réussie ?

1. **Tester le solveur généré** :
   ```bash
   uv run pytest test_solveur_genere.py -v
   ```

2. **Exécuter sur une vraie instance** :
   ```python
   from solveur_genere import resoudre
   from dsl.schema import InstanceTRCO
   import json

   # Charger instance
   with open("greensig_instance_trco_reel.json") as f:
       instance = InstanceTRCO.model_validate(json.load(f))

   # Résoudre
   planning = resoudre(instance)
   ```

3. **Enregistrer dans solver_store** :
   ```bash
   # Adapter scripts/enregistrer_solveur_reference.py
   # pour charger votre solveur généré au lieu de _solveur_minimal
   ```

4. **Comparer avec le solveur de référence** :
   ```bash
   # Exécuter les deux sur la même instance
   # Comparer makespan, temps de résolution
   ```

## 📚 Références

- **Mission** : `generation/mission.md`
- **Prompts agents** : `generation/prompts/*.md`
- **Pipeline** : `generation/pipeline_multi_agents.py`
- **Cascade** : `validation_engine/cascade.py`

## ✨ Prêt à générer !

**Commande recommandée pour démarrer** :

```bash
uv run python -m scripts.generer_avec_boucle
```

Bonne génération ! 🚀
