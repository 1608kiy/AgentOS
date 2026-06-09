# Contributing to AgentFlow

## Development Setup

```bash
git clone https://github.com/1608kiy/AgentOS.git
cd AgentOS
pip install -e ".[dev]"
```

## Code Style

- **Formatter**: `ruff format src/ tests/`
- **Linter**: `ruff check src/ tests/`
- **Type check**: `mypy src/`
- Line length: 100
- Python: 3.11+

## Testing

```bash
# Run all tests
pytest tests/ -v

# With coverage
pytest tests/ --cov=agentflow --cov-report=term-missing
```

## Pull Request Process

1. Create a feature branch from `develop`
2. Make your changes
3. Run `ruff check src/ tests/` and `ruff format --check src/ tests/`
4. Run `pytest tests/ -v`
5. Submit a pull request to `main`

## Commit Messages

Use conventional commits:
- `feat: add new feature`
- `fix: bug fix`
- `docs: documentation update`
- `refactor: code refactoring`
- `test: add tests`
