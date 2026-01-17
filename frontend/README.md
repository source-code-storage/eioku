# Eioku Frontend

## Development

### Setup
```bash
npm install
```

### Run
```bash
npm run dev
```

### Test
```bash
npm test
```

### Build
```bash
npm run build
```

### Lint
```bash
npm run lint
npm run lint:fix
```

## Tech Stack

- **React 18** with TypeScript
- **Vite** for fast development and building
- **Vitest** for testing
- **React Testing Library** for component testing
- **ESLint** for code quality

## Contributing

### Container-First Development (Recommended)
- **All frontend commands must be run inside the dev compose container**
- Use `docker-compose exec frontend <command>` for frontend operations
- Ensures consistent environment across all team members
- Prevents "works on my machine" issues

### Examples
```bash
# Run tests in container
docker-compose exec frontend npm test

# Run linting in container
docker-compose exec frontend npm run lint

# Install dependencies in container
docker-compose exec frontend npm install
```
