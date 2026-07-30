# Schéma Complet des Agents PRISME

Ce document présente l'architecture détaillée des 8 agents du pipeline multi-agents.

---

## 📁 Structure des Fichiers

```
generation/
├── agents/                           # Code des agents
│   ├── __init__.py                   # Exports publics
│   ├── base.py                       # Utilitaires communs
│   ├── client_llm.py                 # Interface LLM LangChain (Mistral, Qwen, Together, NVIDIA, MiniMax, DeepSeek)
│   │
│   ├── analyste.py                   # Agent 1 : Analyse
│   ├── benchmarker.py                # Agent 2 : Choix de l'algorithme
│   ├── architecte.py                 # Agent 3 : Conception
│   ├── generateur.py                 # Agent 4 : Développement
│   ├── testeur.py                    # Agent 5 : Tests
│   ├── reviewer.py                   # Agent 6 : Revue de code
│   ├── debugger.py                   # Agent 7 : Correction
│   ├── documentation.py              # Agent 8 : Documentation
│   └── optimiseur.py                 # Orphelin, plus appelé par le pipeline
│
├── prompts/                          # Prompts des agents (Markdown)
│   ├── generation_solveur.md         # Mission commune (contrat T-R-C-O)
│   │
│   ├── analyste.md                   # Prompt Analyste
│   ├── architecte.md                 # Prompt Architecte
│   ├── developpeur.md                # Prompt Développeur
│   ├── testeur.md                    # Prompt Testeur
│   ├── reviewer.md                   # Prompt Reviewer
│   ├── debugger.md                   # Prompt Debugger
│   ├── optimiseur.md                 # Prompt Optimiseur
│   └── documentation.md              # Prompt Documentation
│
├── graph.py                           # Pipeline + boucle de réparation (StateGraph LangGraph, Étape 6, max 10 tentatives)
├── tentative_unique.py               # Mode simple (1 agent, Étape 4)
├── validation_statique.py            # AST allowlist
└── executer.py                       # exec() isolé
```

---

## 🎨 Architecture des Agents

Chaque agent suit le **même pattern** :

### Structure d'un Agent

```python
# 1. Imports
from dataclasses import dataclass
from langchain_core.messages import HumanMessage, SystemMessage
from generation.agents.base import charger_mission, extraire_texte_brut
from generation.agents.client_llm import _avec_retry, methode_sortie_structuree

# 2. Prompt système (personnalité)
_PROMPT_SYSTEME = "Tu es un [rôle]. Tu réponds toujours en JSON strict."

# 3. Dataclass résultat
@dataclass(frozen=True)
class ResultatAgent:
    reponse_brute: str
    champ_1: str
    champ_2: str
    ...
    
    def en_texte(self) -> str:
        """Rendu lisible pour l'agent suivant."""
        return f"..."

# 4. Fonction principale — `modele` est un `BaseChatModel` LangChain construit
# par `construire_modele_pour_agent(nom_agent)` (routage par fournisseur/agent,
# voir client_llm.py) ; la sortie structurée (schéma Pydantic) évite le
# parsing JSON manuel de l'ancienne convention `AppelLLM`.
def fonction_agent(modele: BaseChatModel, *args) -> ResultatAgent:
    # Charger prompt depuis fichier
    prompt = CHEMIN_PROMPT.read_text(encoding="utf-8")

    # Appeler LLM (sortie structurée, retry sur erreur transitoire)
    structure = modele.with_structured_output(
        _SchemaAgent, include_raw=True, method=methode_sortie_structuree(modele)
    )
    sortie = _avec_retry(structure.invoke)(
        [SystemMessage(content=_PROMPT_SYSTEME), HumanMessage(content=prompt)]
    )
    reponse_brute = extraire_texte_brut(sortie["raw"])
    donnees = sortie["parsed"]

    # Retourner résultat structuré
    return ResultatAgent(
        reponse_brute=reponse_brute,
        champ_1=donnees.champ_1,
        champ_2=donnees.champ_2,
        ...
    )
```

---

## 🤖 Les 8 Agents en Détail

> Pas d'Orchestrateur : l'agent a été supprimé (`generation/agents/orchestrateur.py`,
> `generation/prompts/orchestrateur.md`). Il ne faisait que produire un plan
> JSON jamais lu par personne — l'ordre d'exécution du pipeline a toujours
> été câblé en Python dans `generation/graph.py` (`_construire_graphe`),
> jamais décidé dynamiquement par sa réponse.

### 1️⃣ ANALYSTE

