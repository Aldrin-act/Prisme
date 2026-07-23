"""API PRISME (§5.1, §5.5) : ingestion, exécution, canaux opérationnel et audit,
et le tableau de bord (§2.3, Phase 10) — validation humaine, diagnostic.

Documentation OpenAPI générée automatiquement par FastAPI, disponible sur
`/docs` (Swagger UI) et `/openapi.json` une fois l'application servie.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import (
    adapters,
    audit,
    auth,
    diagnostics,
    execution,
    ingestion,
    planning,
    projets,
    supervision,
    validation,
)

app = FastAPI(
    title="PRISME",
    description=(
        "Génération et exécution de solveurs d'ordonnancement pilotée par IA "
        "(Flexible Job-Shop Scheduling, OR-Tools CP-SAT)."
    ),
    version="0.1.0",
)

# Dev uniquement : le dashboard (Vite, port variable selon disponibilité) et l'API (uvicorn,
# :8000) tournent en processus séparés, sans étape de build/déploiement commune pour ce PoC.
# Regex plutôt qu'une liste de ports fixes : Vite change de port si le précédent est occupé.
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(ingestion.router)
app.include_router(adapters.router)
app.include_router(projets.router)
app.include_router(execution.router)
app.include_router(planning.router)
app.include_router(audit.router)
app.include_router(validation.router)
app.include_router(diagnostics.router)
app.include_router(supervision.router)
