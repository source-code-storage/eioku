"""Unit tests for thumbnail serving endpoint.

Tests for the thumbnail controller API that serves WebP thumbnail images.

Requirements:
- 3.1: GET /api/v1/thumbnails/{video_id}/{timestamp_ms} endpoint
- 3.2: Return WebP file with appropriate content type when thumbnail exists
- 3.3: Return 404 when thumbnail does not exist
- 3.4: Set appropriate cache headers for browser caching (1 week)
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.api.thumbnail_controller import CACHE_MAX_AGE
from src.main_api import app


@pytest.fixture
def client():
    """Create test client for the thumbnail endpoint."""
    with TestClient(app) as test_client:
        yield test_client


class TestGetThumbnailSuccess:
    """Tests for successful thumbnail retrieval.

    Validates: Requirements 3.1, 3.2
    """

    def test_get_thumbnail_success(self, client):
        """Test that existing thumbnail returns 200 with WebP content.

        Requirements:
        - 3.1: GET /api/v1/thumbnails/{video_id}/{timestamp_ms} endpoint
        - 3.2: Return WebP file with appropriate content type when thumbnail exists
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            video_id = "test-video-123"
            timestamp_ms = 5000

            # Create thumbnail directory and file
            thumbnail_dir = temp_path / video_id
            thumbnail_dir.mkdir(parents=True, exist_ok=True)
            thumbnail_file = thumbnail_dir / f"{timestamp_ms}.webp"

            # Write a minimal WebP file (RIFF header for WebP)
            # WebP files start with "RIFF" followed by file size and "WEBP"
            webp_content = b"RIFF\x00\x00\x00\x00WEBP"
            thumbnail_file.write_bytes(webp_content)

            # Mock the THUMBNAIL_DIR to use our temp directory
            with patch("src.api.thumbnail_controller.THUMBNAIL_DIR", temp_path):
                response = client.get(f"/v1/thumbnails/{video_id}/{timestamp_ms}")

                assert response.status_code == 200
                assert response.headers["content-type"] == "image/webp"
                assert response.content == webp_content

    def test_get_thumbnail_returns_correct_file_content(self, client):
        """Test that the correct thumbnail file content is returned."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            video_id = "video-abc"
            timestamp_ms = 12345

            # Create thumbnail directory and file
            thumbnail_dir = temp_path / video_id
            thumbnail_dir.mkdir(parents=True, exist_ok=True)
            thumbnail_file = thumbnail_dir / f"{timestamp_ms}.webp"

            # Write specific content to verify correct file is returned
            expected_content = b"RIFF\x10\x00\x00\x00WEBPtest-content"
            thumbnail_file.write_bytes(expected_content)

            with patch("src.api.thumbnail_controller.THUMBNAIL_DIR", temp_path):
                response = client.get(f"/v1/thumbnails/{video_id}/{timestamp_ms}")

                assert response.status_code == 200
                assert response.content == expected_content


class TestGetThumbnailNotFound:
    """Tests for 404 responses when thumbnail doesn't exist.

    Validates: Requirements 3.3
    """

    def test_get_thumbnail_not_found(self, client):
        """Test that missing thumbnail returns 404.

        Requirements:
        - 3.3: Return 404 when thumbnail does not exist
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Mock the THUMBNAIL_DIR to use our empty temp directory
            with patch("src.api.thumbnail_controller.THUMBNAIL_DIR", temp_path):
                response = client.get("/v1/thumbnails/nonexistent-video/1000")

                assert response.status_code == 404
                assert "not found" in response.json()["detail"].lower()

    def test_get_thumbnail_not_found_video_exists_but_timestamp_missing(self, client):
        """Test 404 when video directory exists but timestamp file is missing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            video_id = "existing-video"

            # Create video directory but no thumbnail file
            thumbnail_dir = temp_path / video_id
            thumbnail_dir.mkdir(parents=True, exist_ok=True)

            with patch("src.api.thumbnail_controller.THUMBNAIL_DIR", temp_path):
                response = client.get(f"/v1/thumbnails/{video_id}/9999")

                assert response.status_code == 404
                assert "not found" in response.json()["detail"].lower()


class TestGetThumbnailCacheHeaders:
    """Tests for cache headers on thumbnail responses.

    Validates: Requirements 3.4
    """

    def test_get_thumbnail_cache_headers(self, client):
        """Test that response includes correct Cache-Control header.

        Requirements:
        - 3.4: Set appropriate cache headers for browser caching (1 week)
        """
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            video_id = "cache-test-video"
            timestamp_ms = 3000

            # Create thumbnail directory and file
            thumbnail_dir = temp_path / video_id
            thumbnail_dir.mkdir(parents=True, exist_ok=True)
            thumbnail_file = thumbnail_dir / f"{timestamp_ms}.webp"
            thumbnail_file.write_bytes(b"RIFF\x00\x00\x00\x00WEBP")

            with patch("src.api.thumbnail_controller.THUMBNAIL_DIR", temp_path):
                response = client.get(f"/v1/thumbnails/{video_id}/{timestamp_ms}")

                assert response.status_code == 200
                assert "cache-control" in response.headers
                cache_control = response.headers["cache-control"]
                assert "public" in cache_control
                assert f"max-age={CACHE_MAX_AGE}" in cache_control

    def test_cache_max_age_is_one_week(self):
        """Test that CACHE_MAX_AGE constant is set to 1 week (604800 seconds)."""
        one_week_in_seconds = 7 * 24 * 60 * 60  # 604800
        assert CACHE_MAX_AGE == one_week_in_seconds

    def test_get_thumbnail_cache_header_format(self, client):
        """Test that Cache-Control header has correct format."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            video_id = "format-test"
            timestamp_ms = 0

            # Create thumbnail directory and file
            thumbnail_dir = temp_path / video_id
            thumbnail_dir.mkdir(parents=True, exist_ok=True)
            thumbnail_file = thumbnail_dir / f"{timestamp_ms}.webp"
            thumbnail_file.write_bytes(b"RIFF\x00\x00\x00\x00WEBP")

            with patch("src.api.thumbnail_controller.THUMBNAIL_DIR", temp_path):
                response = client.get(f"/v1/thumbnails/{video_id}/{timestamp_ms}")

                assert response.status_code == 200
                # Verify exact format: "public, max-age=604800"
                expected_cache_control = f"public, max-age={CACHE_MAX_AGE}"
                assert response.headers["cache-control"] == expected_cache_control
