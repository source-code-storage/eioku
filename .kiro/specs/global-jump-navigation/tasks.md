# Implementation Plan: Global Jump Navigation

## Overview

This implementation plan breaks down the Global Jump Navigation feature into discrete, incremental tasks. The feature enables cross-video artifact search and navigation using a unified API endpoint. Tasks are organized to build functionality piece by piece, with testing integrated at each step.

The implementation follows a bottom-up approach: start with data models and service logic, then expose through API endpoints, then optimize with database indexes.

## Tasks

- [x] 1. Set up project structure and core data models
  - Create `backend/src/global_jump/` module directory
  - Create `backend/src/global_jump/__init__.py`
  - Create `backend/src/global_jump/models.py` with GlobalJumpResult and JumpTo dataclasses
  - Create `backend/src/global_jump/exceptions.py` with GlobalJumpException, VideoNotFoundError, InvalidParameterError
  - _Requirements: 5.1, 8.1, 8.2, 8.3, 8.4_

- [x] 2. Create Pydantic response schemas
  - Create `backend/src/global_jump/schemas.py`
  - Implement JumpToSchema with start_ms and end_ms fields
  - Implement GlobalJumpResultSchema with all required fields (video_id, video_filename, file_created_at, jump_to, artifact_id, preview)
  - Implement GlobalJumpResponseSchema with results array and has_more boolean
  - Add comprehensive docstrings and field descriptions
  - _Requirements: 5.3, 7.1, 7.2, 7.3, 7.4, 7.5, 13.1_

- [ ]* 2.1 Write unit tests for response schemas
  - **Property 12: Response Schema Completeness**
  - **Validates: Requirements 5.3, 7.1, 7.2, 7.3, 7.4, 7.5, 13.1**

- [x] 3. Implement GlobalJumpService - core infrastructure
  - Create `backend/src/global_jump/service.py`
  - Implement GlobalJumpService class with __init__ method accepting session and artifact_repo
  - Implement _get_video() helper method to fetch video by ID and raise VideoNotFoundError if not found
  - Implement _to_global_result() helper method to convert database rows to GlobalJumpResult objects
  - Add comprehensive docstrings
  - _Requirements: 1.1, 1.2, 2.1, 3.1, 4.1, 6.1_

- [ ]* 3.1 Write unit tests for service initialization and helpers
  - Test _get_video() with valid and invalid video IDs
  - Test _to_global_result() with various artifact types
  - _Requirements: 8.1_

- [ ] 4. Implement object label search in GlobalJumpService
  - Implement _search_objects_global() method for "next" direction
  - Build query on object_labels projection table joined with videos
  - Apply label filter
  - Apply min_confidence filter
  - Apply direction-specific WHERE clause for "next" (after current position)
  - Order by file_created_at ASC, video_id ASC, start_ms ASC
  - Limit results
  - Return list of GlobalJumpResult objects
  - _Requirements: 1.1, 1.3, 1.4, 1.5, 6.1, 6.2, 6.3, 6.4_

- [ ]* 4.1 Write property test for object search ordering
  - **Property 1: Global Timeline Ordering Consistency**
  - **Validates: Requirements 6.1, 6.2, 6.3, 6.4**

- [ ]* 4.2 Write property test for object confidence filtering
  - **Property 3: Filter Consistency for Confidence**
  - **Validates: Requirements 1.3, 2.2**

- [ ]* 4.3 Write property test for object label filtering
  - **Property 4: Filter Consistency for Labels**
  - **Validates: Requirements 1.1, 1.2**

- [ ] 5. Implement object label search - "prev" direction
  - Implement _search_objects_global() method for "prev" direction
  - Apply direction-specific WHERE clause for "prev" (before current position)
  - Order by file_created_at DESC, video_id DESC, start_ms DESC
  - Return list of GlobalJumpResult objects
  - _Requirements: 1.2, 6.5_

- [ ]* 5.1 Write property test for reverse direction ordering
  - **Property 2: Reverse Direction Ordering**
  - **Validates: Requirements 6.5**

