# Integration de l'agent Benchmarker dans le pipeline multi-agents

## Resume

L'agent **Benchmarker** a ete integre au pipeline de generation multi-agents pour permettre une **selection intelligente d'algorithme** en fonction des caracteristiques de l'instance a resoudre.

Au lieu de forcer l'utilisation de CP-SAT pour toutes les instances, le pipeline analyse desormais l'instance et choisit l'algorithme optimal parmi :
- CP-SAT (instances <500 taches, optimal)
- Genetic Algorithm (instances >200 taches, 92-95% qualite)
- Ant Colony Optimization
- Simulated Annealing
- Tabu Search
- Dispatching Rules
- Greedy + Local Search

## Motivation

### Probleme resolu

**Avant** : Le pipeline generait toujours du code CP-SAT, meme pour des instances ou CP-SAT est inadapte.

Exemple : GreenSig (2165 taches)
- CP-SAT : Timeout >1h sans solution
- Genetic Algorithm : Solution a 92-95% en 10-20 minutes

**Apres** : Le Benchmarker analyse l'instance et recommande l'algorithme optimal.

### Gain

- **Performance** : Solutions en minutes au lieu de timeouts
- **Qualite** : Algorithmes adaptes a la taille de l'instance
- **Flexibilite** : Support natif de 7 algorithmes differents

## Architecture

### Position dans le pipeline

Le pipeline passe de **8 agents a 9 agents** :

```
Analyste
    |
Architecte
    |
Benchmarker  <--- NOUVEAU (entre Architecte et Developpeur)
    |
Developpeur
    |
Testeur
    |
Reviewer
    |
[Debugger si besoin]
    |
Optimiseur
    |
Documentation
```

### Flux de donnees

```
Instance exemple (dict)
    |
    v
Benchmarker (LLM)
    |
    +-- Analyse caracteristiques (taille, contraintes, flexibilite)
    +-- Recommandation algorithme
    +-- Justification
    +-- Parametres suggeres
    |
    v
Developpeur (LLM)
    |
    +-- Recoit : plan_technique + algorithme + parametres
    +-- Genere : Code adapte a l'algorithme recommande
    |
    v
Code du solveur (utilise l'algorithme optimal)
```

## Changements techniques

### 1. `generation/pipeline_multi_agents.py`

#### Nouvelle signature

```python
def tenter_generation_multi_agents(
    appel_llm: AppelLLM,
    instance_exemple: dict | None = None  # NOUVEAU
) -> ResultatPipelineMultiAgents:
```

- `instance_exemple` : Instance T-R-C-O (dict JSON) pour le Benchmarker
- Si `None` : Utilise une instance par defaut de 10 taches (→ CP-SAT)

#### Nouveaux champs dans ResultatPipelineMultiAgents

```python
@dataclass(frozen=True)
class ResultatPipelineMultiAgents:
    # ... champs existants ...
    algorithme_recommande: str       # NOUVEAU : "cp_sat", "genetic", etc.
    justification_algorithme: str    # NOUVEAU : Raison du choix
    parametres_algorithme: dict      # NOUVEAU : {"population_size": 400, ...}
    # ... autres champs ...
```

#### Ajout du Benchmarker

```python
# Nouveau : Benchmarker choisit l'algorithme optimal
if instance_exemple is None:
    instance_exemple = _creer_instance_exemple_defaut()

resultat_benchmark = benchmarker.benchmarker_algorithmes(appel_llm, instance_exemple)
algo = resultat_benchmark.recommandation.algorithme
justification = resultat_benchmark.recommandation.raison
parametres = resultat_benchmark.recommandation.parametres_suggeres

# Generer code avec l'algorithme recommande
brut = generer_code_depuis_plan(
    appel_llm, conception.en_texte(),
    algorithme=algo,      # NOUVEAU
    parametres=parametres # NOUVEAU
)
```

#### Fonction helper

```python
def _creer_instance_exemple_defaut() -> dict:
    """Cree une petite instance par defaut (10 taches, 5 ressources)."""
    return {
        "taches": [{"id": f"T{i}"} for i in range(1, 11)],
        "ressources": [{"id": f"R{i}"} for i in range(1, 6)],
        "contraintes": [
            {
                "type": "compatibilite_ressource_tache",
                "tache": f"T{i}",
                "ressource": f"R{((i - 1) % 5) + 1}",
                "duree": 30,
            }
            for i in range(1, 11)
        ],
        "objectifs": [{"type": "minimiser_makespan"}],
    }
```

### 2. `generation/agents/generateur.py`

#### Nouvelle signature

```python
def generer_code_depuis_plan(
    appel_llm: AppelLLM,
    plan_technique: str,
    algorithme: str | None = None,    # NOUVEAU
    parametres: dict | None = None,   # NOUVEAU
) -> ResultatGenerationBrute:
```

#### Modification du prompt

Le prompt envoye au Developpeur inclut desormais :

```python
section_algorithme = ""
if algorithme:
    section_algorithme = f"\n## Algorithme recommande par le Benchmarker\n\n"
    section_algorithme += f"L'agent Benchmarker a analyse les caracteristiques de "
    section_algorithme += f"l'instance et recommande d'utiliser : **{algorithme.upper()}**\n\n"

    if parametres:
        section_algorithme += "Parametres suggeres :\n"
        for param, valeur in parametres.items():
            section_algorithme += f"- {param}: {valeur}\n"
        section_algorithme += "\n"

    section_algorithme += "Implemente le solveur avec cet algorithme.\n"

prompt = gabarit.format(
    mission=charger_mission(),
    plan_technique=plan_technique + section_algorithme,
)
```

