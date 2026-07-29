# Configuration de la Génération de Solveurs

## 🎯 Mode par Défaut : Multi-Agents

**Depuis le 2026-07-20**, le mode de génération par défaut est le **pipeline multi-agents** (9 agents).

### Pourquoi Multi-Agents ?

| Avantage | Description |
|----------|-------------|
| **Tests automatiques** | Le Testeur génère des tests unitaires complets |
| **Revue de code** | Le Reviewer détecte les bugs avant exécution |
| **Correction automatique** | Le Debugger corrige les problèmes détectés |
| **Documentation** | Documentation complète générée automatiquement |
| **Qualité** | Taux de succès 85-95% vs 70-85% en mode simple |
| **Plan technique** | Architecture réfléchie par l'Architecte |
| **Optimisation** | L'Optimiseur améliore les performances |

### Scripts Disponibles

```bash
# MODE PAR DÉFAUT : Multi-Agents (recommandé)
python scripts/generer_solveur.py

# Mode Multi-Agents (explicite)
python scripts/generer_multi_agents.py

# Mode Simple (prototypage rapide seulement)
python scripts/generer_solveur_simple.py
```

---

## 📊 Comparaison des Modes

### Mode Simple (1 agent)

**Utilisation** : Prototypage rapide uniquement

**Caractéristiques** :
- ✅ Rapide : 10-30 secondes
- ✅ Économique : ~$0.01-0.05
- ❌ Pas de tests
- ❌ Pas de revue
- ❌ Pas de documentation
- ⚠️ Qualité variable (70-85%)

**Quand l'utiliser** :
- Expérimentation rapide
- Tests de prompts
- Instances très simples (< 5 tâches)
- Budget très limité

**Script** : `scripts/generer_solveur_simple.py`

---

### Mode Multi-Agents (9 agents) ⭐ **DÉFAUT**

**Utilisation** : Production et développement standard

**Caractéristiques** :
- ✅ Tests générés automatiquement
- ✅ Revue de code systématique
- ✅ Correction automatique des bugs
- ✅ Documentation complète
- ✅ Optimisation du code
- ✅ Haute qualité (85-95%)
- ⏱️ Plus lent : 2-5 minutes
- 💰 Plus cher : ~$0.50-1.00

**Quand l'utiliser** :
- Par défaut pour tout
- Production
- Instances complexes
- Besoin de tests/documentation
- Qualité critique

**Script** : `scripts/generer_solveur.py` (défaut)

---

## 🔧 Configuration

### Variables d'Environnement

Fichier `.env` :

```bash
# Provider LLM (obligatoire)
PRISME_LLM_PROVIDER=mistral  # ou anthropic, openai

# Clé API (obligatoire)
MISTRAL_API_KEY=sk-...       # selon le provider

# Modèle (optionnel, utilise le défaut du provider si absent)
PRISME_LLM_MODEL=
```

### Providers Recommandés

| Provider | Modèle | Coût/génération | Qualité | Recommandation |
|----------|--------|-----------------|---------|----------------|
| **Anthropic Claude** | Sonnet 4.5 | $0.30-0.50 | ⭐⭐⭐⭐⭐ | Meilleur pour code |
| **Mistral AI** | Large | $0.05-0.10 | ⭐⭐⭐⭐ | Bon rapport qualité/prix |
| **OpenAI GPT** | GPT-4 | $0.50-1.00 | ⭐⭐⭐⭐⭐ | Très bon mais cher |

**Recommandation** : Claude Sonnet 4.5 pour la production, Mistral pour le développement.

---

## 📋 Pipeline Multi-Agents Détaillé

### Les 8 Agents

```
1. ANALYSTE
   └─> Analyse l'instance T-R-C-O
   └─> Identifie les défis (contraintes, flexibilité, etc.)

2. ARCHITECTE
   └─> Conçoit le plan technique
   └─> Définit variables, contraintes, objectif CP-SAT

3. DÉVELOPPEUR
   └─> Génère le code selon le plan de l'Architecte
   └─> Fonction resoudre(instance) → Planning | None

4. TESTEUR
   └─> Génère tests unitaires pytest
   └─> Couvre cas nominaux et edge cases

5. REVIEWER
   └─> Revoit le code du Développeur
   └─> Détecte bugs, problèmes de structure, violations

6. DEBUGGER (si besoin)
   └─> Corrige les bugs détectés par le Reviewer
   └─> Génère code corrigé

7. OPTIMISEUR (si succès)
   └─> Améliore performances du code validé
   └─> Refactoring, optimisations CP-SAT

8. DOCUMENTATION (si succès)
   └─> Génère docstrings complètes
   └─> Commentaires explicatifs
   └─> Documentation markdown
```

### Sortie du Pipeline

Le pipeline génère **4 fichiers** :

1. **`solveur_genere.py`** - Code final du solveur
2. **`test_solveur_genere.py`** - Tests unitaires
3. **`solveur_genere_doc.md`** - Documentation
4. **Rapport JSON** - Détails de chaque agent (optionnel)

---

## 🎯 Usage Recommandé

### Workflow Standard

```bash
# 1. Génération (mode multi-agents par défaut)
python scripts/generer_solveur.py

# 2. Vérification des résultats
cat solveur_genere.py              # Code généré
cat test_solveur_genere.py         # Tests
cat solveur_genere_doc.md          # Documentation

# 3. Tests
pytest test_solveur_genere.py -v

# 4. Si succès : enregistrement
python scripts/enregistrer_solveur.py
```

### En cas d'Échec

Si la génération échoue :

1. **Examiner l'erreur** affichée par le pipeline
2. **Vérifier** si c'est un problème de structure de données
3. **Options** :
   - Corriger manuellement le code généré
   - Améliorer le prompt système (si erreur récurrente)
   - Relancer avec un autre provider (ex: Claude si Mistral échoue)

---

## 🚀 Migration depuis Mode Simple

Si vous utilisiez le mode simple :

```bash
# AVANT (mode simple)
python scripts/generer_solveur_simple.py

# MAINTENANT (mode multi-agents)
python scripts/generer_solveur.py
```

**Avantages de la migration** :
- ✅ Tests automatiques (plus besoin de les écrire)
- ✅ Documentation générée (gain de temps)
- ✅ Meilleure qualité (moins de bugs)
- ✅ Corrections automatiques

**Inconvénients** :
- ⏱️ Plus lent (2-5 min vs 30s)
- 💰 Plus cher ($0.50 vs $0.05)

**Verdict** : Le gain en qualité vaut largement le coût !

---

## 📚 Références

- [docs/agents_utilises.md](agents_utilises.md) - Détails sur les 9 agents
- [docs/explication_generation_code.md](explication_generation_code.md) - Comment le code est généré
- [generation/pipeline_multi_agents.py](../generation/pipeline_multi_agents.py) - Code source du pipeline
- [generation/tentative_unique.py](../generation/tentative_unique.py) - Code source mode simple

---

## 🔄 Changelog

- **2026-07-20** : Mode multi-agents défini comme défaut
  - Création de `scripts/generer_solveur.py` (multi-agents)
  - Renommage ancien script → `generer_solveur_simple.py`
  - Mise à jour documentation

---

**Mode par défaut** : Pipeline Multi-Agents (9 agents) ⭐
**Script principal** : `scripts/generer_solveur.py`
**Recommandation** : Toujours utiliser le mode multi-agents sauf pour prototypage rapide