- [ ] 6. Implement face cluster search in GlobalJumpService
  - Implement _search_faces_global() method for both "next" and "prev" directions
  - Build query on face_clusters projection table joined with videos
  - Apply face_cluster_id filter
  - Apply min_confidence filter
  - Apply direction-specific WHERE clause
  - Order by global timeline (ascending for next, descending for prev)
  - Return list of GlobalJumpResult objects with face-specific preview data
  - _Requirements: 2.1, 2.2, 2.3, 2.4_

- [ ]* 6.1 Write property test for face cluster search
  - Test both "next" and "prev" directions
  - Verify confidence filtering
  - _Requirements: 2.1, 2.2, 2.4_

- [ ] 7. Implement transcript full-text search in GlobalJumpService
  - Implement _search_transcript_global() method for both "next" and "prev" directions
  - Build query on transcript_fts projection table joined with videos
  - Use PostgreSQL plainto_tsquery for text normalization
  - Apply FTS filter using @@ operator on text_tsv column
  - Apply direction-specific WHERE clause
  - Order by global timeline
  - Return list of GlobalJumpResult objects with text snippet in preview
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ]* 7.1 Write property test for transcript FTS search
  - **Property 5: Filter Consistency for Text Search**
  - **Validates: Requirements 3.1, 3.2, 4.1, 4.2**

- [ ] 8. Implement OCR full-text search in GlobalJumpService
  - Implement _search_ocr_global() method for both "next" and "prev" directions
  - Build query on ocr_fts projection table joined with videos
  - Use PostgreSQL plainto_tsquery for text normalization
  - Apply FTS filter using @@ operator on text_tsv column
  - Apply direction-specific WHERE clause
  - Order by global timeline
  - Return list of GlobalJumpResult objects with text snippet in preview
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [ ]* 8.1 Write property test for OCR FTS search
  - Test both "next" and "prev" directions
  - Verify text matching
  - _Requirements: 4.1, 4.2, 4.3_

- [ ] 9. Implement public jump_next() method in GlobalJumpService
  - Implement async jump_next() method that routes to appropriate search method based on kind
  - Handle kind="object" → _search_objects_global(direction="next")
  - Handle kind="face" → _search_faces_global(direction="next")
  - Handle kind="transcript" → _search_transcript_global(direction="next")
  - Handle kind="ocr" → _search_ocr_global(direction="next")
  - Handle kind="scene" → _search_scenes_global(direction="next")
  - Handle kind="place" → _search_places_global(direction="next")
  - Handle kind="location" → _search_locations_global(direction="next")
  - Raise InvalidParameterError for unknown kind
  - _Requirements: 1.1, 2.1, 3.1, 4.1, 5.1, 6.1, 12.3_

- [ ]* 9.1 Write unit tests for jump_next() routing
  - Test each kind parameter routes to correct search method
  - Test invalid kind raises InvalidParameterError
  - _Requirements: 8.2_

- [ ] 10. Implement public jump_prev() method in GlobalJumpService
  - Implement async jump_prev() method that routes to appropriate search method based on kind
  - Handle all kind values with direction="prev"
  - Raise InvalidParameterError for unknown kind
  - _Requirements: 1.2, 2.1, 3.3, 4.2, 5.1, 6.5, 12.3_

- [ ]* 10.1 Write unit tests for jump_prev() routing
  - Test each kind parameter routes to correct search method
  - Test invalid kind raises InvalidParameterError
  - _Requirements: 8.2_

- [ ] 11. Implement scene and place search methods
  - Implement _search_scenes_global() method for both directions
  - Implement _search_places_global() method for both directions (using object_labels with place-specific labels)
  - Apply appropriate filters and ordering
  - Return GlobalJumpResult objects with scene/place-specific preview data
  - _Requirements: 5.1, 7.5_

- [ ] 12. Implement location search method
  - Implement _search_locations_global() method for both directions
  - Build query on video_locations projection table
  - Apply optional geo_bounds filtering if provided
  - Order by global timeline
  - Return GlobalJumpResult objects with location preview data
  - _Requirements: 5.1_

