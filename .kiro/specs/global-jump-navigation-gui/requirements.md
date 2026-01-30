# Requirements Document

## Introduction

This document specifies the requirements for the Global Jump Navigation GUI feature. The feature replaces the existing single-video JumpNavigationControl component with a new component that leverages the global jump API (`GET /api/v1/jump/global`) to enable cross-video artifact search and navigation. Additionally, it extends the backend location search to support text-based queries on city, state, and country fields.

## Glossary

- **Global_Jump_Control**: The React component that provides the user interface for cross-video artifact navigation
- **Artifact_Type**: A category of searchable content including object, face, transcript, ocr, scene, place, and location
- **Global_Timeline**: The chronological ordering of videos based on file_created_at, video_id, and start_ms
- **Cross_Video_Navigation**: The ability to navigate to search results that exist in different videos than the currently playing video
- **Location_Text_Search**: Text-based search capability for location fields (city, state, country) using case-insensitive partial matching

## Requirements

### Requirement 1: Replace Single-Video Jump with Global Jump

**User Story:** As a user, I want to search for artifacts across all my videos, so that I can find content regardless of which video it appears in.

#### Acceptance Criteria

1. WHEN the Global_Jump_Control is rendered, THE Global_Jump_Control SHALL use the global jump API (`/api/v1/jump/global`) instead of the single-video jump API
2. WHEN a search result is in a different video than the currently playing video, THE Global_Jump_Control SHALL trigger a video change callback to load the new video
3. WHEN navigating to a result in the same video, THE Global_Jump_Control SHALL seek to the result timestamp without changing videos
4. THE Global_Jump_Control SHALL support all artifact types: object, face, transcript, ocr, scene, place, and location
5. THE Global_Jump_Control SHALL replace the existing JumpNavigationControl component in the player page
6. THE Global_Jump_Control SHALL be embedded in the existing player page layout, positioned below the video player

### Requirement 1.1: Standalone Search Page

**User Story:** As a user, I want to search my video library from a dedicated search page, so that I can discover content without first selecting a video.

#### Acceptance Criteria

1. THE application SHALL provide a dedicated search page at `/search` route
2. THE search page SHALL display the Global_Jump_Control form without requiring a video to be loaded first
3. WHEN no video is currently loaded and the user initiates a search, THE Global_Jump_Control SHALL search from the beginning of the global timeline (earliest video)
4. WHEN a search result is found from the search page, THE application SHALL navigate to the player page with the result video loaded at the correct timestamp
5. THE search page SHALL preserve form state when navigating to the player page
6. THE search page MAY display a preview of the search result before navigating to the player

### Requirement 1.2: Persistent Navigation Control

**User Story:** As a user, I want the Global Jump Control to remain visible after navigating to a video, so that I can continue searching and navigating through results.

#### Acceptance Criteria

1. WHEN the user navigates from the search page to the player page, THE Global_Jump_Control SHALL remain visible below the video player
2. THE Global_Jump_Control on the player page SHALL retain the same form state (artifact type, label/query, confidence) from the search page
3. THE user SHALL be able to continue using Previous/Next navigation from the player page
4. THE Global_Jump_Control SHALL function identically whether accessed from the search page or the player page

### Requirement 2: Artifact Type Selection

**User Story:** As a user, I want to select which type of artifact to search for, so that I can focus my search on specific content types.

#### Acceptance Criteria

1. THE Global_Jump_Control SHALL display a dropdown selector for artifact types
2. THE Global_Jump_Control SHALL include options for: object, face, transcript, ocr, scene, place, and location
3. WHEN the user selects an artifact type, THE Global_Jump_Control SHALL update the search interface to show relevant input fields for that type
4. WHEN the artifact type is object or place, THE Global_Jump_Control SHALL display a label input field
5. WHEN the artifact type is transcript, ocr, or location, THE Global_Jump_Control SHALL display a query input field
6. WHEN the artifact type is face, THE Global_Jump_Control SHALL display a face cluster selector
7. WHEN the artifact type is scene, THE Global_Jump_Control SHALL hide text input fields since scenes require no filter

