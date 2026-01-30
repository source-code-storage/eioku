"""Tests for Global Jump Router error handling and response formatting.

Tests verify:
- Error responses include detail, error_code, and timestamp (Requirements 8.1-8.5)
- Proper HTTP status codes (200, 400, 404, 500)
- Empty results return 200 with empty array and has_more=false

Note: Integration tests for the /jump/global endpoint require the router to be
registered in main_api.py (Task 25). These tests focus on the error response
formatting functions.
"""

import json
from datetime import datetime

from fastapi import status

from src.api.global_jump_controller import ERROR_CODES, create_error_response


class TestErrorResponseFormat:
    """Tests for error response format with detail, error_code, and timestamp."""

    def test_create_error_response_includes_all_fields(self):
        """Test create_error_response includes detail, error_code, timestamp."""
        response = create_error_response(
            status_code=400,
            detail="Test error message",
            error_code="TEST_ERROR",
        )

        assert response.status_code == 400
        body = json.loads(response.body.decode())
        assert "detail" in body
        assert "error_code" in body
        assert "timestamp" in body
        assert body["detail"] == "Test error message"
        assert body["error_code"] == "TEST_ERROR"

    def test_create_error_response_400_status(self):
        """Test 400 status code for validation errors."""
        response = create_error_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid parameter",
            error_code="INVALID_KIND",
        )
        assert response.status_code == 400

    def test_create_error_response_404_status(self):
        """Test 404 status code for not found errors."""
        response = create_error_response(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Video not found",
            error_code="VIDEO_NOT_FOUND",
        )
        assert response.status_code == 404

    def test_create_error_response_500_status(self):
        """Test 500 status code for internal errors."""
        response = create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
        )
        assert response.status_code == 500

    def test_error_response_timestamp_is_valid_iso_format(self):
        """Test that timestamp is a valid ISO format datetime."""
        response = create_error_response(
            status_code=400,
            detail="Test error",
            error_code="TEST_ERROR",
        )
        body = json.loads(response.body.decode())
        # Should be parseable as datetime
        timestamp = body["timestamp"]
        assert isinstance(timestamp, str)
        # Parse the ISO format timestamp
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


class TestErrorCodes:
    """Tests for error code constants."""

    def test_all_error_codes_defined(self):
        """Test that all expected error codes are defined."""
        expected_codes = [
            "INVALID_VIDEO_ID",
            "INVALID_KIND",
            "INVALID_DIRECTION",
            "CONFLICTING_FILTERS",
            "INVALID_FROM_MS",
            "INVALID_CONFIDENCE",
            "INVALID_LIMIT",
            "VIDEO_NOT_FOUND",
            "INTERNAL_ERROR",
        ]
        for code in expected_codes:
            assert code in ERROR_CODES
            assert ERROR_CODES[code] == code

    def test_error_codes_match_design_document(self):
        """Test that error codes match the design document specification.

        Design document specifies:
        - INVALID_KIND for invalid artifact kind
        - INVALID_DIRECTION for invalid direction
        - CONFLICTING_FILTERS for both label and query specified
        - VIDEO_NOT_FOUND for non-existent video
        - INVALID_CONFIDENCE for confidence out of range
        - INVALID_LIMIT for limit out of range
        """
        assert ERROR_CODES["INVALID_KIND"] == "INVALID_KIND"
        assert ERROR_CODES["INVALID_DIRECTION"] == "INVALID_DIRECTION"
        assert ERROR_CODES["CONFLICTING_FILTERS"] == "CONFLICTING_FILTERS"
        assert ERROR_CODES["VIDEO_NOT_FOUND"] == "VIDEO_NOT_FOUND"
        assert ERROR_CODES["INVALID_CONFIDENCE"] == "INVALID_CONFIDENCE"
        assert ERROR_CODES["INVALID_LIMIT"] == "INVALID_LIMIT"


class TestErrorResponseSchema:
    """Tests for ErrorResponseSchema in api/schemas.py."""

    def test_error_response_schema_has_required_fields(self):
        """Test ErrorResponseSchema has detail, error_code, timestamp fields."""
        from src.api.schemas import ErrorResponseSchema

        # Create an instance to verify fields
        error = ErrorResponseSchema(
            detail="Test error",
            error_code="TEST_CODE",
            timestamp=datetime.now(),
        )
        assert error.detail == "Test error"
        assert error.error_code == "TEST_CODE"
        assert error.timestamp is not None

    def test_error_response_schema_serialization(self):
        """Test that ErrorResponseSchema serializes correctly to JSON."""
        from src.api.schemas import ErrorResponseSchema

        error = ErrorResponseSchema(
            detail="Video not found",
            error_code="VIDEO_NOT_FOUND",
            timestamp=datetime(2025, 5, 19, 2, 22, 21),
        )
        json_data = error.model_dump(mode="json")
        assert json_data["detail"] == "Video not found"
        assert json_data["error_code"] == "VIDEO_NOT_FOUND"
        assert "timestamp" in json_data
