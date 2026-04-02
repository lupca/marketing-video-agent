"""
Integration tests for the Admin API — exercises full HTTP request/response cycle.
Uses FastAPI TestClient with SQLite in-memory DB.
"""

import pytest
from unittest.mock import patch


class TestHealthEndpoint:

    def test_health_returns_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestAuthFlow:

    def test_register_new_user(self, client):
        resp = client.post("/api/auth/register", json={
            "email": "new@example.com",
            "password": "secure123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "new@example.com"
        assert data["role"] == "creator"
        assert "id" in data

    def test_register_duplicate_email(self, client):
        client.post("/api/auth/register", json={
            "email": "dup@example.com",
            "password": "secure123",
        })
        resp = client.post("/api/auth/register", json={
            "email": "dup@example.com",
            "password": "secure456",
        })
        assert resp.status_code == 400

    def test_login_success(self, client):
        client.post("/api/auth/register", json={
            "email": "login@example.com",
            "password": "secure123",
        })
        resp = client.post("/api/auth/login", json={
            "email": "login@example.com",
            "password": "secure123",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["email"] == "login@example.com"

    def test_login_wrong_password(self, client):
        client.post("/api/auth/register", json={
            "email": "wrong@example.com",
            "password": "correct123",
        })
        resp = client.post("/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "incorrect",
        })
        assert resp.status_code == 401

    def test_get_me(self, client, auth_headers):
        resp = client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["email"] == "test@example.com"

    def test_unauthorized_without_token(self, client):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 401


class TestProjectsCRUD:

    def test_create_project(self, authenticated_client):
        resp = authenticated_client.post("/api/projects", json={
            "name": "My Video Project",
            "description": "Test project",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "My Video Project"
        assert "id" in data

    def test_list_projects(self, authenticated_client):
        authenticated_client.post("/api/projects", json={"name": "P1"})
        authenticated_client.post("/api/projects", json={"name": "P2"})

        resp = authenticated_client.get("/api/projects")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_delete_project(self, authenticated_client):
        resp = authenticated_client.post("/api/projects", json={"name": "ToDelete"})
        proj_id = resp.json()["id"]

        del_resp = authenticated_client.delete(f"/api/projects/{proj_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # Verify it's gone
        list_resp = authenticated_client.get("/api/projects")
        assert len(list_resp.json()) == 0

    def test_delete_nonexistent_project(self, authenticated_client):
        resp = authenticated_client.delete("/api/projects/nonexistent-id")
        assert resp.status_code == 404


class TestJobsCRUD:

    @patch("celery_client.celery_app.send_task")
    def test_create_job(self, mock_send_task, authenticated_client, test_project):
        resp = authenticated_client.post("/api/jobs", json={
            "job_type": "review",
            "config_data": {"timeline_script": []},
            "project_id": test_project.id,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_type"] == "review"
        assert data["status"] == "PENDING"
        assert data["progress_percent"] == 0
        mock_send_task.assert_called_once()

    def test_create_job_invalid_type(self, authenticated_client, test_project):
        resp = authenticated_client.post("/api/jobs", json={
            "job_type": "invalid",
            "config_data": {},
            "project_id": test_project.id,
        })
        assert resp.status_code == 422  # Validation error

    @patch("celery_client.celery_app.send_task")
    def test_list_jobs(self, mock_send_task, authenticated_client, test_project):
        authenticated_client.post("/api/jobs", json={
            "job_type": "review",
            "config_data": {},
            "project_id": test_project.id,
        })
        resp = authenticated_client.get("/api/jobs")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1

    @patch("celery_client.celery_app.send_task")
    def test_get_single_job(self, mock_send_task, authenticated_client, test_project):
        create_resp = authenticated_client.post("/api/jobs", json={
            "job_type": "review",
            "config_data": {"test": True},
            "project_id": test_project.id,
        })
        job_id = create_resp.json()["id"]

        resp = authenticated_client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == job_id

    @patch("celery_client.celery_app.send_task")
    def test_delete_job(self, mock_send_task, authenticated_client, test_project):
        create_resp = authenticated_client.post("/api/jobs", json={
            "job_type": "unbox",
            "config_data": {},
            "project_id": test_project.id,
        })
        job_id = create_resp.json()["id"]

        del_resp = authenticated_client.delete(f"/api/jobs/{job_id}")
        assert del_resp.status_code == 200

    def test_get_nonexistent_job(self, authenticated_client):
        resp = authenticated_client.get("/api/jobs/99999")
        assert resp.status_code == 404

    def test_create_job_wrong_project(self, authenticated_client):
        resp = authenticated_client.post("/api/jobs", json={
            "job_type": "review",
            "config_data": {},
            "project_id": "nonexistent-project-id",
        })
        assert resp.status_code == 403


class TestTemplates:

    def test_create_template(self, authenticated_client):
        resp = authenticated_client.post("/api/templates", json={
            "name": "Default Review",
            "job_type": "review",
            "default_config_data": {"resolution": [1080, 1920]},
            "is_active": True,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Default Review"
        assert "id" in data

    def test_list_templates(self, authenticated_client):
        authenticated_client.post("/api/templates", json={
            "name": "T1",
            "job_type": "review",
            "default_config_data": {},
            "is_active": True,
        })
        resp = authenticated_client.get("/api/templates")
        assert resp.status_code == 200
        assert len(resp.json()) >= 1


class TestDownloadsCRUD:

    @patch("celery_client.celery_app.send_task")
    def test_create_download_job(self, mock_send_task, authenticated_client):
        resp = authenticated_client.post("/api/downloads", json={
            "url": "https://www.youtube.com/watch?v=test123",
            "format": "video",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "PENDING"
        assert data["source_url"] == "https://www.youtube.com/watch?v=test123"
        assert data["format_type"] == "video"
        assert data["progress_percent"] == 0
        assert "id" in data
        mock_send_task.assert_called_once()

    @patch("celery_client.celery_app.send_task")
    def test_create_download_job_audio(self, mock_send_task, authenticated_client):
        resp = authenticated_client.post("/api/downloads", json={
            "url": "https://www.youtube.com/watch?v=audio1",
            "format": "audio",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["format_type"] == "audio"
        assert data["source_url"] == "https://www.youtube.com/watch?v=audio1"

    def test_create_download_job_empty_url(self, authenticated_client):
        resp = authenticated_client.post("/api/downloads", json={
            "url": "   ",
            "format": "video",
        })
        assert resp.status_code == 422

    def test_create_download_job_invalid_format(self, authenticated_client):
        resp = authenticated_client.post("/api/downloads", json={
            "url": "https://example.com/video",
            "format": "invalid",
        })
        assert resp.status_code == 422

    @patch("celery_client.celery_app.send_task")
    def test_list_download_jobs(self, mock_send_task, authenticated_client):
        authenticated_client.post("/api/downloads", json={
            "url": "https://youtube.com/1",
            "format": "video",
        })
        authenticated_client.post("/api/downloads", json={
            "url": "https://youtube.com/2",
            "format": "audio",
        })

        resp = authenticated_client.get("/api/downloads")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    @patch("celery_client.celery_app.send_task")
    def test_get_single_download_job(self, mock_send_task, authenticated_client):
        create_resp = authenticated_client.post("/api/downloads", json={
            "url": "https://youtube.com/single",
            "format": "video",
        })
        job_id = create_resp.json()["id"]

        resp = authenticated_client.get(f"/api/downloads/{job_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == job_id
        assert resp.json()["source_url"] == "https://youtube.com/single"

    @patch("celery_client.celery_app.send_task")
    def test_delete_download_job(self, mock_send_task, authenticated_client):
        create_resp = authenticated_client.post("/api/downloads", json={
            "url": "https://youtube.com/delete-me",
            "format": "video",
        })
        job_id = create_resp.json()["id"]

        del_resp = authenticated_client.delete(f"/api/downloads/{job_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["status"] == "deleted"

        # Verify it's gone
        get_resp = authenticated_client.get(f"/api/downloads/{job_id}")
        assert get_resp.status_code == 404

    def test_get_nonexistent_download_job(self, authenticated_client):
        resp = authenticated_client.get("/api/downloads/99999")
        assert resp.status_code == 404

    @patch("celery_client.celery_app.send_task")
    def test_get_download_job_logs(self, mock_send_task, authenticated_client):
        create_resp = authenticated_client.post("/api/downloads", json={
            "url": "https://youtube.com/logs-test",
            "format": "video",
        })
        job_id = create_resp.json()["id"]

        resp = authenticated_client.get(f"/api/downloads/{job_id}/logs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_download_no_project_required(self, authenticated_client):
        """Verify that download jobs do NOT require project_id."""
        with patch("celery_client.celery_app.send_task"):
            resp = authenticated_client.post("/api/downloads", json={
                "url": "https://tiktok.com/@user/video/123",
                "format": "video",
            })
        assert resp.status_code == 200
        data = resp.json()
        # No project_id field in DownloadJob
        assert "project_id" not in data

    def test_download_type_removed_from_video_jobs(self, authenticated_client, test_project):
        """Verify that 'download' is no longer a valid job_type for video jobs."""
        resp = authenticated_client.post("/api/jobs", json={
            "job_type": "download",
            "config_data": {},
            "project_id": test_project.id,
        })
        assert resp.status_code == 422  # Validation error — 'download' not in VALID_JOB_TYPES