**Fichier** : `generation/agents/analyste.py`  
**Prompt** : `generation/prompts/analyste.md`

**Fonction** :
```python
def analyser_mission(appel_llm: AppelLLM) -> ResultatAnalyse
```

**Input** : Mission (contrat T-R-C-O)

**Output** : `ResultatAnalyse`
```python
@dataclass
class ResultatAnalyse:
    reponse_brute: str
    entrees: str                          # Description inputs
    sorties: str                          # Description outputs
    contraintes_a_couvrir: tuple[str, ...]  # Liste contraintes
    
    def en_texte(self) -> str:
        """Pour l'Architecte."""
```

**Prompt système** :
```
"Tu es un analyste technique spécialisé en ordonnancement (FJSP) et en 
modélisation. Tu réponds toujours en JSON strict."
```

**Format JSON attendu** :
```json
{
  "entrees": "InstanceTRCO avec tâches, ressources, contraintes",
  "sorties": "Planning avec opérations planifiées ou None",
  "contraintes_a_couvrir": [
    "Précédence entre tâches",
    "Compatibilité ressource-tâche",
    "No-overlap (une ressource par tâche à la fois)"
  ]
}
```

---

### 2️⃣ ARCHITECTE

**Fichier** : `generation/agents/architecte.py`  
**Prompt** : `generation/prompts/architecte.md`

**Fonction** :
```python
def concevoir_modele(appel_llm: AppelLLM, analyse: ResultatAnalyse) -> PlanTechnique
```

**Input** : `ResultatAnalyse` (spécification)

**Output** : `PlanTechnique`
```python
@dataclass
class PlanTechnique:
    reponse_brute: str
    variables: str        # Variables CP-SAT à créer
    contraintes: str      # Contraintes à ajouter
    objectif: str         # Objectif à minimiser
    
    def en_texte(self) -> str:
        """Pour le Développeur."""
```

**Prompt système** :
```
"Tu es un architecte logiciel expert en programmation par contraintes (CP-SAT). 
Tu réponds toujours en JSON strict."
```

**Format JSON attendu** :
```json
{
  "variables": "start_times[t]: IntVar(0, 1000), assigned_resources[t]: IntVar(...)",
  "contraintes": "Précédence: start[t2] >= start[t1] + duration[t1], No-overlap: AddNoOverlap(intervals)",
  "objectif": "Minimize(makespan)"
}
```

---

### 3️⃣ DÉVELOPPEUR (Générateur)

**Fichier** : `generation/agents/generateur.py`  
**Prompt** : `generation/prompts/developpeur.md`

**Fonction** :
```python
def generer_code_depuis_plan(appel_llm: AppelLLM, plan_technique: str) -> CodeGenere
```

**Input** : Plan technique (architecture)

**Output** : `CodeGenere`
```python
@dataclass
class CodeGenere:
    reponse_brute: str
    code_source: str      # Code Python complet (~100-200 lignes)
```

**Prompt système** :
```
"Tu es un développeur Python expert en OR-Tools CP-SAT. Tu réponds toujours 
en JSON strict avec un champ 'code' contenant le code Python."
```

**Format JSON attendu** :
```json
{
  "code": "from ortools.sat.python import cp_model\n\ndef resoudre(instance):\n    ..."
}
```

---

### 4️⃣ TESTEUR

**Fichier** : `generation/agents/testeur.py`  
**Prompt** : `generation/prompts/testeur.md`

**Fonction** :
```python
def generer_tests(appel_llm: AppelLLM, code_source: str) -> CodeTests
```

**Input** : Code source (du Développeur)

**Output** : `CodeTests`
```python
@dataclass
class CodeTests:
    reponse_brute: str
    code_tests: str       # Code pytest (~50-100 lignes)
```

**Prompt système** :
```
"Tu es un ingénieur QA expert en pytest. Tu réponds toujours en JSON strict 
avec un champ 'tests' contenant le code pytest."
```

**Format JSON attendu** :
```json
{
  "tests": "import pytest\n\ndef test_instance_vide():\n    ..."
}
```

**⚠️ Note** : Ces tests ne sont **jamais exécutés** par le pipeline (livrable documentaire uniquement).

---

### 5️⃣ REVIEWER

**Fichier** : `generation/agents/reviewer.py`  
**Prompt** : `generation/prompts/reviewer.md`

**Fonction** :
```python
def relire_code(appel_llm: AppelLLM, code_source: str) -> ResultatRevue
```

**Input** : Code source (du Développeur)

