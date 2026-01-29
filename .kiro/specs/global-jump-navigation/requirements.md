# Requirements Document: Global Jump Navigation

## Introduction

Global Jump Navigation enables users to search for and navigate to specific artifacts (objects, faces, text, scenes) across their entire video library in chronological order. Instead of being limited to jumping within a single video, users can now query "next video with DOG" or "next occurrence of WORD" and seamlessly navigate across videos. This feature leverages existing projection tables (object_labels, face_clusters, transcript_fts, ocr_fts, scene_ranges, video_locations) to provide fast, cross-video navigation.

## Glossary

- **Artifact**: A detected or extracted element within a video (object, face, text, scene, location)
- **Projection Table**: Pre-computed, denormalized table containing artifact data across all videos (e.g., object_labels, transcript_fts)
- **Global Timeline**: Chronological ordering of all videos based on file_created_at (EXIF/filesystem date), then by artifact timestamp within each video
- **Jump**: Navigation action to move to a specific artifact occurrence
- **Kind**: Type of artifact being searched (object, face, transcript, ocr, scene, place, location)
- **Direction**: Navigation direction (next or prev) along the global timeline
- **Confidence**: Probability score (0-1) indicating detection confidence for objects and faces
- **Face Cluster**: Grouping of face detections representing the same person across videos
- **FTS**: Full-Text Search capability for text-based artifacts (transcript, OCR)
- **Asset ID**: Unique identifier for a video (video_id)
- **Artifact ID**: Unique identifier for a specific artifact occurrence

## Requirements

### Requirement 1: Cross-Video Navigation by Object Label

**User Story:** As a video analyst, I want to navigate to the next or previous occurrence of a specific object (e.g., "dog", "car") across all my videos, so that I can quickly find all instances of that object without manually searching each video.

#### Acceptance Criteria

1. WHEN a user requests the next occurrence of an object label THEN THE GlobalJumpService SHALL query the object_labels projection table and return the first matching object in chronological order after the current position
2. WHEN a user requests the previous occurrence of an object label THEN THE GlobalJumpService SHALL query the object_labels projection table and return the first matching object in reverse chronological order before the current position
3. WHEN a user specifies a minimum confidence threshold THEN THE GlobalJumpService SHALL filter results to only include objects with confidence >= the specified threshold
4. WHEN multiple objects match the search criteria THEN THE GlobalJumpService SHALL order results by file_created_at (ascending for next, descending for prev), then by video_id, then by start_ms within the video
5. WHEN a user navigates to a result in a different video THEN THE System SHALL return the video_id, video_filename, file_created_at, and jump_to timestamps (start_ms, end_ms)

### Requirement 2: Cross-Video Navigation by Face Cluster

**User Story:** As a video editor, I want to find all occurrences of a specific person (face cluster) across my video library, so that I can quickly compile scenes featuring that person.

#### Acceptance Criteria

1. WHEN a user requests navigation by face cluster ID THEN THE GlobalJumpService SHALL query the face_clusters projection table and return matching face detections in chronological order
2. WHEN a user specifies a minimum confidence threshold for face detection THEN THE GlobalJumpService SHALL filter results to only include faces with confidence >= the specified threshold
3. WHEN a user navigates to a face result THEN THE System SHALL return the face cluster ID, confidence score, and temporal boundaries (start_ms, end_ms)
4. WHEN multiple face detections match the search criteria THEN THE GlobalJumpService SHALL order results by file_created_at, then video_id, then start_ms

### Requirement 3: Cross-Video Full-Text Search in Transcripts

**User Story:** As a researcher, I want to search for specific words or phrases across all video transcripts and navigate between occurrences, so that I can find all mentions of a topic across my video collection.

#### Acceptance Criteria

1. WHEN a user provides a text query THEN THE GlobalJumpService SHALL perform full-text search across the transcript_fts projection table using PostgreSQL FTS capabilities
2. WHEN a user requests the next occurrence of a search term THEN THE GlobalJumpService SHALL return the first matching transcript segment in chronological order after the current position
3. WHEN a user requests  the previous occurrence of a search term THEN THE GlobalJumpService SHALL return the first matching transcript segment in reverse chronological order before the current position
4. WHEN multiple transcript segments match the search query THEN THE GlobalJumpService SHALL order results by file_created_at, then video_id, then start_ms
5. WHEN a user navigates to a transcript result THEN THE System SHALL return the matched text snippet and temporal boundaries

### Requirement 4: Cross-Video Full-Text Search in OCR

