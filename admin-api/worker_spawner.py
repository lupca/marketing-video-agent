import os
import subprocess
import signal
import logging
import json
from typing import Dict, Optional

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = "/tmp/worker_spawner_state.json"

# Worker definitions: worker_type -> (venv_path, work_dir, queue, concurrency)
VENV_LIGHT = ".venv-light"
VENV_HEAVY = ".venv-heavy"

WORKER_DEFS: Dict[str, dict] = {
    # GPU / Heavy AI workers (using MoviePy 1.0.3 + PyTorch + CUDA)
    "review":    {"venv": VENV_HEAVY, "cwd": "worker_review",    "queue": "review_queue",    "concurrency": 2},
    "unbox":     {"venv": VENV_HEAVY, "cwd": "worker_unbox",     "queue": "unbox_queue",     "concurrency": 2},
    "translify": {"venv": VENV_HEAVY, "cwd": "worker_translify", "queue": "translify_queue", "concurrency": 1},
    "agent":     {"venv": VENV_HEAVY, "cwd": "worker_agent",     "queue": "agent_queue",     "concurrency": 1},
    
    # CPU / Light workers (using MoviePy 2.x, APIs, scrapers)
    "download":  {"venv": VENV_LIGHT, "cwd": "worker_download",  "queue": "download_queue",  "concurrency": 3},
    "slideshow": {"venv": VENV_LIGHT, "cwd": "worker_slideshow", "queue": "slideshow_queue", "concurrency": 2},
    "promotion": {"venv": VENV_LIGHT, "cwd": "worker_promotion", "queue": "promotion_queue", "concurrency": 2},
    "research":  {"venv": VENV_LIGHT, "cwd": "worker_research",  "queue": "research_queue",  "concurrency": 2},
    "text2img":  {"venv": VENV_LIGHT, "cwd": "worker_text2img",  "queue": "text2img_queue",  "concurrency": 2},
}

# Track running processes: worker_type -> PID (persisted)
_worker_pids: Dict[str, int] = {}


def _save_state():
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(_worker_pids, f)
    except Exception as e:
        logger.error(f"Failed to save spawner state: {e}")


def _load_state():
    global _worker_pids
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                _worker_pids = json.load(f)
            # Verify if processes are still alive
            for wtype, pid in list(_worker_pids.items()):
                if not _is_pid_alive(pid):
                    del _worker_pids[wtype]
            _save_state()
        except Exception as e:
            logger.error(f"Failed to load spawner state: {e}")


def _is_pid_alive(pid: int) -> bool:
    """Check if a PID is still running."""
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


# Load state on module import
_load_state()


def start_worker(worker_type: str) -> bool:
    """
    Start a Celery worker process for the given type.
    """
    if worker_type not in WORKER_DEFS:
        return False

    # Check if already running
    if worker_type in _worker_pids and _is_pid_alive(_worker_pids[worker_type]):
        logger.info(f"Worker '{worker_type}' is already running (PID={_worker_pids[worker_type]})")
        return True

    defn = WORKER_DEFS[worker_type]
    venv_path = os.path.join(ROOT_DIR, defn["venv"])
    work_dir = os.path.join(ROOT_DIR, defn["cwd"])
    celery_bin = os.path.join(venv_path, "bin", "celery")

    cmd = [
        celery_bin, "-A", "celery_worker", "worker",
        "-Q", defn["queue"], "-n", f"worker_{worker_type}@%h",
        "--loglevel=info", "-c", str(defn["concurrency"]),
    ]

    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT_DIR

    try:
        # Start in its own process group
        proc = subprocess.Popen(cmd, cwd=work_dir, env=env, preexec_fn=os.setsid)
        _worker_pids[worker_type] = proc.pid
        _save_state()
        logger.info(f"🚀 Started worker '{worker_type}' (PID={proc.pid})")
        return True
    except Exception as e:
        logger.error(f"Failed to start worker '{worker_type}': {e}")
        return False


def stop_worker(worker_type: str) -> bool:
    """
    Stop a running Celery worker process.
    """
    pid = _worker_pids.get(worker_type)
    if not pid or not _is_pid_alive(pid):
        _worker_pids.pop(worker_type, None)
        _save_state()
        return True

    try:
        # Kill the entire process group
        os.killpg(os.getpgid(pid), signal.SIGTERM)
        logger.info(f"🛑 Stopped worker '{worker_type}' (PID={pid})")
    except Exception as e:
        logger.error(f"Error stopping worker '{worker_type}': {e}")
    finally:
        _worker_pids.pop(worker_type, None)
        _save_state()

    return True


def get_worker_status(worker_type: str) -> dict:
    pid = _worker_pids.get(worker_type)
    running = _is_pid_alive(pid) if pid else False
    return {"worker_type": worker_type, "running": running, "pid": pid if running else None}


def get_all_statuses() -> list:
    return [get_worker_status(wt) for wt in WORKER_DEFS]


def shutdown_all():
    """Stop all managed workers."""
    for wt in list(_worker_pids.keys()):
        stop_worker(wt)
