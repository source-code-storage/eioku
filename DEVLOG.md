# Eioku Development Log

**Duration**: Jan 17-29, 2026 (11 active days)
**Total Commits**: 228
**Peak Day**: Jan 18 (64 commits)

---

## Timeline

### Day 1 - Jan 17 (9 commits)
- Project init, steering files, boilerplate
- Docker compose for dev environment
- **Decision**: FastAPI + React + PostgreSQL stack

### Day 2 - Jan 18 (64 commits) - Heavy lift day
- Database schema: Videos, Transcriptions, Scenes, Objects, Faces, Topics, Tasks
- Clean architecture: DAOs, repositories, domain models
- Path management & video discovery service
- Task orchestration with worker pools
- Whisper transcription pipeline
- **Decision**: Separate table per artifact type (later revised)
- **Challenge**: Wiring worker pools with automatic task processing

### Day 3 - Jan 19 (12 commits)
- YOLO object detection integration
- Scene detection with PySceneDetect
- Face detection pipeline
- **Decision**: GPU worker pool separate from CPU pool
- **Challenge**: GPU memory management across models

### Day 4 - Jan 20 (16 commits)
- Place recognition (Places365)
- OCR pipeline (EasyOCR)
- Artifact envelope architecture design
- **Decision**: JSONB payloads with schema versioning
- **Decision**: Projection tables for fast queries

### Day 5 - Jan 22 (8 commits)
- Artifact envelope implementation
- Schema registry pattern
- **Challenge**: Migration from separate tables to unified artifacts

### Day 6 - Jan 24 (23 commits)
- GPU semaphore for concurrency control
- Async job queue with arq
- Redis/Valkey integration
- **Decision**: Queue between API and ML worker (not HTTP)
- **Challenge**: CUDA library paths in Docker

### Day 7 - Jan 25 (39 commits)
- ML Service separation from API
- Job producer/consumer pattern
- Reconciler for stale tasks
- Input hash verification
- **Decision**: Separate ML service for GPU isolation
- **Challenge**: Service communication without tight coupling

### Day 8 - Jan 26 (6 commits)
- JSON structured logging
- Kiro hooks: lint, test, db reset, code review
- Test suite updates for new architecture

### Day 9 - Jan 27 (16 commits)
- Complete worker-ML service separation
- Video streaming endpoint
- Frontend POCs: scene jumping, face detection, gallery
- Inference performance improvements
- **Challenge**: Scene detection threshold tuning (settled on 0.7)

### Day 10 - Jan 28 (25 commits)
- Metadata extraction pipeline (EXIF, ffprobe)
- Reverse geocoding for GPS
- Global jump navigation backend
- Projection sync for metadata
- **Decision**: Use `file_created_at` for chronological ordering
- **Challenge**: Cross-video search ordering strategy

### Day 11 - Jan 29 (10 commits)
- Global jump frontend
- Video clip export with ffmpeg
- API documentation
- Spec finalization

### Day 12 - Jan 30
- Complete prod images and prod demo docker compose files
- Add ML to CI
- Do not allow retry completed tasks
- Enable API_URL override in frontend

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| JSONB + projection tables | Flexibility of document store + performance of relational |
| Redis queue (not HTTP) | ML inference takes 30s-2min, HTTP would timeout |
| Separate ML service | GPU resources expensive, API scales on cheap CPUs |
| `file_created_at` ordering | EXIF date reflects actual filming order |
| arq for job queue | Built-in retry, backpressure, Redis-native |
| Schema versioning | Multiple model versions coexist, re-process without data loss |

---

## Major Challenges

1. **GPU memory** - Multiple models competing for VRAM
   - Solved: GPU semaphore limiting concurrent inference

2. **CUDA in Docker** - Library paths, driver compatibility
   - Solved: nvidia-container-toolkit, explicit LD_LIBRARY_PATH

3. **Artifact migration** - Moving from 6 tables to envelope pattern
   - Solved: Phased migration with projection tables for backwards compat

4. **Cross-video search** - Consistent ordering across videos
   - Solved: Triple sort key (file_created_at, video_id, start_ms)

5. **Service decoupling** - API and ML service communication
   - Solved: Redis queue, no direct HTTP calls

---

## Commits by Day

```
Jan 17  ████████░░░░░░░░░░░░  9
Jan 18  ████████████████████  64 (peak)
Jan 19  ██████░░░░░░░░░░░░░░  12
Jan 20  ████████░░░░░░░░░░░░  16
Jan 22  ████░░░░░░░░░░░░░░░░  8
Jan 24  ███████████░░░░░░░░░  23
Jan 25  ███████████████████░  39
Jan 26  ███░░░░░░░░░░░░░░░░░  6
Jan 27  ████████░░░░░░░░░░░░  16
Jan 28  ████████████░░░░░░░░  25
Jan 29  █████░░░░░░░░░░░░░░░  10
```

---

## Kiro Specs Created

1. `artifact-envelope-architecture` - Core storage design
2. `worker-ml-service-separation` - Service architecture
3. `global-jump-navigation` - Cross-video search
4. `global-jump-navigation-gui` - Frontend spec
5. `video-metadata-extraction` - EXIF pipeline
6. `artifact-thumbnails-gallery` - Gallery UI
7. `semantic-video-search` - Future: vector embeddings
