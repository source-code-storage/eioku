#!/bin/bash

# Script to create GitHub milestones and issues for Eioku project
# Prerequisites: GitHub CLI (gh) must be installed and authenticated
# Usage: ./scripts/create-github-issues.sh

set -e

echo "Creating GitHub Milestones and Issues for Eioku..."
echo ""

# Check if gh is installed
if ! command -v gh &> /dev/null; then
    echo "Error: GitHub CLI (gh) is not installed."
    echo "Install it from: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo "Error: Not authenticated with GitHub CLI."
    echo "Run: gh auth login"
    exit 1
fi

echo "✓ GitHub CLI is installed and authenticated"
echo ""

# Create Milestones using GitHub API
echo "Creating Milestones..."

# Get repository info
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

gh api repos/$REPO/milestones \
    -f title="Phase 1: Foundation" \
    -f description="Project setup, database schema, and core data access layer" \
    -f due_on="2026-01-31T23:59:59Z" \
    -f state="open" > /dev/null

gh api repos/$REPO/milestones \
    -f title="Phase 2: Video Processing" \
    -f description="Transcription, scene detection, object/face detection, and topic extraction" \
    -f due_on="2026-02-28T23:59:59Z" \
    -f state="open" > /dev/null

gh api repos/$REPO/milestones \
    -f title="Phase 3: Search & API" \
    -f description="Semantic search with FAISS, error handling, and backend API" \
    -f due_on="2026-03-31T23:59:59Z" \
    -f state="open" > /dev/null

gh api repos/$REPO/milestones \
    -f title="Phase 4: Frontend" \
    -f description="Electron application, library view, search interface, and player view" \
    -f due_on="2026-04-30T23:59:59Z" \
    -f state="open" > /dev/null

gh api repos/$REPO/milestones \
    -f title="Phase 5: Polish & Release" \
    -f description="Data persistence, library management, UI polish, and packaging" \
    -f due_on="2026-05-31T23:59:59Z" \
    -f state="open" > /dev/null

echo "✓ Milestones created"
echo ""

# Create Labels
echo "Creating labels..."

gh api repos/$REPO/labels -f name="setup" -f color="0e8a16" -f description="Project setup and configuration" > /dev/null 2>&1 || true
gh api repos/$REPO/labels -f name="infrastructure" -f color="0e8a16" -f description="Infrastructure and DevOps" > /dev/null 2>&1 || true
gh api repos/$REPO/labels -f name="database" -f color="d4c5f9" -f description="Database related tasks" > /dev/null 2>&1 || true
gh api repos/$REPO/labels -f name="backend" -f color="d4c5f9" -f description="Backend development" > /dev/null 2>&1 || true
gh api repos/$REPO/labels -f name="frontend" -f color="5319e7" -f description="Frontend development" > /dev/null 2>&1 || true
gh api repos/$REPO/labels -f name="ui" -f color="5319e7" -f description="User interface" > /dev/null 2>&1 || true
gh api repos/$REPO/labels -f name="ml" -f color="fbca04" -f description="Machine learning and AI" > /dev/null 2>&1 || true
gh api repos/$REPO/labels -f name="video-processing" -f color="fbca04" -f description="Video processing tasks" > /dev/null 2>&1 || true
gh api repos/$REPO/labels -f name="search" -f color="c5def5" -f description="Search functionality" > /dev/null 2>&1 || true
gh api repos/$REPO/labels -f name="api" -f color="c5def5" -f description="API development" > /dev/null 2>&1 || true
gh api repos/$REPO/labels -f name="architecture" -f color="d93f0b" -f description="Architecture and design" > /dev/null 2>&1 || true
gh api repos/$REPO/labels -f name="error-handling" -f color="d93f0b" -f description="Error handling and recovery" > /dev/null 2>&1 || true
gh api repos/$REPO/labels -f name="checkpoint" -f color="0052cc" -f description="Checkpoint and review" > /dev/null 2>&1 || true
gh api repos/$REPO/labels -f name="release" -f color="0052cc" -f description="Release preparation" > /dev/null 2>&1 || true
gh api repos/$REPO/labels -f name="video-player" -f color="5319e7" -f description="Video player functionality" > /dev/null 2>&1 || true

echo "✓ Labels created"
echo ""

# Create Issues for Phase 1: Foundation
echo "Creating Phase 1 issues..."

gh issue create \
    --title "Task 1: Set up project structure and development environment" \
    --body "**Milestone**: Phase 1: Foundation

