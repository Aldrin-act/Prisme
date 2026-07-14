# Image du bac à sable éphémère (§5.2, §5.3, §7) : surface minimale,
# utilisateur non-root, aucun outil réseau ou de diagnostic superflu.
# Construction : docker build -t prisme-sandbox:latest -f sandbox/container/Dockerfile .
# (exécuter depuis la racine du dépôt, pour que `dsl/` soit dans le contexte)

FROM python:3.11-slim

RUN pip install --no-cache-dir "ortools>=9.9" "pydantic>=2.6" \
    && useradd --no-create-home --uid 10001 --shell /usr/sbin/nologin executant

COPY dsl/ /app/dsl/
COPY sandbox/container/executer_dans_conteneur.py /app/executer_dans_conteneur.py

WORKDIR /app
USER 10001:10001

ENTRYPOINT ["python", "executer_dans_conteneur.py"]
