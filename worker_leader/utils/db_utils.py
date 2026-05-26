"""
Database helper utilities for the Leader Agent.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_global_model_setting(key: str) -> Optional[str]:
    """
    Read a model setting from the ``system_settings`` table.

    Args:
        key: The setting key to look up inside the ``model_settings`` JSON value.

    Returns:
        The setting value string, or ``None`` if not found.
    """
    try:
        from shared_core.database import SessionLocal as InternalSessionLocal
        from shared_core.models import SystemSetting

        with InternalSessionLocal() as db:
            setting = db.query(SystemSetting).filter(
                SystemSetting.key == "model_settings"
            ).first()
            if setting and setting.value and isinstance(setting.value, dict):
                return setting.value.get(key)
    except Exception:
        pass
    return None