**Description**:
- Create Python backend project with poetry or pip-tools
- Create Electron + React + TypeScript frontend project
- Configure development tools (linting, formatting, type checking)
- Set up testing framework (pytest, jest)
- Create Dockerfile for backend
- Set up GitHub Actions for CI/CD (build, test, Docker image)

**Requirements**: 1.1, 1.2, 1.3, 7.1, 7.2

**Acceptance Criteria**:
- [ ] Python project structure created with dependency management
- [ ] Electron + React + TypeScript project initialized
- [ ] Linting and formatting configured (ruff/pylint, black, prettier)
- [ ] Testing frameworks set up (pytest, jest)
- [ ] Dockerfile builds successfully
- [ ] GitHub Actions workflow runs on push" \
    --milestone "Phase 1: Foundation" \
    --label "setup,infrastructure"

gh issue create \
    --title "Task 2: Create database schema and migrations" \
    --body "**Milestone**: Phase 1: Foundation

**Description**:
Create SQLite database schema for all data models with proper indexes and foreign keys.

**Sub-tasks**:
- [ ] 2.1 Create Videos table schema
- [ ] 2.2 Create Transcriptions table schema
- [ ] 2.3 Create Scenes table schema
- [ ] 2.4 Create Objects table schema
- [ ] 2.5 Create Faces table schema
- [ ] 2.6 Create Topics table schema
- [ ] 2.7 Create PathConfigs table schema
- [ ] 2.8 Create Tasks table schema
- [ ] 2.9 Create database migration scripts

**Requirements**: 1.1, 1.4, 1.5, 4.1, 4.4, 7.1, 9.1, 9.2, 10.4, 10.6, 10.7, 10.9, 10.10

**Acceptance Criteria**:
- [ ] All tables created with proper columns and types
- [ ] Foreign keys and indexes defined
- [ ] Migration scripts implement schema versioning
- [ ] Database can be initialized from scratch" \
    --milestone "Phase 1: Foundation" \
    --label "database,backend"

gh issue create \
    --title "Task 3: Implement database access layer" \
    --body "**Milestone**: Phase 1: Foundation

**Description**:
Create Data Access Objects (DAOs) for all database tables with CRUD operations.

**Sub-tasks**:
- [ ] 3.1 Create Video DAO
- [ ] 3.2 Create Transcription DAO
- [ ] 3.3 Create Scene DAO
- [ ] 3.4 Create Object DAO
- [ ] 3.5 Create Face DAO
- [ ] 3.6 Create Topic DAO
- [ ] 3.7 Create PathConfig DAO
- [ ] 3.8 Create Task DAO
- [ ] 3.9 Implement database connection management
- [ ] 3.10 Write unit tests for all DAOs (optional)

**Requirements**: 1.1, 1.4, 1.5, 4.1, 4.2, 4.3, 4.7, 6.2, 6.5, 9.1, 9.2, 9.3, 10.4, 10.6, 10.7, 10.9, 10.10

**Acceptance Criteria**:
- [ ] All DAOs implement CRUD operations
- [ ] Query methods implemented for common use cases
- [ ] Connection pooling and transaction management working
- [ ] Unit tests pass (if implemented)" \
    --milestone "Phase 1: Foundation" \
    --label "database,backend"

gh issue create \
    --title "Task 4: Implement path management and video discovery" \
    --body "**Milestone**: Phase 1: Foundation

**Description**:
Implement path configuration management and video file discovery.

**Sub-tasks**:
- [ ] 4.1 Create path configuration manager
- [ ] 4.2 Implement video file discovery
- [ ] 4.3 Implement file validation and missing file detection
- [ ] 4.4 Write property test for path discovery (optional)
- [ ] 4.5 Write property test for individual file processing (optional)

**Requirements**: 1.1, 1.2, 1.3, 1.8, 4.3, 4.5, 4.7

**Acceptance Criteria**:
- [ ] Can add/remove folder and file paths
- [ ] Recursive folder scanning works
- [ ] Supports MP4, MOV, AVI, MKV formats
- [ ] Detects duplicate videos
- [ ] Validates file existence" \
    --milestone "Phase 1: Foundation" \
    --label "backend,video-processing"

gh issue create \
    --title "Task 5: Implement task orchestration system" \
    --body "**Milestone**: Phase 1: Foundation

**Description**:
Create parallel task orchestration system with worker pools and processing profiles.

