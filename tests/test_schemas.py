"""
Unit tests for shared_core.schemas — validation rules.
"""

import pytest
from shared_core.schemas import (
    UserCreate, JobCreate, ProjectCreate,
    TemplateCreate, VALID_JOB_TYPES,
)


class TestUserCreateSchema:

    def test_valid_user(self):
        user = UserCreate(email="test@example.com", password="secure123")
        assert user.email == "test@example.com"

    def test_invalid_email(self):
        with pytest.raises(Exception):
            UserCreate(email="not-an-email", password="secure123")

    def test_password_too_short(self):
        with pytest.raises(Exception):
            UserCreate(email="test@example.com", password="abc")

    def test_password_min_length(self):
        user = UserCreate(email="test@example.com", password="123456")
        assert user.password == "123456"


class TestJobCreateSchema:

    def test_valid_review_job(self):
        job = JobCreate(
            job_type="review",
            config_data={"key": "value"},
            project_id="proj-123",
        )
        assert job.job_type == "review"
        assert job.priority == 0
        assert job.asset_ids == []

    def test_valid_unbox_job(self):
        job = JobCreate(
            job_type="unbox",
            config_data={},
            project_id="proj-123",
        )
        assert job.job_type == "unbox"

    def test_invalid_job_type(self):
        with pytest.raises(Exception):
            JobCreate(
                job_type="invalid_type",
                config_data={},
                project_id="proj-123",
            )

    def test_with_priority_and_assets(self):
        job = JobCreate(
            job_type="review",
            config_data={"timeline_script": []},
            project_id="proj-123",
            priority=5,
            asset_ids=["a1", "a2"],
        )
        assert job.priority == 5
        assert len(job.asset_ids) == 2


class TestProjectCreateSchema:

    def test_valid_project(self):
        proj = ProjectCreate(name="My Project")
        assert proj.name == "My Project"
        assert proj.description is None

    def test_project_with_description(self):
        proj = ProjectCreate(name="Project X", description="Test desc")
        assert proj.description == "Test desc"

    def test_empty_name_rejected(self):
        with pytest.raises(Exception):
            ProjectCreate(name="   ")


class TestTemplateCreateSchema:

    def test_valid_template(self):
        t = TemplateCreate(
            name="Default Review",
            job_type="review",
            default_config_data={"key": "val"},
        )
        assert t.is_active is True

    def test_invalid_job_type(self):
        with pytest.raises(Exception):
            TemplateCreate(
                name="Bad Template",
                job_type="nonexistent",
                default_config_data={},
            )

    def test_valid_job_types_constant(self):
        assert "review" in VALID_JOB_TYPES
        assert "unbox" in VALID_JOB_TYPES
