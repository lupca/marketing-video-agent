"""
Prompt template loading utilities.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Resolve the worker_leader package root once at module level.
_WORKER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_prompt(filename: str) -> str:
    """
    Safely load a prompt template from the ``prompts/`` directory.

    Args:
        filename: Name of the prompt file (e.g. ``leader_system_prompt.txt``).

    Returns:
        The full text content of the prompt file.

    Raises:
        The original exception if the file cannot be read.
    """
    path = os.path.join(_WORKER_DIR, "prompts", filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Failed to load prompt file {filename}: {e}")
        raise e
