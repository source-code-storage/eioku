# Design Document: Global Jump Navigation

## Overview

The Global Jump Navigation feature enables cross-video artifact search and navigation using a unified API endpoint. Users can search for objects, faces, text, and scenes across their entire video library in chronological order. The design leverages existing projection tables (object_labels, face_clusters, transcript_fts, ocr_fts, scene_ranges, video_locations) to provide fast queries without requiring new data structures.

The architecture follows a service-oriented pattern with clear separation between API layer, business logic, and data access. All queries use a deterministic global timeline based on file_created_at (EXIF/filesystem date) as the primary ordering mechanism.

## Architecture

### High-Level Flow

```
Client Request (GET /jump/global)
    ↓
GlobalJumpController (validates parameters, routes request)
    ↓
GlobalJumpService (orchestrates search logic)
    ↓
Projection Table Queries (object_labels, face_clusters, transcript_fts, ocr_fts, etc.)
    ↓
Video Metadata Join (file_created_at, filename)
    ↓
GlobalJumpResult (formatted response)
    ↓
Client Response (video_id, jump_to, preview)
```

### Service Architecture

```
GlobalJumpService
├── jump_next() - Navigate forward in global timeline
├── jump_prev() - Navigate backward in global timeline
├── _search_objects_global() - Query object_labels projection
├── _search_faces_global() - Query face_clusters projection
├── _search_transcript_global() - Query transcript_fts projection
├── _search_ocr_global() - Query ocr_fts projection
├── _search_scenes_global() - Query scene_ranges projection
├── _search_locations_global() - Query video_locations projection
└── _to_global_result() - Format database results to response schema
```

## Components and Interfaces

### 1. GlobalJumpController

**File:** `backend/src/api/global_jump_controller.py`

**Responsibility:** HTTP request handling, parameter validation, response formatting

**Key Methods:**
- `global_jump(kind, direction, from_video_id, from_ms, label, query, face_cluster_id, min_confidence, limit)` → GlobalJumpResponseSchema

**Validation Rules:**
- `kind` must be one of: object, face, transcript, ocr, scene, place, location
- `direction` must be: next or prev
- `from_video_id` must reference an existing video
- `from_ms` must be non-negative integer (optional)
- `label` and `query` are mutually exclusive
- `min_confidence` must be between 0 and 1 (optional)
- `limit` must be between 1 and 50

**Error Responses:**
- 400: Invalid parameters
- 404: Video not found
- 500: Database or service error

### 2. GlobalJumpService

**File:** `backend/src/services/global_jump_service.py`

**Responsibility:** Business logic for cross-video navigation, query orchestration

**Key Methods:**

```python
async def jump_next(
    kind: str,
    from_video_id: str,
    from_ms: int | None = None,
    label: str | None = None,
    query: str | None = None,
    face_cluster_id: str | None = None,
    min_confidence: float | None = None,
    limit: int = 1,
) -> list[GlobalJumpResult]
```

Returns list of GlobalJumpResult objects ordered by global timeline (ascending for next).

```python
async def jump_prev(
    kind: str,
    from_video_id: str,
    from_ms: int | None = None,
    label: str | None = None,
    query: str | None = None,
    face_cluster_id: str | None = None,
    min_confidence: float | None = None,
    limit: int = 1,
) -> list[GlobalJumpResult]
```

Returns list of GlobalJumpResult objects ordered by global timeline (descending for prev).

**Internal Methods:**

Each search method follows the same pattern:
1. Get current video metadata (file_created_at)
2. Build base query on projection table
3. Apply filters (label, confidence, text query)
4. Apply direction-specific WHERE clause
5. Order by global timeline
6. Limit results
7. Format and return

### 3. GlobalJumpResult (Data Model)

**File:** `backend/src/models/global_jump.py`

```python
@dataclass
class GlobalJumpResult:
    video_id: str
    video_filename: str
    file_created_at: datetime | None
    jump_to: JumpTo
    artifact_id: str
    preview: dict
    
@dataclass
class JumpTo:
    start_ms: int
    end_ms: int
```

### 4. Response Schemas (Pydantic)

**File:** `backend/src/api/schemas/global_jump_schemas.py`