**User Story:** As a document analyst, I want to search for text that appears in video frames (OCR) across all videos, so that I can find all instances of specific text or document content.

#### Acceptance Criteria

1. WHEN a user provides a text query for OCR search THEN THE GlobalJumpService SHALL perform full-text search across the ocr_fts projection table
2. WHEN a user requests navigation by OCR text THEN THE GlobalJumpService SHALL return matching OCR segments in chronological order following the global timeline
3. WHEN multiple OCR segments match the search query THEN THE GlobalJumpService SHALL order results by file_created_at, then video_id, then start_ms
4. WHEN a user navigates to an OCR result THEN THE System SHALL return the matched text and temporal boundaries

### Requirement 5: Global Jump API Endpoint

**User Story:** As a frontend developer, I want a unified API endpoint for cross-video navigation, so that I can implement global jump functionality without managing multiple endpoints.

#### Acceptance Criteria

1. THE System SHALL provide a GET /jump/global endpoint that accepts query parameters for kind, direction, from_video_id, from_ms, label, query, face_cluster_id, min_confidence, and limit
2. WHEN a request is made to /jump/global THEN THE System SHALL validate all input parameters and return a 400 error if required parameters are missing or invalid
3. WHEN a valid request is made to /jump/global THEN THE System SHALL return a JSON response containing results array with video_id, video_filename, file_created_at, jump_to (start_ms, end_ms), artifact_id, and preview data
4. WHEN the limit parameter is specified THEN THE System SHALL return at most that many results (default 1, maximum 50)
5. WHEN results are returned THEN THE System SHALL include a has_more boolean indicating whether additional results exist beyond the limit

### Requirement 6: Global Timeline Ordering

**User Story:** As a user, I want consistent, predictable ordering when navigating across videos, so that I can understand the sequence of results and navigate intuitively.

#### Acceptance Criteria

1. THE GlobalJumpService SHALL order all results using a deterministic global timeline based on file_created_at (EXIF/filesystem date) as the primary sort key
2. WHEN two videos have the same file_created_at THEN THE GlobalJumpService SHALL use video_id as a secondary sort key to ensure deterministic ordering
3. WHEN navigating within the same video THEN THE GlobalJumpService SHALL use start_ms as the tertiary sort key to order artifacts chronologically
4. WHEN a user requests "next" THEN THE GlobalJumpService SHALL return results in ascending order along the global timeline
5. WHEN a user requests "prev" THEN THE GlobalJumpService SHALL return results in descending order along the global timeline

### Requirement 7: Result Preview Data

**User Story:** As a user, I want to see relevant preview information about each result before navigating to it, so that I can verify it's the result I'm looking for.

#### Acceptance Criteria

1. WHEN returning an object detection result THEN THE System SHALL include preview data containing the label and confidence score
2. WHEN returning a face cluster result THEN THE System SHALL include preview data containing the cluster ID and confidence score
3. WHEN returning a transcript search result THEN THE System SHALL include preview data containing the matched text snippet
4. WHEN returning an OCR search result THEN THE System SHALL include preview data containing the matched text snippet
5. WHEN returning a scene result THEN THE System SHALL include preview data containing the scene index or description

### Requirement 8: Error Handling for Global Jump

**User Story:** As a developer, I want clear error messages when global jump queries fail, so that I can debug issues and provide helpful feedback to users.

#### Acceptance Criteria

1. IF a user requests navigation from a non-existent video_id THEN THE System SHALL return a 404 error with message "Video not found"
2. IF a user provides an invalid kind parameter THEN THE System SHALL return a 400 error with message "Invalid artifact kind"
3. IF a user provides an invalid direction parameter THEN THE System SHALL return a 400 error with message "Direction must be 'next' or 'prev'"
4. IF a user provides conflicting parameters (e.g., both label and query) THEN THE System SHALL return a 400 error with message "Cannot specify both label and query"
5. IF no results are found matching the criteria THEN THE System SHALL return a 200 response with empty results array and has_more=false

### Requirement 9: Performance and Scalability

**User Story:** As a system administrator, I want global jump queries to execute efficiently even with large video libraries, so that users experience responsive navigation.

#### Acceptance Criteria

1. WHEN a global jump query is executed THEN THE System SHALL complete within 500ms for typical queries (< 10,000 videos)
2. WHEN querying by object label THEN THE System SHALL use composite indexes on (label, asset_id, start_ms) to optimize performance
3. WHEN querying by face cluster THEN THE System SHALL use composite indexes on (cluster_id, asset_id, start_ms) to optimize performance
4. WHEN querying by text (transcript or OCR) THEN THE System SHALL use existing GIN indexes on full-text search vectors
5. WHEN querying by video ordering THEN THE System SHALL use composite indexes on (file_created_at, video_id) to optimize timeline ordering

