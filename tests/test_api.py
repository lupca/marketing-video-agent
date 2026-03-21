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
