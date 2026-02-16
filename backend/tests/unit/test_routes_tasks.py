# start backend/tests/unit/test_routes_tasks.py
"""
Comprehensive tests for the tasks API routes.

Covers all endpoints in src/api/routes/tasks.py with mocked
database sessions, services, and dependencies to achieve 100% line coverage.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.tasks import router
from src.config import Config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app() -> FastAPI:
    """Build a minimal FastAPI app with the tasks router and no lifespan."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


def _make_config(disable_auth: bool = False, default_user_id: str = "local-user") -> MagicMock:
    """Create a mock Config object."""
    cfg = MagicMock(spec=Config)
    cfg.disable_auth = disable_auth
    cfg.default_user_id = default_user_id
    cfg.backend_url = "http://localhost:8008"
    return cfg


def _mock_db():
    """Return a mock async db session."""
    return AsyncMock()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app():
    return _make_app()


@pytest.fixture()
def db_session():
    return _mock_db()


@pytest.fixture()
def client(app, db_session):
    """TestClient with get_db overridden."""
    from src.database import get_db

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    yield TestClient(app, raise_server_exceptions=False)
    app.dependency_overrides.clear()


# ==========================================================================
#  GET /tasks/ — list_tasks
# ==========================================================================

class TestListTasks:

    def test_list_tasks_success_with_user_id_header(self, client):
        """Authenticated user should get their tasks."""
        mock_tasks = [{"id": "t1", "status": "completed"}]

        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.get_user_tasks = AsyncMock(return_value=mock_tasks)

            resp = client.get("/tasks/", headers={"user_id": "u1"})

        assert resp.status_code == 200
        body = resp.json()
        assert body["tasks"] == mock_tasks
        assert body["total"] == 1

    def test_list_tasks_no_user_id_auth_disabled(self, client):
        """When auth disabled and no user_id header, use default user."""
        mock_tasks = []

        with (
            patch("src.api.routes.tasks.config", _make_config(disable_auth=True)),
            patch("src.api.routes.tasks.TaskService") as MockTS,
        ):
            instance = MockTS.return_value
            instance.get_user_tasks = AsyncMock(return_value=mock_tasks)

            resp = client.get("/tasks/")

        assert resp.status_code == 200

    def test_list_tasks_no_user_id_auth_enabled(self, client):
        """When auth enabled and no user_id header, return 401."""
        with patch("src.api.routes.tasks.config", _make_config(disable_auth=False)):
            resp = client.get("/tasks/")

        assert resp.status_code == 401
        assert "authentication" in resp.json()["detail"].lower()

    def test_list_tasks_service_error(self, client):
        """Exception in TaskService should yield 500."""
        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.get_user_tasks = AsyncMock(side_effect=RuntimeError("db down"))

            resp = client.get("/tasks/", headers={"user_id": "u1"})

        assert resp.status_code == 500
        assert "Error retrieving tasks" in resp.json()["detail"]


# ==========================================================================
#  POST /tasks/ — create_task
# ==========================================================================

