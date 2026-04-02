"""
Unit tests for shared_core.minio_utils — pure helper functions.
"""

from shared_core.minio_utils import is_minio_path, get_object_name


class TestIsMinioPath:

    def test_s3_path(self):
        assert is_minio_path("s3://videos/assets/file.mp4") is True

    def test_local_path(self):
        assert is_minio_path("/tmp/file.mp4") is False

    def test_empty_string(self):
        assert is_minio_path("") is False

    def test_none(self):
        assert is_minio_path(None) is False

    def test_http_path(self):
        assert is_minio_path("https://example.com/file.mp4") is False


class TestGetObjectName:

    def test_standard_s3_path(self):
        result = get_object_name("s3://videos/assets/video/abc_test.mp4")
        assert result == "assets/video/abc_test.mp4"

    def test_nested_path(self):
        result = get_object_name("s3://videos/outputs/review_job_1.mp4")
        assert result == "outputs/review_job_1.mp4"

    def test_non_s3_path_returned_as_is(self):
        result = get_object_name("some/local/path.mp4")
        assert result == "some/local/path.mp4"

    def test_path_with_segments(self):
        result = get_object_name("s3://videos/assets/segments/01_hook/clip1.mov")
        assert result == "assets/segments/01_hook/clip1.mov"
