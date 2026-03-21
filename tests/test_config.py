"""
Unit tests for shared_core.config
"""

import os
import pytest


class TestConfig:
    """Test centralized configuration loading."""

    def test_default_config_loads(self):
        """Config should load with reasonable defaults."""
        # Clear the lru_cache to force re-creation
        from shared_core.config import get_settings
        get_settings.cache_clear()
        cfg = get_settings()

        assert cfg.db.pool_size == 5
        assert cfg.db.max_overflow == 10
        assert cfg.db.pool_pre_ping is True
        assert cfg.auth.algorithm == "HS256"
        assert cfg.auth.access_token_expire_minutes == 60 * 24 * 7  # 7 days

    def test_minio_config_defaults(self):
        from shared_core.config import get_settings
        get_settings.cache_clear()
        cfg = get_settings()

        assert cfg.minio.bucket_name == "videos"
        assert cfg.minio.secure is False

    def test_redis_config(self):
        from shared_core.config import get_settings
        get_settings.cache_clear()
        cfg = get_settings()

        # Should have a valid URL
        assert "redis" in cfg.redis.url

    def test_config_is_frozen(self):
        """Config dataclasses should be immutable."""
        from shared_core.config import get_settings
        get_settings.cache_clear()
        cfg = get_settings()

        with pytest.raises(AttributeError):
            cfg.db.pool_size = 999