### Requirement 2.1: Available Options Aggregation (Nice to Have)

**User Story:** As a user, I want to see what labels and options are available across my video library, so that I can quickly select from existing values.

#### Acceptance Criteria

1. WHEN the artifact type is object, THE Global_Jump_Control SHOULD fetch and display available object labels as selectable chips
2. WHEN the artifact type is place, THE Global_Jump_Control SHOULD fetch and display available place labels as selectable chips
3. WHEN the artifact type is face, THE Global_Jump_Control SHOULD fetch and display available face clusters as selectable chips
4. THE available options chips SHALL show the count of occurrences for each option
5. WHEN the user clicks an option chip, THE Global_Jump_Control SHALL use that value for the search filter
6. THE Global_Jump_Control SHALL NOT aggregate options for transcript, ocr, scene, or location types (free-text or no filter needed)

### Requirement 3: Confidence Threshold Control

**User Story:** As a user, I want to filter results by confidence level, so that I can focus on high-confidence detections.

#### Acceptance Criteria

1. WHEN the artifact type is object, face, or place, THE Global_Jump_Control SHALL display a confidence threshold slider
2. THE confidence slider SHALL allow values from 0 to 1 in increments of 0.1
3. THE Global_Jump_Control SHALL display the current confidence value as a percentage
4. WHEN the artifact type is transcript, ocr, scene, or location, THE Global_Jump_Control SHALL hide the confidence slider
5. WHEN min_confidence is set above 0, THE Global_Jump_Control SHALL include the min_confidence parameter in API requests

### Requirement 4: Navigation Controls

**User Story:** As a user, I want to navigate forward and backward through search results, so that I can browse all matching artifacts.

#### Acceptance Criteria

1. THE Global_Jump_Control SHALL display Previous and Next navigation buttons
2. WHEN the user clicks Next, THE Global_Jump_Control SHALL request the next result in global timeline order
3. WHEN the user clicks Previous, THE Global_Jump_Control SHALL request the previous result in global timeline order
4. WHILE a navigation request is in progress, THE Global_Jump_Control SHALL disable the navigation buttons
5. WHILE a navigation request is in progress, THE Global_Jump_Control SHALL display a loading indicator

### Requirement 4.1: Form State Preservation

**User Story:** As a user, I want my search settings to persist while navigating through results, so that I don't have to re-enter my search criteria.

#### Acceptance Criteria

1. WHEN navigating between results, THE Global_Jump_Control SHALL preserve the selected artifact type
2. WHEN navigating between results, THE Global_Jump_Control SHALL preserve the label or query input value
3. WHEN navigating between results, THE Global_Jump_Control SHALL preserve the confidence threshold setting
4. WHEN navigating to a different video, THE Global_Jump_Control SHALL preserve all form state after the video change completes

### Requirement 5: Current Match Display

**User Story:** As a user, I want to see information about the current search result, so that I know where I am in the video library.

#### Acceptance Criteria

1. THE Global_Jump_Control SHALL display the current match information after navigation
2. THE current match display SHALL include the video filename
3. THE current match display SHALL include the timestamp in MM:SS format
4. WHEN the navigation result is in a different video than the previous position, THE Global_Jump_Control SHALL display a visual indicator showing cross-video navigation occurred
5. WHEN no results are found, THE Global_Jump_Control SHALL display a "No results found" message

### Requirement 6: Cross-Video Navigation Callback

**User Story:** As a developer integrating the component, I want a callback when navigation requires changing videos, so that I can update the video player accordingly.

#### Acceptance Criteria

1. THE Global_Jump_Control SHALL accept an `onVideoChange` callback prop
2. WHEN a navigation result is in a different video, THE Global_Jump_Control SHALL call `onVideoChange` with the new video_id and target timestamp
3. THE Global_Jump_Control SHALL wait for the video change to complete before seeking to the timestamp
4. IF the `onVideoChange` callback is not provided, THE Global_Jump_Control SHALL log a warning when cross-video navigation is attempted

