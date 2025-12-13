# Test Coverage Strategy

## Overview

This document outlines the strategy for achieving high code coverage while avoiding API calls in tests.

## Coverage Goals

- **Target**: 80%+ code coverage
- **Focus**: Business logic, error handling, edge cases
- **Avoid**: External API calls, network requests, subprocess calls

## Test Categories

### 1. Unit Tests (No Dependencies)

These test individual functions and methods in isolation:

- **Configuration**: Loading, validation, defaults
- **Scheduler**: Time calculations, boundary conditions
- **Context Metadata**: Formatting, date calculations, season/time detection
- **Memory Manager**: CRUD operations, edge cases, error handling
- **Prompt Templates**: Content validation, structure

### 2. Mocked Integration Tests

These test components with mocked external dependencies:

- **Weather Client**: Cache logic, formatting, error handling (mocked API)
- **News Client**: Data parsing, error handling (mocked requests)
- **LLM Client**: Formatting functions, prompt generation (no actual API calls)
- **Hugo Generator**: File operations, front matter generation

### 3. Edge Case Tests

These test boundary conditions and error scenarios:

- **Empty inputs**: None, empty strings, empty lists
- **Boundary values**: Min/max, zero, negative
- **Error conditions**: File not found, invalid JSON, network errors
- **Special characters**: Quotes, newlines, unicode
- **Large inputs**: Long strings, many entries

## Coverage Areas

### ✅ Well Covered

- Configuration loading and validation
- Scheduler time calculations
- Context metadata generation
- Memory manager operations
- Prompt template structure
- Weather client caching and formatting
- News client data parsing

### 🔄 Partially Covered

- Error handling paths (some branches)
- Edge cases in formatting functions
- File I/O error scenarios
- Validation edge cases

### ❌ Not Covered (By Design)

- Actual API calls (Groq, Pirate Weather, Pulse)
- Subprocess calls (yt-dlp, ffmpeg, Hugo build)
- Network requests
- Docker/container operations
- Deployment operations

## Testing Patterns

### Mocking External Dependencies

```python
# Mock API calls
with patch('requests.get') as mock_get:
    mock_response = Mock()
    mock_response.json.return_value = {'data': 'test'}
    mock_get.return_value = mock_response
    
    result = function_under_test()
    assert result == expected
```

### Testing Error Handling

```python
# Test error paths
with patch('module.function', side_effect=Exception("Error")):
    result = function_that_handles_errors()
    assert result == fallback_value
```

### Testing Edge Cases

```python
# Test boundaries
assert function(0) == expected
assert function(MAX_VALUE) == expected
assert function(None) == expected
```

## Running Coverage Reports

```bash
# Generate coverage report
pytest tests/ --cov=src --cov-report=term-missing

# Generate HTML report
pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html

# Generate XML for CI
pytest tests/ --cov=src --cov-report=xml
```

## Coverage Metrics

### Current Coverage (Target)

- **Overall**: 80%+
- **Core Logic**: 90%+
- **Error Handling**: 70%+
- **Edge Cases**: 75%+

### Files by Coverage

- `config.py`: 85%+ (validation, loading)
- `scheduler.py`: 90%+ (time calculations)
- `context/metadata.py`: 85%+ (formatting, calculations)
- `memory/manager.py`: 80%+ (CRUD, edge cases)
- `llm/client.py`: 60%+ (formatting only, no API calls)
- `llm/prompts.py`: 100% (static templates)
- `weather/pirate_weather.py`: 75%+ (caching, formatting, mocked API)
- `news/pulse_client.py`: 70%+ (parsing, mocked requests)
- `hugo/generator.py`: 70%+ (file operations, no builds)

## Continuous Improvement

1. **Regular Coverage Reviews**: Check coverage reports after each feature
2. **Identify Gaps**: Focus on untested error paths and edge cases
3. **Add Tests Incrementally**: Don't try to cover everything at once
4. **Prioritize Critical Paths**: Focus on business logic first
5. **Maintain Test Quality**: Keep tests fast, independent, and clear

## Best Practices

1. **Test Behavior, Not Implementation**: Focus on what functions do, not how
2. **Use Descriptive Names**: Test names should explain what they test
3. **Keep Tests Independent**: No shared state between tests
4. **Mock External Dependencies**: Always mock APIs, file I/O, subprocess
5. **Test Edge Cases**: Empty inputs, None values, boundaries
6. **Test Error Handling**: Verify graceful degradation
7. **Avoid Testing Implementation Details**: Test public interfaces

## Future Improvements

- Add property-based testing for edge cases
- Add integration tests with test fixtures
- Add performance tests for critical paths
- Add mutation testing to verify test quality
- Add coverage thresholds in CI

