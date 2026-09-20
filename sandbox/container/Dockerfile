# Image du bac à sable éphémère (§5.2, §5.3, §7) : surface minimale,
# utilisateur non-root, aucun outil réseau ou de diagnostic superflu.
# Construction : docker build -t prisme-sandbox:latest -f sandbox/container/Dockerfile .
# (exécuter depuis la racine du dépôt, pour que `dsl/` soit dans le contexte)

FROM python:3.11-slim

# pytest==9.1.1 (même version que l'extra `dev` de pyproject.toml) : mode audit des
# tests générés par l'agent Testeur, voir sandbox/runner.py::executer_tests_dans_sandbox
# — jamais de plugin tiers (pytest-json-report ou équivalent), le harnais collecte les
# résultats lui-même via un plugin en process.
# `ortools` : LEGACY — uniquement pour les solveurs CP-SAT déjà figés dans
# `solver_store/artifacts/` avant le retrait de CP-SAT du projet (ils continuent de tourner).
# PRISME ne génère plus rien qui l'importe (allowlist AST de `generation/validation_statique.py`) ;
# à retirer d'ici quand ces anciens solveurs auront été régénérés ou désactivés.
RUN pip install --no-cache-dir "ortools>=9.9" "pydantic>=2.6" "pytest==9.1.1" \
    && useradd --no-create-home --uid 10001 --shell /usr/sbin/nologin executant

COPY dsl/ /app/dsl/
COPY sandbox/container/executer_dans_conteneur.py /app/executer_dans_conteneur.py
COPY sandbox/container/executer_tests_dans_conteneur.py /app/executer_tests_dans_conteneur.py

WORKDIR /app
USER 10001:10001
ENV PYTHONDONTWRITEBYTECODE=1

ENTRYPOINT ["python", "executer_dans_conteneur.py"]
