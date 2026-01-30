# Implementation Tasks: Global Jump Navigation GUI

## Overview

Tasks for implementing the Global Jump Navigation GUI, including the frontend component, backend location text search enhancement, and video clip export feature.

## Tasks

### Backend: Location Text Search Enhancement

- [x] 1. Add text search to location search method
  - Modify `_search_locations_global()` in `backend/src/services/global_jump_service.py`
  - Add `query` parameter to method signature
  - Add ILIKE filter for country, state, city fields when query is provided
  - Ensure existing geo_bounds filtering still works
  - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [x] 2. Update jump_next and jump_prev to pass query for location
  - Modify `jump_next()` to pass query parameter when kind='location'
  - Modify `jump_prev()` to pass query parameter when kind='location'
  - _Requirements: 7.1_

- [x] 3. Write tests for location text search
  - Test search matching country field
  - Test search matching state field
  - Test search matching city field
  - Test case-insensitive matching
  - Test partial matching
  - Test combined query + geo_bounds filtering
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

### Frontend: GlobalJumpControl Component

- [x] 4. Create GlobalJumpControl component skeleton
  - Create `frontend/src/components/GlobalJumpControl.tsx`
  - Define props interface with videoId, videoRef, onVideoChange, onNavigate
  - Set up component state for artifactType, label, query, confidence, loading
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 5. Implement artifact type selector
  - Add dropdown with all 7 artifact types
  - Configure which input fields show for each type
  - Show label input for object/place
  - Show query input for transcript/ocr/location
  - Hide inputs for scene
  - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

- [x] 6. Implement confidence threshold slider
  - Add range slider (0-1, step 0.1)
  - Display percentage value
  - Show only for object/face/place types
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 7. Implement navigation buttons and API calls
  - Add Previous and Next buttons
  - Build API request with correct parameters per artifact type
  - Call `/api/v1/jump/global` endpoint
  - Handle loading state (disable buttons, show indicator)
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

- [x] 8. Implement cross-video navigation handling
  - Detect when result video_id differs from current video
  - Call onVideoChange callback for cross-video results
  - Seek video for same-video results
  - Log warning if onVideoChange not provided
  - _Requirements: 1.2, 1.3, 6.1, 6.2, 6.3, 6.4_

- [x] 9. Implement current match display
  - Show video filename and timestamp after navigation
  - Show visual indicator for cross-video navigation
  - Show "No results found" for empty results
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 10. Implement form state preservation
  - Preserve artifact type during navigation
  - Preserve label/query during navigation
  - Preserve confidence during navigation
  - Accept initial state props for page transitions
  - _Requirements: 4.1.1, 4.1.2, 4.1.3, 4.1.4_

- [x] 11. Apply component styling
  - Use dark theme colors (#1a1a1a, #2a2a2a, #333)
  - Match existing JumpNavigationControl layout
  - Use 12px font sizes, 8px gaps, 16px padding
  - _Requirements: 9.1, 9.2, 9.3, 9.4_

### Frontend: Search Page

- [x] 12. Create Search page component
  - Create `frontend/src/pages/SearchPage.tsx`
  - Render GlobalJumpControl without video context
  - Fetch earliest video ID for starting point
  - _Requirements: 1.1.1, 1.1.2, 1.1.3_

- [x] 13. Implement search page navigation
  - Handle onNavigate callback from GlobalJumpControl
  - Navigate to player page with video_id and timestamp
  - Pass form state to player page via location state
  - _Requirements: 1.1.4, 1.1.5_

- [x] 14. Add search page route
  - Add `/search` route to app router
  - Link to search page from navigation/header
  - _Requirements: 1.1.1_

### Frontend: Player Page Integration

- [x] 15. Replace JumpNavigationControl with GlobalJumpControl
  - Remove JumpNavigationControl import
  - Add GlobalJumpControl with videoId and videoRef props
  - Implement onVideoChange handler to load new videos
  - _Requirements: 1.5, 1.6, 1.2.1, 1.2.2, 1.2.3_

- [x] 16. Handle form state from search page
  - Read initial state from location.state
  - Pass to GlobalJumpControl as initial props
  - _Requirements: 1.2.2_

### Backend: Video Clip Export (Nice to Have)

- [x] 17. Create clip export endpoint
  - Add `GET /api/v1/videos/{video_id}/clip` endpoint
  - Accept start_ms, end_ms, buffer_ms parameters
  - Validate video exists and timestamp range
  - _Requirements: 11.4_

- [x] 18. Implement ffmpeg clip extraction
  - Build ffmpeg command with stream copy
  - Use fragmented MP4 for streaming output
  - Stream output directly to response
  - Generate descriptive filename
  - _Requirements: 11.5, 11.6, 11.7, 11.9_

- [ ]* 19. Add export clip button to GlobalJumpControl
  - Show button when lastResult is set
  - Implement download handler
  - Show loading state during export
  - _Requirements: 11.1, 11.2, 11.3, 11.8_

### Testing

- [x] 20. Write GlobalJumpControl unit tests
  - Test component renders without video (search page mode)
  - Test component renders with video (player mode)
  - Test artifact type dropdown options
  - Test input field visibility per artifact type
  - Test confidence slider visibility
  - _Requirements: All frontend requirements_

- [x] 21. Write integration tests
  - Test search page to player page flow
  - Test cross-video navigation
  - Test form state preservation
  - _Requirements: 1.1, 1.2, 4.1_

### Checkpoints

- [x] 22. Checkpoint: Backend location search works
  - Run backend tests for location text search
  - Manually test with curl/API client
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 23. Checkpoint: GlobalJumpControl works in player
  - Test all artifact types
  - Test cross-video navigation
  - Test same-video navigation
  - _Requirements: 1, 2, 3, 4, 5, 6, 8_

- [x] 24. Checkpoint: Search page works
  - Test search from search page
  - Test navigation to player
  - Test form state preservation
  - _Requirements: 1.1, 1.2_

- [x] 25. Final checkpoint: All tests pass
  - Run frontend tests
  - Run backend tests
  - Run lint checks
  - _Requirements: All_

## Notes

- Tasks marked with `*` are nice-to-have and can be skipped for MVP
- Backend tasks (1-3) can be done in parallel with frontend tasks (4-16)
- Search page (12-14) depends on GlobalJumpControl (4-11)
- Player integration (15-16) depends on GlobalJumpControl (4-11)
