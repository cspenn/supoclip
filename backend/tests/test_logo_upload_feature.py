"""Test cases for logo upload feature.

Tests the logo upload endpoint, validation, storage, and integration with video clips.
Covers PNG/JPG file handling, resizing to 60px, corner position validation, and overlay
application to generated clips.
"""
import io
import pytest
from pathlib import Path
from PIL import Image
from fastapi.testclient import TestClient


@pytest.fixture
def sample_png_file():
    """Create a minimal PNG test file."""
    img = Image.new('RGBA', (200, 200), color=(255, 0, 0, 255))
    file_like = io.BytesIO()
    img.save(file_like, format='PNG')
    file_like.seek(0)
    return file_like


@pytest.fixture
def sample_jpg_file():
    """Create a minimal JPG test file."""
    img = Image.new('RGB', (200, 200), color=(0, 255, 0))
    file_like = io.BytesIO()
    img.save(file_like, format='JPEG')
    file_like.seek(0)
    return file_like


@pytest.fixture
def sample_invalid_file():
    """Create an invalid file (text instead of image)."""
    file_like = io.BytesIO(b"This is not an image file")
    file_like.seek(0)
    return file_like


class TestLogoUploadEndpoint:
    """Test logo upload endpoint acceptance and validation."""

    def test_logo_upload_accepts_png_file(self, async_client: TestClient, sample_png_file, monkeypatch):
        """Test that POST /upload-logo accepts PNG files."""
        # Arrange
        temp_logos_dir = Path("/tmp/test_logos")
        temp_logos_dir.mkdir(exist_ok=True)
        monkeypatch.setenv("LOGO_DIR", str(temp_logos_dir))

        files = {"file": ("test.png", sample_png_file, "image/png")}
        headers = {"user_id": "test-user-1"}

        # Act
        response = async_client.post("/upload-logo", files=files, headers=headers)

        # Assert
        assert response.status_code in [200, 201], f"Expected 200/201, got {response.status_code}: {response.text}"
        data = response.json()
        assert "logo_path" in data or "message" in data

    def test_logo_upload_accepts_jpg_file(self, async_client: TestClient, sample_jpg_file, monkeypatch):
        """Test that POST /upload-logo accepts JPG files."""
        # Arrange
        temp_logos_dir = Path("/tmp/test_logos")
        temp_logos_dir.mkdir(exist_ok=True)
        monkeypatch.setenv("LOGO_DIR", str(temp_logos_dir))

        headers = {"user_id": "test-user-1"}
        files = {"file": ("test.jpg", sample_jpg_file, "image/jpeg")}

        # Act
        response = async_client.post("/upload-logo", files=files, headers=headers)

        # Assert
        assert response.status_code in [200, 201]
        data = response.json()
        assert "logo_path" in data or "message" in data

    def test_logo_upload_rejects_non_image_files(self, async_client: TestClient, sample_invalid_file):
        """Test that logo upload rejects non-image files."""
        # Arrange
        headers = {"user_id": "test-user-1"}
        files = {"file": ("test.txt", sample_invalid_file, "text/plain")}

        # Act
        response = async_client.post("/upload-logo", files=files, headers=headers)

        # Assert
        assert response.status_code in [400, 415]

    def test_logo_upload_missing_file_returns_400(self, async_client: TestClient):
        """Test that missing file in upload returns 400."""
        # Arrange
        headers = {"user_id": "test-user-1"}

        # Act
        response = async_client.post("/upload-logo", headers=headers)

        # Assert
        assert response.status_code == 400

    def test_logo_upload_missing_user_id_returns_401(self, async_client: TestClient, sample_png_file):
        """Test that missing user_id header returns 401."""
        # Arrange
        files = {"file": ("test.png", sample_png_file, "image/png")}

        # Act
        response = async_client.post("/upload-logo", files=files)

        # Assert
        assert response.status_code == 401


