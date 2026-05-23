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
from routers.folders import router as folders_router
from routers.jobs import router as jobs_router
from routers.downloads import router as downloads_router
from routers.system import router as system_router
from routers.agent import router as agent_router
from routers.worker_config import router as worker_config_router
from routers.translify import router as translify_router

# ── Logging ───────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Create DB Tables ──────────────────────────────────────────────────────────

models.Base.metadata.create_all(bind=database.engine)

from contextlib import asynccontextmanager
import worker_spawner

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic can go here
    yield
    # Shutdown logic: Kill all managed workers
    logger.info("Lifespan: Shutting down all managed workers...")
    worker_spawner.shutdown_all()

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Video Creator Platform API", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9173", "http://localhost:3000"],
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
app.include_router(folders_router)
app.include_router(jobs_router)
app.include_router(downloads_router)
app.include_router(system_router)
app.include_router(agent_router)
app.include_router(worker_config_router)
app.include_router(translify_router)