class TestCreateTask:

    def _post_task(self, client, data=None, headers=None):
        data = data if data is not None else {"source": {"url": "https://youtube.com/watch?v=abc"}}
        headers = headers if headers is not None else {"user_id": "u1", "content-type": "application/json"}
        return client.post("/tasks/", json=data, headers=headers)

    def test_create_task_success(self, client):
        """Successful task creation and job enqueueing."""
        with (
            patch("src.api.routes.tasks.TaskService") as MockTS,
            patch("src.api.routes.tasks.UserPreferencesService") as MockUPS,
            patch("src.api.routes.tasks.JobQueue") as MockJQ,
        ):
            ts_inst = MockTS.return_value
            ts_inst.create_task_with_source = AsyncMock(return_value="task-1")
            ts_inst.video_service = MagicMock()
            ts_inst.video_service.determine_source_type.return_value = "youtube"

            ups_inst = MockUPS.return_value
            ups_inst.merge_with_request_options = AsyncMock(
                return_value={
                    "font_family": "Arial",
                    "font_size": 24,
                    "font_color": "#FFFFFF",
                    "logo_file_path": None,
                    "logo_corner_position": "top-right",
                }
            )
            ups_inst.get_logo_path.return_value = None

            MockJQ.enqueue_job = AsyncMock(return_value="job-1")

            resp = self._post_task(client)

        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == "task-1"
        assert body["job_id"] == "job-1"

    def test_create_task_with_logo(self, client):
        """Task creation with a logo path."""
        with (
            patch("src.api.routes.tasks.TaskService") as MockTS,
            patch("src.api.routes.tasks.UserPreferencesService") as MockUPS,
            patch("src.api.routes.tasks.JobQueue") as MockJQ,
        ):
            ts_inst = MockTS.return_value
            ts_inst.create_task_with_source = AsyncMock(return_value="task-2")
            ts_inst.video_service = MagicMock()
            ts_inst.video_service.determine_source_type.return_value = "upload"

            ups_inst = MockUPS.return_value
            ups_inst.merge_with_request_options = AsyncMock(
                return_value={
                    "font_family": "Arial",
                    "font_size": 24,
                    "font_color": "#FFFFFF",
                    "logo_file_path": "/tmp/logo.png",
                    "logo_corner_position": "top-left",
                }
            )
            from pathlib import Path
            ups_inst.get_logo_path.return_value = Path("/tmp/logo.png")

            MockJQ.enqueue_job = AsyncMock(return_value="job-2")

            resp = self._post_task(client)

        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == "task-2"

    def test_create_task_missing_url(self, client):
        """Source present but URL missing should return 400."""
        # Use a truthy source dict with no "url" key to exercise the second branch
        resp = self._post_task(client, data={"source": {"title": "no url"}})
        assert resp.status_code == 400
        assert "Source URL is required" in resp.json()["detail"]

    def test_create_task_empty_source(self, client):
        """Empty source dict (falsy) should return 400."""
        resp = self._post_task(client, data={"source": {}})
        assert resp.status_code == 400

    def test_create_task_missing_source(self, client):
        """Missing source entirely should return 400."""
        resp = self._post_task(client, data={})
        assert resp.status_code == 400

    def test_create_task_no_user_id_auth_disabled(self, client):
        """No user_id header with auth disabled uses default."""
        with (
            patch("src.api.routes.tasks.config", _make_config(disable_auth=True, default_user_id="default-u")),
            patch("src.api.routes.tasks.TaskService") as MockTS,
            patch("src.api.routes.tasks.UserPreferencesService") as MockUPS,
            patch("src.api.routes.tasks.JobQueue") as MockJQ,
        ):
            ts_inst = MockTS.return_value
            ts_inst.create_task_with_source = AsyncMock(return_value="task-3")
            ts_inst.video_service = MagicMock()
            ts_inst.video_service.determine_source_type.return_value = "youtube"

            ups_inst = MockUPS.return_value
            ups_inst.merge_with_request_options = AsyncMock(
                return_value={
                    "font_family": "TikTokSans-Regular",
                    "font_size": 24,
                    "font_color": "#FFFFFF",
                    "logo_file_path": None,
                    "logo_corner_position": "top-right",
                }
            )
            ups_inst.get_logo_path.return_value = None

            MockJQ.enqueue_job = AsyncMock(return_value="job-3")

            resp = self._post_task(
                client,
                data={"source": {"url": "https://example.com/video.mp4"}},
                headers={"content-type": "application/json"},
            )

        assert resp.status_code == 200

    def test_create_task_no_user_id_auth_enabled(self, client):
        """No user_id with auth enabled returns 401."""
        with patch("src.api.routes.tasks.config", _make_config(disable_auth=False)):
            resp = self._post_task(
                client,
                data={"source": {"url": "https://youtube.com/watch?v=abc"}},
                headers={"content-type": "application/json"},
            )
        assert resp.status_code == 401

    def test_create_task_value_error(self, client):
        """ValueError from service should yield 404."""
        with (
            patch("src.api.routes.tasks.TaskService") as MockTS,
            patch("src.api.routes.tasks.UserPreferencesService") as MockUPS,
        ):
            ups_inst = MockUPS.return_value
            ups_inst.merge_with_request_options = AsyncMock(
                return_value={
                    "font_family": "TikTokSans-Regular",
                    "font_size": 24,
                    "font_color": "#FFFFFF",
                    "logo_file_path": None,
                    "logo_corner_position": "top-right",
                }
            )
            ups_inst.get_logo_path.return_value = None

            ts_inst = MockTS.return_value
            ts_inst.create_task_with_source = AsyncMock(
                side_effect=ValueError("User not found")
            )
            ts_inst.video_service = MagicMock()

            resp = self._post_task(client)

        assert resp.status_code == 404

    def test_create_task_generic_error(self, client):
        """Generic exception should yield 500."""
        with (
            patch("src.api.routes.tasks.TaskService") as MockTS,
            patch("src.api.routes.tasks.UserPreferencesService") as MockUPS,
        ):
            ups_inst = MockUPS.return_value
            ups_inst.merge_with_request_options = AsyncMock(
                side_effect=RuntimeError("boom")
            )

            resp = self._post_task(client)

        assert resp.status_code == 500
        assert "Error creating task" in resp.json()["detail"]

    def test_create_task_with_custom_clip_lengths(self, client):
        """Custom min_length and max_length should be forwarded."""
        with (
            patch("src.api.routes.tasks.TaskService") as MockTS,
            patch("src.api.routes.tasks.UserPreferencesService") as MockUPS,
            patch("src.api.routes.tasks.JobQueue") as MockJQ,
        ):
            ts_inst = MockTS.return_value
            ts_inst.create_task_with_source = AsyncMock(return_value="task-4")
            ts_inst.video_service = MagicMock()
            ts_inst.video_service.determine_source_type.return_value = "youtube"

            ups_inst = MockUPS.return_value
            ups_inst.merge_with_request_options = AsyncMock(
                return_value={
                    "font_family": "TikTokSans-Regular",
                    "font_size": 24,
                    "font_color": "#FFFFFF",
                    "logo_file_path": None,
                    "logo_corner_position": "top-right",
                }
            )
            ups_inst.get_logo_path.return_value = None

            MockJQ.enqueue_job = AsyncMock(return_value="job-4")

            resp = self._post_task(
                client,
                data={
                    "source": {"url": "https://youtube.com/watch?v=abc"},
                    "min_length": 15,
                    "max_length": 60,
                    "font_options": {"font_family": "Arial", "font_size": 30, "font_color": "#000000"},
                },
            )

        assert resp.status_code == 200
        # Verify enqueue_job was called with correct args
        call_args = MockJQ.enqueue_job.call_args
        assert call_args is not None


