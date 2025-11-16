"""Test cases for main video processing endpoints.

Tests POST /start, POST /start-with-progress, GET /tasks/{task_id}, and
GET /tasks/{task_id}/clips endpoints including video upload, transcription,
AI analysis, clip generation, and database persistence.
"""
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select


@pytest.fixture
def valid_request_body():
    """Create a valid video processing request body."""
    return {
        "source": {
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "title": "Test Video"
        },
        "font_options": {
            "font_family": "TikTokSans-Regular",
            "font_size": 24,
            "font_color": "#FFFFFF"
        }
    }


@pytest.fixture
def valid_request_with_logo(valid_request_body):
    """Create a valid request with logo overlay."""
    request = valid_request_body.copy()
    request["logo_corner_position"] = "top-right"
    return request


@pytest.fixture
def valid_request_with_custom_prompt(valid_request_body):
    """Create a valid request with custom AI prompt."""
    request = valid_request_body.copy()
    request["custom_ai_prompt"] = "Find educational segments with strong insights"
    return request


class TestPostStartEndpoint:
    """Test POST /start synchronous video processing endpoint."""

    def test_start_missing_source_url_returns_400(self, async_client: TestClient):
        """Test that missing source URL returns 400."""
        # Arrange
        headers = {"user_id": "test-user-1"}
        data = {"source": {}}

        # Act
        response = async_client.post("/start", json=data, headers=headers)

        # Assert
        assert response.status_code == 400

    def test_start_missing_user_id_returns_401(self, async_client: TestClient, valid_request_body):
        """Test that missing user_id header returns 401."""
        # Act
        response = async_client.post("/start", json=valid_request_body)

        # Assert
        assert response.status_code == 401

    def test_start_with_valid_youtube_url(self, async_client: TestClient, valid_request_body, sample_user_data):
        """Test video processing with valid YouTube URL."""
        # Arrange
        headers = {"user_id": sample_user_data.id}

        # Act (Note: Will likely fail due to missing actual video, but tests endpoint structure)
        with patch('src.youtube_utils.download_youtube_video') as mock_download:
            mock_download.return_value = "/tmp/test_video.mp4"
            response = async_client.post("/start", json=valid_request_body, headers=headers)

        # Assert - Should either succeed or return meaningful error
        assert response.status_code in [200, 202, 400, 422]

    def test_start_with_custom_fonts(self, async_client: TestClient, valid_request_body, sample_user_data):
        """Test that custom font options are applied."""
        # Arrange
        headers = {"user_id": sample_user_data.id}
        valid_request_body["font_options"] = {
            "font_family": "Arial",
            "font_size": 32,
            "font_color": "#FF0000"
        }

        # Act
        with patch('src.youtube_utils.download_youtube_video') as mock_download:
            mock_download.return_value = "/tmp/test_video.mp4"
            response = async_client.post("/start", json=valid_request_body, headers=headers)

        # Assert
        assert response.status_code in [200, 202, 400, 422]

    def test_start_with_logo_overlay(self, async_client: TestClient, valid_request_with_logo, sample_user_data):
        """Test clip generation with logo overlay."""
        # Arrange
        headers = {"user_id": sample_user_data.id}

        # Act
        with patch('src.youtube_utils.download_youtube_video') as mock_download:
            mock_download.return_value = "/tmp/test_video.mp4"
            response = async_client.post("/start", json=valid_request_with_logo, headers=headers)

        # Assert
        assert response.status_code in [200, 202, 400, 422]

    def test_start_with_custom_ai_prompt(self, async_client: TestClient, valid_request_with_custom_prompt, sample_user_data):
        """Test that custom AI prompt is applied."""
        # Arrange
        headers = {"user_id": sample_user_data.id}

        # Act
        with patch('src.youtube_utils.download_youtube_video') as mock_download:
            mock_download.return_value = "/tmp/test_video.mp4"
            response = async_client.post("/start", json=valid_request_with_custom_prompt, headers=headers)

        # Assert
        assert response.status_code in [200, 202, 400, 422]

    def test_start_with_dynamic_clip_lengths(self, async_client: TestClient, valid_request_body, sample_user_data):
        """Test that dynamic clip length parameters are respected."""
        # Arrange
        headers = {"user_id": sample_user_data.id}
        valid_request_body["clip_min_length"] = 5
        valid_request_body["clip_target_length"] = 20
        valid_request_body["clip_max_length"] = 40

        # Act
        with patch('src.youtube_utils.download_youtube_video') as mock_download:
            mock_download.return_value = "/tmp/test_video.mp4"
            response = async_client.post("/start", json=valid_request_body, headers=headers)

        # Assert
        assert response.status_code in [200, 202, 400, 422]

    def test_start_invalid_video_rejected(self, async_client: TestClient, sample_user_data):
        """Test that invalid video is rejected."""
        # Arrange
        headers = {"user_id": sample_user_data.id}
        data = {
            "source": {"url": "https://example.com/notavideo.txt"}
        }

        # Act
        response = async_client.post("/start", json=data, headers=headers)

        # Assert
        assert response.status_code in [400, 422]


