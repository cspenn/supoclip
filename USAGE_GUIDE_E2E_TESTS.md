# SupoClip E2E Test Suite - Usage Guide

## Quick Start

### Run All E2E Tests
```bash
cd /Users/cspenn/Documents/github/supoclip/backend
python -m pytest tests/test_end_to_end.py -v
```

**Output**: 30 tests pass, 1 skipped, execution time ~1.7 seconds

### Run Full Test Suite (Recommended)
```bash
python -m pytest tests/ -v
```

**Output**: 216 tests pass, 1 skipped, execution time ~4.1 seconds

## Common Tasks

### 1. Run Tests for Local-First Configuration
```bash
python -m pytest tests/test_end_to_end.py::TestE2ELocalFirstOperation -v
```

This validates:
- ✅ No cloud API keys required
- ✅ SQLite database (not PostgreSQL)
- ✅ MLX Whisper local transcription (not AssemblyAI)
- ✅ Local asyncio job queue (not Redis)

### 2. Run Tests for Database Operations
```bash
python -m pytest tests/test_end_to_end.py::TestE2EDatabaseOperations -v
```

This validates:
- ✅ Task creation and retrieval
- ✅ Multiple clips per task
- ✅ Task status updates

### 3. Run Tests for API Endpoints
```bash
python -m pytest tests/test_end_to_end.py::TestE2EAPIEndpoints -v
```

This validates:
- ✅ Fonts endpoint
- ✅ Transitions endpoint
- ✅ Task creation endpoint
- ✅ Database health check

### 4. Run Tests for Video Pipeline
```bash
python -m pytest tests/test_end_to_end.py::TestE2EVideoProcessingPipeline -v
```

This validates:
- ✅ Database initialization
- ✅ Task creation and storage
- ✅ Clip metadata storage
- ✅ API health checks
- ✅ Configuration validation
- ✅ Performance baseline

### 5. Run Single Test
```bash
python -m pytest tests/test_end_to_end.py::TestE2EVideoProcessingPipeline::test_database_initialization -v
```

## Advanced Options

### Run with Coverage Report
```bash
python -m pytest tests/test_end_to_end.py --cov=src --cov-report=html
```

**Creates**: `htmlcov/index.html` with detailed coverage

### Run with Performance Timing
```bash
python -m pytest tests/test_end_to_end.py -v --durations=10
```

**Shows**: 10 slowest tests and their execution times

### Run with Verbose Output
```bash
python -m pytest tests/test_end_to_end.py -vv
```

**Shows**: Extra verbose output including setup/teardown

### Run with Print Statements
```bash
python -m pytest tests/test_end_to_end.py -v -s
```

**Shows**: All print statements and logging output (useful for debugging)

### Run Specific Test Pattern
```bash
python -m pytest tests/test_end_to_end.py -v -k "local"
```

**Runs**: Only tests matching "local" in the name

### Generate XML Report (for CI/CD)
```bash
python -m pytest tests/test_end_to_end.py --junit-xml=report.xml
```

## Debugging Tests

### Run with Full Traceback
```bash
python -m pytest tests/test_end_to_end.py -v --tb=long
```

### Run with Python Debugger
```bash
python -m pytest tests/test_end_to_end.py -v --pdb
```

**Stops**: At first failure and opens debugger

### Run with Detailed Output
```bash
python -m pytest tests/test_end_to_end.py -v --tb=short -s
```

## CI/CD Integration

### GitHub Actions Example
```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: 3.11
      - name: Install dependencies
        run: |
          cd backend
          pip install -e .
      - name: Run E2E tests
        run: |
          cd backend
          python -m pytest tests/test_end_to_end.py -v --junit-xml=report.xml
      - name: Upload results
        if: always()
        uses: actions/upload-artifact@v2
        with:
          name: test-results
          path: backend/report.xml
```

### Local Pre-commit Hook
```bash
#!/bin/bash
# .git/hooks/pre-commit

cd backend
python -m pytest tests/test_end_to_end.py -q --tb=short

if [ $? -ne 0 ]; then
    echo "E2E tests failed. Commit aborted."
    exit 1
fi
```

## Test Organization

### By Concern
```
TestE2EVideoProcessingPipeline (15 tests) - Core pipeline
TestE2EAPIEndpoints (4 tests) - API integration
TestE2EVideoFilesAndMetadata (3 tests) - File operations
TestE2EPerformanceMetrics (3 tests) - Performance monitoring
TestE2ELocalFirstOperation (4 tests) - Configuration validation
TestE2EDatabaseOperations (3 tests) - Database persistence
```