**Output** : `ResultatRevue`
```python
@dataclass
class ResultatRevue:
    reponse_brute: str
    approuve: bool            # True si parfait, False si bugs
    commentaires: str         # Explications (bugs si rejeté)
```

**Prompt système** :
```
"Tu es un reviewer senior expert en OR-Tools et Python. Tu réponds toujours 
en JSON strict avec 'approuve' (bool) et 'commentaires' (string)."
```

**Format JSON attendu** :
```json
{
  "approuve": false,
  "commentaires": "Bug ligne 42: vous passez l'objet 'tache' au lieu de 'tache.id'"
}
```

---

### 6️⃣ DEBUGGER

**Fichier** : `generation/agents/debugger.py`  
**Prompt** : `generation/prompts/debugger.md`

**Fonction** :
```python
def corriger_code(appel_llm: AppelLLM, code_source: str, erreurs: str) -> CodeCorrige
```

**Input** :
- Code source bugué
- Erreurs (commentaires Reviewer OU erreurs validation)

**Output** : `CodeCorrige`
```python
@dataclass
class CodeCorrige:
    reponse_brute: str
    code_source: str      # Code corrigé complet
```

**Prompt système** :
```
"Tu es un debugger expert en OR-Tools et Python. Tu réponds toujours en JSON 
strict avec un champ 'code_corrige' contenant le code Python corrigé."
```

**Format JSON attendu** :
```json
{
  "code_corrige": "from ortools.sat.python import cp_model\n\ndef resoudre(instance):\n    # CORRIGÉ: ligne 42, tache.id au lieu de tache\n    ..."
}
```

---

### 7️⃣ OPTIMISEUR (orphelin, plus appelé par le pipeline)

**Fichier** : `generation/agents/optimiseur.py`  
**Prompt** : `generation/prompts/optimiseur.md`

**Fonction** :
```python
def optimiser_code(appel_llm: AppelLLM, code_source: str, verdict: str = "") -> ResultatOptimisation
```

**Input** :
- Code source validé
- Verdict cascade (métriques, optionnel)

**Output** : `ResultatOptimisation`
```python
@dataclass
class ResultatOptimisation:
    reponse_brute: str
    proposee: bool               # True si optimisation proposée
    code_source: str | None      # Code optimisé (si proposee=True)
    justification: str           # Explications
```

**Prompt système** :
```
"Tu es un expert en optimisation CP-SAT. Tu réponds toujours en JSON strict."
```

**Format JSON attendu** :
```json
{
  "proposee": true,
  "code_optimise": "...",
  "justification": "Ajout de hints pour accélérer la recherche (reduction 30% temps)"
}
```

**⚠️ Sécurité** : Le code optimisé est **re-validé** (cascade complète). Si échec, on garde le code non-optimisé.

---

### 8️⃣ DOCUMENTATION

**Fichier** : `generation/agents/documentation.py`  
**Prompt** : `generation/prompts/documentation.md`

**Fonction** :
```python
def documenter_code(appel_llm: AppelLLM, code_source: str) -> ResultatDocumentation
```

**Input** : Code source final

**Output** : `ResultatDocumentation`
```python
@dataclass
class ResultatDocumentation:
    reponse_brute: str
    documentation: str    # Markdown (~500-1000 mots)
    
    def en_texte(self) -> str:
        return self.documentation
```

**Prompt système** :
```
"Tu es un rédacteur technique expert. Tu réponds toujours en JSON strict 
avec un champ 'documentation' contenant le Markdown."
```

**Format JSON attendu** :
```json
{
  "documentation": "# Solveur FJSP OR-Tools\n\n## Description\n...\n\n## Exemple\n..."
}
```

---

## 🔧 Composants Communs

### `base.py` - Utilitaires

**Fonctions** :

1. **`charger_mission() -> str`**
   - Charge `generation/prompts/generation_solveur.md`
   - Mission commune (contrat T-R-C-O) injectée dans tous les prompts

2. **`extraire_json(reponse: str) -> dict[str, Any]`**
   - Parse JSON depuis réponse LLM
   - Tolère bloc ```json...``` ou ``` ...```
   - Lève `ErreurReponseAgentInvalide` si parsing échoue

3. **`extraire_bloc_code(reponse: str) -> str`**
   - Extrait bloc ```python...```
   - Utilisé uniquement en mode simple (Étape 4)

**Exception** :
```python
class ErreurReponseAgentInvalide(Exception):
    """LLM n'a pas retourné le JSON attendu."""
```

---

### `client_llm.py` - Interface LLM

**Type** :
```python
AppelLLM = Callable[[str, str], str]
# Signature: appel_llm(prompt_systeme: str, prompt_user: str) -> str
```

