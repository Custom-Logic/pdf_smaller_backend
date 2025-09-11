# Testing Guide

This guide provides comprehensive documentation for testing the PDF Smaller backend service, including unit tests, integration tests, test data management, and best practices.

## Table of Contents

1. [Testing Overview](#testing-overview)
2. [Test Structure](#test-structure)
3. [Test Configuration](#test-configuration)
4. [Writing Tests](#writing-tests)
5. [Test Fixtures](#test-fixtures)
6. [Mocking and Patching](#mocking-and-patching)
7. [Database Testing](#database-testing)
8. [API Testing](#api-testing)
9. [Service Testing](#service-testing)
10. [Integration Testing](#integration-testing)
11. [Test Data Management](#test-data-management)
12. [Running Tests](#running-tests)
13. [Test Coverage](#test-coverage)
14. [Continuous Integration](#continuous-integration)
15. [Best Practices](#best-practices)

## Testing Overview

### Testing Framework

The project uses **pytest** as the primary testing framework with the following key dependencies:

- `pytest==7.4.3` - Core testing framework
- `pytest-flask==1.3.0` - Flask application testing utilities
- `pytest-mock==3.12.0` - Enhanced mocking capabilities
- `unittest.mock` - Python standard library mocking

### Testing Philosophy

- **Test-Driven Development (TDD)**: Write tests before implementation when possible
- **Comprehensive Coverage**: Aim for 80%+ code coverage
- **Fast Execution**: Tests should run quickly to enable frequent execution
- **Isolation**: Each test should be independent and not affect others
- **Realistic Scenarios**: Test real-world usage patterns and edge cases

## Test Structure

### Directory Organization

```
tests/
├── conftest.py                    # Pytest configuration and shared fixtures
├── test_config.py                 # Configuration testing
├── test_auth_service.py           # Authentication service tests
├── test_auth_endpoints.py         # Authentication API tests
├── test_auth_utils.py             # Authentication utilities tests
├── test_compression_job_tracking.py # Job tracking tests
├── test_enhanced_compression_service.py # Compression service tests
├── test_bulk_compression_service.py # Bulk compression tests
├── test_bulk_compression_api.py   # Bulk compression API tests
├── test_file_management_service.py # Unified file management tests
├── test_celery_tasks.py           # Celery task tests
├── test_rate_limiter.py           # Rate limiting tests
├── test_security_middleware.py    # Security middleware tests
├── test_security_utils.py         # Security utilities tests
├── test_logging_system.py         # Logging system tests
├── test_error_handling.py         # Error handling tests
├── test_validation_utils.py       # Validation utilities tests
├── test_user_model.py             # User model tests
├── test_subscription_models.py    # Subscription model tests
├── test_subscription_service.py   # Subscription service tests
├── test_subscription_endpoints.py # Subscription API tests
├── test_stripe_service.py         # Stripe integration tests
└── fixtures/                      # Test data and fixtures
    ├── sample_files/
    │   ├── test.pdf
    │   ├── large_file.pdf
    │   └── corrupted.pdf
    └── test_data.json
```

### Test Categories

1. **Unit Tests**: Test individual functions and methods in isolation
2. **Integration Tests**: Test interactions between components
3. **API Tests**: Test HTTP endpoints and request/response handling
4. **Service Tests**: Test business logic and service layer functionality
5. **Model Tests**: Test database models and relationships
6. **Utility Tests**: Test helper functions and utilities

## Test Configuration

### Test Environment Setup

The testing environment is configured in `conftest.py`:

```python
import pytest
import tempfile
import os
from src.main import create_app
from src.models.base import db
from src.config import Config

class TestConfig(Config):
    """Test configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
```

### Environment Variables for Testing

Create `.env.testing` file:

```bash
# Application
FLASK_ENV=testing
SECRET_KEY=test-secret-key-for-testing-only
DEBUG=true
TESTING=true

# Database (In-memory SQLite)
DATABASE_URL=sqlite:///:memory:

# File Storage
UPLOAD_FOLDER=./uploads/test
MAX_FILE_SIZE=10485760  # 10MB for faster tests
MAX_FILE_AGE_HOURS=1

# Redis & Celery (Use different DB)
REDIS_URL=redis://localhost:6379/15
CELERY_BROKER_URL=redis://localhost:6379/15
CELERY_RESULT_BACKEND=redis://localhost:6379/15
CELERY_TASK_ALWAYS_EAGER=true  # Synchronous execution for tests

# Security (Disabled for testing)
SECURITY_HEADERS_ENABLED=false
RATE_LIMIT_ENABLED=false
WTF_CSRF_ENABLED=false

# Logging
LOG_LEVEL=DEBUG
LOG_FILE=test.log

# Monitoring
HEALTH_CHECK_ENABLED=true
METRICS_ENABLED=false
```

## Writing Tests

### Basic Test Structure

```python
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.services.compression_service import CompressionService

class TestCompressionService:
    """Test cases for CompressionService."""
    
    def test_compress_pdf_success(self, sample_pdf_file):
        """Test successful PDF compression."""
        service = CompressionService()
        result = service.compress_pdf(sample_pdf_file, 'medium')
        
        assert result['success'] is True
        assert result['compressed_size'] < result['original_size']
        assert os.path.exists(result['output_path'])
    
    def test_compress_pdf_invalid_file(self):
        """Test compression with invalid file."""
        service = CompressionService()
        
        with pytest.raises(FileNotFoundError):
            service.compress_pdf('nonexistent.pdf', 'medium')
    
    @patch('src.services.compression_service.subprocess.run')
    def test_compress_pdf_ghostscript_failure(self, mock_subprocess):
        """Test handling of Ghostscript failures."""
        mock_subprocess.return_value.returncode = 1
        mock_subprocess.return_value.stderr = b'Ghostscript error'
        
        service = CompressionService()
        
        with pytest.raises(CompressionError):
            service.compress_pdf('test.pdf', 'medium')
```

### Test Naming Conventions

- **Test files**: `test_<module_name>.py`
- **Test classes**: `Test<ClassName>`
- **Test methods**: `test_<functionality>_<scenario>`

Examples:
- `test_compress_pdf_success`
- `test_compress_pdf_invalid_file`
- `test_user_creation_with_valid_data`
- `test_authentication_with_invalid_credentials`

## Test Fixtures

### Core Fixtures (conftest.py)

```python
@pytest.fixture
def app():
    """Create application for testing"""
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()

@pytest.fixture
def db_session(app):
    """Create database session for testing"""
    with app.app_context():
        yield db.session

@pytest.fixture
def test_user(app):
    """Create a test user"""
    from src.models import User
    with app.app_context():
        user = User(
            email='test@example.com',
            password='TestPassword123',
            name='Test User'
        )
        db.session.add(user)
        db.session.commit()
        yield user

@pytest.fixture
def auth_headers(app, test_user):
    """Create authentication headers with JWT token"""
    from flask_jwt_extended import create_access_token
    with app.app_context():
        access_token = create_access_token(identity=str(test_user.id))
        return {'Authorization': f'Bearer {access_token}'}
```

### File Fixtures

```python
@pytest.fixture
def temp_upload_folder():
    """Create temporary upload folder"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)

@pytest.fixture
def sample_pdf_file():
    """Create sample PDF file for testing"""
    # Create a minimal PDF file
    pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
    
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        f.write(pdf_content)
        f.flush()
        yield f.name
    
    os.unlink(f.name)

@pytest.fixture
def mock_file():
    """Create mock file object for testing"""
    from werkzeug.datastructures import FileStorage
    from io import BytesIO
    
    file_content = b"Mock PDF content for testing"
    file_obj = FileStorage(
        stream=BytesIO(file_content),
        filename="test_document.pdf",
        content_type="application/pdf"
    )
    return file_obj
```

## Mocking and Patching

### External Service Mocking

```python
# Mock Ghostscript subprocess calls
@patch('src.services.compression_service.subprocess.run')
def test_compression_with_ghostscript_mock(mock_subprocess):
    mock_subprocess.return_value.returncode = 0
    mock_subprocess.return_value.stdout = b'Success'
    
    service = CompressionService()
    result = service.compress_pdf('test.pdf', 'medium')
    
    assert result['success'] is True
    mock_subprocess.assert_called_once()

# Mock Redis/Celery
@patch('src.tasks.compression_tasks.process_compression.delay')
def test_async_compression_task(mock_task):
    mock_task.return_value.id = 'test-task-id'
    
    # Test code that triggers async task
    result = trigger_compression_task('test.pdf')
    
    assert result['task_id'] == 'test-task-id'
    mock_task.assert_called_once()

# Mock external APIs
@patch('requests.post')
def test_ai_service_api_call(mock_post):
    mock_response = Mock()
    mock_response.json.return_value = {'result': 'success'}
    mock_response.status_code = 200
    mock_post.return_value = mock_response
    
    service = AIService()
    result = service.process_request('test prompt')
    
    assert result['result'] == 'success'
```

### Database Mocking

```python
@patch('src.models.base.db.session')
def test_user_creation_with_db_mock(mock_session):
    mock_session.add = Mock()
    mock_session.commit = Mock()
    
    user = User(email='test@example.com', password='password')
    user.save()
    
    mock_session.add.assert_called_once_with(user)
    mock_session.commit.assert_called_once()
```

## Database Testing

### Model Testing

```python
class TestUserModel:
    """Test User model functionality"""
    
    def test_user_creation(self, app):
        """Test creating a new user"""
        with app.app_context():
            user = User(
                email='test@example.com',
                password='SecurePassword123',
                name='Test User'
            )
            
            db.session.add(user)
            db.session.commit()
            
            assert user.id is not None
            assert user.email == 'test@example.com'
            assert user.check_password('SecurePassword123')
    
    def test_user_password_hashing(self, app):
        """Test password hashing functionality"""
        with app.app_context():
            user = User(email='test@example.com', password='password123')
            
            # Password should be hashed
            assert user.password_hash != 'password123'
            assert user.check_password('password123')
            assert not user.check_password('wrongpassword')
    
    def test_user_validation(self, app):
        """Test user input validation"""
        with app.app_context():
            # Test invalid email
            with pytest.raises(ValueError):
                User(email='invalid-email', password='password123')
            
            # Test weak password
            with pytest.raises(ValueError):
                User(email='test@example.com', password='weak')
```

### Relationship Testing

```python
def test_user_subscription_relationship(self, app, test_user, test_plan):
    """Test user-subscription relationship"""
    with app.app_context():
        subscription = Subscription(
            user_id=test_user.id,
            plan_id=test_plan.id,
            status='active'
        )
        
        db.session.add(subscription)
        db.session.commit()
        
        # Test relationship access
        assert subscription.user.email == test_user.email
        assert subscription.plan.name == test_plan.name
        assert test_user.subscription.plan.name == test_plan.name
```

## API Testing

### Endpoint Testing

```python
class TestCompressionAPI:
    """Test compression API endpoints"""
    
    def test_compress_endpoint_success(self, client, auth_headers, mock_file):
        """Test successful file compression"""
        response = client.post(
            '/api/compress',
            data={
                'file': mock_file,
                'compressionLevel': 'medium',
                'imageQuality': 80
            },
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'job_id' in data
    
    def test_compress_endpoint_no_file(self, client, auth_headers):
        """Test compression endpoint without file"""
        response = client.post('/api/compress', headers=auth_headers)
        
        assert response.status_code == 400
        data = response.get_json()
        assert 'error' in data
    
    def test_compress_endpoint_unauthorized(self, client, mock_file):
        """Test compression endpoint without authentication"""
        response = client.post(
            '/api/compress',
            data={'file': mock_file}
        )
        
        assert response.status_code == 401
```

### Response Validation

```python
def test_api_response_structure(self, client, auth_headers):
    """Test API response structure consistency"""
    response = client.get('/api/jobs', headers=auth_headers)
    
    assert response.status_code == 200
    data = response.get_json()
    
    # Validate response structure
    assert 'success' in data
    assert 'data' in data
    assert isinstance(data['data'], list)
    
    # Validate job structure if jobs exist
    if data['data']:
        job = data['data'][0]
        required_fields = ['id', 'status', 'created_at', 'job_type']
        for field in required_fields:
            assert field in job
```

## Service Testing

### Service Layer Testing

```python
class TestCompressionService:
    """Test compression service functionality"""
    
    def setup_method(self):
        """Set up test environment"""
        self.service = CompressionService()
        self.temp_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('src.services.compression_service.subprocess.run')
    def test_compress_pdf_with_settings(self, mock_subprocess):
        """Test PDF compression with custom settings"""
        mock_subprocess.return_value.returncode = 0
        
        settings = {
            'compression_level': 'high',
            'image_quality': 60,
            'remove_metadata': True
        }
        
        result = self.service.compress_pdf('input.pdf', settings)
        
        # Verify Ghostscript was called with correct parameters
        call_args = mock_subprocess.call_args[0][0]
        assert '-dPDFSETTINGS=/ebook' in call_args  # High compression
        assert '-dJPEGQ=60' in call_args  # Image quality
    
    def test_validate_compression_settings(self):
        """Test compression settings validation"""
        # Valid settings
        valid_settings = {
            'compression_level': 'medium',
            'image_quality': 80
        }
        assert self.service.validate_settings(valid_settings) is True
        
        # Invalid compression level
        invalid_settings = {
            'compression_level': 'invalid',
            'image_quality': 80
        }
        with pytest.raises(ValidationError):
            self.service.validate_settings(invalid_settings)
```

## Integration Testing

### End-to-End Testing

```python
class TestCompressionWorkflow:
    """Test complete compression workflow"""
    
    def test_complete_compression_workflow(self, app, client, auth_headers, sample_pdf_file):
        """Test complete compression workflow from upload to download"""
        with app.app_context():
            # Step 1: Upload file for compression
            with open(sample_pdf_file, 'rb') as f:
                response = client.post(
                    '/api/compress',
                    data={
                        'file': (f, 'test.pdf'),
                        'compressionLevel': 'medium'
                    },
                    headers=auth_headers
                )
            
            assert response.status_code == 200
            job_data = response.get_json()
            job_id = job_data['job_id']
            
            # Step 2: Check job status
            response = client.get(f'/api/jobs/{job_id}/status', headers=auth_headers)
            assert response.status_code == 200
            
            # Step 3: Download compressed file (assuming job completes)
            # In real tests, you might need to wait or mock completion
            response = client.get(f'/api/jobs/{job_id}/download', headers=auth_headers)
            
            # Verify download response
            assert response.status_code == 200
            assert response.headers['Content-Type'] == 'application/pdf'
```

### Service Integration Testing

```python
from src.services.file_management_service import FileManagementService
from src.services.compression_service import CompressionService

def test_service_integration(self, app, temp_upload_folder):
    """Test integration between multiple services"""
    with app.app_context():
        # Initialize services
        file_service = FileManagementService(upload_folder=temp_upload_folder)
        compression_service = CompressionService()
        
        # Create test file
        test_file_data = b'%PDF-1.4 test content'
        file_id, file_path = file_service.save_file(test_file_data, 'test.pdf')
        
        # Test file processing pipeline
        assert file_service.file_exists(file_path) is True
        compression_result = compression_service.compress_pdf(file_path, 'medium')
        
        assert compression_result['success'] is True
        assert os.path.exists(compression_result['output_path'])
        
        # Test cleanup
        cleanup_result = file_service.cleanup_expired_jobs()
        assert cleanup_result['files_cleaned'] >= 0
```

## Test Data Management

### Test Data Organization

```
tests/fixtures/
├── sample_files/
│   ├── small_document.pdf      # < 1MB
│   ├── medium_document.pdf     # 1-10MB
│   ├── large_document.pdf      # > 10MB
│   ├── corrupted.pdf           # Corrupted file for error testing
│   ├── password_protected.pdf  # Password-protected PDF
│   └── empty.pdf              # Empty PDF file
├── test_data.json             # Test data configurations
└── database_fixtures.sql      # Database test data
```

### Dynamic Test Data Generation

```python
def create_test_pdf(size_mb=1, pages=1):
    """Create test PDF file with specified size and pages"""
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    
    for page in range(pages):
        c.drawString(100, 750, f"Test Page {page + 1}")
        # Add content to reach desired size
        content = "Test content " * (size_mb * 1000)
        c.drawString(100, 700, content[:1000])  # Truncate if too long
        c.showPage()
    
    c.save()
    buffer.seek(0)
    return buffer.getvalue()

@pytest.fixture
def large_pdf_file():
    """Create large PDF file for testing"""
    pdf_content = create_test_pdf(size_mb=15, pages=50)
    
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        f.write(pdf_content)
        f.flush()
        yield f.name
    
    os.unlink(f.name)
```

### Database Test Data

```python
@pytest.fixture
def sample_compression_jobs(app, test_user):
    """Create sample compression jobs for testing"""
    with app.app_context():
        jobs = []
        
        for i in range(5):
            job = CompressionJob(
                user_id=test_user.id,
                job_type='single',
                original_filename=f'test_{i}.pdf',
                status='completed' if i < 3 else 'pending',
                original_size=1024 * (i + 1),
                compressed_size=512 * (i + 1) if i < 3 else None
            )
            jobs.append(job)
            db.session.add(job)
        
        db.session.commit()
        yield jobs
```

## Running Tests

### Command Line Usage

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_compression_service.py

# Run specific test class
pytest tests/test_compression_service.py::TestCompressionService

# Run specific test method
pytest tests/test_compression_service.py::TestCompressionService::test_compress_pdf_success

# Run tests with verbose output
pytest -v

# Run tests with coverage
pytest --cov=src

# Run tests with coverage report
pytest --cov=src --cov-report=html

# Run tests in parallel
pytest -n auto

# Run only failed tests from last run
pytest --lf

# Run tests matching pattern
pytest -k "compression"

# Run tests with specific markers
pytest -m "slow"
```

### Test Configuration (pytest.ini)

```ini
[tool:pytest]
addopts = 
    -v
    --strict-markers
    --disable-warnings
    --cov=src
    --cov-report=term-missing
    --cov-report=html:htmlcov
    --cov-fail-under=80

testpaths = tests

markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests
    unit: marks tests as unit tests
    api: marks tests as API tests
    requires_redis: marks tests that require Redis
    requires_external: marks tests that require external services

filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
```

## Test Coverage

### Coverage Configuration (.coveragerc)

```ini
[run]
source = src
omit = 
    src/config/config.py
    src/main/wsgi.py
    */migrations/*
    */venv/*
    */tests/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    class .*\(Protocol\):
    @(abc\.)?abstractmethod

[html]
directory = htmlcov
```

### Coverage Targets

- **Overall Coverage**: 80% minimum
- **Critical Services**: 90% minimum
- **API Endpoints**: 85% minimum
- **Models**: 80% minimum
- **Utilities**: 75% minimum

### Coverage Analysis

```bash
# Generate coverage report
pytest --cov=src --cov-report=html

# View coverage in browser
open htmlcov/index.html

# Generate coverage badge
coverage-badge -o coverage.svg

# Check coverage thresholds
pytest --cov=src --cov-fail-under=80
```

## Continuous Integration

### GitHub Actions Configuration

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11]
    
    services:
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install system dependencies
      run: |
        sudo apt-get update
        sudo apt-get install -y ghostscript tesseract-ocr
    
    - name: Install Python dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests
      env:
        FLASK_ENV: testing
        REDIS_URL: redis://localhost:6379/15
      run: |
        pytest --cov=src --cov-report=xml
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        types: [python]
        pass_filenames: false
        always_run: true
        args: ["--cov=src", "--cov-fail-under=80"]
```

## Best Practices

### Test Design Principles

1. **FIRST Principles**:
   - **Fast**: Tests should run quickly
   - **Independent**: Tests should not depend on each other
   - **Repeatable**: Tests should produce consistent results
   - **Self-Validating**: Tests should have clear pass/fail results
   - **Timely**: Tests should be written close to the code they test

2. **AAA Pattern**:
   - **Arrange**: Set up test data and conditions
   - **Act**: Execute the code being tested
   - **Assert**: Verify the results

3. **Test Isolation**:
   - Each test should be independent
   - Use fresh database state for each test
   - Clean up resources after tests

### Writing Effective Tests

```python
def test_user_registration_success():
    """Test successful user registration with valid data"""
    # Arrange
    user_data = {
        'email': 'newuser@example.com',
        'password': 'SecurePassword123',
        'name': 'New User'
    }
    
    # Act
    response = client.post('/api/auth/register', json=user_data)
    
    # Assert
    assert response.status_code == 201
    data = response.get_json()
    assert data['success'] is True
    assert 'user_id' in data
    
    # Verify user was created in database
    user = User.query.filter_by(email=user_data['email']).first()
    assert user is not None
    assert user.name == user_data['name']
```

### Error Testing

```python
def test_error_scenarios():
    """Test various error conditions"""
    service = CompressionService()
    
    # Test file not found
    with pytest.raises(FileNotFoundError):
        service.compress_pdf('nonexistent.pdf', 'medium')
    
    # Test invalid compression level
    with pytest.raises(ValidationError) as exc_info:
        service.compress_pdf('test.pdf', 'invalid_level')
    
    assert 'Invalid compression level' in str(exc_info.value)
    
    # Test corrupted file
    with pytest.raises(CompressionError):
        service.compress_pdf('corrupted.pdf', 'medium')
```

### Performance Testing

```python
import time

def test_compression_performance():
    """Test compression performance benchmarks"""
    service = CompressionService()
    
    start_time = time.time()
    result = service.compress_pdf('large_file.pdf', 'medium')
    end_time = time.time()
    
    processing_time = end_time - start_time
    
    # Assert performance requirements
    assert processing_time < 30.0  # Should complete within 30 seconds
    assert result['success'] is True
    
    # Log performance metrics
    print(f"Compression took {processing_time:.2f} seconds")
```

### Test Documentation

```python
class TestCompressionService:
    """
    Test suite for CompressionService
    
    This test suite covers:
    - PDF compression functionality
    - Settings validation
    - Error handling
    - Performance requirements
    
    Prerequisites:
    - Ghostscript installed
    - Test PDF files available
    - Temporary directory access
    """
    
    def test_compress_pdf_medium_quality(self):
        """
        Test PDF compression with medium quality settings
        
        This test verifies that:
        1. PDF files are compressed successfully
        2. Output file size is smaller than input
        3. Compression ratio meets expectations
        4. Output file is valid PDF
        
        Expected behavior:
        - Compression ratio: 30-70%
        - Processing time: < 10 seconds for 5MB file
        - Output file maintains readability
        """
        # Test implementation...
```

### Debugging Tests

```python
# Add debugging information to tests
def test_with_debugging(caplog):
    """Test with debugging output"""
    with caplog.at_level(logging.DEBUG):
        service = CompressionService()
        result = service.compress_pdf('test.pdf', 'medium')
    
    # Check log messages
    assert 'Starting compression' in caplog.text
    assert 'Compression completed' in caplog.text
    
    # Print debug information
    print(f"Compression result: {result}")
    print(f"Log messages: {caplog.messages}")

# Use pytest debugging features
# pytest --pdb  # Drop into debugger on failures
# pytest --pdbcls=IPython.terminal.debugger:Pdb  # Use IPython debugger
```

---

*This testing guide should be updated as new testing patterns and requirements are identified. Always maintain comprehensive test coverage and follow established testing best practices.*