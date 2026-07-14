# api — Cœur PRISME (§5.1, §5.5)

`app.py` assemble les quatre routeurs dans une `FastAPI()` ; documentation OpenAPI générée automatiquement (`/docs`, `/openapi.json`) une fois servie (`uvicorn api.app:app`).

- `routes/ingestion.py` — réception du payload T-R-C-O canonique (venant d'un adaptateur ERP) ; passe par `input_validation/` puis met l'instance en attente d'exécution.
- `routes/execution.py` — déclenchement d'une exécution : retrouve un solveur validé dans `solver_store/registry.py` (par client + structure de contraintes), l'exécute via `sandbox/runner.py`.
- `routes/planning.py` — canal opérationnel : retourne le planning en JSON, à chaque itération.
- `routes/audit.py` — canal d'audit : expose le code source du solveur sur demande explicite (transparence, souveraineté) — jamais mêlé au canal opérationnel.
- `input_validation/` — garde-fou amont (§6.7) : `dsl.validation.charger_instance`, traduit en `HTTPException` 422.
- `etat.py` — état en mémoire (démo PoC) reliant les routes : file d'instances ingérées, résultats d'exécution. Pas une persistance réelle — voir `solver_store/`.
- `dependencies.py` — le `Registre` partagé, injecté par FastAPI (`Depends`), substituable en test (`app.dependency_overrides`).

Démo bout en bout (adaptateur ERP → ingestion → exécution → planning → audit) : `scripts/demo_bout_en_bout.py`, à lancer avec `python -m scripts.demo_bout_en_bout` depuis la racine du dépôt (nécessite Docker, §7).