- [ ] 13. Create GlobalJumpController with parameter validation
  - Create `backend/src/global_jump/router.py`
  - Implement global_jump() endpoint handler
  - Add parameter validation:
    - kind must be one of: object, face, transcript, ocr, scene, place, location
    - direction must be: next or prev
    - from_video_id must be non-empty string
    - from_ms must be non-negative integer (optional)
    - label and query are mutually exclusive
    - min_confidence must be between 0 and 1 (optional)
    - limit must be between 1 and 50
  - Raise 400 errors with descriptive messages for validation failures
  - _Requirements: 5.1, 5.2, 8.2, 8.3, 8.4_

- [ ]* 13.1 Write unit tests for parameter validation
  - **Property 9: Parameter Validation - Invalid Kind**
  - **Property 10: Parameter Validation - Invalid Direction**
  - **Property 11: Parameter Validation - Conflicting Filters**
  - **Validates: Requirements 8.2, 8.3, 8.4**

- [ ] 14. Implement GET /jump/global endpoint
  - Create APIRouter with prefix="/jump" and tags=["global-navigation"]
  - Implement @router.get("/global", response_model=GlobalJumpResponseSchema)
  - Call GlobalJumpService.jump_next() or jump_prev() based on direction parameter
  - Handle VideoNotFoundError and return 404 response
  - Handle InvalidParameterError and return 400 response
  - Return GlobalJumpResponseSchema with results and has_more
  - Add comprehensive OpenAPI documentation
  - _Requirements: 5.1, 5.3, 5.4, 5.5_

- [ ]* 14.1 Write integration tests for /jump/global endpoint
  - Test successful object search across multiple videos
  - Test successful face cluster search
  - Test successful transcript search
  - Test successful OCR search
  - Test 404 for non-existent video
  - Test 400 for invalid parameters
  - _Requirements: 5.1, 5.2, 5.3, 8.1, 8.2, 8.3, 8.4_

- [ ] 15. Implement error handling and response formatting
  - Ensure all error responses include detail, error_code, and timestamp
  - Implement proper HTTP status codes (200, 400, 404, 500)
  - Add error logging for debugging
  - Test error scenarios
  - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ]* 15.1 Write property test for empty result handling
  - **Property 6: Empty Result Handling**
  - **Validates: Requirements 8.5, 12.5, 14.4**

- [ ]* 15.2 Write property test for limit enforcement
  - **Property 7: Limit Enforcement**
  - **Validates: Requirements 5.4, 5.5**

- [ ] 16. Implement optional from_ms parameter handling
  - Update GlobalJumpService methods to handle from_ms=None
  - For "next" direction: default from_ms to 0 (start of video)
  - For "prev" direction: default from_ms to video duration (end of video)
  - Update endpoint to accept from_ms as optional query parameter
  - _Requirements: 11.5_

- [ ]* 16.1 Write property test for optional from_ms parameter
  - **Property 14: Optional from_ms Parameter**
  - **Validates: Requirements 11.5**

- [ ] 17. Implement boundary condition handling for from_ms
  - Update GlobalJumpService to handle from_ms beyond video duration
  - Treat from_ms > duration as end of video for "next" direction
  - Treat from_ms > duration as end of video for "prev" direction
  - No errors should be raised
  - _Requirements: 11.4_

- [ ]* 17.1 Write property test for boundary conditions
  - **Property 15: Boundary Condition - from_ms Beyond Duration**
  - **Validates: Requirements 11.4**

- [ ] 18. Implement arbitrary position navigation
  - Verify GlobalJumpService correctly handles any from_video_id and from_ms combination
  - Results should be chronologically after (for "next") or before (for "prev") that position
  - Test with various video orderings and timestamps
  - _Requirements: 11.1, 11.2, 11.3_

- [ ]* 18.1 Write property test for arbitrary position navigation
  - **Property 13: Arbitrary Position Navigation**
  - **Validates: Requirements 11.1, 11.2, 11.3**

- [ ] 19. Implement filter change independence
  - Verify that changing filters (label, query, kind) doesn't affect timeline position
  - Each query is independent and doesn't carry state from previous queries
  - Test with multiple consecutive queries with different filters
  - _Requirements: 12.1, 12.2, 12.3, 12.4_

