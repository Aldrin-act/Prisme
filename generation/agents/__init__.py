"""agents — Client LLM (`client_llm.py`) et les 9 agents du pipeline de
génération (§5.6) : Orchestrateur, Analyste, Architecte, Développeur
(`generateur.py`), Testeur, Reviewer, Debugger, Optimiseur, Documentation.
Chaque agent est une fonction pure `(AppelLLM, ...) -> Resultat...` — voir
`generation.pipeline_multi_agents` pour leur enchaînement, ou
`generation.tentative_unique` pour le mode simple à un seul agent (Étape 4)."""
