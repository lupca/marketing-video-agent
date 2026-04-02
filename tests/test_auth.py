"""
Unit tests for admin-api auth module — password hashing, JWT tokens.
"""

import sys
import os
import time

# Ensure admin-api is importable
_admin_api_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "admin-api")
if _admin_api_dir not in sys.path:
    sys.path.insert(0, _admin_api_dir)

import jwt as pyjwt
from auth import verify_password, get_password_hash, create_access_token
from shared_core.config import get_settings


class TestPasswordHashing:

    def test_hash_and_verify(self):
        password = "my_secure_password"
        hashed = get_password_hash(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails(self):
        hashed = get_password_hash("correct_password")
        assert verify_password("wrong_password", hashed) is False

    def test_hash_is_unique(self):
        """Two hashes of the same password should be different (salt)."""
        h1 = get_password_hash("same_password")
        h2 = get_password_hash("same_password")
        assert h1 != h2

    def test_verify_with_bytes_hash(self):
        password = "test123"
        hashed = get_password_hash(password)
        # Simulate bytes stored in DB
        assert verify_password(password, hashed.encode("utf-8")) is True


class TestJWTTokens:

    def test_create_and_decode_token(self):
        cfg = get_settings().auth
        token = create_access_token(data={"sub": "user-123"})
        payload = pyjwt.decode(token, cfg.secret_key, algorithms=[cfg.algorithm])
        assert payload["sub"] == "user-123"
        assert "exp" in payload

    def test_token_has_correct_expiry(self):
        """Token should use configured expiry (7 days), not 15 minutes."""
        cfg = get_settings().auth
        token = create_access_token(data={"sub": "user-456"})
        payload = pyjwt.decode(token, cfg.secret_key, algorithms=[cfg.algorithm])

        now = time.time()
        exp = payload["exp"]
        # Should expire roughly 7 days from now (with tolerance)
        expected_seconds = cfg.access_token_expire_minutes * 60
        actual_seconds = exp - now
        assert actual_seconds > expected_seconds - 60  # within 1 minute tolerance
        assert actual_seconds < expected_seconds + 60

    def test_custom_expiry_delta(self):
        from datetime import timedelta
        cfg = get_settings().auth
        token = create_access_token(
            data={"sub": "user-789"},
            expires_delta=timedelta(hours=1),
        )
        payload = pyjwt.decode(token, cfg.secret_key, algorithms=[cfg.algorithm])
        now = time.time()
        exp = payload["exp"]
        # Should expire in ~1 hour
        assert 3500 < (exp - now) < 3700
