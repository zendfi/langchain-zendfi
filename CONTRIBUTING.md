# Contributing to LangChain ZendFi

Thank you for your interest in contributing to LangChain ZendFi!

## Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/zendfi/langchain-zendfi.git
   cd langchain-zendfi
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install in development mode**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Set up environment variables**
   ```bash
   cp examples/.env.example .env
   # Edit .env with your API keys
   ```

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=langchain_zendfi

# Run specific test file
pytest tests/test_tools.py

# Run with verbose output
pytest -v
```

## Code Style

We use `black` for formatting and `ruff` for linting:

```bash
# Format code
black langchain_zendfi tests examples

# Lint code
ruff check langchain_zendfi tests

# Type check
mypy langchain_zendfi
```

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests and linting
5. Commit with clear messages
6. Push and create a Pull Request

## API Key for Testing

For integration tests, you'll need a ZendFi API key:

1. Sign up at [zendfi.com](https://zendfi.com)
2. Get a test API key (prefix: `zk_test_`)
3. Set `ZENDFI_API_KEY` environment variable

Unit tests use mocks and don't require an API key.

## Release Process

1. Update version in `pyproject.toml` and `langchain_zendfi/__init__.py`
2. Update CHANGELOG.md
3. Create a git tag: `git tag v0.1.0`
4. Push tag: `git push origin v0.1.0`
5. GitHub Actions will publish to PyPI

## Questions?

- Open an issue on GitHub
- Join our Discord: [discord.gg/zendfi](https://discord.gg/zendfi)
- Email: support@zendfi.com