**Sub-tasks**:
- [ ] 5.1 Create task data models and queue structures
- [ ] 5.2 Implement task orchestrator
- [ ] 5.3 Implement worker pool management
- [ ] 5.4 Implement processing profile configuration
- [ ] 5.5 Write unit tests for task orchestration (optional)

**Requirements**: 1.4, 1.5, 1.6, 1.7, 6.2, 6.5

**Acceptance Criteria**:
- [ ] Tasks can be created and queued
- [ ] Dependencies managed correctly
- [ ] Worker pools execute tasks in parallel
- [ ] Processing profiles load and apply correctly
- [ ] Task completion triggers dependent tasks" \
    --milestone "Phase 1: Foundation" \
    --label "backend,architecture"

gh issue create \
    --title "Checkpoint: Phase 1 - Ensure all tests pass" \
    --body "**Milestone**: Phase 1: Foundation

**Description**:
Verify that all Phase 1 tasks are complete and tests pass.

**Checklist**:
- [ ] All Phase 1 tasks completed
- [ ] All unit tests passing
- [ ] Database schema validated
- [ ] DAOs working correctly
- [ ] Path management functional
- [ ] Task orchestration working

**Action**: Review with team and address any issues before proceeding to Phase 2." \
    --milestone "Phase 1: Foundation" \
    --label "checkpoint"

echo "✓ Phase 1 issues created"
echo ""

# Create Issues for Phase 2: Video Processing
echo "Creating Phase 2 issues..."

gh issue create \
    --title "Task 7: Implement video transcription pipeline" \
    --body "**Milestone**: Phase 2: Video Processing

**Description**:
Implement audio extraction and Whisper transcription with GPU acceleration.

**Sub-tasks**:
- [ ] 7.1 Implement audio extraction from video
- [ ] 7.2 Implement Whisper transcription
- [ ] 7.3 Store transcription segments in database
- [ ] 7.4 Write property test for transcription generation (optional)
- [ ] 7.5 Write property test for confidence flagging (optional)

**Requirements**: 1.4, 1.5, 5.1, 5.3, 5.5, 6.6

**Acceptance Criteria**:
- [ ] FFmpeg extracts audio successfully
- [ ] Whisper transcribes with timestamps
- [ ] GPU acceleration works when available
- [ ] Multi-speaker audio handled
- [ ] Segments stored with confidence scores" \
    --milestone "Phase 2: Video Processing" \
    --label "backend,ml,video-processing"

gh issue create \
    --title "Task 8: Implement scene detection pipeline" \
    --body "**Milestone**: Phase 2: Video Processing

**Description**:
Implement PySceneDetect integration and thumbnail generation.

**Sub-tasks**:
- [ ] 8.1 Implement PySceneDetect integration
- [ ] 8.2 Generate scene thumbnails
- [ ] 8.3 Store scene boundaries in database
- [ ] 8.4 Write property test for scene detection (optional)

**Requirements**: 3.1, 3.2, 10.4

**Acceptance Criteria**:
- [ ] Scene boundaries detected accurately
- [ ] Thumbnails generated for each scene
- [ ] Timecodes converted to seconds
- [ ] Scene data stored in database" \
    --milestone "Phase 2: Video Processing" \
    --label "backend,ml,video-processing"

gh issue create \
    --title "Task 9: Implement object detection pipeline" \
    --body "**Milestone**: Phase 2: Video Processing

**Description**:
Implement YOLOv8 object detection with GPU acceleration.

**Sub-tasks**:
- [ ] 9.1 Implement YOLOv8 object detection
- [ ] 9.2 Aggregate and store object detections
- [ ] 9.3 Write unit tests for object detection (optional)

**Requirements**: 6.6, 10.6, 10.7

**Acceptance Criteria**:
- [ ] YOLOv8 model loads successfully
- [ ] Frame sampling at configured interval
- [ ] GPU acceleration works when available
- [ ] Objects grouped by label
- [ ] Timestamps and bounding boxes stored" \
    --milestone "Phase 2: Video Processing" \
    --label "backend,ml,video-processing"

gh issue create \
    --title "Task 10: Implement face detection pipeline" \
    --body "**Milestone**: Phase 2: Video Processing

**Description**:
Implement YOLOv8 face detection with GPU acceleration.

**Sub-tasks**:
- [ ] 10.1 Implement YOLOv8 face detection
- [ ] 10.2 Store face detections in database
- [ ] 10.3 Write unit tests for face detection (optional)

**Requirements**: 6.6, 10.9, 10.10

