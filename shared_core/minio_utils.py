import os
import io
from minio import Minio
from minio.error import S3Error

# Initialize MinIO Client
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "videos")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE
)

def ensure_bucket_exists():
    """Ensure the target bucket exists before doing operations."""
    try:
        found = minio_client.bucket_exists(MINIO_BUCKET_NAME)
        if not found:
            minio_client.make_bucket(MINIO_BUCKET_NAME)
            print(f"Bucket '{MINIO_BUCKET_NAME}' created.")
    except S3Error as err:
        print(f"MinIO bucket error: {err}")

def upload_file_to_minio(object_name: str, file_path: str):
    """
    Upload a file from local filesystem to MinIO.
    """
    try:
        ensure_bucket_exists()
        minio_client.fput_object(MINIO_BUCKET_NAME, object_name, file_path)
        return f"s3://{MINIO_BUCKET_NAME}/{object_name}"
    except Exception as e:
        print(f"Failed to upload {file_path} to {object_name}: {e}")
        raise e

def upload_bytes_to_minio(object_name: str, file_data, length: int, content_type: str = "application/octet-stream"):
    """
    Upload raw bytes/file-like object to MinIO.
    """
    try:
        ensure_bucket_exists()
        if isinstance(file_data, bytes):
            file_data = io.BytesIO(file_data)
        minio_client.put_object(MINIO_BUCKET_NAME, object_name, file_data, length, content_type=content_type)
        return f"s3://{MINIO_BUCKET_NAME}/{object_name}"
    except Exception as e:
        print(f"Failed to upload bytes to {object_name}: {e}")
        raise e

def download_file_from_minio(object_name: str, file_path: str):
    """
    Download a file from MinIO to the local filesystem.
    """
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        minio_client.fget_object(MINIO_BUCKET_NAME, object_name, file_path)
        return file_path
    except Exception as e:
        print(f"Failed to download {object_name} to {file_path}: {e}")
        raise e

def delete_object_from_minio(object_name: str):
    """Delete an object from MinIO."""
    try:
        minio_client.remove_object(MINIO_BUCKET_NAME, object_name)
    except Exception as e:
        print(f"Failed to delete {object_name}: {e}")
        raise e

def list_objects_from_minio(prefix: str = ""):
    """List objects in the bucket with optional prefix filter."""
    try:
        objects = minio_client.list_objects(MINIO_BUCKET_NAME, prefix=prefix, recursive=True)
        return [{"name": obj.object_name, "size": obj.size} for obj in objects]
    except Exception as e:
        print(f"Failed to list objects: {e}")
        raise e

def is_minio_path(path: str) -> bool:
    """Helper to check if a path is an s3 URI."""
    return path.startswith("s3://")

def get_object_name(s3_path: str) -> str:
    """Extract object name from a generic s3 URI."""
    prefix = f"s3://{MINIO_BUCKET_NAME}/"
    if s3_path.startswith(prefix):
        return s3_path[len(prefix):]
    return s3_path
