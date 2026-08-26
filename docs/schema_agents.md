# Schéma Complet des Agents PRISME

Ce document présente l'architecture détaillée des agents du pipeline multi-agents. **7 sont
réellement câblés dans `generation/graph.py`** (Analyste, Benchmarker, Architecte, Développeur,
Testeur, Debugger, Documentation) ; **Reviewer** existe et fonctionne mais n'est **pas** appelé par
le pipeline (§6.6bis — `test_sandbox`, l'exécution réelle des tests du Testeur en Docker, rend son
avis consultatif redondant) ; **Optimiseur** est orphelin pour une raison différente (réponse JSON
trop fragile pour embarquer du code Python complet). Les deux restent réactivables sans refonte.

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
def analyser_mission(modele: BaseChatModel) -> ResultatAnalyse
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

### 2️⃣ BENCHMARKER

**Fichier** : `generation/agents/benchmarker.py`  
**Prompt** : `generation/prompts/benchmarker.md`

Toujours appelé, avant l'Architecte — aucun seuil de taille, aucun raccourci déterministe : choisit
l'algorithme le mieux adapté à l'instance dans son catalogue complet (`cp_sat` — seul traité comme
*exact* — ou une heuristique `genetic`/`aco`/`tabu_search`/`simulated_annealing`/`dispatching`/
`greedy_local` pour les très grandes instances où CP-SAT ne passe pas à l'échelle).

**Fonction** :
```python
def benchmarker_algorithmes(modele: BaseChatModel, instance: InstanceTRCO) -> ResultatBenchmark
```

**Input** : Instance T-R-C-O (ou une petite instance d'exemple par défaut si aucune fournie)

**Output** : `ResultatBenchmark` — algorithme choisi, justification, paramètres suggérés (ex.
`limite_temps_s`, `population_size`...). Détermine aussi la tolérance de la cascade de validation
qui suit — une heuristique n'est jamais comparée au strict optimum comme `cp_sat`.

---

### 3️⃣ ARCHITECTE

**Fichier** : `generation/agents/architecte.py`  
**Prompt** : `generation/prompts/architecte.md`

**Fonction** :
```python
def concevoir_modele(
    modele: BaseChatModel, analyse: ResultatAnalyse, algorithme: str = "cp_sat", parametres: dict | None = None
) -> ResultatConception
```

**Input** : `ResultatAnalyse` (spécification) + algorithme et paramètres recommandés par le Benchmarker

**Output** : `ResultatConception` — champs génériques, jamais « CP-SAT » en dur, car le contenu peut
décrire un algorithme alternatif :
```python
@dataclass
class ResultatConception:
    reponse_brute: str
    variables: str        # Représentation de la solution (variables CP-SAT, encodage GA, ...)
    contraintes_modele: str  # Contraintes métier à respecter
    objectif: str          # Objectif à optimiser
    fonctions_internes: str | None
    
    def en_texte(self) -> str:
        """Pour le Développeur."""
```

**Prompt système** :
```
"Tu es un architecte logiciel spécialisé en optimisation combinatoire
(CP-SAT/OR-Tools et métaheuristiques d'ordonnancement — génétique, ACO,
recuit simulé, tabou, dispatching). Tu réponds toujours en JSON strict."
```

**Format JSON attendu** (cas `algorithme="cp_sat"`) :
```json
{
  "variables": "start_times[t]: IntVar(0, 1000), assigned_resources[t]: IntVar(...)",
  "contraintes_modele": "Précédence: start[t2] >= start[t1] + duration[t1], No-overlap: AddNoOverlap(intervals)",
  "objectif": "Minimize(makespan)"
}
```
Pour une heuristique, `variables` décrit plutôt l'encodage chromosomique/la structure de solution.

---

### 4️⃣ DÉVELOPPEUR (Générateur)

**Fichier** : `generation/agents/generateur.py`  
**Prompt** : `generation/prompts/developpeur.md`

**Fonction** :
```python
def generer_code_depuis_plan(modele: BaseChatModel, plan_technique: str) -> CodeGenere
```

**Input** : Plan technique (architecture)

**Output** : `CodeGenere`
```python
@dataclass
class CodeGenere:
    reponse_brute: str
    code_source: str      # Code Python complet (~100-200 lignes)
```

**Prompt système** (algorithme-agnostique, pas de « CP-SAT » en dur) :
```
"Tu es un générateur de code Python expert en optimisation combinatoire.
Tu réponds toujours en JSON strict avec un champ 'code' contenant le code Python."
```

**Format JSON attendu** :
```json
{
  "code": "from ortools.sat.python import cp_model\n\ndef resoudre(instance):\n    ..."
}
```

---

### 5️⃣ TESTEUR

**Fichier** : `generation/agents/testeur.py`  
**Prompt** : `generation/prompts/testeur.md`

**Fonction** :
```python
def generer_tests(modele: BaseChatModel, code_source: str) -> CodeTests
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

**⚠️ Note** : Ces tests **sont bien exécutés** pour de vrai, à chaque tentative — voir `test_sandbox`
(§6.6bis) dans le flux de données ci-dessous. Ce n'est plus un simple livrable documentaire.

---

### 6️⃣ REVIEWER — présent dans le code, **pas câblé dans le pipeline**

> Fonctionne (testable isolément), mais `_construire_graphe` (`generation/graph.py`) ne
> l'enregistre jamais comme nœud du `StateGraph` — `test_sandbox` (exécution réelle des tests du
> Testeur en conteneur Docker, §6.6bis) et la cascade déterministe suffisent, son avis LLM
> consultatif étant devenu redondant. Réactivable en deux lignes (`_noeud_reviewer`/
> `_route_apres_reviewer` restent intacts) si un besoin réapparaît.

**Fichier** : `generation/agents/reviewer.py`  
**Prompt** : `generation/prompts/reviewer.md`

**Fonction** :
```python
def relire_code(modele: BaseChatModel, code_source: str) -> ResultatRevue
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

### 7️⃣ DEBUGGER

**Fichier** : `generation/agents/debugger.py`  
**Prompt** : `generation/prompts/debugger.md`

**Fonction** :
```python
def corriger_code(modele: BaseChatModel, code_source: str, erreurs: str) -> ResultatCorrection
```

**Input** :
- Code source bugué (peut implémenter n'importe quel algorithme choisi par le Benchmarker)
- Erreurs (commentaires Reviewer OU erreurs validation)

**Output** : `ResultatCorrection`
```python
@dataclass
class ResultatCorrection:
    reponse_brute: str
    code_source: str      # Code corrigé complet
    cause: str | None     # Cause identifiée (aide diagnostic, jamais bloquant si absent)
```

**Prompt système** (algorithme-agnostique) :
```
"Tu es un développeur Python expert en débogage de modèles d'optimisation
combinatoire (CP-SAT/OR-Tools et métaheuristiques d'ordonnancement). Tu
réponds toujours en JSON strict, jamais en texte libre."
```

**Format JSON attendu** :
```json
{
  "code": "from ortools.sat.python import cp_model\n\ndef resoudre(instance):\n    # CORRIGÉ: ligne 42, tache.id au lieu de tache\n    ...",
  "cause": "tache.id manquant, objet tache passé directement"
}
```

---

### 8️⃣ OPTIMISEUR (orphelin, plus appelé par le pipeline)

**Fichier** : `generation/agents/optimiseur.py`  
**Prompt** : `generation/prompts/optimiseur.md`

**Fonction** :
```python
def optimiser_code(modele: BaseChatModel, code_source: str, verdict: str = "") -> ResultatOptimisation
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

**Prompt système** (orphelin — agent non appelé par `generation/graph.py`, prompt jamais mis à
jour pour être algorithme-agnostique comme les autres) :
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

### 9️⃣ DOCUMENTATION

**Fichier** : `generation/agents/documentation.py`  
**Prompt** : `generation/prompts/documentation.md`

**Fonction** :
```python
def documenter_code(modele: BaseChatModel, code_source: str) -> ResultatDocumentation
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

### `client_llm.py` - Interface LLM (LangChain)

Chaque agent expose désormais un `BaseChatModel` LangChain brut — l'ancienne convention `AppelLLM`
(`Callable[[str, str], str]`, texte brut) a été entièrement retirée une fois le dernier appelant
converti.

**Fonctions** :
```python
def construire_modele() -> BaseChatModel
# Générique, sans identité d'agent — d'après PRISME_LLM_PROVIDER/PRISME_LLM_MODEL.

def construire_modele_pour_agent(nom_agent: str) -> BaseChatModel
# Routage par agent via config_fournisseurs.py — point d'entrée réel du pipeline.
```

**Providers supportés** :
- `mistral` (via `MISTRAL_API_KEY`, API native — fallback générique du mode single-shot)
- `nemotron` (via `NVIDIA_API_KEY`, catalogue NVIDIA NIM — modèle `nvidia/nemotron-3-super-120b-a12b`,
  défaut de la majorité des agents du pipeline multi-agents)
- `nvidia` (via `NVIDIA_API_KEY`, même catalogue — modèle `meta/llama-3.3-70b-instruct`)
- `minimax` (via `MINIMAX_API_KEY`, hébergé sur le catalogue NVIDIA — modèle `minimaxai/minimax-m3`)
- `deepseek` (via `DEEPSEEK_API_KEY`, hébergé sur le catalogue NVIDIA — plus le défaut d'aucun agent,
  reste un choix de repli valide)
- `qwen` / `together` (via `TOGETHER_API_KEY`, Qwen hébergé sur Together)

Anthropic/OpenAI ne sont **pas** des fournisseurs supportés par ce module.

**Répartition par défaut** (`generation/agents/config_fournisseurs.py::FOURNISSEURS_PAR_AGENT`) —
pas un fournisseur unique pour tout le pipeline :

| Agent(s) | Fournisseur | Modèle |
|---|---|---|
| Analyste, Architecte, Développeur, Testeur, Debugger, Reviewer (inactif), Compréhension ERP | `nemotron` | `nvidia/nemotron-3-super-120b-a12b` |
| Benchmarker, Optimiseur (inactif) | `minimax` | `minimaxai/minimax-m3` |
| Documentation | `nvidia` | `meta/llama-3.3-70b-instruct` |
| Supervision (MT7, hors pipeline de génération) | `mistral` | `mistral-large-latest` |

**Sélection** : `PRISME_LLM_PROVIDER`/`PRISME_LLM_MODEL` (fallback générique, mode single-shot
uniquement), ou par agent via `PRISME_LLM_PROVIDER_<AGENT>`/`PRISME_LLM_MODEL_<AGENT>`/
`PRISME_LLM_TIMEOUT_SECONDES_<AGENT>` — voir `generation/agents/config_fournisseurs.py`.

---

## 🔄 Flux de Données Complet

```
Instance T-R-C-O (DSL)
    │
    ▼
ANALYSTE
    │
    ▼ ResultatAnalyse (entrees, sorties, contraintes)
    │
    ▼
BENCHMARKER  (toujours appelé — choisit l'algorithme : cp_sat exact, ou une
    │         heuristique genetic/aco/tabu_search/simulated_annealing/
    │         dispatching/greedy_local pour les très grandes instances)
    ▼ algorithme + paramètres
    │
    ▼
ARCHITECTE
    │
    ▼ ResultatConception (variables, contraintes_modele, objectif)
    │
    ▼
DÉVELOPPEUR
    │
    ▼ CodeGenere (code_source)
    │
    ▼
TESTEUR ────► CodeTests (code_tests, un module pytest)
    │
    ▼
TEST_SANDBOX (§6.6bis, pas un agent LLM — exécution réelle du module pytest
    │          du Testeur, dans le conteneur Docker éphémère de production)
    │
    ├─── ÉCHEC ──────────────────────────────────────────────┐
    │                                                          │
    └─── SUCCÈS ────► VALIDATION (statique → exécution → cascade déterministe)
                              │                                │
                              ├─ SUCCÈS ──► DOCUMENTATION       │
                              │             (best-effort)       │
                              │                                 │
                              └─ ÉCHEC ─────────────────────────┤
                                                                 ▼
                                                          DEBUGGER (max 10 tentatives,
                                                          MAX_TENTATIVES_REPARATION)
                                                                 │
                                                                 ▼ ResultatCorrection
                                                                 │
                                                                 └─► retour TEST_SANDBOX
                                                                        │
                                                                        ▼ (tentatives épuisées → échec honnête, STOP)
                                                                        ▼ (succès)
                                                                 DOCUMENTATION (best-effort)
                                                                        │
                                                                        ▼
                                                                 ResultatPipelineAvecBoucle
```

Le Reviewer n'apparaît pas dans ce flux : présent dans le code (`generation/agents/reviewer.py`),
mais jamais câblé dans `_construire_graphe` (voir section 6️⃣ plus haut). Optimiseur non plus :
orphelin, plus appelé (réponse JSON jugée trop fragile pour embarquer du code Python complet).

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
- `benchmarker.md` : Choix de l'algorithme (cp_sat ou heuristique) selon l'instance
- `architecte.md` : Conception du modèle (variables/contraintes, ou l'équivalent pour l'algorithme choisi)
- `developpeur.md` : Code Python complet
- `testeur.md` : Tests pytest
- `reviewer.md` : Revue de code (approuve/commentaires)
- `debugger.md` : Correction bugs
- `optimiseur.md` : Optimisations performance (orphelin, plus appelé)
- `documentation.md` : Documentation Markdown

---

## 🎯 Design Patterns

### 1. Séparation Code / Prompt

**Pourquoi** : Faciliter l'itération sur les prompts sans toucher au code Python.

```python
# ❌ Mauvais : prompt hardcodé
def analyser(modele: BaseChatModel):
    prompt = "Tu es un analyste. Analyse cette instance..."
    return modele.invoke(prompt)

# ✅ Bon : prompt dans fichier externe
CHEMIN_PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "analyste.md"

def analyser(modele: BaseChatModel):
    prompt = CHEMIN_PROMPT.read_text(encoding="utf-8")
    return modele.invoke(prompt)
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

Estimation (instance 12 tâches, illustrative — le fournisseur réel varie par agent, voir la
répartition par défaut plus haut, pas un seul modèle pour tout le pipeline) :

| Agent / étape | Durée (s) | Tokens In | Tokens Out | Coût ($) |
|-------|-----------|-----------|------------|----------|
| Analyste | 11 | 600 | 300 | 0.038 |
| Benchmarker | variable | 700 | 300 | 0.040 |
| Architecte | 15 | 900 | 400 | 0.051 |
| Développeur | 21 | 1200 | 800 | 0.075 |
| Testeur | 18 | 1000 | 500 | 0.058 |
| Test_sandbox (Docker, pas un appel LLM) | variable | 0 | 0 | 0.000 |
| Debugger* | 15 | 1300 | 700 | 0.068 |
| Documentation | 8 | 900 | 400 | 0.048 |

*Conditionnel — seulement si `test_sandbox` ou `validation` échoue à une tentative donnée.
Reviewer et Optimiseur absents de ce tableau : aucun des deux n'est appelé par le pipeline actuel
(voir sections dédiées plus haut).

**Total pipeline complet (cas nominal, une seule tentative)** : ~95s, ~$0.35-0.50 selon fournisseurs

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
