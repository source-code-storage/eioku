# Eioku - Semantic Video Search Platform

A powerful semantic video search platform designed for video editors with large content libraries. Eioku enables natural language search across video content with advanced navigation features including transcript-based navigation, scene jumping, and object/face detection.

## Overview

Eioku processes videos from configured file paths, extracts audio for transcription, performs computer vision analysis (scene detection, object detection, face detection), and enables semantic search through natural language queries. The platform provides an interactive player view with multiple navigation methods to help editors quickly find and navigate to specific content.

**Example Query**: "Show me clips where I talk about Kiro"
**Result**: Gallery of video segments with timestamps where the term appears

## Key Features

### 🔍 Semantic Search
- Natural language queries across video transcriptions
- Synonym and concept understanding
- Relevance-ranked results with timestamps
- Topic-based search suggestions

### 🎬 Advanced Video Navigation
- **Transcript Navigation**: Click any transcript text to jump to that moment
- **Scene Navigation**: Next/previous scene controls with automatic boundary detection
- **Object Navigation**: Jump between occurrences of detected objects
- **Face Navigation**: Navigate between appearances of detected faces
- **Timeline Markers**: Visual timeline with scene, object, and face markers

### 🚀 Parallel Processing
- Independent task processing for maximum efficiency
- GPU acceleration for object/face detection
- CPU parallelization for transcription and scene detection
- Configurable processing profiles (Balanced, Search First, Visual First, Low Resource)

### 📊 Topic Discovery
- Automatic topic extraction from video content
- Aggregated topics across entire library
- Clickable topic suggestions for quick search

### 💾 Zero-Ops Architecture
- No external servers or databases required
- File-based storage (SQLite + FAISS)
- Single-host deployment
- Desktop application (Electron)

## Technology Stack

### Backend
- **Language**: Python 3.10+
- **Framework**: FastAPI
- **Database**: SQLite
- **Vector Store**: FAISS
- **Task Queue**: Python multiprocessing

### Machine Learning
- **Transcription**: OpenAI Whisper (Large V3 or Turbo)
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2)
- **Scene Detection**: PySceneDetect
- **Object Detection**: Ultralytics YOLOv8
- **Face Detection**: YOLOv8 Face Model

### Frontend
- **Framework**: Electron + React + TypeScript
- **UI Library**: Material-UI or Tailwind CSS
- **Video Player**: HTML5 Video with custom controls

## Project Structure

```
.
├── .kiro/
│   └── specs/
│       └── semantic-video-search/
│           ├── requirements.md    # EARS-compliant requirements
│           ├── design.md          # Architecture and design
│           └── tasks.md           # Implementation tasks
├── DEVLOG.md                      # Development log
└── README.md                      # This file
```

## Getting Started

### Prerequisites

**Minimum Requirements:**
- CPU: 4 cores
- RAM: 8 GB
- Storage: 10 GB + video library size
- Python 3.10+
- Node.js 18+ (for Electron frontend)

**Recommended:**
- CPU: 8+ cores
- RAM: 16 GB
- GPU: NVIDIA GPU with 4+ GB VRAM (CUDA support)
- Storage: SSD with 50 GB + video library size

### Installation

*Coming soon - implementation in progress*

## Specification Documents

This project follows a spec-driven development approach with comprehensive documentation:

### 📋 Requirements Document
- 10 major requirements with 60+ acceptance criteria
- EARS-compliant format (Easy Approach to Requirements Syntax)
- INCOSE quality rules applied
- Complete glossary of terms

**Location**: `.kiro/specs/semantic-video-search/requirements.md`

### 🏗️ Design Document
- Parallel processing architecture with task orchestration
- Complete technology stack definition
- 4 processing profiles with worker configurations
- 7 comprehensive user flow diagrams
- 29 correctness properties with requirements traceability
- Component interfaces and data models
- Error handling and testing strategy

**Location**: `.kiro/specs/semantic-video-search/design.md`

### ✅ Implementation Tasks
- 25 major tasks with 100+ sub-tasks
- Granular breakdown of database schema and DAOs
- Property-based tests for correctness validation
- GitHub Actions and Docker integration
- Requirements traceability for every task

**Location**: `.kiro/specs/semantic-video-search/tasks.md`

## Development Approach

### Spec-Driven Development
1. **Requirements First**: Define what the system should do
2. **Design Second**: Define how the system will work
3. **Tasks Third**: Break down implementation into actionable steps
4. **Implementation**: Execute tasks with continuous validation

### Property-Based Testing
- Formal correctness properties derived from requirements
- Universal properties tested across all inputs (not just examples)
- Minimum 100 iterations per property test
- Hypothesis (Python) for property-based testing

### Incremental Development
- Bottom-up approach: data layer → processing → API → UI
- Strategic checkpoints for validation
- Optional tasks marked for faster MVP

## Processing Profiles

### Balanced (Default)
Even resource distribution, optimized for general use
- Transcription: 2 workers (high priority)
- Scene Detection: 2 workers (medium priority)
- Object Detection: 2 workers (medium priority, GPU)
- Face Detection: 2 workers (medium priority, GPU)

### Search First
Prioritize getting videos searchable quickly
- Transcription: 4 workers (critical priority)
- Embedding Generation: 2 workers (critical priority)
- Visual features: 1 worker each (low priority)

### Visual First
Prioritize object and face detection for visual navigation
- Object Detection: 3 workers (critical priority, GPU)
- Face Detection: 3 workers (critical priority, GPU)
- Scene Detection: 2 workers (high priority)

### Low Resource
Minimal resource usage for background processing
- All tasks: 1 worker each
- Max concurrent videos: 1

## Supported Video Formats

- MP4
- MOV
- AVI
- MKV

## Roadmap

### Phase 1: Core Platform (Current)
- ✅ Requirements specification
- ✅ Design specification
- ✅ Implementation tasks
- ⏳ Backend implementation
- ⏳ Frontend implementation

### Phase 2: Adobe Premiere Plugin
- Integration with Adobe Premiere Pro
- Direct timeline insertion
- Seamless workflow integration

### Phase 3: Advanced Features
- Multi-language support
- Action detection (optional)
- Face clustering and recognition
- Custom vocabulary support

## Contributing

*Coming soon*

## License

*To be determined*

## Acknowledgments

- OpenAI Whisper for transcription
- Ultralytics for YOLOv8
- Facebook Research for FAISS
- PySceneDetect for scene detection
- sentence-transformers for embeddings
