
- [Eioku Backend](#eioku-backend)
  - [Development](#development)
    - [Setup](#setup)
    - [Run](#run)
    - [Test](#test)
    - [Format](#format)

# Eioku Backend

## Development

### Setup
```bash
poetry install
```

### Run
```bash
poetry run uvicorn src.main:app --reload
```

### Test
```bash
poetry run pytest
```

### Format
```bash
poetry run ruff format src tests
poetry run ruff check src tests
```

### Lint
```bash
poetry run ruff check src tests --fix
```

## Contributing

### Container-First Development (Recommended)
- **All backend commands must be run inside the dev compose container**
- Use `docker-compose exec backend <command>` for backend operations
- Ensures consistent environment across all team members
- Prevents "works on my machine" issues

### Examples
```bash
# Run tests in container
docker-compose exec backend poetry run pytest

# Run linting in container  
docker-compose exec backend poetry run ruff check src tests

# Install dependencies in container
docker-compose exec backend poetry install
```
