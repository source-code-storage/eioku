# Contributing to Eioku

## Overview

See the main [README.md](README.md) for project overview and architecture details.

## Development Environment

### Quick Start (Recommended)

```bash
./dev/start
```

This starts the full development environment with:
- **Frontend**: React dev server with hot reload
- **Backend**: FastAPI with auto-reload  
- **Nginx**: Reverse proxy combining both services
- **Single URL**: http://localhost:8080

Stop with:
```bash
./dev/stop
```

### URLs
- **Application**: http://localhost:8080
- **Backend API**: http://localhost:8080/api/
- **Backend API docs**: http://localhost:8080/api/docs
- **Health Check**: http://localhost:8080/health

## Development Workflow

1. Make small, incremental changes
2. Run tests: `poetry run pytest` (backend) / `npm test` (frontend)
3. Check code quality: `poetry run ruff check src tests` (backend) / `npm run lint` (frontend)
4. Get approval before committing
5. Follow conventional commit format
