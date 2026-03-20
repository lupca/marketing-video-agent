from fastapi import APIRouter, HTTPException
from .make_viral import make_viral

router = APIRouter(prefix="/video-unbox", tags=["Video Unbox"])

@router.post("/preview")
def preview_unbox(config: dict):
    try:
        result = make_viral(config, preview=True)
        return {"status": "success", "preview": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/render")
def render_unbox(config: dict):
    """Trigger a synchronous full render (for small/quick jobs)."""
    try:
        result = make_viral(config, preview=False)
        return {"status": "success", "output": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
