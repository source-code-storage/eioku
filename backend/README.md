
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
