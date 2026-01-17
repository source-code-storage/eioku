# FastAPI Best Practices & Development Environment

## FastAPI Best Practices

Following [FastAPI Best Practices](https://github.com/zhanymkanov/fastapi-best-practices) for consistent, scalable development.

### Project Structure
```
src/
├── auth/
│   ├── router.py
│   ├── schemas.py      # pydantic models
│   ├── models.py       # db models
│   ├── dependencies.py
│   ├── service.py
│   └── exceptions.py
├── video/
│   ├── router.py
│   ├── schemas.py
│   ├── models.py
│   ├── dependencies.py
│   ├── service.py
│   └── exceptions.py
└── main.py
```

### Key Principles
- **Async-first**: Use `async def` for I/O operations, `def` for CPU-bound tasks
- **Pydantic everywhere**: Leverage validation, serialization, and type safety
- **Dependency injection**: Use FastAPI dependencies for validation and reusability
- **Custom base models**: Standardize datetime formats and common methods
- **Proper error handling**: Module-specific exceptions with clear messages

### Code Quality
- Use **Ruff** for linting and formatting
- Follow REST conventions for consistent API design
- Async test client from day 0
- Comprehensive API documentation with response models

## Docker Dev Containers

Using [Docker Dev Containers](https://www.docker.com/blog/streamlining-local-development-with-dev-containers-and-testcontainers-cloud/) for consistent development environments.

### Benefits
- **Consistent environment** across all team members
- **Isolated dependencies** - no local Python/Node conflicts
- **Pre-configured tools** - IDE, linters, formatters ready to use
- **Easy onboarding** - new developers productive immediately

### Configuration
Create `.devcontainer/devcontainer.json`:
```json
{
  "name": "Eioku Development",
  "image": "mcr.microsoft.com/devcontainers/python:3.11",
  "features": {
    "ghcr.io/devcontainers/features/node:1": {
      "version": "18"
    },
    "ghcr.io/devcontainers/features/docker-in-docker:2": {}
  },
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-python.black-formatter",
        "charliermarsh.ruff"
      ]
    }
  },
  "postCreateCommand": "pip install -r requirements.txt"
}
```

### Development Workflow
1. **Clone repository**
2. **Open in dev container** - VS Code/IntelliJ will prompt
3. **Start coding** - all tools pre-configured
4. **Run tests** - Docker available for integration tests
5. **Commit changes** - following our approval workflow

## Integration Points

### FastAPI + Dev Containers
- Pre-install Python dependencies in container
- Configure Ruff for code formatting
- Set up async test client
- Include database containers for integration tests

### Testing Strategy
- Unit tests with pytest
- Integration tests with Testcontainers
- API tests with async HTTP client
- All tests run in isolated container environment

## Implementation Checklist

- [ ] Create `.devcontainer/devcontainer.json`
- [ ] Set up FastAPI project structure
- [ ] Configure Ruff for code quality
- [ ] Implement custom Pydantic base models
- [ ] Set up async dependencies pattern
- [ ] Create module-specific exceptions
- [ ] Configure async test client
- [ ] Add API documentation standards
