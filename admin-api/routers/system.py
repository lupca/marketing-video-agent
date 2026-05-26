"""
System router - Facade mounting all segregated sub-routers (health, workers, templates, models, tts, capcut).
Ensures 100% backward compatibility of the API specification.
"""

from fastapi import APIRouter

# Import sub-routers
from routers.system_health import router as health_router
from routers.system_workers import router as workers_router
from routers.system_templates import router as templates_router
from routers.system_models import router as models_router
from routers.system_tts import router as tts_router
from routers.system_capcut import router as capcut_router

# Initialize the main system router with prefix /api and tag System
router = APIRouter(prefix="/api", tags=["System"])

# Include sub-routers
router.include_router(health_router)
router.include_router(workers_router)
router.include_router(templates_router)
router.include_router(models_router)
router.include_router(tts_router)
router.include_router(capcut_router)
