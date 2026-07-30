# Configuration des fournisseurs LLM par agent

## Vue d'ensemble

Depuis l'implémentation de la configuration optimale, chaque agent du pipeline multi-agents utilise automatiquement le fournisseur LLM le mieux adapté à sa tâche spécifique. Cela optimise le rapport qualité/coût/performance de la génération.

## Répartition des fournisseurs

### DeepSeek V4 Pro (6 agents) 🧠
**Caractéristiques** : Thinking mode, 16K tokens, température=1.0

Utilisé pour les tâches nécessitant un raisonnement complexe et de grands contextes :

- **Développeur/Générateur** : 16K tokens pour code long, thinking mode pour logique complexe
- **Debugger** : Thinking mode excellent pour analyse d'erreurs et corrections
- **Architecte** : Raisonnement structurel complexe sur l'architecture CP-SAT
- **Analyste** : Compréhension profonde de la mission T-R-C-O
- **Reviewer** : Thinking mode pour revue critique approfondie
- **Agent ERP Compréhension** : 16K tokens pour grandes données ERP, mapping complexe

### MiniMax M3 (2 agents) 💡
**Caractéristiques** : Créativité maximale (temp=1.0), 8K tokens

Utilisé pour les tâches nécessitant créativité et exploration :

- **Benchmarker** : Exploration créative d'algorithmes alternatifs (CP-SAT, GA, ACO, etc.)
- **Optimiseur** : Optimisations non évidentes, approches créatives

### NVIDIA Llama-3.3-70B (1 agent) 🎯
**Caractéristiques** : Déterministe (temp=0.6), 4K tokens

Utilisé pour les tâches simples et structurées :

- **Documentation** : Tâche simple, peu de tokens, sortie structurée

### Testeur : DeepSeek (fallback depuis Together)

- **Testeur** : routé sur DeepSeek (16K tokens) dans `config_fournisseurs.py`,
  Together n'est plus utilisé pour aucun agent par défaut malgré son
  intégration (`_construire_modele_together` dans `client_llm.py`).

### Mistral Large (fallback) 🔄
**Utilisé comme** : Provider par défaut si non spécifié

## Utilisation

### Mode automatique (recommandé)

Le pipeline (`generation/graph.py`, StateGraph LangGraph) utilise automatiquement la configuration optimale :

```python
from generation.graph import tenter_generation_avec_boucle

# Chaque agent utilisera automatiquement son fournisseur optimal
resultat = tenter_generation_avec_boucle(instance_exemple=instance.model_dump(mode="json"))
```

### Surcharge par agent (avancé)

Vous pouvez surcharger le fournisseur pour un agent spécifique :

```bash
# Forcer le Générateur à utiliser Mistral au lieu de DeepSeek
export PRISME_LLM_PROVIDER_GENERATEUR=mistral

# Forcer le Benchmarker à utiliser DeepSeek
export PRISME_LLM_PROVIDER_BENCHMARKER=deepseek
```

### Surcharge du modèle (avancé)

Vous pouvez aussi surcharger le modèle pour un agent :

```bash
# Utiliser un modèle spécifique pour le Debugger
export PRISME_LLM_MODEL_DEBUGGER=deepseek-ai/deepseek-v4-ultra
```

### Mode manuel

Pour utiliser un agent individuellement avec un fournisseur personnalisé :

```python
from generation.agents.client_llm import construire_modele_pour_agent
from generation.agents import analyste

# Utilise automatiquement DeepSeek (config optimale)
modele = construire_modele_pour_agent("analyste")
resultat = analyste.analyser_mission(modele)
```

## Configuration

La répartition est définie dans `generation/agents/config_fournisseurs.py` :

```python
FOURNISSEURS_PAR_AGENT = {
    "generateur": "deepseek",
    "debugger": "deepseek",
    "architecte": "deepseek",
    "analyste": "deepseek",
    "reviewer": "deepseek",
    "benchmarker": "minimax",
    "optimiseur": "minimax",
    "documentation": "nvidia",
    "testeur": "together",
    "comprehension": "deepseek",  # Agent ERP
}
```

