"""API PRISME (§5.1, §5.5) : ingestion, exécution, canaux opérationnel et audit.

Documentation OpenAPI générée automatiquement par FastAPI, disponible sur
`/docs` (Swagger UI) et `/openapi.json` une fois l'application servie.
"""

from __future__ import annotations

from fastapi import FastAPI

from api.routes import audit, execution, ingestion, planning

app = FastAPI(
    title="PRISME",
    description=(
        "Génération et exécution de solveurs d'ordonnancement pilotée par IA "
        "(Flexible Job-Shop Scheduling, OR-Tools CP-SAT)."
    ),
    version="0.1.0",
)

app.include_router(ingestion.router)
app.include_router(execution.router)
app.include_router(planning.router)
app.include_router(audit.router)