### Requirement 10: Backward Compatibility

**User Story:** As a developer, I want the new global jump feature to coexist with existing single-video jump functionality, so that I can migrate gradually without breaking existing code.

#### Acceptance Criteria

1. THE existing GET /videos/{video_id}/jump endpoint SHALL remain unchanged and functional
2. THE new GET /jump/global endpoint SHALL be additive and not modify existing video jump behavior
3. WHEN a user uses the existing single-video jump endpoint THEN THE System SHALL continue to return results scoped to that video only
4. WHEN a user uses the new global jump endpoint THEN THE System SHALL return results across all videos without affecting single-video jump functionality

### Requirement 11: Jump from Arbitrary Timeline Position

**User Story:** As a user, I want to start a global jump search from any point in the timeline (not just the current video), so that I can explore different branches of the timeline without navigating to that video first.

#### Acceptance Criteria

1. WHEN a user specifies from_video_id and from_ms parameters THEN THE GlobalJumpService SHALL treat that position as the starting point for the global timeline search
2. WHEN a user requests "next" from an arbitrary position THEN THE GlobalJumpService SHALL return results chronologically after that position
3. WHEN a user requests "prev" from an arbitrary position THEN THE GlobalJumpService SHALL return results chronologically before that position
4. WHEN a user specifies a from_video_id that exists but from_ms is beyond the video duration THEN THE System SHALL treat it as the end of that video and search forward/backward accordingly
5. THE from_ms parameter SHALL be optional; if omitted, the search SHALL start from the beginning (for "next") or end (for "prev") of the specified video

### Requirement 12: Dynamic Filter Changes

**User Story:** As a user, I want to change search filters while navigating the timeline, so that I can switch from searching for "dogs" to "cats" without losing my position in the timeline.

#### Acceptance Criteria

1. WHEN a user changes the search filter (e.g., from label="dog" to label="cat") THEN THE System SHALL accept the new filter in a subsequent /jump/global request
2. WHEN a user changes filters while maintaining the same from_video_id and from_ms THEN THE GlobalJumpService SHALL search for the new filter starting from that same timeline position
3. WHEN a user changes from one artifact kind to another (e.g., from object to transcript) THEN THE System SHALL route to the appropriate projection table and return results of the new kind
4. WHEN a user changes filters THEN THE System SHALL NOT require re-navigation to a specific video; the timeline position (from_video_id, from_ms) remains the reference point
5. WHEN a user changes filters and no results exist for the new filter THEN THE System SHALL return an empty results array and has_more=false, allowing the user to try different filters

### Requirement 13: Direct Navigation to Result Artifact

**User Story:** As a user, I want to navigate directly to the exact timestamp of a search result, so that I can immediately see the artifact I'm looking for without manual seeking.

#### Acceptance Criteria

1. WHEN a global jump result is returned THEN THE System SHALL include jump_to object containing start_ms and end_ms for the artifact
2. WHEN a user navigates to a result in a different video THEN THE System SHALL automatically load that video and seek to the start_ms timestamp
3. WHEN a user navigates to a result in the same video THEN THE System SHALL seek to the start_ms timestamp without reloading the video
4. WHEN a user navigates to a result THEN THE System SHALL highlight or focus on the artifact (start_ms to end_ms) to draw attention to the specific occurrence
5. WHEN a user requests the next result after navigating to a result THEN THE GlobalJumpService SHALL use the result's video_id and end_ms as the new from_video_id and from_ms for the next search

### Requirement 14: Navigate to Next Video in Timeline

**User Story:** As a user, I want to jump to the next video in the global timeline, so that I can browse through my video library sequentially.

#### Acceptance Criteria

1. WHEN a user requests navigation to the next video (without specifying a search filter) THEN THE System SHALL return the first artifact from the next video in chronological order
2. WHEN a user is at the end of a video and requests "next" THEN THE GlobalJumpService SHALL return results from the next video in the global timeline
3. WHEN a user is at the beginning of a video and requests "prev" THEN THE GlobalJumpService SHALL return results from the previous video in the global timeline
4. WHEN a user requests next/prev video navigation and no next/previous video exists THEN THE System SHALL return an empty results array and has_more=false
5. WHEN navigating between videos THEN THE System SHALL maintain the same search filter (kind, label, query) across video boundaries
