"""
We need a thin wrapper to import the FastAPI app from admin-api
in a way that works for pytest running from the project root.
"""

import sys
import os

# Ensure admin-api is importable
_admin_api_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "admin-api")
if _admin_api_dir not in sys.path:
    sys.path.insert(0, _admin_api_dir)

from main import app  # noqa: F401

__all__ = ["app"]