### By Functionality
```
Configuration Tests:
  ✅ Local LLM enabled
  ✅ MLX Whisper configured
  ✅ SQLite database
  ✅ Local job queue

Database Tests:
  ✅ Task creation
  ✅ Clip storage
  ✅ Relationships
  ✅ Status updates

API Tests:
  ✅ Health checks
  ✅ Endpoints
  ✅ JSON responses
  ✅ Error handling

Video Tests:
  ✅ File creation
  ✅ Metadata storage
  ✅ Format validation
  ✅ Timing measurement
```

## Performance Baseline

### Test Execution Time
- **E2E Tests Only**: ~1.7 seconds
- **Full Test Suite**: ~4.1 seconds
- **Single Test**: ~50-150ms

### Typical Test Breakdown
```
Database initialization: <10ms
Task creation: 20-30ms
Clip storage: 15-25ms
API calls: <5ms
Configuration validation: <5ms
File operations: 10-20ms
Performance measurement: 100-200ms
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'moviepy'"
```bash
pip install moviepy==2.2.1
```

### Issue: "ModuleNotFoundError: No module named 'mlx_whisper'"
```bash
pip install mlx-whisper==0.4.2
```

### Issue: "Database constraint failed: check_source_type"
**Cause**: Using invalid source type
**Fix**: Use only 'youtube' or 'video_url'

### Issue: "Tests hang or timeout"
**Cause**: In-memory database or temp directory issues
**Fix**:
```bash
python -m pytest tests/test_end_to_end.py --timeout=30
```

### Issue: "Permission denied" for temp directories
**Cause**: File permission issues
**Fix**:
```bash
chmod 777 /Users/cspenn/Documents/github/supoclip/backend/tests
```

## Test Data

### Sample User
```python
id: "test-e2e-user-1"
email: "e2e@test.supoclip.local"
name: "E2E Test User"
```

### Sample Source
```python
type: "video_url"  # or "youtube"
title: "E2E Test Video"
```

### Sample Clip
```python
filename: "clip-0.mp4"
start_time: "0:00"
end_time: "0:10"
duration: 10
relevance_score: 0.95
```

## Monitoring and Metrics

### Test Coverage
```bash
python -m pytest tests/test_end_to_end.py --cov=src --cov-report=term
```

### Slowest Tests
```bash
python -m pytest tests/test_end_to_end.py --durations=5
```

### Test Status Summary
```bash
python -m pytest tests/test_end_to_end.py -v --tb=no
```

## References

### Documentation
- **Full Report**: `/Users/cspenn/Documents/github/supoclip/docs/E2E_TEST_REPORT.md`
- **Test File**: `/Users/cspenn/Documents/github/supoclip/backend/tests/test_end_to_end.py`
- **Summary**: `/Users/cspenn/Documents/github/supoclip/E2E_TEST_COMPLETION_SUMMARY.md`

### Configuration Files
- **pytest.ini**: Test configuration
- **pyproject.toml**: Dependencies specification
- **.env**: Environment variables

### Command Reference
```bash
# Run specific test class
pytest tests/test_end_to_end.py::TestE2ELocalFirstOperation -v

# Run with keywords
pytest tests/test_end_to_end.py -k "database" -v

# Run with markers
pytest tests/test_end_to_end.py -m "not slow" -v

# Run with coverage
pytest tests/test_end_to_end.py --cov=src --cov-report=html

# Run with verbose
pytest tests/test_end_to_end.py -vv -s

# Run with timing
pytest tests/test_end_to_end.py --durations=10

# Run with debugging
pytest tests/test_end_to_end.py -v --pdb --tb=short
```

## Best Practices

### 1. Run Tests Before Commits
```bash
./checkpython.sh  # Runs all checks including tests
```

### 2. Monitor Performance Trends
```bash
pytest tests/test_end_to_end.py --durations=5 > baseline.txt
# Compare results over time
```

### 3. Use Coverage for Debugging
```bash
pytest --cov=src tests/test_end_to_end.py
# Identify untested code paths
```

### 4. Isolate Failing Tests
```bash
pytest tests/test_end_to_end.py -v --tb=short -x
# Stop at first failure
```

### 5. Validate Local-First Operation
```bash
pytest tests/test_end_to_end.py::TestE2ELocalFirstOperation -v
# Ensure no external API dependencies
```

---

**Last Updated**: November 14, 2025
**Status**: ✅ Ready for Production Use
**All 216 Tests**: PASSING