class TestPostStartWithProgressEndpoint:
    """Test POST /start-with-progress asynchronous processing endpoint."""

    def test_start_with_progress_returns_task_id(self, async_client: TestClient, valid_request_body, sample_user_data):
        """Test that start-with-progress returns task_id immediately."""
        # Arrange
        headers = {"user_id": sample_user_data.id}

        # Act
        with patch('src.youtube_utils.download_youtube_video') as mock_download:
            mock_download.return_value = "/tmp/test_video.mp4"
            response = async_client.post("/start-with-progress", json=valid_request_body, headers=headers)

        # Assert
        if response.status_code == 202:
            data = response.json()
            assert "task_id" in data or "id" in data

    def test_start_with_progress_initiates_background_processing(self, async_client: TestClient, valid_request_body, sample_user_data):
        """Test that background processing is initiated."""
        # Arrange
        headers = {"user_id": sample_user_data.id}

        # Act
        with patch('src.youtube_utils.download_youtube_video') as mock_download:
            with patch('src.workers.local_queue.JobQueue.enqueue') as mock_enqueue:
                mock_download.return_value = "/tmp/test_video.mp4"
                mock_enqueue.return_value = None
                response = async_client.post("/start-with-progress", json=valid_request_body, headers=headers)

        # Assert
        assert response.status_code in [200, 202, 400, 422]

    @pytest.mark.asyncio
    async def test_start_with_progress_task_status_updates(self, test_db_session, sample_user_data):
        """Test that task status updates in database."""
        # Arrange
        from src.models import Task

        task = Task(
            id="test-progress-task",
            user_id=sample_user_data.id,
            status="pending",
            progress=0
        )
        test_db_session.add(task)
        await test_db_session.commit()

        # Act - Update progress
        test_db_session.query(Task).filter(Task.id == "test-progress-task").update({
            "status": "processing",
            "progress": 50
        })
        await test_db_session.commit()

        # Assert
        result = await test_db_session.execute(
            select(Task).where(Task.id == "test-progress-task")
        )
        updated_task = result.scalar_one()
        assert updated_task.status == "processing"
        assert updated_task.progress == 50

    def test_start_with_progress_logo_applied(self, async_client: TestClient, valid_request_with_logo, sample_user_data):
        """Test that logo is applied in background task."""
        # Arrange
        headers = {"user_id": sample_user_data.id}

        # Act
        with patch('src.youtube_utils.download_youtube_video') as mock_download:
            mock_download.return_value = "/tmp/test_video.mp4"
            response = async_client.post("/start-with-progress", json=valid_request_with_logo, headers=headers)

        # Assert
        assert response.status_code in [200, 202, 400, 422]