```python
class JumpToSchema(BaseModel):
    start_ms: int
    end_ms: int

class GlobalJumpResultSchema(BaseModel):
    video_id: str
    video_filename: str
    file_created_at: datetime | None = None
    jump_to: JumpToSchema
    artifact_id: str
    preview: dict

class GlobalJumpResponseSchema(BaseModel):
    results: list[GlobalJumpResultSchema]
    has_more: bool
```

## Data Models

### Global Timeline Ordering

All queries use this deterministic ordering:

**For "next" direction (ascending):**
```sql
ORDER BY
  videos.file_created_at ASC,
  videos.video_id ASC,
  projection_table.start_ms ASC
```

**For "prev" direction (descending):**
```sql
ORDER BY
  videos.file_created_at DESC,
  videos.video_id DESC,
  projection_table.start_ms DESC
```

### Query Pattern for "Next" Direction

```sql
SELECT
  projection.artifact_id,
  projection.asset_id,
  projection.start_ms,
  projection.end_ms,
  projection.[kind_specific_fields],
  videos.filename,
  videos.file_created_at
FROM projection_table projection
JOIN videos ON videos.video_id = projection.asset_id
WHERE
  (videos.file_created_at > :current_file_created_at)
  OR (
    videos.file_created_at = :current_file_created_at
    AND videos.video_id = :current_video_id
    AND projection.start_ms > :from_ms
  )
  OR (
    videos.file_created_at = :current_file_created_at
    AND videos.video_id > :current_video_id
  )
  AND [kind_specific_filters]
ORDER BY
  videos.file_created_at ASC,
  videos.video_id ASC,
  projection.start_ms ASC
LIMIT :limit
```

### Query Pattern for "Prev" Direction

```sql
SELECT
  projection.artifact_id,
  projection.asset_id,
  projection.start_ms,
  projection.end_ms,
  projection.[kind_specific_fields],
  videos.filename,
  videos.file_created_at
FROM projection_table projection
JOIN videos ON videos.video_id = projection.asset_id
WHERE
  (videos.file_created_at < :current_file_created_at)
  OR (
    videos.file_created_at = :current_file_created_at
    AND videos.video_id = :current_video_id
    AND projection.start_ms < :from_ms
  )
  OR (
    videos.file_created_at = :current_file_created_at
    AND videos.video_id < :current_video_id
  )
  AND [kind_specific_filters]
ORDER BY
  videos.file_created_at DESC,
  videos.video_id DESC,
  projection.start_ms DESC
LIMIT :limit
```

### Projection Table Schemas (Existing)

**object_labels:**
- artifact_id (PK)
- asset_id (FK to videos)
- label (string)
- confidence (float 0-1)
- start_ms (int)
- end_ms (int)

**face_clusters:**
- artifact_id (PK)
- asset_id (FK to videos)
- cluster_id (string)
- confidence (float 0-1)
- start_ms (int)
- end_ms (int)

**transcript_fts:**
- artifact_id (PK)
- asset_id (FK to videos)
- text (string)
- text_tsv (tsvector for FTS)
- start_ms (int)
- end_ms (int)

**ocr_fts:**
- artifact_id (PK)
- asset_id (FK to videos)
- text (string)
- text_tsv (tsvector for FTS)
- start_ms (int)
- end_ms (int)

**scene_ranges:**
- artifact_id (PK)
- asset_id (FK to videos)
- scene_index (int)
- start_ms (int)
- end_ms (int)

**video_locations:**
- artifact_id (PK)
- asset_id (FK to videos)
- latitude (float)
- longitude (float)
- country (string)

## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property 1: Global Timeline Ordering Consistency

*For any* two results returned from a global jump query with direction="next", if result A has an earlier file_created_at than result B, then result A should appear before result B in the results list. If they have the same file_created_at, then the one with the earlier video_id should appear first. If they have the same video_id, then the one with the earlier start_ms should appear first.

**Validates: Requirements 6.1, 6.2, 6.3, 6.4**

### Property 2: Reverse Direction Ordering

*For any* two results returned from a global jump query with direction="prev", if result A has a later file_created_at than result B, then result A should appear before result B in the results list. If they have the same file_created_at, then the one with the later video_id should appear first. If they have the same video_id, then the one with the later start_ms should appear first.

**Validates: Requirements 6.5**

### Property 3: Filter Consistency for Confidence

*For any* global jump query with a min_confidence parameter, all returned results should have confidence >= min_confidence. No result should have confidence below the specified threshold.

**Validates: Requirements 1.3, 2.2**

### Property 4: Filter Consistency for Labels

