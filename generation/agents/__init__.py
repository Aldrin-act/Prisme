"""agents — Client LLM (`client_llm.py`, LangChain) et les agents du pipeline
de génération (§5.6) : Analyste, Benchmarker, Architecte,
Développeur (`generateur.py`), Testeur, Reviewer, Debugger, Documentation
(Optimiseur orphelin, plus appelé). Chaque agent est une fonction pure
`(BaseChatModel, ...) -> Resultat...` (sortie structurée Pydantic) — voir
`generation.graph` pour leur enchaînement, ou
`generation.tentative_unique` pour le mode simple à un seul agent (Étape 4)."""
