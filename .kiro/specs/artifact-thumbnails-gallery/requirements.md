# Requirements Document

## Introduction

This document specifies the requirements for artifact thumbnail generation and an artifact-based gallery search feature. The thumbnail task extracts small WebP images at artifact timestamps for use in search result galleries. The gallery search enables browsing artifacts as a visual grid with thumbnails.

## Glossary

- **Artifact_Thumbnail**: A small WebP image extracted from a video frame at an artifact's timestamp
- **Artifact_Gallery**: A visual grid display of artifact search results with thumbnails
- **Timestamp_Deduplication**: The process of generating only one thumbnail per unique timestamp, even when multiple artifacts share that timestamp

## Requirements

### Requirement 1: Thumbnail Extraction Task

**User Story:** As a system operator, I want thumbnails generated for all artifact timestamps, so that search results can display visual previews.

#### Acceptance Criteria

1. THE system SHALL provide a `thumbnail.extraction` task type that generates thumbnails for a video's artifacts
2. THE task SHALL query all artifacts for the video and collect unique `start_ms` timestamps
3. THE task SHALL skip thumbnail generation for timestamps that already have a thumbnail file on disk (idempotent)
4. THE task SHALL generate WebP format thumbnails with maximum width of 320 pixels (height proportional)
5. THE task SHALL store thumbnails at `/data/thumbnails/{video_id}/{timestamp_ms}.webp`
6. THE task SHALL target thumbnail file size of approximately 10-20KB each
7. THE task SHALL use ffmpeg for frame extraction

### Requirement 2: Thumbnail Deduplication

**User Story:** As a system operator, I want to avoid generating duplicate thumbnails, so that storage is used efficiently.

#### Acceptance Criteria

1. WHEN multiple artifacts share the same `start_ms` timestamp, THE task SHALL generate only one thumbnail for that timestamp
2. WHEN a thumbnail file already exists for a timestamp, THE task SHALL skip extraction for that timestamp
3. THE task SHALL log the count of skipped (already existing) thumbnails vs newly generated thumbnails

### Requirement 3: Thumbnail Serving Endpoint

**User Story:** As a frontend developer, I want an API endpoint to retrieve thumbnails, so that I can display them in the UI.

#### Acceptance Criteria

1. THE backend SHALL provide a `GET /v1/thumbnails/{video_id}/{timestamp_ms}` endpoint
2. WHEN the thumbnail exists, THE endpoint SHALL return the WebP file with appropriate content type
3. WHEN the thumbnail does not exist, THE endpoint SHALL return 404
4. THE endpoint SHALL set appropriate cache headers for browser caching (e.g., 1 week)

### Requirement 4: Artifact Gallery Search API

**User Story:** As a user, I want to search artifacts and see results as a visual gallery, so that I can quickly browse matching content.

#### Acceptance Criteria

1. THE backend SHALL provide a `GET /api/v1/artifacts/search` endpoint for gallery-style artifact search
2. THE endpoint SHALL accept parameters: `kind`, `label`, `query`, `min_confidence`, `filename`, `limit`, `offset`, `group_by_video`
3. THE endpoint SHALL return results ordered by global timeline (file_created_at, video_id, start_ms)
4. EACH result SHALL include: `video_id`, `artifact_id`, `start_ms`, `thumbnail_url`, `preview`, `video_filename`
5. THE `thumbnail_url` SHALL point to the thumbnail serving endpoint for that artifact's timestamp
6. THE endpoint SHALL support pagination via `limit` and `offset` parameters
7. THE endpoint SHALL return total count of matching artifacts for pagination UI
8. WHEN `filename` parameter is provided, THE endpoint SHALL filter results to videos whose filename contains the search string (case-insensitive)
9. WHEN `group_by_video` is true, THE endpoint SHALL return only the first matching artifact per video (collapsed view)
10. WHEN `group_by_video` is true, EACH result SHALL include `artifact_count` indicating total matches in that video

### Requirement 5: Artifact Gallery UI Component

**User Story:** As a user, I want a visual gallery interface to browse artifact search results, so that I can find content by looking at thumbnails.

#### Acceptance Criteria

1. THE frontend SHALL provide an `ArtifactGallery` component that displays search results as a thumbnail grid
2. THE gallery SHALL display thumbnails in a responsive grid layout (adapting to screen width)
3. EACH thumbnail card SHALL display: the thumbnail image, artifact label/text preview, video filename, timestamp
4. WHEN the user clicks a thumbnail, THE application SHALL navigate to the player page at that video and timestamp
5. THE gallery SHALL display a loading state while fetching results
6. THE gallery SHALL display "No results found" when the search returns empty
7. THE gallery SHALL support infinite scroll or pagination for browsing large result sets

### Requirement 6: Gallery Search Form

**User Story:** As a user, I want to filter the artifact gallery by type and search criteria, so that I can find specific content.

#### Acceptance Criteria

1. THE gallery page SHALL include a search form with artifact type selector
2. THE search form SHALL include appropriate input fields based on artifact type (label for objects, query for transcript/ocr)
3. THE search form SHALL include a confidence threshold slider for applicable artifact types
4. THE search form SHALL include a filename filter input to search within specific videos
5. WHEN the user submits the search form, THE gallery SHALL update to show matching results
6. THE search form state SHALL be preserved in the URL for shareable links
7. THE search form SHALL include a "Group by video" toggle to collapse results by video
8. WHEN "Group by video" is enabled, THE gallery SHALL show one thumbnail per video with artifact count badge

### Requirement 7: Thumbnail Fallback

**User Story:** As a user, I want to see a placeholder when a thumbnail is not available, so that the gallery layout remains consistent.

#### Acceptance Criteria

1. WHEN a thumbnail fails to load (404 or error), THE gallery SHALL display a placeholder image
2. THE placeholder SHALL indicate the artifact type (e.g., icon for object, face, transcript)
3. THE gallery layout SHALL not break when thumbnails are missing

