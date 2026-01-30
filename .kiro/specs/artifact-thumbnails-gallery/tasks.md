# Implementation Tasks: Artifact Thumbnails & Gallery

## Overview

Tasks for implementing artifact thumbnail generation and the artifact gallery search feature.

## Tasks

### Backend: Thumbnail Extraction Task

- [ ] 1. Create thumbnail extractor module
  - Create `ml-service/src/workers/thumbnail_extractor.py`
  - Define constants: THUMBNAIL_DIR, THUMBNAIL_WIDTH (320), THUMBNAIL_QUALITY (75)
  - Create output directory structure
  - _Requirements: 1.1, 1.4, 1.5, 1.6_

- [ ] 2. Implement timestamp collection
  - Query all artifacts for video
  - Extract unique start_ms timestamps
  - Deduplicate timestamps (multiple artifacts at same ms)
  - _Requirements: 1.2, 2.1_

- [ ] 3. Implement idempotent thumbnail generation
  - Check if thumbnail file exists before extraction
  - Skip existing thumbnails
  - Log skipped vs generated counts
  - _Requirements: 1.3, 2.2, 2.3_

- [ ] 4. Implement ffmpeg frame extraction
  - Build ffmpeg command for WebP output
  - Use scale filter for 320px width
  - Handle extraction errors gracefully
  - Add timeout (10 seconds per frame)
  - _Requirements: 1.7_

- [ ] 5. Register thumbnail task type
  - Add `thumbnail.extraction` to task registry
  - Configure as low priority task
  - _Requirements: 1.1_

- [ ] 6. Write tests for thumbnail extraction
  - Test timestamp deduplication
  - Test idempotent behavior (skip existing)
  - Test ffmpeg command construction
  - Test error handling
  - _Requirements: 1, 2_

### Backend: Thumbnail Serving API

- [ ] 7. Create thumbnail controller
  - Create `backend/src/api/thumbnail_controller.py`
  - Add router with `/thumbnails` prefix
  - _Requirements: 3.1_

- [ ] 8. Implement thumbnail serving endpoint
  - Add `GET /{video_id}/{timestamp_ms}` endpoint
  - Return FileResponse with WebP content type
  - Return 404 if thumbnail not found
  - Set cache headers (1 week)
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [ ] 9. Register thumbnail router
  - Import router in main_api.py
  - Include router with `/v1/thumbnails` prefix
  - _Requirements: 3.1_

- [ ] 10. Write tests for thumbnail serving
  - Test successful thumbnail retrieval
  - Test 404 for missing thumbnail
  - Test cache headers
  - _Requirements: 3_

### Backend: Artifact Search API

- [ ] 11. Create artifact search controller
  - Create `backend/src/api/artifact_search_controller.py`
  - Add router with `/artifacts` prefix
  - Define response schemas
  - _Requirements: 4.1_

- [ ] 12. Implement search endpoint
  - Add `GET /search` endpoint
  - Accept kind, label, query, filename, min_confidence, limit, offset params
  - Map kind to artifact_type
  - _Requirements: 4.1, 4.2_

- [ ] 13. Implement search query building
  - Build base query joining artifacts and videos
  - Add label filter for object/place
  - Add query filter for transcript/ocr
  - Add filename filter (ILIKE)
  - Add min_confidence filter
  - _Requirements: 4.2, 4.8_

- [ ] 14. Implement pagination and ordering
  - Order by global timeline (file_created_at, video_id, start_ms)
  - Apply limit and offset
  - Return total count for pagination UI
  - _Requirements: 4.3, 4.6, 4.7_

- [ ] 15. Build response with thumbnail URLs
  - Construct thumbnail_url for each result
  - Include video_filename, file_created_at
  - Return ArtifactSearchResponse
  - _Requirements: 4.4, 4.5_

- [ ] 16. Register artifact search router
  - Import router in main_api.py
  - Include router with `/v1/artifacts` prefix
  - _Requirements: 4.1_

- [ ] 17. Write tests for artifact search
  - Test search by kind
  - Test label filter
  - Test query filter
  - Test filename filter
  - Test min_confidence filter
  - Test pagination
  - Test ordering
  - _Requirements: 4_