## Justification des choix

### Pourquoi DeepSeek pour le code ?
- **16K tokens** : Essentiel pour générer du code complexe en un seul appel
- **Thinking mode** : Améliore la qualité du raisonnement (débogage, architecture)
- **Température 1.0** : Créatif mais guidé par le thinking

### Pourquoi MiniMax pour l'exploration ?
- **Température 1.0** : Créativité maximale
- **Top-p 0.95** : Large exploration de l'espace des solutions
- Idéal pour le Benchmarker (explorer algorithmes) et l'Optimiseur (optimisations non évidentes)

### Pourquoi NVIDIA pour les tâches simples ?
- **Température 0.6** : Plus déterministe, cohérent
- **4K tokens** : Suffisant pour plan JSON et documentation
- Coût optimal pour tâches simples

### Pourquoi Together pour les tests ?
- **Équilibre** : Créativité (edge cases) + Structure (pytest)
- **8K tokens** : Suffisant pour batterie de tests
- Bon rapport qualité/prix

## Comparer les fournisseurs

```bash
# Mesurer taux de succès (Étape 4, tir unique)
uv run python -m scripts.mesurer_taux_succes_generation
```

Observabilité (durée/coût/tokens par agent, tracing des appels LLM) : LangSmith, pas d'instrumentation maison.

## Fournisseurs disponibles

| Provider | Modèle par défaut | Temp | Top P | Max Tokens | Spécialité |
|----------|--------|------|-------|------------|------------|
| deepseek | deepseek-v4-pro | 1.0 | 0.95 | 16384 | Raisonnement complexe |
| minimax | minimax-m3 | 1.0 | 0.95 | 8192 | Créativité |
| nvidia | llama-3.3-70b-instruct | 0.6 | 0.7 | 4096 | Déterminisme |
| together | Qwen2.5-72B | 0.7 | 0.9 | 8192 | Équilibré (non utilisé par défaut, voir ci-dessus) |
| mistral | mistral-large-latest | N/A | N/A | N/A | Fallback |

Modèles par défaut définis dans `_MODELES_PAR_DEFAUT` (`client_llm.py`), surchageables par
`PRISME_LLM_MODEL_<AGENT>` — les défauts NVIDIA/MiniMax ont déjà été mis à jour une fois en
pratique après que les modèles précédents (qwen3-next-80b, minimax-m2.7) ont atteint leur fin
de vie côté catalogue.

## Historique

L'ancienne convention (avant l'introduction de LangChain/LangGraph) exposait un type
`AppelLLM` (`Callable[[str, str], str]`, texte brut) construit par `construire_appel_llm()`,
un unique fournisseur pour tous les agents. Entièrement retiré une fois le dernier appelant
converti aux `BaseChatModel` LangChain de `client_llm.py` — il n'existe plus de mode « ancien
comportement » ni de paramètre `appel_llm` conservé pour compatibilité.

## Troubleshooting

### Erreur "fournisseur LLM inconnu"
Vérifiez que tous les fournisseurs mentionnés dans `config_fournisseurs.py` sont bien définis dans `client_llm.py`.

### Un agent utilise le mauvais fournisseur
1. Vérifiez `PRISME_LLM_PROVIDER_<AGENT>` dans l'environnement
2. Vérifiez le mapping dans `config_fournisseurs.py`
3. Le nom de l'agent doit correspondre exactement (minuscules)

### Performance dégradée
Certains fournisseurs peuvent être plus lents. Vous pouvez surcharger pour un agent spécifique si nécessaire.

## Notes de sécurité

- Les clés API restent dans les variables d'environnement standard
- Aucune clé n'est jamais loggée ou exposée
- Chaque fournisseur via NVIDIA utilise sa propre clé codée (à externaliser en production)
