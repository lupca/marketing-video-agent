"""
MinIO / S3 utility functions with lazy client initialization and proper logging.
"""

import io
import os
import logging
import time
from functools import wraps
from typing import List, Dict, Optional

from minio import Minio
from minio.error import S3Error

from shared_core.config import get_settings

logger = logging.getLogger(__name__)

# ── Lazy Client Singleton ─────────────────────────────────────────────────────

_client: Optional[Minio] = None


def get_minio_client() -> Minio:
    """Lazy-initialize and return the MinIO client singleton."""
    global _client
    if _client is None:
        cfg = get_settings().minio
        _client = Minio(
            cfg.endpoint,
            access_key=cfg.access_key,
            secret_key=cfg.secret_key,
            secure=cfg.secure,
        )
        logger.info("MinIO client initialized → %s", cfg.endpoint)
    return _client


def get_bucket_name() -> str:
    return get_settings().minio.bucket_name


# Keep backward-compatible module-level aliases
# These are properties that lazily resolve to avoid import-time failures.
def _get_legacy_client():
    return get_minio_client()


# ── Retry Decorator ──────────────────────────────────────────────────────────

def _retry(max_retries: int = 3, delay: float = 1.0):
    """Simple retry decorator for transient S3 errors."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except S3Error as e:
                    last_error = e
                    if attempt < max_retries:
                        logger.warning(
                            "S3 error on attempt %d/%d for %s: %s. Retrying in %.1fs...",
                            attempt, max_retries, func.__name__, e, delay,
                        )
                        time.sleep(delay * attempt)
                    else:
                        logger.error("S3 error on final attempt %d/%d for %s: %s", attempt, max_retries, func.__name__, e)
                        raise
                except Exception:
                    raise  # Non-S3 errors are not retried
            raise last_error  # Should not reach here
        return wrapper
    return decorator


# ── Core Operations ──────────────────────────────────────────────────────────

def ensure_bucket_exists() -> None:
    """Ensure the target bucket exists, creating it if necessary."""
    client = get_minio_client()
    bucket = get_bucket_name()
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
            logger.info("Bucket '%s' created.", bucket)
    except S3Error as err:
        logger.error("MinIO bucket check/create error: %s", err)
        raise


@_retry()
def upload_file_to_minio(object_name: str, file_path: str) -> str:
    """Upload a local file to MinIO. Returns s3:// URI."""
    ensure_bucket_exists()
    client = get_minio_client()
    bucket = get_bucket_name()
    client.fput_object(bucket, object_name, file_path)
    uri = f"s3://{bucket}/{object_name}"
    logger.info("Uploaded %s → %s", file_path, uri)
    return uri


@_retry()
def upload_bytes_to_minio(
    object_name: str,
    file_data,
    length: int,
    content_type: str = "application/octet-stream",
) -> str:
    """Upload raw bytes or file-like object to MinIO. Returns s3:// URI."""
    ensure_bucket_exists()
    client = get_minio_client()
    bucket = get_bucket_name()
    if isinstance(file_data, bytes):
        file_data = io.BytesIO(file_data)
    client.put_object(bucket, object_name, file_data, length, content_type=content_type)
    uri = f"s3://{bucket}/{object_name}"
    logger.info("Uploaded bytes → %s (%d bytes)", uri, length)
    return uri


@_retry()
def download_file_from_minio(object_name: str, file_path: str) -> str:
    """Download a file from MinIO to the local filesystem."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    client = get_minio_client()
    bucket = get_bucket_name()
    client.fget_object(bucket, object_name, file_path)
    logger.debug("Downloaded %s → %s", object_name, file_path)
    return file_path


@_retry()
def delete_object_from_minio(object_name: str) -> None:
    """Delete an object from MinIO."""
    client = get_minio_client()
    bucket = get_bucket_name()
    client.remove_object(bucket, object_name)
    logger.info("Deleted object: %s", object_name)


def list_objects_from_minio(prefix: str = "") -> List[Dict]:
    """List objects in the bucket with optional prefix filter."""
    client = get_minio_client()
    bucket = get_bucket_name()
    objects = client.list_objects(bucket, prefix=prefix, recursive=True)
    return [{"name": obj.object_name, "size": obj.size} for obj in objects]


def get_presigned_url(object_name: str, expires_seconds: int = 7200) -> str:
    """Generate a presigned GET URL for an object."""
    from datetime import timedelta
    client = get_minio_client()
    bucket = get_bucket_name()
    return client.presigned_get_object(bucket, object_name, expires=timedelta(seconds=expires_seconds))


# ── Pure Helpers (no network calls) ──────────────────────────────────────────

def is_minio_path(path: str) -> bool:
    """Check if a path is an s3:// URI."""
    return isinstance(path, str) and path.startswith("s3://")


def is_downloadable_path(path: str) -> bool:
    """Check if a path is downloadable (either s3:// or http:// or https://)."""
    return isinstance(path, str) and (path.startswith("s3://") or path.startswith("http://") or path.startswith("https://"))


def get_object_name(s3_path: str) -> str:
    """Extract object name from an s3:// URI."""
    bucket = get_bucket_name()
    prefix = f"s3://{bucket}/"
    if s3_path.startswith(prefix):
        return s3_path[len(prefix):]
    return s3_path


def download_file_or_s3(url_or_s3_path: str, local_path: str) -> str:
    """
    Tải tài nguyên từ MinIO s3:// hoặc qua HTTP/HTTPS về đường dẫn cục bộ.
    """
    import os
    import requests
    
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    
    if is_minio_path(url_or_s3_path):
        obj_name = get_object_name(url_or_s3_path)
        download_file_from_minio(obj_name, local_path)
        logger.info(f"Downloaded from MinIO: {url_or_s3_path} -> {local_path}")
        return local_path
        
    elif isinstance(url_or_s3_path, str) and (url_or_s3_path.startswith("http://") or url_or_s3_path.startswith("https://")):
        logger.info(f"Downloading remote HTTP asset: {url_or_s3_path} -> {local_path}")
        response = requests.get(url_or_s3_path, stream=True, timeout=60)
        response.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        logger.info(f"Successfully downloaded HTTP asset: {local_path}")
        return local_path
        
    else:
        # Nếu đã tồn tại dưới dạng tệp cục bộ
        if isinstance(url_or_s3_path, str) and os.path.exists(url_or_s3_path):
            import shutil
            shutil.copy2(url_or_s3_path, local_path)
            logger.info(f"Copied local file: {url_or_s3_path} -> {local_path}")
            return local_path
        return url_or_s3_path
