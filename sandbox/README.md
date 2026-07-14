# sandbox — Exécution éphémère

À chaque exécution, un conteneur Docker neuf démarre, reçoit le code déjà figé (`solver_store/`) plus les données du moment, calcule le planning, puis meurt (§5.2, §5.3, §7). Réseau coupé, système de fichiers en lecture seule, utilisateur non-root, limites CPU/mémoire/PID.

- `runner.py` — `executer_dans_sandbox` : injection code figé + données, orchestration de l'exécution jetable via le SDK `docker` (extra optionnel `sandbox`, `pip install -e .[sandbox]`). `executer_solveur_valide` chaîne store → sandbox → garde-fou de faisabilité en aval (§6.7) ; suppose l'instance déjà validée en amont (`dsl.validation.charger_instance`).
- `container/` — `Dockerfile` (image minimale : Python + OR-Tools + Pydantic, utilisateur non-root, aucun outil réseau superflu) et `executer_dans_conteneur.py`, le harnais qui tourne à l'intérieur.

Construction de l'image (jamais faite automatiquement par `runner.py`, depuis la racine du dépôt) :

```
docker build -t prisme-sandbox:latest -f sandbox/container/Dockerfile .
```

Les tests d'intégration (`tests/integration/test_sandbox_*.py`) construisent l'image eux-mêmes via une fixture et sont ignorés (pas en échec) si Docker est indisponible.