**Acceptance Criteria**:
- [ ] YOLOv8 face model loads successfully
- [ ] Frame sampling by time interval
- [ ] GPU acceleration works when available
- [ ] Face data stored with timestamps and bounding boxes" \
    --milestone "Phase 2: Video Processing" \
    --label "backend,ml,video-processing"

gh issue create \
    --title "Checkpoint: Phase 2 Part 1 - Ensure all tests pass" \
    --body "**Milestone**: Phase 2: Video Processing

**Description**:
Verify that video processing tasks are complete and tests pass.

**Checklist**:
- [ ] Transcription pipeline working
- [ ] Scene detection working
- [ ] Object detection working
- [ ] Face detection working
- [ ] All tests passing
- [ ] GPU acceleration verified

**Action**: Review and address any issues before proceeding to topic extraction." \
    --milestone "Phase 2: Video Processing" \
    --label "checkpoint"

gh issue create \
    --title "Task 12: Implement topic extraction" \
    --body "**Milestone**: Phase 2: Video Processing

**Description**:
Implement topic extraction from transcriptions using KeyBERT or BERTopic.

**Sub-tasks**:
- [ ] 12.1 Implement topic extraction from transcriptions
- [ ] 12.2 Store topics in database
- [ ] 12.3 Implement topic aggregation across videos
- [ ] 12.4 Write property test for topic extraction (optional)
- [ ] 12.5 Write property test for topic aggregation (optional)

**Requirements**: 9.1, 9.2, 9.3, 9.5

**Acceptance Criteria**:
- [ ] Topics extracted from transcriptions
- [ ] Topics ranked by relevance and frequency
- [ ] Topics stored with keywords and scores
- [ ] Aggregation across videos works" \
    --milestone "Phase 2: Video Processing" \
    --label "backend,ml"

echo "✓ Phase 2 issues created"
echo ""

# Create Issues for Phase 3: Search & API
echo "Creating Phase 3 issues..."

gh issue create \
    --title "Task 13: Implement semantic search with FAISS" \
    --body "**Milestone**: Phase 3: Search & API

**Description**:
Implement embedding generation and FAISS vector search.

**Sub-tasks**:
- [ ] 13.1 Implement embedding generation
- [ ] 13.2 Implement FAISS vector store
- [ ] 13.3 Implement semantic search engine
- [ ] 13.4 Implement search result formatting
- [ ] 13.5 Write property test for search result relevance (optional)
- [ ] 13.6 Write property test for synonym understanding (optional)
- [ ] 13.7 Write property test for timestamp accuracy (optional)

**Requirements**: 2.1, 2.2, 2.3, 3.1, 3.2, 3.5, 7.1, 7.2

**Acceptance Criteria**:
- [ ] Embeddings generated with sentence-transformers
- [ ] FAISS index created and persisted
- [ ] Search returns relevant results
- [ ] Results ranked by relevance
- [ ] Filters work (video, date range)" \
    --milestone "Phase 3: Search & API" \
    --label "backend,ml,search"

gh issue create \
    --title "Task 14: Implement error handling and recovery" \
    --body "**Milestone**: Phase 3: Search & API

**Description**:
Implement comprehensive error handling and recovery mechanisms.

**Sub-tasks**:
- [ ] 14.1 Implement error handling for video processing
- [ ] 14.2 Implement data corruption detection and recovery
- [ ] 14.3 Implement disk space monitoring
- [ ] 14.4 Write property test for error isolation (optional)

**Requirements**: 1.7, 7.4, 7.5, 8.3

**Acceptance Criteria**:
- [ ] Processing errors caught and logged
- [ ] Videos marked with error status
- [ ] Other videos continue processing
- [ ] Database integrity validated on startup
- [ ] Disk space warnings issued" \
    --milestone "Phase 3: Search & API" \
    --label "backend,error-handling"

gh issue create \
    --title "Checkpoint: Phase 3 Part 1 - Ensure all tests pass" \
    --body "**Milestone**: Phase 3: Search & API

**Description**:
Verify that search and error handling are complete.

**Checklist**:
- [ ] Semantic search working
- [ ] FAISS index persists correctly
- [ ] Error handling functional
- [ ] All tests passing

**Action**: Review before proceeding to API implementation." \
    --milestone "Phase 3: Search & API" \
    --label "checkpoint"

gh issue create \
    --title "Task 16: Implement backend API layer" \
    --body "**Milestone**: Phase 3: Search & API