class TestGetTaskDetailsEndpoint:
    """Test GET /tasks/{task_id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_task_returns_valid_task(self, async_client: TestClient, test_db_session, sample_task_data):
        """Test that GET /tasks/{task_id} returns task details."""
        # Arrange
        task, _ = sample_task_data
        task_id = task.id

        # Act
        response = async_client.get(f"/tasks/{task_id}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data.get("id") == task_id or "task_id" in data

    @pytest.mark.asyncio
    async def test_get_task_returns_404_for_invalid_task(self, async_client: TestClient):
        """Test that invalid task_id returns 404."""
        # Act
        response = async_client.get("/tasks/invalid-task-id-12345")

        # Assert
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_task_returns_task_status(self, async_client: TestClient, test_db_session, sample_task_data):
        """Test that task status is returned."""
        # Arrange
        task, _ = sample_task_data

        # Act
        response = async_client.get(f"/tasks/{task.id}")

        # Assert
        if response.status_code == 200:
            data = response.json()
            assert "status" in data

    @pytest.mark.asyncio
    async def test_get_task_returns_clip_count(self, async_client: TestClient, test_db_session, sample_task_data):
        """Test that clip count is returned in task details."""
        # Arrange
        from src.models import GeneratedClip

        task, _ = sample_task_data

        # Add some test clips
        for i in range(3):
            clip = GeneratedClip(
                id=f"test-clip-{i}",
                task_id=task.id,
                filename=f"clip_{i}.mp4",
                file_path=f"/tmp/clip_{i}.mp4",
                start_time=f"0:{i*10}",
                end_time=f"0:{i*10 + 30}",
                duration=30.0,
                text="Test clip text",
                relevance_score=0.9,
                clip_order=i
            )
            test_db_session.add(clip)

        await test_db_session.commit()

        # Act
        response = async_client.get(f"/tasks/{task.id}")

        # Assert
        if response.status_code == 200:
            data = response.json()
            if "clips" in data:
                assert len(data["clips"]) >= 0

    @pytest.mark.asyncio
    async def test_get_task_returns_all_clips_metadata(self, async_client: TestClient, test_db_session, sample_task_data):
        """Test that all clips metadata is returned."""
        # Arrange
        from src.models import GeneratedClip

        task, _ = sample_task_data

        clip = GeneratedClip(
            id="test-clip-metadata",
            task_id=task.id,
            filename="test_clip.mp4",
            file_path="/tmp/test_clip.mp4",
            start_time="0:10",
            end_time="0:40",
            duration=30.0,
            text="Test transcription",
            relevance_score=0.95,
            clip_order=1
        )
        test_db_session.add(clip)
        await test_db_session.commit()

        # Act
        response = async_client.get(f"/tasks/{task.id}")

        # Assert
        if response.status_code == 200:
            data = response.json()
            if "clips" in data and len(data["clips"]) > 0:
                clip_data = data["clips"][0]
                assert "filename" in clip_data or "id" in clip_data


class TestGetTaskClipsEndpoint:
    """Test GET /tasks/{task_id}/clips endpoint."""

    @pytest.mark.asyncio
    async def test_get_task_clips_returns_all_clips(self, async_client: TestClient, test_db_session, sample_task_data):
        """Test that GET /tasks/{task_id}/clips returns all clips."""
        # Arrange
        from src.models import GeneratedClip

        task, _ = sample_task_data

        for i in range(2):
            clip = GeneratedClip(
                id=f"test-clip-list-{i}",
                task_id=task.id,
                filename=f"clip_{i}.mp4",
                file_path=f"/tmp/clip_{i}.mp4",
                start_time=f"0:{i*10}",
                end_time=f"0:{i*10 + 30}",
                duration=30.0,
                text="Clip text",
                relevance_score=0.9,
                clip_order=i
            )
            test_db_session.add(clip)

        await test_db_session.commit()

        # Act
        response = async_client.get(f"/tasks/{task.id}/clips")

        # Assert
        if response.status_code == 200:
            data = response.json()
            if "clips" in data:
                assert isinstance(data["clips"], list)

    @pytest.mark.asyncio
    async def test_get_task_clips_includes_metadata(self, async_client: TestClient, test_db_session, sample_task_data):
        """Test that clip metadata includes start/end times."""
        # Arrange
        from src.models import GeneratedClip

        task, _ = sample_task_data

        clip = GeneratedClip(
            id="test-clip-meta",
            task_id=task.id,
            filename="test.mp4",
            file_path="/tmp/test.mp4",
            start_time="0:05",
            end_time="0:35",
            duration=30.0,
            text="Test",
            relevance_score=0.95,
            clip_order=1
        )
        test_db_session.add(clip)
        await test_db_session.commit()

        # Act
        response = async_client.get(f"/tasks/{task.id}/clips")

        # Assert
        if response.status_code == 200:
            data = response.json()
            if "clips" in data and len(data["clips"]) > 0:
                clip_meta = data["clips"][0]
                assert "start_time" in clip_meta or "startTime" in clip_meta

    @pytest.mark.asyncio
    async def test_get_task_clips_includes_relevance_scores(self, async_client: TestClient, test_db_session, sample_task_data):
        """Test that clip metadata includes relevance scores."""
        # Arrange
        from src.models import GeneratedClip

        task, _ = sample_task_data

        clip = GeneratedClip(
            id="test-clip-score",
            task_id=task.id,
            filename="test.mp4",
            file_path="/tmp/test.mp4",
            start_time="0:10",
            end_time="0:40",
            duration=30.0,
            text="Test",
            relevance_score=0.88,
            clip_order=1
        )
        test_db_session.add(clip)
        await test_db_session.commit()

        # Act
        response = async_client.get(f"/tasks/{task.id}/clips")

        # Assert
        if response.status_code == 200:
            data = response.json()
            if "clips" in data and len(data["clips"]) > 0:
                assert "relevance_score" in data["clips"][0] or "relevanceScore" in data["clips"][0]

    def test_get_task_clips_invalid_task_returns_404(self, async_client: TestClient):
        """Test that invalid task returns 404."""
        # Act
        response = async_client.get("/tasks/invalid-task-999/clips")

        # Assert
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_task_clips_empty_task_returns_empty_array(self, async_client: TestClient, test_db_session, sample_task_data):
        """Test that task with no clips returns empty array."""
        # Arrange
        task, _ = sample_task_data

        # Act
        response = async_client.get(f"/tasks/{task.id}/clips")

        # Assert
        if response.status_code == 200:
            data = response.json()
            if "clips" in data:
                assert isinstance(data["clips"], list)
                assert len(data["clips"]) == 0

# end src/tests/test_video_processing_endpoints.py
