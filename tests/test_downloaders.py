"""
Unit tests for is_downloadable_path, download_file_or_s3, and worker downloaders.
Uses sys.modules mocking to ensure tests are environment-agnostic.
"""

import os
import sys
import shutil
import tempfile
from unittest.mock import patch, MagicMock

# Mock heavy/external modules to prevent import failures in different virtualenvs
sys.modules['moviepy'] = MagicMock()
sys.modules['moviepy.editor'] = MagicMock()
sys.modules['video_builder'] = MagicMock()
sys.modules['slideshow_engine'] = MagicMock()
sys.modules['slideshow_engine.config'] = MagicMock()
sys.modules['slideshow_engine.pipeline'] = MagicMock()
sys.modules['slideshow_engine.data_input'] = MagicMock()
sys.modules['video_pipeline'] = MagicMock()
sys.modules['video_pipeline.logo_overlay'] = MagicMock()
sys.modules['make_viral'] = MagicMock()
sys.modules['unbox_viral'] = MagicMock()

import pytest

from shared_core.minio_utils import is_downloadable_path, download_file_or_s3
from worker_review.celery_worker import prepare_working_directory
from worker_unbox.celery_worker import download_unbox_assets
from worker_slideshow.celery_worker import download_slideshow_assets


def test_is_downloadable_path():
    assert is_downloadable_path("s3://videos/sample.mp4") is True
    assert is_downloadable_path("http://assets.mixkit.co/videos/preview/sample.mp4") is True
    assert is_downloadable_path("https://assets.mixkit.co/videos/preview/sample.mp4") is True
    assert is_downloadable_path("/root/local/file.mp4") is False
    assert is_downloadable_path("raw/1/video.mp4") is False


@patch("shared_core.minio_utils.download_file_from_minio")
@patch("requests.get")
def test_download_file_or_s3(mock_get, mock_download_minio):
    # 1. Test MinIO path
    download_file_or_s3("s3://videos/sample.mp4", "/tmp/local_sample.mp4")
    mock_download_minio.assert_called_once_with("sample.mp4", "/tmp/local_sample.mp4")
    mock_download_minio.reset_mock()

    # 2. Test HTTP path
    mock_response = MagicMock()
    mock_response.iter_content.return_value = [b"data1", b"data2"]
    mock_get.return_value = mock_response

    with patch("builtins.open", MagicMock()) as mock_open:
        download_file_or_s3("https://example.com/test.mp3", "/tmp/local_test.mp3")
        mock_get.assert_called_once_with("https://example.com/test.mp3", stream=True, timeout=60)
        mock_response.raise_for_status.assert_called_once()


@patch("worker_review.celery_worker._download_s3")
@patch("worker_review.celery_worker._download_s3_folder")
def test_review_prepare_working_directory(mock_download_folder, mock_download_s3):
    work_dir = tempfile.mkdtemp()
    try:
        config_data = {
            "bgm_path": "https://assets.mixkit.co/music/sample.mp3",
            "scenes": [
                {
                    "scene_id": "01_hook",
                    "clip_url": "https://assets.mixkit.co/videos/preview/sample.mp4",
                    "text_overlay": "Hook Text",
                    "duration": 5.0
                }
            ]
        }
        res = prepare_working_directory(config_data, work_dir)
        
        # Verify bgm and clip download functions were called
        mock_download_s3.assert_any_call("https://assets.mixkit.co/music/sample.mp3", os.path.join(work_dir, "raw", "bgm.mp3"))
        mock_download_s3.assert_any_call("https://assets.mixkit.co/videos/preview/sample.mp4", os.path.join(work_dir, "raw", "1", "sample.mp4"))
        
        # Verify paths in config were mapped locally
        assert res["bgm_path"] == "raw/bgm.mp3"
        assert res["scenes"][0]["clip_url"] == "raw/1/"
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@patch("worker_unbox.celery_worker.download_file_or_s3")
@patch("worker_unbox.celery_worker.ensure_h264_mp4", side_effect=lambda x: x)
def test_unbox_download_assets(mock_h264, mock_download):
    work_dir = tempfile.mkdtemp()
    try:
        config_data = {
            "bgm_path": "https://assets.mixkit.co/music/sample.mp3",
            "scenes": [
                {
                    "scene_id": "01_hook",
                    "clip_url": "https://assets.mixkit.co/videos/preview/sample.mp4",
                }
            ]
        }
        res = download_unbox_assets(config_data, work_dir)
        
        # Verify download functions called
        mock_download.assert_any_call("https://assets.mixkit.co/music/sample.mp3", os.path.join(work_dir, "input", "sample.mp3"))
        mock_download.assert_any_call("https://assets.mixkit.co/videos/preview/sample.mp4", os.path.join(work_dir, "input", "sample.mp4"))
        
        # Verify local path mappings
        assert res["bgm_path"] == os.path.join(work_dir, "input", "sample.mp3")
        assert res["scenes"][0]["clip_url"] == os.path.join(work_dir, "input", "sample.mp4")
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


@patch("worker_slideshow.celery_worker.download_file_or_s3")
def test_slideshow_download_assets(mock_download):
    work_dir = tempfile.mkdtemp()
    try:
        config_data = {
            "bgm_path": "https://assets.mixkit.co/music/sample.mp3",
            "scenes": [
                {
                    "scene_id": "01_hook",
                    "clip_url": "https://assets.com/image.png",
                }
            ]
        }
        res = download_slideshow_assets(config_data, work_dir)
        
        # Verify local download mappings
        mock_download.assert_any_call("https://assets.mixkit.co/music/sample.mp3", os.path.join(work_dir, "bg_music.mp3"))
        mock_download.assert_any_call("https://assets.com/image.png", os.path.join(work_dir, "images", "image.png"))
        
        assert res["bgm_path"] == "bg_music.mp3"
        assert res["scenes"][0]["clip_url"] == "image.png"
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