- [ ]* 19.1 Write property test for filter change independence
  - **Property 16: Filter Change Independence**
  - **Validates: Requirements 12.1, 12.2, 12.3, 12.4**

- [ ] 20. Implement result chaining capability
  - Verify that using a result's video_id and end_ms as the next starting point works correctly
  - Results should be chronologically after the previous result
  - Test continuous navigation through multiple results
  - _Requirements: 13.5, 14.2, 14.3_

- [ ]* 20.1 Write property test for result chaining
  - **Property 17: Result Chaining**
  - **Validates: Requirements 13.5, 14.2, 14.3**

- [ ] 21. Implement cross-video navigation correctness
  - Verify that results from different videos are the first matching artifacts in the next/previous video
  - Test with multiple videos in different chronological orders
  - Verify video_id in results matches expected video
  - _Requirements: 14.1, 14.5_

- [ ]* 21.1 Write property test for cross-video navigation
  - **Property 18: Cross-Video Navigation**
  - **Validates: Requirements 14.1, 14.5**

- [ ] 22. Verify backward compatibility with single-video jump
  - Ensure existing GET /videos/{video_id}/jump endpoint still works
  - Verify single-video jump returns results scoped to that video only
  - Verify new global jump doesn't affect single-video jump behavior
  - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [ ]* 22.1 Write integration tests for backward compatibility
  - **Property 19: Backward Compatibility**
  - **Property 20: Global Jump Independence**
  - **Validates: Requirements 10.1, 10.2, 10.3, 10.4**

- [ ] 23. Checkpoint - Ensure all unit and property tests pass
  - Run all unit tests: `cd backend && poetry run pytest tests/global_jump/ -v`
  - Run all property tests: `cd backend && poetry run pytest tests/global_jump/ -v -k property`
  - Verify 100% test pass rate
  - Address any failing tests
  - Ensure all tests complete within reasonable time
  - _Requirements: All_

- [ ] 24. Add composite database indexes for optimization
  - Create migration file: `backend/alembic/versions/xxx_add_global_jump_indexes.py`
  - Add index on object_labels(label, asset_id, start_ms)
  - Add index on face_clusters(cluster_id, asset_id, start_ms)
  - Add index on videos(file_created_at, video_id)
  - Run migration: `cd backend && poetry run alembic upgrade head`
  - Verify indexes are created in database
  - _Requirements: 9.2, 9.3, 9.5_

- [ ]* 24.1 Write performance tests for query execution time
  - Test object search completes within 500ms
  - Test face search completes within 500ms
  - Test transcript search completes within 500ms
  - _Requirements: 9.1_

- [ ] 25. Register GlobalJumpRouter in main application
  - Import GlobalJumpRouter in `backend/src/main.py`
  - Register router with app: `app.include_router(global_jump_router)`
  - Verify endpoint is accessible at GET /jump/global
  - Test endpoint with curl or API client
  - _Requirements: 5.1_

- [ ] 26. Add comprehensive API documentation
  - Add docstrings to all endpoint handlers
  - Add response examples to OpenAPI schema
  - Document all query parameters with descriptions
  - Document all error responses
  - Verify documentation appears in /docs endpoint
  - _Requirements: 5.1, 5.3_

- [ ] 27. Final checkpoint - Run all tests and quality checks
  - Run all tests: `cd backend && poetry run pytest tests/ -v`
  - Run format check: `cd backend && poetry run ruff format --check src tests`
  - Run lint check: `cd backend && poetry run ruff check src tests`
  - Fix any formatting or linting issues
  - Verify all tests pass
  - Ensure code quality gates are met
  - _Requirements: All_

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP, but comprehensive testing is recommended
- Each task references specific requirements for traceability
- Property tests should run minimum 100 iterations each
- All code must follow FastAPI best practices and PEP 8 style guide
- Use async/await for all I/O operations
- Comprehensive error handling with descriptive messages
- All endpoints must have OpenAPI documentation