**Fonction** :
```python
def construire_appel_llm() -> AppelLLM
```

**Providers supportés** :
- `mistral` (via `MISTRAL_API_KEY`)
- `anthropic` (via `ANTHROPIC_API_KEY`)
- `openai` (via `OPENAI_API_KEY`)

**Sélection** : Variable d'environnement `PRISME_LLM_PROVIDER`

**Configuration** :
```python
# .env
PRISME_LLM_PROVIDER=mistral
MISTRAL_API_KEY=...

# Ou
PRISME_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
```

---

## 🔄 Flux de Données Complet

```
Instance T-R-C-O (DSL)
    │
    ├────► ANALYSTE
    │          │
    │          ▼ ResultatAnalyse (entrees, sorties, contraintes)
    │          │
    │          ▼
    └────► ARCHITECTE
               │
               ▼ PlanTechnique (variables, contraintes, objectif)
               │
               ▼
           DÉVELOPPEUR
               │
               ▼ CodeGenere (code_source)
               │
               ├────► TESTEUR ────► CodeTests (code_tests)
               │
               └────► REVIEWER
                          │
                          ▼ ResultatRevue (approuve, commentaires)
                          │
                          ├─── APPROUVÉ ────► VALIDATION (3 passes)
                          │                       │
                          │                       ├─ SUCCÈS ───┐
                          │                       │            │
                          │                       └─ ÉCHEC ────┼─► DEBUGGER
                          │                                    │      │
                          └─── REJETÉ ─────────────────────────┘      │
                                                                       │
                                                                       ▼ CodeCorrige
                                                                       │
                                                                       └─► VALIDATION (retry)
                                                                              │
                                                                              ├─ SUCCÈS ───┐
                                                                              │            │
                                                                              └─ ÉCHEC ────┤
                                                                                           │
                                                                                           ▼
                                                                                      OPTIMISEUR
                                                                                           │
                                                                                           ▼ ResultatOptimisation
                                                                                           │
                                                                                           └─► VALIDATION (bis)
                                                                                                  │
                                                                                                  ▼
                                                                                           DOCUMENTATION
                                                                                                  │
                                                                                                  ▼
                                                                                          ResultatPipeline
```

---

## 📋 Prompts (generation/prompts/)

Tous les prompts sont en **Markdown** et suivent ce pattern :

```markdown
# Agent [Nom]

Tu es un [rôle]. Ta mission : [objectif].

## Contexte

{mission}  <!-- Injecté via charger_mission() -->

## Entrées

[Description inputs spécifiques à cet agent]

## Sorties

IMPORTANT : Tu réponds UNIQUEMENT en JSON strict, format :

```json
{
  "champ_1": "...",
  "champ_2": "..."
}
```

## Contraintes

- [Contrainte 1]
- [Contrainte 2]

## Exemples

[Exemples concrets]
```

**Prompts existants** :
- `generation_solveur.md` : Mission commune (contrat T-R-C-O, signature `resoudre()`)
- `analyste.md` : Analyse inputs/outputs/contraintes
- `architecte.md` : Architecture CP-SAT (variables, contraintes, objectif)
- `developpeur.md` : Code Python complet
- `testeur.md` : Tests pytest
- `reviewer.md` : Revue de code (approuve/commentaires)
- `debugger.md` : Correction bugs
- `optimiseur.md` : Optimisations performance
- `documentation.md` : Documentation Markdown

---

## 🎯 Design Patterns

### 1. Séparation Code / Prompt

**Pourquoi** : Faciliter l'itération sur les prompts sans toucher au code Python.

```python
# ❌ Mauvais : prompt hardcodé
def analyser(appel_llm):
    prompt = "Tu es un analyste. Analyse cette instance..."
    return appel_llm(prompt)

# ✅ Bon : prompt dans fichier externe
CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "analyste.md"

def analyser(appel_llm):
    prompt = CHEMIN_PROMPT.read_text(encoding="utf-8")
    return appel_llm(prompt)
```

### 2. JSON Strict Partout

**Pourquoi** : Parsing fiable, pas de regex fragile, détection d'erreur immédiate.

```python
# Tous les agents retournent du JSON structuré
donnees = extraire_json(reponse)  # Lève ErreurReponseAgentInvalide si invalide

# Accès typé
return ResultatAnalyse(
    entrees=donnees["entrees"],  # KeyError si manquant → échec net
    sorties=donnees["sorties"],
    ...
)
```

### 3. Dataclasses Immuables

