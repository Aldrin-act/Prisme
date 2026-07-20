# dsl — Modèle pivot T-R-C-O

Le DSL est le contrat entre le métier et la ressource (§4 de la note de cadrage) : format d'échange avec les ERP, entrée de génération pour l'IA, et cadre de validation (vocabulaire fini et typé).

- `schema/` — définitions typées des quatre axes : Tâches, Ressources, Contraintes, Objectifs.
- `validation/` — validation du payload T-R-C-O reçu (garde-fou amont, §6.7).
- `examples/` — instances DSL d'exemple pour le noyau minimal (précédence, compatibilité ressource-tâche, durées).