*For any* global jump query with a label parameter, all returned results should have label exactly matching the specified label. No result should have a different label.

**Validates: Requirements 1.1, 1.2**

### Property 5: Filter Consistency for Text Search

*For any* global jump query with a query parameter (for transcript or OCR search), all returned results should contain the search term in their text field. The full-text search should match the query.

**Validates: Requirements 3.1, 3.2, 4.1, 4.2**

### Property 6: Empty Result Handling

*For any* global jump query that finds no matching results, the response should contain an empty results array and has_more=false, without raising an error.

**Validates: Requirements 8.5, 12.5, 14.4**

### Property 7: Limit Enforcement

*For any* global jump query with limit=N, the response should contain at most N results. If exactly N results are returned and more exist, has_more should be true. If fewer than N results exist, all available results should be returned and has_more should be false.

**Validates: Requirements 5.4, 5.5**

### Property 8: Video Existence Validation

*For any* global jump query with a from_video_id that does not exist in the database, the system should return a 404 error with message "Video not found".

**Validates: Requirements 8.1**

### Property 9: Parameter Validation - Invalid Kind

*For any* global jump query with an invalid kind parameter (not one of: object, face, transcript, ocr, scene, place, location), the system should return a 400 error with message "Invalid artifact kind".

**Validates: Requirements 8.2**

### Property 10: Parameter Validation - Invalid Direction

*For any* global jump query with an invalid direction parameter (not "next" or "prev"), the system should return a 400 error with message "Direction must be 'next' or 'prev'".

**Validates: Requirements 8.3**

### Property 11: Parameter Validation - Conflicting Filters

*For any* global jump query where both label and query parameters are specified, the system should return a 400 error with message "Cannot specify both label and query".

**Validates: Requirements 8.4**

### Property 12: Response Schema Completeness

*For any* global jump result returned, the response should include all required fields: video_id, video_filename, file_created_at, jump_to (with start_ms and end_ms), artifact_id, and preview. No required field should be missing or null (except file_created_at which may be null).

**Validates: Requirements 5.3, 7.1, 7.2, 7.3, 7.4, 7.5, 13.1**

### Property 13: Arbitrary Position Navigation

*For any* global jump query with from_video_id and from_ms parameters, the search should start from that position in the global timeline. Results should be chronologically after (for "next") or before (for "prev") that position.

**Validates: Requirements 11.1, 11.2, 11.3**

### Property 14: Optional from_ms Parameter

*For any* global jump query where from_ms is omitted, the search should start from the beginning of the video (for "next") or the end of the video (for "prev"). The query should execute without error.

**Validates: Requirements 11.5**

### Property 15: Boundary Condition - from_ms Beyond Duration

*For any* global jump query where from_ms is beyond the video duration, the system should treat it as the end of that video and search forward (for "next") or backward (for "prev") accordingly without error.

**Validates: Requirements 11.4**

### Property 16: Filter Change Independence

*For any* two consecutive global jump queries with the same from_video_id and from_ms but different filters (e.g., label="dog" vs label="cat"), the results should be independent. The second query should not be affected by the first query's filter.

**Validates: Requirements 12.1, 12.2, 12.3, 12.4**

### Property 17: Result Chaining

*For any* global jump result R, if we make a subsequent query with from_video_id=R.video_id and from_ms=R.end_ms, the new results should be chronologically after R in the global timeline.

**Validates: Requirements 13.5, 14.2, 14.3**

### Property 18: Cross-Video Navigation

*For any* global jump query that returns a result from a different video than from_video_id, that result should be the first matching artifact in the next/previous video in the global timeline (based on direction).

**Validates: Requirements 14.1, 14.5**

### Property 19: Backward Compatibility

*For any* request to the existing GET /videos/{video_id}/jump endpoint, the system should continue to return results scoped to that video only, without being affected by the new global jump feature.

**Validates: Requirements 10.1, 10.3**

### Property 20: Global Jump Independence

*For any* request to the new GET /jump/global endpoint, the system should return results across all videos without affecting the behavior of the existing single-video jump endpoint.

**Validates: Requirements 10.2, 10.4**

## Error Handling

### Error Categories

**Validation Errors (400):**
- Invalid kind parameter
- Invalid direction parameter
- Conflicting parameters (label and query both specified)
- Invalid min_confidence (not between 0-1)
- Invalid limit (not between 1-50)
- Invalid from_ms (negative)