**Description**:
Create FastAPI application with all endpoints.

**Sub-tasks**:
- [ ] 16.1 Create FastAPI application
- [ ] 16.2 Implement library management endpoints
- [ ] 16.3 Implement search endpoints
- [ ] 16.4 Implement player endpoints
- [ ] 16.5 Implement processing status endpoints
- [ ] 16.6 Write integration tests for API endpoints (optional)

**Requirements**: 1.6, 2.1, 2.4, 4.1, 4.2, 4.7, 6.5, 8.1, 8.2, 8.3, 9.3, 10.2, 10.5, 10.6, 10.9

**Acceptance Criteria**:
- [ ] FastAPI app runs with CORS
- [ ] All endpoints implemented
- [ ] Request/response models defined
- [ ] API documentation generated
- [ ] Integration tests pass (if implemented)" \
    --milestone "Phase 3: Search & API" \
    --label "backend,api"

echo "✓ Phase 3 issues created"
echo ""

# Create Issues for Phase 4: Frontend
echo "Creating Phase 4 issues..."

gh issue create \
    --title "Task 17: Implement Electron frontend application" \
    --body "**Milestone**: Phase 4: Frontend

**Description**:
Create Electron + React + TypeScript application with core views.

**Sub-tasks**:
- [ ] 17.1 Set up Electron + React + TypeScript project
- [ ] 17.2 Implement library view
- [ ] 17.3 Implement path configuration dialog
- [ ] 17.4 Implement search interface
- [ ] 17.5 Implement result gallery
- [ ] 17.6 Implement processing status view
- [ ] 17.7 Write UI component tests (optional)

**Requirements**: 1.1, 1.2, 1.6, 2.1, 2.4, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.7, 6.5, 8.1, 8.2, 8.4, 9.2, 9.4

**Acceptance Criteria**:
- [ ] Electron app launches successfully
- [ ] IPC communication working
- [ ] Library view displays videos
- [ ] Search interface functional
- [ ] Result gallery displays results
- [ ] Processing status updates in real-time" \
    --milestone "Phase 4: Frontend" \
    --label "frontend,ui"

gh issue create \
    --title "Task 18: Implement player view" \
    --body "**Milestone**: Phase 4: Frontend

**Description**:
Create interactive video player with advanced navigation.

**Sub-tasks**:
- [ ] 18.1 Implement video player component
- [ ] 18.2 Implement transcript panel
- [ ] 18.3 Implement scene navigation
- [ ] 18.4 Implement object navigation
- [ ] 18.5 Implement face navigation
- [ ] 18.6 Implement timeline markers
- [ ] 18.7-18.11 Write property tests for navigation (optional)

**Requirements**: 10.1, 10.2, 10.3, 10.5, 10.6, 10.7, 10.8, 10.9, 10.10, 10.11

**Acceptance Criteria**:
- [ ] Video plays from file path
- [ ] Transcript syncs with playback
- [ ] Clicking transcript jumps to timestamp
- [ ] Scene navigation works
- [ ] Object navigation works
- [ ] Face navigation works
- [ ] Timeline markers visible and clickable" \
    --milestone "Phase 4: Frontend" \
    --label "frontend,ui,video-player"

gh issue create \
    --title "Checkpoint: Phase 4 - Ensure all tests pass" \
    --body "**Milestone**: Phase 4: Frontend

**Description**:
Verify that frontend is complete and functional.

**Checklist**:
- [ ] All views implemented
- [ ] Player view fully functional
- [ ] Navigation features working
- [ ] UI tests passing (if implemented)
- [ ] End-to-end flow tested

**Action**: Review and address any UI/UX issues." \
    --milestone "Phase 4: Frontend" \
    --label "checkpoint"

echo "✓ Phase 4 issues created"
echo ""

# Create Issues for Phase 5: Polish & Release
echo "Creating Phase 5 issues..."

gh issue create \
    --title "Task 20: Implement data persistence and recovery" \
    --body "**Milestone**: Phase 5: Polish & Release

**Description**:
Implement application state persistence and startup recovery.

**Sub-tasks**:
- [ ] 20.1 Implement application state persistence
- [ ] 20.2 Implement graceful shutdown
- [ ] 20.3 Implement startup recovery
- [ ] 20.4 Write property test for data persistence round-trip (optional)

**Requirements**: 4.5, 7.1, 7.2