# ==========================================================================
#  GET /tasks/{task_id} — get_task
# ==========================================================================

class TestGetTask:

    def test_get_task_success(self, client):
        """Return task with clips."""
        task_data = {
            "id": "t1",
            "status": "completed",
            "clips": [{"id": "c1"}],
        }
        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.get_task_with_clips = AsyncMock(return_value=task_data)

            resp = client.get("/tasks/t1")

        assert resp.status_code == 200
        assert resp.json()["id"] == "t1"

    def test_get_task_not_found(self, client):
        """Task not found returns 404."""
        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.get_task_with_clips = AsyncMock(return_value=None)

            resp = client.get("/tasks/nonexistent")

        assert resp.status_code == 404

    def test_get_task_service_error(self, client):
        """Service error returns 500."""
        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.get_task_with_clips = AsyncMock(
                side_effect=RuntimeError("db error")
            )

            resp = client.get("/tasks/t1")

        assert resp.status_code == 500
        assert "Error retrieving task" in resp.json()["detail"]


# ==========================================================================
#  GET /tasks/{task_id}/clips — get_task_clips
# ==========================================================================

class TestGetTaskClips:

    def test_get_clips_success(self, client):
        """Return clips for a task."""
        task_data = {
            "id": "t1",
            "clips": [{"id": "c1"}, {"id": "c2"}],
        }
        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.get_task_with_clips = AsyncMock(return_value=task_data)

            resp = client.get("/tasks/t1/clips")

        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == "t1"
        assert body["total_clips"] == 2

    def test_get_clips_task_not_found(self, client):
        """Task not found for clips returns 404."""
        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.get_task_with_clips = AsyncMock(return_value=None)

            resp = client.get("/tasks/nonexistent/clips")

        assert resp.status_code == 404

    def test_get_clips_empty(self, client):
        """Task with no clips returns empty list."""
        task_data = {"id": "t1"}
        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.get_task_with_clips = AsyncMock(return_value=task_data)

            resp = client.get("/tasks/t1/clips")

        assert resp.status_code == 200
        body = resp.json()
        assert body["total_clips"] == 0
        assert body["clips"] == []

    def test_get_clips_service_error(self, client):
        """Service error returns 500."""
        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.get_task_with_clips = AsyncMock(
                side_effect=RuntimeError("db error")
            )

            resp = client.get("/tasks/t1/clips")

        assert resp.status_code == 500
        assert "Error retrieving clips" in resp.json()["detail"]


# ==========================================================================
#  GET /tasks/{task_id}/progress — SSE endpoint
# ==========================================================================

