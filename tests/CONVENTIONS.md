# Test Conventions

## Test Organization

Tests are organized by module/component:
- One test file per source module
- Test classes named `Test<ModuleName>`
- Test methods named `test_<functionality>`

## Test Requirements

All tests must:
1. **Not require API calls** - Use mocks, fixtures, or dummy data
2. **Be fast** - Complete in < 1 second each
3. **Be independent** - No shared state between tests
4. **Use fixtures** - For setup/teardown and reusable test data
5. **Test edge cases** - Empty inputs, None values, boundary conditions

## Mocking Strategy

- **External APIs**: Always mock (Groq, Pirate Weather, YouTube)
- **File I/O**: Use temporary directories via fixtures
- **Environment variables**: Use `monkeypatch` to set test values
- **Time-dependent code**: Mock `datetime.now()` when needed

## Fixture Patterns

```python
@pytest.fixture
def temp_dir():
    """Create temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)

@pytest.fixture
def mock_client():
    """Create mock client without API key."""
    with patch('module.Client.__init__', lambda self: None):
        client = Client()
        client.api = Mock()
        return client
```

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific file
pytest tests/test_config.py -v

# With coverage
pytest tests/ --cov=src --cov-report=term-missing

# Specific test
pytest tests/test_config.py::TestConfig::test_location_config -v
```

