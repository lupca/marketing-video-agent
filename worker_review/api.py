from fastapi import APIRouter, HTTPException
from .video_builder import build_video

router = APIRouter(prefix="/video-review", tags=["Video Review"])

@router.post("/preview")
def preview_video(config: dict):
    try:
        result = build_video(config, preview=True)
        return {"status": "success", "preview": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/render")
def render_video(config: dict):
    """Trigger a synchronous full render (for small/quick jobs)."""
    try:
        result = build_video(config, preview=False)
        return {"status": "success", "output": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