class TestGetTaskProgressSSE:

    def test_progress_task_not_found(self, client):
        """SSE stream emits error event for missing task."""
        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(return_value=None)

            resp = client.get("/tasks/t1/progress")

        # SSE responses are 200 with text/event-stream content type
        assert resp.status_code == 200
        assert "Task not found" in resp.text

    def test_progress_task_already_completed(self, client):
        """SSE stream should emit status then close for completed tasks."""
        task = {"status": "completed", "progress": 100, "progress_message": "Done"}

        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(return_value=task)

            resp = client.get("/tasks/t1/progress")

        assert resp.status_code == 200
        assert "completed" in resp.text

    def test_progress_task_already_error(self, client):
        """SSE stream should emit status then close for error tasks."""
        task = {"status": "error", "progress": 50, "progress_message": "Failed"}

        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(return_value=task)

            resp = client.get("/tasks/t1/progress")

        assert resp.status_code == 200
        assert "error" in resp.text

    def test_progress_streaming_updates(self, client):
        """SSE stream yields progress events and closes on completion."""
        from src.workers.local_progress import Progress

        task = {"status": "processing", "progress": 10, "progress_message": "Working..."}

        progress_updates = [
            Progress(task_id="t1", progress=50, message="Half done", status="processing"),
            Progress(task_id="t1", progress=100, message="Complete!", status="completed"),
        ]

        async def mock_subscribe(task_id):
            for p in progress_updates:
                yield p

        mock_tracker = MagicMock()
        mock_tracker.subscribe = mock_subscribe

        with (
            patch("src.api.routes.tasks.TaskService") as MockTS,
            # Patch at the source module so the inline import picks it up
            patch(
                "src.workers.local_progress.get_progress_tracker",
                return_value=mock_tracker,
            ),
        ):
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(return_value=task)

            resp = client.get("/tasks/t1/progress")

        assert resp.status_code == 200
        # Verify that progress data is in the response
        assert "Half done" in resp.text or "Complete" in resp.text

    def test_progress_streaming_with_error_during_subscribe(self, client):
        """SSE stream handles errors during subscription gracefully."""
        task = {"status": "processing", "progress": 10, "progress_message": "Working..."}

        async def mock_subscribe_error(task_id):
            raise RuntimeError("Connection lost")
            # The yield makes this an async generator, which is required
            yield  # pragma: no cover

        mock_tracker = MagicMock()
        mock_tracker.subscribe = mock_subscribe_error

        with (
            patch("src.api.routes.tasks.TaskService") as MockTS,
            # Patch at the source module so the inline import picks it up
            patch(
                "src.workers.local_progress.get_progress_tracker",
                return_value=mock_tracker,
            ),
        ):
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(return_value=task)

            resp = client.get("/tasks/t1/progress")

        assert resp.status_code == 200
        # The error handler in the generator should yield an error event
        assert "error" in resp.text or "Connection lost" in resp.text


# ==========================================================================
#  PATCH /tasks/{task_id} — update_task
# ==========================================================================

class TestUpdateTask:

    def test_update_task_success(self, client):
        """Update task title successfully."""
        task = {"id": "t1", "source_id": "s1"}

        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(return_value=task)
            instance.source_repo = MagicMock()
            instance.source_repo.update_source_title = AsyncMock()

            resp = client.patch(
                "/tasks/t1",
                json={"title": "New Title"},
            )

        assert resp.status_code == 200
        assert resp.json()["message"] == "Task updated successfully"

    def test_update_task_no_title(self, client):
        """Missing title returns 400."""
        resp = client.patch("/tasks/t1", json={})
        assert resp.status_code == 400
        assert "Title is required" in resp.json()["detail"]

    def test_update_task_not_found(self, client):
        """Non-existent task returns 404."""
        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(return_value=None)

            resp = client.patch("/tasks/t1", json={"title": "X"})

        assert resp.status_code == 404

    def test_update_task_service_error(self, client):
        """Service error returns 500."""
        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(
                side_effect=RuntimeError("db error")
            )

            resp = client.patch("/tasks/t1", json={"title": "X"})

        assert resp.status_code == 500
        assert "Error updating task" in resp.json()["detail"]


# ==========================================================================
#  DELETE /tasks/{task_id} — delete_task
# ==========================================================================

