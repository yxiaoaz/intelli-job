# Intelli-Job Backend Testing Guide

## 📋 Overview

This document provides comprehensive information about testing the Intelli-Job backend application.

---

## 🚀 Quick Start

### Run All Tests

```bash
# Activate virtual environment
cd backend
.\venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Run all tests with coverage
python run_tests.py

# Or use pytest directly
pytest tests/ -v --cov=app
```

### Run Specific Test Files

```bash
# Authentication tests only
python run_tests.py tests/test_auth.py

# Job search tests only
python run_tests.py tests/test_jobs.py

# User profile tests only
python run_tests.py tests/test_users.py

# Chat agent tests only
python run_tests.py tests/test_chat.py
```

### Run with Coverage Report

```bash
# Terminal report
pytest tests/ --cov=app --cov-report=term-missing

# HTML report (opens in browser)
pytest tests/ --cov=app --cov-report=html
# Open htmlcov/index.html in your browser
```

---

## 📁 Test Structure

```
backend/tests/
├── __init__.py              # Package marker
├── conftest.py              # Shared fixtures and configuration
├── test_auth.py             # Authentication & authorization tests
├── test_jobs.py             # Job search & bookmarking tests
├── test_users.py            # User profile & resume tests
└── test_chat.py             # AI conversation agent tests
```

---

## 🧪 Test Categories

### 1. **Authentication Tests** (`test_auth.py`)

Tests for user registration, login, token management, and security:

- ✅ User registration (success, duplicate email, validation)
- ✅ User login (correct credentials, wrong password, inactive user)
- ✅ Token refresh mechanism
- ✅ Protected route access control
- ✅ Password hashing verification
- ✅ JWT token structure and expiration

**Example:**
```bash
pytest tests/test_auth.py::TestUserRegistration::test_register_success -v
```

---

### 2. **Job Search Tests** (`test_jobs.py`)

Tests for job matching, filtering, and bookmarking:

- ✅ Basic job search (hybrid, keyword, vector modes)
- ✅ Advanced filtering (city, industry, experience)
- ✅ Job bookmarking/unbookmarking
- ✅ Job details retrieval
- ✅ Job export functionality

**Example:**
```bash
pytest tests/test_jobs.py::TestJobSearch::test_search_with_filters -v
```

---

### 3. **User Profile Tests** (`test_users.py`)

Tests for user management and resume handling:

- ✅ User profile retrieval and updates
- ✅ Resume upload and parsing
- ✅ File type validation
- ✅ Search history tracking
- ✅ User statistics

**Example:**
```bash
pytest tests/test_users.py::TestResumeUpload::test_upload_resume -v
```

---

### 4. **Chat Agent Tests** (`test_chat.py`)

Tests for AI conversation and tool invocation:

- ✅ Message sending and receiving
- ✅ Conversation context maintenance
- ✅ Job search via chat
- ✅ Resume analysis requests
- ✅ Agent tool invocations

**Example:**
```bash
pytest tests/test_chat.py::TestChatEndpoint::test_send_message -v
```

---

## 🔧 Fixtures

### Available Fixtures (in `conftest.py`)

| Fixture | Description | Usage |
|---------|-------------|-------|
| `test_engine` | In-memory SQLite database engine | Database operations |
| `test_db` | Async database session | Database queries |
| `client` | Unauthenticated HTTP client | Public endpoints |
| `authenticated_client` | Authenticated HTTP client | Protected endpoints |
| `test_user_data` | Sample user credentials | Login/register tests |

**Example Usage:**
```python
@pytest.mark.asyncio
async def test_example(authenticated_client):
    response = await authenticated_client.get("/api/v1/users/me")
    assert response.status_code == 200
```

---

## 📊 Code Coverage

### View Coverage Report

```bash
# Terminal summary
pytest --cov=app --cov-report=term-missing

# Detailed HTML report
pytest --cov=app --cov-report=html
open htmlcov/index.html  # Mac/Linux
start htmlcov/index.html  # Windows
```

### Coverage Targets

| Module | Target Coverage |
|--------|----------------|
| Authentication | 90%+ |
| Job Matching | 85%+ |
| User Management | 85%+ |
| Chat Agent | 80%+ |
| **Overall** | **85%+** |

---

## 🏷️ Test Markers

Use markers to categorize and filter tests:

```bash
# Run only unit tests
pytest -m unit

# Run only integration tests
pytest -m integration

# Skip slow tests
pytest -m "not slow"

# Run slow tests only
pytest -m slow
```

**Available Markers:**
- `unit`: Fast, isolated unit tests
- `integration`: Tests requiring external services
- `slow`: Tests that take >1 second

---

## 🐛 Debugging Tests

### Verbose Output

```bash
# Show detailed test execution
pytest tests/test_auth.py -vv

# Show print statements
pytest -s tests/test_auth.py
```

### Stop on First Failure

```bash
pytest -x tests/
```

### Run Last Failed Tests

```bash
pytest --lf
```

### PDB Debugging

```bash
# Drop into debugger on failure
pytest --pdb tests/test_auth.py
```

---

## 🌐 Testing with Real Database

By default, tests use an in-memory SQLite database. To test with PostgreSQL:

1. **Set up test database:**
```sql
CREATE DATABASE intelli_job_test;
```

2. **Update `conftest.py`:**
```python
TEST_DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/intelli_job_test"
```

3. **Run migrations:**
```bash
alembic upgrade head
```

4. **Run tests:**
```bash
pytest tests/
```

---

## 🔄 Continuous Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: intelli_job_test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      
      - name: Run tests
        run: |
          cd backend
          pytest tests/ --cov=app --cov-fail-under=85
```

---

## 📝 Writing New Tests

### Test Template

```python
import pytest
import pytest_asyncio


class TestYourFeature:
    """Test description"""
    
    @pytest.mark.asyncio
    async def test_your_feature(self, authenticated_client):
        """Test case description"""
        # Arrange
        test_data = {"key": "value"}
        
        # Act
        response = await authenticated_client.post(
            "/api/v1/your-endpoint",
            json=test_data
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "expected_field" in data
```

### Best Practices

1. **Use descriptive test names**: `test_login_with_valid_credentials`
2. **Follow AAA pattern**: Arrange, Act, Assert
3. **Test one thing per test**: Keep tests focused
4. **Use fixtures**: Reuse setup code
5. **Mock external services**: Don't depend on real APIs
6. **Clean up after tests**: Use teardown in fixtures

---

## 🚨 Common Issues

### Issue: Import Errors

**Solution:**
```bash
# Make sure you're in the backend directory
cd backend

# Ensure virtual environment is activated
.\venv\Scripts\activate  # Windows

# Install test dependencies
pip install pytest pytest-asyncio pytest-cov
```

### Issue: Database Connection Errors

**Solution:**
```bash
# Check if using in-memory SQLite (default)
# No action needed - it's automatic

# If using PostgreSQL, ensure it's running
docker run --name postgres-test -e POSTGRES_PASSWORD=test -p 5432:5432 -d postgres
```

### Issue: Async Test Errors

**Solution:**
```bash
# Ensure pytest-asyncio is installed
pip install pytest-asyncio

# Check pyproject.toml has asyncio_mode = "auto"
```

---

## 📚 Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [httpx Documentation](https://www.python-httpx.org/)

---

## 🎯 Running All Tests Now

```bash
cd backend
.\venv\Scripts\activate
python run_tests.py
```

Happy Testing! 🎉
