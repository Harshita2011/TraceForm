"""
# TraceForm FastAPI Application — main entry point.

Mounts all API v1 routes, configures CORS and structured logging,
and provides the startup event for DB table creation in dev mode.
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from teams.auth import WorkspaceBoundary
from api.routes import teams,benchmarks,operations

from api.routes import artifacts, audit, evaluations, generations, health, metrics, sources, settings, presets, workspaces, synthesis

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app = FastAPI(
    title="TraceForm API",
    description="AI content generation with full traceability, compliance, and auditability.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[x.strip() for x in os.getenv('TRACEFORM_WEB_ORIGINS','http://localhost:3000,http://127.0.0.1:3000').split(',')],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=['Content-Disposition'],
)

# Register routes
app.include_router(health.router, prefix="/api/v1")
app.include_router(sources.router, prefix="/api/v1")
app.include_router(generations.router, prefix="/api/v1")
app.include_router(metrics.router, prefix="/api/v1")
app.include_router(evaluations.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(artifacts.router, prefix="/api/v1")
app.include_router(settings.router, prefix="/api/v1")
app.include_router(presets.router, prefix="/api/v1")
app.include_router(workspaces.router, prefix="/api/v1")
app.include_router(synthesis.router, prefix="/api/v1")
app.include_router(teams.router, prefix="/api/v1")
app.include_router(benchmarks.router, prefix="/api/v1")
app.include_router(operations.router, prefix="/api/v1")
app.add_middleware(WorkspaceBoundary)
from operations_logging import RequestEvents
app.add_middleware(RequestEvents)

from synthesis.context import SourceUnavailable


@app.exception_handler(SourceUnavailable)
async def source_unavailable(request, exc):
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=409, content={'detail':str(exc)})


from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    # Pydantic's default error includes raw input; never echo credential-bearing request bodies.
    return JSONResponse(status_code=422, content={"detail": [
        {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
        for error in exc.errors()]})


@app.on_event("startup")
async def on_startup():
    """Check the versioned schema; production migrations run before service startup."""
    from db.session import engine
    from db.migrate import initialize
    await initialize(engine)
    logging.getLogger(__name__).info("Versioned database migrations checked.")