**Pourquoi** : Résultats traçables, debuggable, jamais mutés accidentellement.

```python
@dataclass(frozen=True)  # Immuable
class ResultatAnalyse:
    reponse_brute: str   # Toujours garder la réponse brute (debugging)
    entrees: str
    sorties: str
    ...
```

### 4. Méthode `en_texte()`

**Pourquoi** : Chaque agent peut formater son output pour l'agent suivant.

```python
class ResultatAnalyse:
    def en_texte(self) -> str:
        """Injecté dans le prompt de l'Architecte."""
        return f"### Entrées\n{self.entrees}\n\n..."
```

---

## 🔒 Sécurité

### Validation en Cascade

Le code généré passe **3 gardes** avant acceptation :

1. **Validation statique** (`validation_statique.py`)
   - AST allowlist : imports autorisés uniquement
   - Rejet : `eval`, `exec`, `__import__`, `open`, dunders

2. **Exécution isolée** (`executer.py`)
   - `exec()` dans namespace propre
   - Récupère fonction `resoudre`

3. **Validation cascade** (`validation_engine/cascade.py`)
   - Faisabilité (toutes instances)
   - Optimalité (banc synthétique)
   - Fidélité (reference_cases)

### Sandboxing Production

En production, le code validé est exécuté dans un **conteneur Docker** éphémère :
- Réseau désactivé
- Rootfs read-only
- Utilisateur non-root (uid 10001)
- CPU/RAM/PID limités
- Timeout forcé

Voir `sandbox/runner.py` (Étape 7).

---

## 📊 Métriques par Agent

Estimation (instance 12 tâches, Mistral Large) :

| Agent | Durée (s) | Tokens In | Tokens Out | Coût ($) |
|-------|-----------|-----------|------------|----------|
| Analyste | 11 | 600 | 300 | 0.038 |
| Architecte | 15 | 900 | 400 | 0.051 |
| Développeur | 21 | 1200 | 800 | 0.075 |
| Testeur | 18 | 1000 | 500 | 0.058 |
| Reviewer | 10 | 1100 | 150 | 0.042 |
| Debugger* | 15 | 1300 | 700 | 0.068 |
| Optimiseur* | 12 | 1000 | 600 | 0.055 |
| Documentation | 8 | 900 | 400 | 0.048 |

*Conditionnel (pas toujours exécuté)

**Total pipeline complet** : ~95s, ~$0.48

---

## 🚀 Utilisation

### Appeler un Agent Seul

```python
from generation.agents import analyste
from generation.agents.client_llm import construire_modele_pour_agent

modele = construire_modele_pour_agent("analyste")
resultat = analyste.analyser_mission(modele)

print(resultat.entrees)
print(resultat.sorties)
print(resultat.contraintes_a_couvrir)
```

### Pipeline AVEC Boucle (Étape 6, production)

`generation/graph.py` construit lui-même le `BaseChatModel` de chaque agent
(routage par fournisseur via `construire_modele_pour_agent`, voir
`config_fournisseurs.py`) — aucun client LLM à passer en argument.

```python
from generation.graph import tenter_generation_avec_boucle

resultat = tenter_generation_avec_boucle(instance_exemple=instance.model_dump(mode="json"))

if resultat.reussi:  # propriété : validation statique + exécution + cascade toutes vertes
    print(f"✅ Code généré : {len(resultat.code_final)} caractères")
else:
    print(f"❌ Échec : {resultat.erreur_execution}")

# Historique des tentatives de la boucle de réparation
for i, tentative in enumerate(resultat.boucle_reparation.tentatives, 1):
    print(f"Tentative {i} : {'✅ SUCCÈS' if tentative.reussi else '❌ ÉCHEC'}")
```

Version streaming (un `EvenementEtape` par agent/sous-étape, consommée par
`api/routes/generation.py` pour le SSE) : `tenter_generation_avec_boucle_stream(...)`.

---

## 📚 Fichiers Liés

- **Agents** : `generation/agents/{analyste,benchmarker,architecte,generateur,testeur,reviewer,debugger,documentation}.py` (`optimiseur.py` orphelin)
- **Prompts** : `generation/prompts/*.md`
- **Pipeline + boucle** : `generation/graph.py` (StateGraph LangGraph, remplace les anciens `pipeline_multi_agents.py`/`pipeline_avec_boucle.py`/`loop.py`, supprimés)
- **Documentation** : `docs/agents_fonctionnement_detaille.md`, `docs/boucle_reparation.md`

---

**Schéma complet des 8 agents documenté ! 🎉**