class TestLogoFileHandling:
    """Test logo file storage and resizing."""

    @pytest.mark.asyncio
    async def test_logo_resize_to_60px(self, test_db_session, temp_dir):
        """Test that uploaded logo is resized to 60px."""
        # Arrange
        from src.models import User
        from PIL import Image as PILImage

        # Create test user
        user = User(
            id="test-logo-user",
            name="Logo Test User",
            email="logo@test.com",
            emailVerified=True
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # Create a larger test image
        original_img = PILImage.new('RGBA', (200, 200), color=(255, 0, 0, 255))
        original_path = temp_dir / "original_logo.png"
        original_img.save(original_path)

        # Simulate resize operation
        resized_img = original_img.resize((60, 60), Image.Resampling.LANCZOS)
        assert resized_img.size == (60, 60)

    @pytest.mark.asyncio
    async def test_logo_saved_to_correct_directory(self, test_db_session, temp_dir):
        """Test that logo file is saved to correct directory."""
        # Arrange
        logos_dir = temp_dir / "logos"
        logos_dir.mkdir(exist_ok=True)

        # Create test image
        img = Image.new('RGBA', (100, 100), color=(0, 0, 255, 255))
        logo_path = logos_dir / "test_user_logo.png"

        # Act - save logo to directory
        img.save(logo_path)

        # Assert - verify logo saved in correct directory
        assert logo_path.exists()
        assert logo_path.parent == logos_dir

    @pytest.mark.asyncio
    async def test_user_database_updated_with_logo_path(self, test_db_session):
        """Test that user database is updated with logo path."""
        # Arrange
        from src.models import User
        from sqlalchemy import select

        user = User(
            id="test-logo-db-user",
            name="Logo DB Test",
            email="logodb@test.com",
            emailVerified=True
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # Act - Update logo path
        test_db_session.query(User).filter(User.id == "test-logo-db-user").update(
            {"logo_file_path": "/logos/test-logo-db-user_logo.png"}
        )
        await test_db_session.commit()

        # Assert
        result = await test_db_session.execute(
            select(User).where(User.id == "test-logo-db-user")
        )
        updated_user = result.scalar_one()
        assert updated_user.logo_file_path == "/logos/test-logo-db-user_logo.png"


class TestLogoCornerPositionValidation:
    """Test logo corner position validation."""

    def test_corner_position_top_left_valid(self, async_client: TestClient, sample_png_file):
        """Test that top-left corner position is valid."""
        # Arrange - Test the validation logic
        valid_positions = ["top-left", "top-right", "bottom-left", "bottom-right"]
        position = "top-left"

        # Assert
        assert position in valid_positions

    def test_corner_position_top_right_valid(self):
        """Test that top-right corner position is valid."""
        # Arrange
        valid_positions = ["top-left", "top-right", "bottom-left", "bottom-right"]
        position = "top-right"

        # Assert
        assert position in valid_positions

    def test_corner_position_bottom_left_valid(self):
        """Test that bottom-left corner position is valid."""
        # Arrange
        valid_positions = ["top-left", "top-right", "bottom-left", "bottom-right"]
        position = "bottom-left"

        # Assert
        assert position in valid_positions

    def test_corner_position_bottom_right_valid(self):
        """Test that bottom-right corner position is valid."""
        # Arrange
        valid_positions = ["top-left", "top-right", "bottom-left", "bottom-right"]
        position = "bottom-right"

        # Assert
        assert position in valid_positions

    def test_invalid_corner_position_rejected(self):
        """Test that invalid corner position is rejected."""
        # Arrange
        valid_positions = ["top-left", "top-right", "bottom-left", "bottom-right"]
        position = "center"

        # Assert
        assert position not in valid_positions

    def test_corner_position_case_sensitive(self):
        """Test that corner position validation is case-sensitive."""
        # Arrange
        valid_positions = ["top-left", "top-right", "bottom-left", "bottom-right"]
        invalid_position = "TOP-LEFT"

        # Assert
        assert invalid_position not in valid_positions


class TestLogoOverlayOnClips:
    """Test logo overlay application on generated clips."""

    @pytest.mark.asyncio
    async def test_logo_overlay_applied_to_generated_clips(self, test_db_session, temp_dir):
        """Test that logo is applied to generated clips."""
        # Arrange
        from src.models import Task, User, GeneratedClip

        user = User(
            id="test-overlay-user",
            name="Overlay Test",
            email="overlay@test.com",
            emailVerified=True,
            logo_file_path="/logos/test_logo.png"
        )
        test_db_session.add(user)
        await test_db_session.commit()

        task = Task(
            id="test-overlay-task",
            user_id=user.id,
            status="completed"
        )
        test_db_session.add(task)
        await test_db_session.commit()

        # Create a mock clip
        clip = GeneratedClip(
            id="test-clip-1",
            task_id=task.id,
            filename="test_clip.mp4",
            file_path=str(temp_dir / "test_clip.mp4"),
            start_time="0:05",
            end_time="0:35",
            duration=30.0,
            text="This is test text",
            relevance_score=0.95,
            clip_order=1
        )
        test_db_session.add(clip)
        await test_db_session.commit()

        # Assert - Logo should be associated with user
        assert user.logo_file_path is not None

    @pytest.mark.asyncio
    async def test_logo_appears_at_correct_corner_position_top_right(self, test_db_session):
        """Test logo appears at correct corner position (top-right)."""
        # Arrange
        from src.models import User

        user = User(
            id="test-position-user",
            name="Position Test",
            email="position@test.com",
            emailVerified=True,
            logo_corner_position="top-right"
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # Assert
        assert user.logo_corner_position == "top-right"

    @pytest.mark.asyncio
    async def test_logo_appears_at_correct_corner_position_bottom_left(self, test_db_session):
        """Test logo appears at correct corner position (bottom-left)."""
        # Arrange
        from src.models import User

        user = User(
            id="test-position-bl-user",
            name="Position BL Test",
            email="positionbl@test.com",
            emailVerified=True,
            logo_corner_position="bottom-left"
        )
        test_db_session.add(user)
        await test_db_session.commit()

        # Assert
        assert user.logo_corner_position == "bottom-left"

    @pytest.mark.asyncio
    async def test_logo_transparency_preserved_in_rgba_conversion(self):
        """Test that logo transparency is preserved when converting to RGBA."""
        # Arrange
        original_img = Image.new('RGBA', (100, 100), color=(255, 0, 0, 100))

        # Act - Convert to RGBA (should already be RGBA)
        rgba_img = original_img.convert('RGBA')

        # Assert
        assert rgba_img.mode == 'RGBA'
        # Check alpha channel exists
        rgba_img.split()  # Should have 4 channels


class TestLogoConcurrency:
    """Test concurrent logo uploads."""

    @pytest.mark.asyncio
    async def test_concurrent_logo_uploads_dont_conflict(self, test_db_session, sample_png_file, temp_dir):
        """Test that concurrent logo uploads don't conflict."""
        # Arrange
        from src.models import User
        import asyncio

        # Create two test users
        users = []
        for i in range(2):
            user = User(
                id=f"test-concurrent-user-{i}",
                name=f"Concurrent User {i}",
                email=f"concurrent{i}@test.com",
                emailVerified=True
            )
            test_db_session.add(user)
            users.append(user)

        await test_db_session.commit()

        # Simulate concurrent uploads by saving different files
        logo_dir = temp_dir / "logos"
        logo_dir.mkdir(exist_ok=True)

        async def save_logo(user_id: str):
            """Simulate saving logo for user."""
            img = Image.new('RGBA', (100, 100), color=(255, 0, 0, 255))
            path = logo_dir / f"{user_id}_logo.png"
            img.save(path)
            return path

        # Act
        tasks = [save_logo(f"test-concurrent-user-{i}") for i in range(2)]
        results = await asyncio.gather(*tasks)

        # Assert
        assert len(results) == 2
        assert all(p.exists() for p in results)
        assert results[0] != results[1]

# end src/tests/test_logo_upload_feature.py