**Not Found Errors (404):**
- from_video_id does not exist

**Server Errors (500):**
- Database connection failure
- Unexpected query execution error
- Service initialization failure

### Error Response Format

```python
class ErrorResponse(BaseModel):
    detail: str
    error_code: str
    timestamp: datetime
```

### Error Messages

| Scenario | Message | Code |
|----------|---------|------|
| Invalid kind | "Invalid artifact kind. Must be one of: object, face, transcript, ocr, scene, place, location" | INVALID_KIND |
| Invalid direction | "Direction must be 'next' or 'prev'" | INVALID_DIRECTION |
| Conflicting filters | "Cannot specify both label and query parameters" | CONFLICTING_FILTERS |
| Video not found | "Video not found" | VIDEO_NOT_FOUND |
| Invalid confidence | "min_confidence must be between 0 and 1" | INVALID_CONFIDENCE |
| Invalid limit | "limit must be between 1 and 50" | INVALID_LIMIT |

## Testing Strategy

### Unit Testing Approach

Unit tests verify specific examples, edge cases, and error conditions:

1. **Parameter Validation Tests**
   - Test each invalid parameter combination
   - Verify correct error codes and messages
   - Test boundary values (limit=1, limit=50, confidence=0, confidence=1)

2. **Query Logic Tests**
   - Test ordering correctness with mock data
   - Test filter application (label, confidence, text query)
   - Test direction reversal (next vs prev)
   - Test boundary conditions (from_ms at video end, etc.)

3. **Integration Tests**
   - Test with real database (using test fixtures)
   - Test cross-video navigation
   - Test empty result handling
   - Test with multiple videos in different chronological orders

4. **Error Handling Tests**
   - Test 404 for non-existent video
   - Test 400 for invalid parameters
   - Test graceful handling of database errors

### Property-Based Testing Approach

Property-based tests verify universal properties across many generated inputs:

1. **Timeline Ordering Property Test**
   - Generate random videos with random file_created_at dates
   - Generate random artifacts in each video
   - Run global jump queries
   - Verify results are ordered by global timeline
   - Minimum 100 iterations

2. **Filter Consistency Property Test**
   - Generate random artifacts with various labels and confidence scores
   - Run queries with different filters
   - Verify all results satisfy the filter criteria
   - Minimum 100 iterations

3. **Direction Symmetry Property Test**
   - Generate random video/artifact data
   - Run "next" query from position A
   - Run "prev" query from result position
   - Verify we can navigate back to original position
   - Minimum 100 iterations

4. **Boundary Handling Property Test**
   - Generate videos with various durations
   - Test from_ms at boundaries (0, duration, beyond duration)
   - Verify no errors and correct results
   - Minimum 100 iterations

5. **Empty Result Property Test**
   - Generate scenarios with no matching results
   - Verify empty results array and has_more=false
   - Verify no errors raised
   - Minimum 100 iterations

### Test Configuration

- **Framework:** pytest with pytest-asyncio for async tests
- **Property Testing:** hypothesis for property-based tests
- **Database:** PostgreSQL test container
- **Fixtures:** Pre-populated test data with known ordering
- **Minimum iterations:** 100 per property test
- **Timeout:** 5 seconds per test

### Test Tags

Each property test includes a comment tag:
```python
# Feature: global-jump-navigation, Property N: [Property Title]
```

## Performance Considerations

### Query Optimization

1. **Composite Indexes** (Phase 3)
   - `idx_object_labels_label_global` on (label, asset_id, start_ms)
   - `idx_face_clusters_cluster_global` on (cluster_id, asset_id, start_ms)
   - `idx_videos_created_at_id` on (file_created_at, video_id)

2. **Full-Text Search Optimization**
   - Existing GIN indexes on transcript_fts.text_tsv and ocr_fts.text_tsv
   - PostgreSQL plainto_tsquery for text normalization

3. **Query Execution**
   - Use LIMIT to restrict result set early
   - Avoid full table scans through proper indexing
   - Target query execution time: < 500ms for typical queries

### Scalability

- Design supports millions of artifacts across thousands of videos
- Projection tables already denormalized for cross-video queries
- No new data structures required for MVP
- Future: Materialized views for very large datasets (Phase 3)

## Future Enhancements (Out of Scope for MVP)

### Phase 4: Multi-Filter Searches

