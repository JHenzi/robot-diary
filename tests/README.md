# Robot Diary Test Suite

This directory contains test classes for the Robot Diary project. All tests are designed to run **without API calls** to keep them fast, reliable, and free.

## Test Structure

### Core Functionality Tests
- `test_config.py` - Configuration loading and validation
- `test_scheduler.py` - Scheduler logic and time calculations
- `test_context_metadata.py` - Context metadata generation and formatting
- `test_memory_manager.py` - Memory storage and retrieval operations
- `test_prompts.py` - Prompt template validation
- `test_llm_client_formatting.py` - LLM client formatting methods (no API calls)
- `test_hugo_generator.py` - Hugo post generation and file operations

### Edge Cases and Error Handling
- `test_weather_client.py` - Weather client caching, formatting, error handling (mocked)
- `test_news_client.py` - News client functions with mocked requests
- `test_memory_manager_edge_cases.py` - Memory manager edge cases and error conditions
- `test_scheduler_edge_cases.py` - Scheduler boundary conditions
- `test_context_metadata_edge_cases.py` - Context metadata edge cases
- `test_hugo_generator_edge_cases.py` - Hugo generator edge cases

### Documentation
- `COVERAGE_STRATEGY.md` - Comprehensive coverage strategy and goals
- `CONVENTIONS.md` - Testing conventions and patterns

## Running Tests

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test File

```bash
pytest tests/test_config.py -v
```

### Run with Coverage

```bash
# Terminal report
pytest tests/ --cov=src --cov-report=term-missing

# HTML report (opens in browser)
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# XML report (for CI)
pytest tests/ --cov=src --cov-report=xml
```

### Coverage Goals

- **Target**: 80%+ overall coverage
- **Core Logic**: 90%+ coverage
- **Error Handling**: 70%+ coverage
- **Edge Cases**: 75%+ coverage

See `COVERAGE_STRATEGY.md` for detailed coverage strategy.

## Test Philosophy

All tests are designed to:
- **Not require API keys** - Tests use mocks and dummy data
- **Be fast** - No network calls or long-running operations
- **Be deterministic** - Same inputs produce same outputs
- **Test logic, not APIs** - Focus on business logic, formatting, and data transformations

## CI/CD

Tests run automatically on:
- Push to main/master/develop branches
- Pull requests
- Multiple Python versions (3.10, 3.11, 3.12)

See `.github/workflows/ci.yml` for CI configuration.

## Adding New Tests

When adding new tests:
1. Use descriptive test names starting with `test_`
2. Use fixtures for setup/teardown
3. Mock external dependencies (APIs, file systems)
4. Test edge cases and error conditions
5. Keep tests independent (no shared state)

## Test Markers

- `@pytest.mark.api` - Tests that require API calls (not used in this suite)
- `@pytest.mark.slow` - Tests that take a long time
- `@pytest.mark.integration` - Integration tests

