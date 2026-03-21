"""
Video Creator Platform — Admin API
Slim main entry point: middleware, lifespan, and router mounting.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from shared_core import models, database

from routers.auth_router import router as auth_router
from routers.projects import router as projects_router
from routers.assets import router as assets_router
from routers.jobs import router as jobs_router
from routers.downloads import router as downloads_router
from routers.system import router as system_router

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Create DB Tables ──────────────────────────────────────────────────────────

models.Base.metadata.create_all(bind=database.engine)

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Video Creator Platform API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Global Exception Handler ─────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )

# ── Mount Routers ─────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(assets_router)
app.include_router(jobs_router)
app.include_router(downloads_router)
app.include_router(system_router)