### Requirement 7: Location Text Search Backend Enhancement

**User Story:** As a user, I want to search for videos by location name, so that I can find videos taken in specific cities, states, or countries.

#### Acceptance Criteria

1. WHEN kind is location and a query parameter is provided, THE Global_Jump_Service SHALL search across country, state, and city fields
2. THE location text search SHALL use case-insensitive partial matching (ILIKE in PostgreSQL)
3. THE location text search SHALL match if the query appears in any of: country, state, or city
4. WHEN both query and geo_bounds are provided for location search, THE Global_Jump_Service SHALL apply both filters (AND logic)
5. WHEN only geo_bounds is provided for location search, THE Global_Jump_Service SHALL filter by geographic bounds only (existing behavior)

### Requirement 8: API Integration

**User Story:** As a developer, I want the component to correctly integrate with the global jump API, so that searches work reliably.

#### Acceptance Criteria

1. THE Global_Jump_Control SHALL construct API requests with the correct query parameters based on artifact type
2. FOR object and place searches, THE Global_Jump_Control SHALL include the `label` parameter
3. FOR transcript and ocr searches, THE Global_Jump_Control SHALL include the `query` parameter
4. FOR location searches with text input, THE Global_Jump_Control SHALL include the `query` parameter
5. FOR face searches, THE Global_Jump_Control SHALL include the `face_cluster_id` parameter
6. THE Global_Jump_Control SHALL include `min_confidence` when the confidence slider is set above 0
7. THE Global_Jump_Control SHALL handle API errors gracefully and display error messages to the user

### Requirement 9: Component Styling

**User Story:** As a user, I want the component to match the existing application style, so that the interface feels consistent.

#### Acceptance Criteria

1. THE Global_Jump_Control SHALL use inline styles matching the existing JumpNavigationControl pattern
2. THE Global_Jump_Control SHALL use the dark theme color scheme (#1a1a1a background, #2a2a2a inputs, #333 borders)
3. THE Global_Jump_Control SHALL use consistent font sizes (12px for labels and inputs)
4. THE Global_Jump_Control SHALL use consistent spacing (8px gaps, 16px padding)


### Requirement 10: Searchable Gallery (Nice to Have - Future)

**User Story:** As a user, I want to search and filter the video gallery by artifacts, so that I can browse videos containing specific content.

#### Acceptance Criteria

1. THE home page gallery SHOULD support filtering videos by artifact type and search criteria
2. WHEN a user searches in the gallery, THE gallery SHOULD display videos that contain matching artifacts
3. THE gallery search SHOULD show thumbnail previews of matching moments within each video
4. THE gallery search SHOULD allow clicking a result to navigate directly to that moment in the player
5. THE gallery search SHOULD integrate with the same Global Jump API for consistency

### Requirement 11: Video Clip Export (Nice to Have)

**User Story:** As a user, I want to export a clip from a search result, so that I can save and share specific moments from my videos.

#### Acceptance Criteria

1. THE Global_Jump_Control SHOULD display an "Export Clip" button when a search result is displayed
2. WHEN the user clicks "Export Clip", THE application SHOULD download a video clip containing the current search result
3. THE exported clip SHOULD include a configurable buffer time before and after the artifact timestamp (default 2 seconds)
4. THE backend SHALL provide a `GET /api/v1/videos/{video_id}/clip` endpoint that accepts `start_ms` and `end_ms` parameters
5. THE clip export endpoint SHALL use ffmpeg to extract the video segment
6. THE clip export endpoint SHALL stream the video file directly to the client for download
7. THE exported clip filename SHOULD include the video name and timestamp range
8. THE Global_Jump_Control SHOULD display a loading indicator while the clip is being generated
9. THE clip export SHOULD use stream copy (`-c copy`) for fast extraction when possible