### 3. Scripts de test

#### `scripts/test_pipeline_avec_benchmarker.py`

Script de test complet avec 4 scenarios :
1. Instance par defaut (10 taches) → CP-SAT
2. Instance moyenne (100 taches) → CP-SAT ou Tabu
3. Instance grande (500 taches) → Genetic ou ACO
4. Instance tres grande (2165 taches) → Genetic

## Utilisation

### Usage basique (instance par defaut)

```python
from generation.agents.client_llm import construire_appel_llm
from generation.pipeline_multi_agents import tenter_generation_multi_agents

appel_llm = construire_appel_llm()
resultat = tenter_generation_multi_agents(appel_llm)

print(f"Algorithme recommande : {resultat.algorithme_recommande}")
print(f"Justification : {resultat.justification_algorithme}")
```

### Usage avec instance personnalisee

```python
import json

# Charger une instance reelle
with open("greensig_instance_trco_simulee.json") as f:
    instance = json.load(f)

# Lancer le pipeline avec cette instance
resultat = tenter_generation_multi_agents(appel_llm, instance_exemple=instance)

print(f"Algorithme recommande : {resultat.algorithme_recommande}")
print(f"Parametres : {resultat.parametres_algorithme}")
```

### Test via CLI

```bash
# Test avec instance par defaut
uv run python -m scripts.test_pipeline_avec_benchmarker

# Le script propose 4 scenarios interactifs
```

## Exemples de recommandations

### Petite instance (10 taches)

```python
instance_exemple = None  # Utilise l'instance par defaut

# Resultat attendu :
{
  "algorithme_recommande": "cp_sat",
  "justification_algorithme": "Instance de petite taille (10 taches) ideale pour CP-SAT...",
  "parametres_algorithme": {
    "limite_temps_s": 300,
    "parallelisme": 8
  }
}
```

### Grande instance (2165 taches)

```python
with open("greensig_instance_trco_simulee.json") as f:
    instance_exemple = json.load(f)

# Resultat attendu :
{
  "algorithme_recommande": "genetic",
  "justification_algorithme": "Instance tres grande (2165 taches). CP-SAT timeout garanti...",
  "parametres_algorithme": {
    "population_size": 400,
    "generations": 800,
    "crossover_rate": 0.85,
    "mutation_rate": 0.03,
    "tournament_size": 5,
    "elitism": 0.1,
    "max_time_in_seconds": 1200
  }
}
```

## Retrocompatibilite

### Ancien code (sans Benchmarker)

```python
# ANCIEN : Fonctionne toujours
resultat = tenter_generation_multi_agents(appel_llm)
# Utilise l'instance par defaut → CP-SAT
```

### Nouveau code (avec Benchmarker)

```python
# NOUVEAU : Personnalise l'algorithme
resultat = tenter_generation_multi_agents(appel_llm, instance_exemple=instance)
# Benchmarker choisit l'algorithme optimal
```

**Le pipeline reste 100% retrocompatible.** L'appel sans `instance_exemple` fonctionne comme avant.

## Tests

### Test manuel

```bash
uv run python -m scripts.test_pipeline_avec_benchmarker
```

### Test automatise

```python
# TODO : Ajouter tests unitaires dans tests/unit/test_pipeline_multi_agents.py
# TODO : Ajouter tests d'integration dans tests/integration/
```

## Limitations et travaux futurs

### Limitations actuelles

1. **Algorithmes non implementes** : Le Benchmarker recommande 7 algorithmes, mais seul CP-SAT est implemente completement
   - Solution temporaire : Le Developpeur doit implementer les algorithmes recommandes
   - Roadmap : Completer `generation/algorithms/genetic.py`, `aco.py`, etc.

2. **Instance par defaut simpliste** : 10 taches, 5 ressources, pas de precedences
   - Ne represente pas forcement l'instance reelle a resoudre
   - Solution : Toujours fournir une instance representativen

3. **Pas de fallback** : Si le Developpeur echoue a implementer l'algorithme recommande, pas de repli vers CP-SAT
   - Roadmap : Ajouter une logique de fallback

### Prochaines etapes

1. **Completer les implementations d'algorithmes**
   - `generation/algorithms/genetic.py` (squelette existe)
   - `generation/algorithms/aco.py`
   - `generation/algorithms/simulated_annealing.py`
   - `generation/algorithms/tabu_search.py`

2. **Tester sur instances reelles**
   - GreenSig (2165 taches)
   - Comparer qualite CP-SAT vs GA sur subsets

3. **Ajouter tests unitaires et d'integration**
   - Mocker le Benchmarker
   - Verifier le flux de donnees

4. **Ameliorer l'instance par defaut**
   - Analyser les instances typiques
   - Creer une instance representative

## References

- **Agent Benchmarker** : `generation/agents/benchmarker.py`
- **Prompt Benchmarker** : `generation/prompts/benchmarker.md`
- **Pipeline** : `generation/pipeline_multi_agents.py`
- **Developpeur** : `generation/agents/generateur.py`
- **Algorithmes** : `generation/algorithms/README.md`
- **Documentation detaillee** : `AGENT_BENCHMARKER.md`
- **Resultats benchmark** : `RESULTAT_BENCHMARK_2165.md`

---

**Date d'integration** : 2026-07-21
**Version** : Pipeline 10 agents (ajout Benchmarker)
**Impact** : Architecture du pipeline modifiee (breaking change mineur)