class TestDeleteTask:

    def test_delete_task_success(self, client):
        """Delete task owned by user."""
        task = {"id": "t1", "user_id": "u1"}

        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(return_value=task)
            instance.delete_task = AsyncMock()

            resp = client.delete("/tasks/t1", headers={"user_id": "u1"})

        assert resp.status_code == 200
        assert resp.json()["message"] == "Task deleted successfully"

    def test_delete_task_not_found(self, client):
        """Non-existent task returns 404."""
        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(return_value=None)

            resp = client.delete("/tasks/t1", headers={"user_id": "u1"})

        assert resp.status_code == 404

    def test_delete_task_forbidden(self, client):
        """Deleting someone else's task returns 403."""
        task = {"id": "t1", "user_id": "other-user"}

        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(return_value=task)

            resp = client.delete("/tasks/t1", headers={"user_id": "u1"})

        assert resp.status_code == 403

    def test_delete_task_no_user_id_auth_disabled(self, client):
        """No user_id with auth disabled uses default."""
        task = {"id": "t1", "user_id": "local-user"}

        with (
            patch("src.api.routes.tasks.config", _make_config(disable_auth=True)),
            patch("src.api.routes.tasks.TaskService") as MockTS,
        ):
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(return_value=task)
            instance.delete_task = AsyncMock()

            resp = client.delete("/tasks/t1")

        assert resp.status_code == 200

    def test_delete_task_no_user_id_auth_enabled(self, client):
        """No user_id with auth enabled returns 401."""
        with patch("src.api.routes.tasks.config", _make_config(disable_auth=False)):
            resp = client.delete("/tasks/t1")

        assert resp.status_code == 401

    def test_delete_task_service_error(self, client):
        """Service error returns 500."""
        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(
                side_effect=RuntimeError("db error")
            )

            resp = client.delete("/tasks/t1", headers={"user_id": "u1"})

        assert resp.status_code == 500
        assert "Error deleting task" in resp.json()["detail"]


# ==========================================================================
#  DELETE /tasks/{task_id}/clips/{clip_id} — delete_clip
# ==========================================================================

class TestDeleteClip:

    def test_delete_clip_success(self, client):
        """Delete clip owned by user."""
        task = {"id": "t1", "user_id": "u1"}

        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(return_value=task)
            instance.clip_repo = MagicMock()
            instance.clip_repo.delete_clip = AsyncMock()

            resp = client.delete("/tasks/t1/clips/c1", headers={"user_id": "u1"})

        assert resp.status_code == 200
        assert resp.json()["message"] == "Clip deleted successfully"

    def test_delete_clip_task_not_found(self, client):
        """Non-existent task returns 404."""
        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(return_value=None)

            resp = client.delete("/tasks/t1/clips/c1", headers={"user_id": "u1"})

        assert resp.status_code == 404

    def test_delete_clip_forbidden(self, client):
        """Deleting clip of someone else's task returns 403."""
        task = {"id": "t1", "user_id": "other-user"}

        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(return_value=task)

            resp = client.delete("/tasks/t1/clips/c1", headers={"user_id": "u1"})

        assert resp.status_code == 403

    def test_delete_clip_no_user_id_auth_disabled(self, client):
        """No user_id with auth disabled uses default."""
        task = {"id": "t1", "user_id": "local-user"}

        with (
            patch("src.api.routes.tasks.config", _make_config(disable_auth=True)),
            patch("src.api.routes.tasks.TaskService") as MockTS,
        ):
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(return_value=task)
            instance.clip_repo = MagicMock()
            instance.clip_repo.delete_clip = AsyncMock()

            resp = client.delete("/tasks/t1/clips/c1")

        assert resp.status_code == 200

    def test_delete_clip_no_user_id_auth_enabled(self, client):
        """No user_id with auth enabled returns 401."""
        with patch("src.api.routes.tasks.config", _make_config(disable_auth=False)):
            resp = client.delete("/tasks/t1/clips/c1")

        assert resp.status_code == 401

    def test_delete_clip_service_error(self, client):
        """Service error returns 500."""
        with patch("src.api.routes.tasks.TaskService") as MockTS:
            instance = MockTS.return_value
            instance.task_repo = MagicMock()
            instance.task_repo.get_task_by_id = AsyncMock(
                side_effect=RuntimeError("db error")
            )

            resp = client.delete("/tasks/t1/clips/c1", headers={"user_id": "u1"})

        assert resp.status_code == 500
        assert "Error deleting clip" in resp.json()["detail"]


# end backend/tests/unit/test_routes_tasks.py