- Support AND/OR logic for combining multiple filters
- Example: "next frame with DOG AND CAT"
- Example: "next frame with Kubernetes text AND plant object"
- Requires query builder for complex filter combinations
- May require new database views or query optimization

### Phase 5: Embedding-Based Search

- Add pgvector extension for similarity search
- Store face embeddings for fuzzy face matching
- Implement CLIP embeddings for visual similarity
- Add embedding-based global jump queries

### Phase 6: Advanced Filtering

- Geo-spatial queries for location-based navigation
- Date range filtering
- Confidence score distribution analysis
- Multi-label filtering (AND/OR logic)

### Phase 7: Performance Optimization

- Materialized views for frequently accessed queries
- Query result caching
- Asynchronous index building
- Partitioning large projection tables by date

## Backward Compatibility

The new global jump feature is fully additive:
- Existing `/videos/{video_id}/jump` endpoint remains unchanged
- No modifications to existing projection tables
- No breaking changes to existing APIs
- New `/jump/global` endpoint is independent

## API Endpoint Specification

### GET /jump/global

**Query Parameters:**
- `kind` (required): artifact type (object, face, transcript, ocr, scene, place, location)
- `direction` (required): next or prev
- `from_video_id` (required): current video ID
- `from_ms` (optional): current position in milliseconds (default: 0 for next, video end for prev)
- `label` (optional): filter by label (objects, places)
- `query` (optional): text search query (transcript, ocr)
- `face_cluster_id` (optional): filter by face cluster
- `min_confidence` (optional): minimum confidence threshold (0-1)
- `limit` (optional): max results (default: 1, max: 50)

**Response:**
```json
{
  "results": [
    {
      "video_id": "abc-123",
      "video_filename": "beach_trip.mp4",
      "file_created_at": "2025-05-19T02:22:21Z",
      "jump_to": {
        "start_ms": 15000,
        "end_ms": 15500
      },
      "artifact_id": "artifact_xyz",
      "preview": {
        "label": "dog",
        "confidence": 0.95
      }
    }
  ],
  "has_more": true
}
```

**Status Codes:**
- 200: Success
- 400: Invalid parameters
- 404: Video not found
- 500: Server error

## User Experience Flow

### Initial Search Scenario

1. **User initiates search** from the UI (e.g., clicks "Find next DOG" button, or uses a search form/bar)
   - *Note: The specific UI implementation (search bar, form, buttons, etc.) is a frontend concern and not specified in this backend design*
2. **Frontend calls** `GET /jump/global?kind=object&label=dog&direction=next&from_video_id={current_video}&from_ms={current_position}`
3. **Backend returns** first matching result with video_id, filename, and jump_to timestamps
4. **Frontend behavior:**
   - If result.video_id == current_video: Seek to result.jump_to.start_ms in current video
   - If result.video_id != current_video: Navigate to new video and seek to result.jump_to.start_ms
5. **Video player** displays the artifact at the specified timestamp

### Continuous Navigation Scenario

1. **User watches** the artifact at jump_to.start_ms to jump_to.end_ms
2. **User clicks** "Find next DOG" again
3. **Frontend calls** `GET /jump/global?kind=object&label=dog&direction=next&from_video_id={result.video_id}&from_ms={result.end_ms}`
4. **Backend returns** next matching result (chronologically after the previous result)
5. **Process repeats** - navigate to new video or seek in current video

### Filter Change Scenario

1. **User is watching** a video with DOG search active
2. **User changes filter** to search for CAT instead
3. **Frontend calls** `GET /jump/global?kind=object&label=cat&direction=next&from_video_id={current_video}&from_ms={current_position}`
4. **Backend searches** for CAT starting from current position
5. **Results are independent** of previous DOG search - no state carried over

### No Results Scenario

1. **User searches** for a rare object (e.g., "giraffe")
2. **Backend returns** empty results array with has_more=false
3. **Frontend displays** "No results found" message
4. **User can** change filters and try again, or navigate manually

### Timeline Exploration Scenario

1. **User wants to explore** the entire video library chronologically
2. **User calls** `GET /jump/global?kind=object&label=dog&direction=next&from_video_id={first_video}&from_ms=0`
3. **Backend returns** first DOG occurrence in the library
4. **User clicks** "Next" repeatedly to browse all DOG occurrences in chronological order
5. **Each click** uses the previous result's position as the starting point for the next search