**Acceptance Criteria**:
- [ ] Window size/position saved
- [ ] Processing profile saved
- [ ] UI preferences saved
- [ ] Graceful shutdown works
- [ ] Startup recovery works" \
    --milestone "Phase 5: Polish & Release" \
    --label "backend,frontend"

gh issue create \
    --title "Task 21: Implement library management operations" \
    --body "**Milestone**: Phase 5: Polish & Release

**Description**:
Implement video removal, duplicate detection, and incremental updates.

**Sub-tasks**:
- [ ] 21.1 Implement video removal
- [ ] 21.2 Implement duplicate detection
- [ ] 21.3 Implement incremental path updates
- [ ] 21.4 Write property test for deletion safety (optional)
- [ ] 21.5 Write property test for duplicate detection (optional)

**Requirements**: 4.2, 4.3, 4.6

**Acceptance Criteria**:
- [ ] Video removal cleans up all data
- [ ] Original files preserved
- [ ] Duplicates detected and prevented
- [ ] Incremental updates detect new/modified videos" \
    --milestone "Phase 5: Polish & Release" \
    --label "backend"

gh issue create \
    --title "Task 22: Implement UI interactions and feedback" \
    --body "**Milestone**: Phase 5: Polish & Release

**Description**:
Implement UI interactions and visual feedback.

**Sub-tasks**:
- [ ] 22.1 Implement search result navigation
- [ ] 22.2 Implement topic search trigger
- [ ] 22.3 Implement visual feedback for actions
- [ ] 22.4 Implement error message display
- [ ] 22.5-22.6 Write property tests (optional)

**Requirements**: 3.4, 8.2, 8.3, 9.4

**Acceptance Criteria**:
- [ ] Clicking results opens player
- [ ] Clicking topics triggers search
- [ ] Loading spinners shown
- [ ] Progress bars update
- [ ] Error messages user-friendly" \
    --milestone "Phase 5: Polish & Release" \
    --label "frontend,ui"

gh issue create \
    --title "Task 23: Implement keyboard shortcuts" \
    --body "**Milestone**: Phase 5: Polish & Release

**Description**:
Implement keyboard shortcuts for common actions.

**Sub-tasks**:
- [ ] 23.1 Define keyboard shortcuts
- [ ] 23.2 Implement shortcut handlers
- [ ] 23.3 Write unit tests for keyboard shortcuts (optional)

**Requirements**: 8.5

**Acceptance Criteria**:
- [ ] Cmd/Ctrl + F opens search
- [ ] Space plays/pauses video
- [ ] Cmd/Ctrl + Arrow navigates scenes
- [ ] Shortcuts documented" \
    --milestone "Phase 5: Polish & Release" \
    --label "frontend,ui"

gh issue create \
    --title "Task 24: Implement packaging and distribution" \
    --body "**Milestone**: Phase 5: Polish & Release

**Description**:
Configure electron-builder and create installers.

**Sub-tasks**:
- [ ] 24.1 Configure electron-builder
- [ ] 24.2 Create installers
- [ ] 24.3 Test installers on target platforms

**Requirements**: 8.1

**Acceptance Criteria**:
- [ ] Windows .exe builds
- [ ] macOS .dmg builds
- [ ] Linux .AppImage builds
- [ ] Installers tested on each platform
- [ ] App icons configured" \
    --milestone "Phase 5: Polish & Release" \
    --label "infrastructure,release"

gh issue create \
    --title "Final Checkpoint: Ensure all tests pass and release" \
    --body "**Milestone**: Phase 5: Polish & Release

**Description**:
Final verification before release.

**Checklist**:
- [ ] All tasks completed
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Installers working on all platforms
- [ ] Performance validated
- [ ] Security review complete
- [ ] User acceptance testing complete

**Action**: Prepare for v1.0 release!" \
    --milestone "Phase 5: Polish & Release" \
    --label "checkpoint,release"

echo "✓ Phase 5 issues created"
echo ""

echo "=========================================="
echo "✓ All milestones and issues created!"
echo "=========================================="
echo ""
echo "Summary:"
echo "- 5 Milestones created"
echo "- 15 Labels created"
echo "- 25 Issues created (matching tasks)"
echo "- 5 Checkpoint issues created"
echo ""
echo "Next steps:"
echo "1. Review milestones: gh issue list --milestone 'Phase 1: Foundation'"
echo "2. Review all issues: gh issue list"
echo "3. View labels: gh label list"
echo "4. Assign issues to team members"
echo "5. Start working on Phase 1!"
echo ""