### Frontend: ArtifactGallery Component

- [ ] 18. Create ArtifactGallery component skeleton
  - Create `frontend/src/components/ArtifactGallery.tsx`
  - Define props interface
  - Set up state for results, loading, pagination
  - _Requirements: 5.1_

- [ ] 19. Implement search form
  - Add artifact type selector dropdown
  - Add label/query input based on type
  - Add filename filter input
  - Add confidence slider for applicable types
  - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 20. Implement API integration
  - Build search request with form state
  - Call `/api/v1/artifacts/search` endpoint
  - Handle loading state
  - Handle errors
  - _Requirements: 6.5_

- [ ] 21. Implement thumbnail grid
  - Create responsive grid layout
  - Render ThumbnailCard for each result
  - Handle thumbnail load errors with placeholder
  - _Requirements: 5.2, 7.1, 7.2, 7.3_

- [ ] 22. Create ThumbnailCard component
  - Display thumbnail image
  - Show label/text preview
  - Show video filename
  - Show timestamp (MM:SS format)
  - Handle click to navigate
  - _Requirements: 5.3, 5.4_

- [ ] 23. Implement pagination/infinite scroll
  - Add pagination controls or infinite scroll
  - Load more results on scroll/click
  - _Requirements: 5.7_

- [ ] 24. Implement empty and loading states
  - Show loading spinner during fetch
  - Show "No results found" for empty results
  - _Requirements: 5.5, 5.6_

- [ ] 25. Implement URL state preservation
  - Sync form state to URL query params
  - Read initial state from URL on mount
  - _Requirements: 6.6_

- [ ] 26. Apply component styling
  - Use dark theme colors
  - Responsive grid (auto-fill, minmax 200px)
  - Card hover effects
  - _Requirements: 5.2_

### Frontend: Gallery Page

- [ ] 27. Create Gallery page
  - Create `frontend/src/pages/GalleryPage.tsx`
  - Render ArtifactGallery component
  - Handle artifact click navigation to player
  - _Requirements: 5.4_

- [ ] 28. Add gallery page route
  - Add `/gallery` route to app router
  - Link to gallery from navigation/header
  - _Requirements: 5.1_

### Testing

- [ ] 29. Write ArtifactGallery unit tests
  - Test search form rendering
  - Test grid layout
  - Test thumbnail card rendering
  - Test placeholder on image error
  - Test loading state
  - Test empty state
  - _Requirements: 5, 6, 7_

- [ ] 30. Write integration tests
  - Test search flow end-to-end
  - Test navigation to player
  - Test URL state preservation
  - _Requirements: 5, 6_

### Checkpoints

- [ ] 31. Checkpoint: Thumbnail extraction works
  - Run thumbnail task on test video
  - Verify thumbnails created in /data/thumbnails
  - Verify deduplication
  - Verify idempotency
  - _Requirements: 1, 2_

- [ ] 32. Checkpoint: Thumbnail serving works
  - Test endpoint returns thumbnails
  - Test 404 for missing
  - Test cache headers
  - _Requirements: 3_

- [ ] 33. Checkpoint: Artifact search API works
  - Test all filter combinations
  - Test pagination
  - Test thumbnail URLs in response
  - _Requirements: 4_

- [ ] 34. Checkpoint: Gallery UI works
  - Test search form
  - Test thumbnail grid display
  - Test navigation to player
  - _Requirements: 5, 6, 7_

- [ ] 35. Final checkpoint: All tests pass
  - Run ml-service tests
  - Run backend tests
  - Run frontend tests
  - Run lint checks
  - _Requirements: All_

## Notes

- Backend tasks (1-17) can be done before frontend tasks (18-28)
- Thumbnail extraction (1-6) is independent of thumbnail serving (7-10)
- Artifact search API (11-17) is independent of thumbnail tasks
- Gallery UI (18-28) depends on both thumbnail serving and artifact search APIs
- Consider running thumbnail extraction as a batch job for existing videos
