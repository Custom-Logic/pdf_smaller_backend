"""Test configuration and fixtures for PDF Smaller Backend."""

import pytest
import tempfile
import os
from unittest.mock import Mock, patch

# Import Flask and extensions
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Import application components
from src.app import create_app
from src.extensions import db as _db
from src.celery_app import make_celery
from src.models.job import Job, JobStatus, TaskType


@pytest.fixture(scope='session')
def app():
    """Create application for the tests."""
    # Create test configuration
    test_config = {
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'CELERY_BROKER_URL': 'memory://',
        'CELERY_RESULT_BACKEND': 'cache+memory://',
        'SECRET_KEY': 'test-secret-key',
        'WTF_CSRF_ENABLED': False,
        'UPLOAD_FOLDER': tempfile.mkdtemp(),
        'MAX_CONTENT_LENGTH': 16 * 1024 * 1024,  # 16MB
    }
    
    # Create Flask app with test config
    app = create_app(test_config)
    
    # Establish application context
    with app.app_context():
        yield app


@pytest.fixture(scope='session')
def db(app):
    """Create database for the tests."""
    _db.app = app
    with app.app_context():
        _db.create_all()
        yield _db
        _db.drop_all()


@pytest.fixture(scope='function')
def session(db):
    """Create a fresh database session for each test."""
    connection = db.engine.connect()
    transaction = connection.begin()
    
    options = dict(bind=connection, binds={})
    session = db.create_scoped_session(options=options)
    
    db.session = session
    
    yield session
    
    transaction.rollback()
    connection.close()
    session.remove()


@pytest.fixture(scope='function')
def db_session(db):
    """Create a fresh database session for each test (alias for session)."""
    connection = db.engine.connect()
    transaction = connection.begin()
    
    options = dict(bind=connection, binds={})
    session = db.create_scoped_session(options=options)
    
    db.session = session
    
    yield session
    
    transaction.rollback()
    connection.close()
    session.remove()


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test runner for the Flask CLI commands."""
    return app.test_cli_runner()


@pytest.fixture
def celery_app(app):
    """Create Celery app for testing."""
    celery = make_celery(app)
    celery.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
        broker_url='memory://',
        result_backend='cache+memory://',
    )
    return celery


@pytest.fixture
def sample_job(session):
    """Create a sample job for testing."""
    job = Job(
        job_id='test-job-123',
        task_type=TaskType.COMPRESSION,
        status=JobStatus.PENDING,
        input_data={'file_path': '/tmp/test.pdf'},
        result=None,
        error=None
    )
    session.add(job)
    session.commit()
    return job


@pytest.fixture
def temp_pdf_file():
    """Create a temporary PDF file for testing."""
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
        # Write minimal PDF content
        f.write(b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n')
        f.write(b'2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n')
        f.write(b'3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n>>\nendobj\n')
        f.write(b'xref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n')
        f.write(b'0000000074 00000 n \n0000000120 00000 n \n')
        f.write(b'trailer\n<<\n/Size 4\n/Root 1 0 R\n>>\nstartxref\n202\n%%EOF')
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def mock_services():
    """Mock all service dependencies."""
    services = {
        'compression_service': Mock(),
        'conversion_service': Mock(),
        'ocr_service': Mock(),
        'ai_service': Mock(),
        'file_management_service': Mock(),
        'extraction_service': Mock(),
    }
    
    # Configure default return values
    services['compression_service'].compress_pdf.return_value = {
        'output_path': '/tmp/compressed.pdf',
        'original_size': 1000000,
        'compressed_size': 500000,
        'compression_ratio': 0.5
    }
    
    services['conversion_service'].convert_pdf.return_value = {
        'output_path': '/tmp/converted.pdf',
        'format': 'pdf',
        'pages': 1
    }
    
    services['ocr_service'].process_pdf.return_value = {
        'text': 'Sample extracted text',
        'confidence': 0.95,
        'pages': 1
    }
    
    services['ai_service'].summarize_text.return_value = {
        'summary': 'This is a summary',
        'word_count': 100
    }
    
    services['file_management_service'].merge_pdfs.return_value = {
        'success': True,
        'page_count': 10
    }
    
    services['extraction_service'].extract_invoice_data.return_value = {
        'invoice_number': 'INV-001',
        'total_amount': 100.00,
        'date': '2024-01-15'
    }
    
    return services


@pytest.fixture
def mock_task_context():
    """Mock task context manager."""
    mock_progress = Mock()
    mock_progress.current_step = 0
    mock_progress.total_steps = 5
    mock_progress.progress_percentage = 0.0
    
    mock_temp_manager = Mock()
    mock_temp_manager.create_temp_file.return_value = '/tmp/test_file.pdf'
    mock_temp_manager.create_temp_dir.return_value = '/tmp/test_dir'
    
    with patch('src.tasks.utils.task_context') as mock_context:
        mock_context.return_value.__enter__.return_value = (mock_progress, mock_temp_manager)
        mock_context.return_value.__exit__.return_value = None
        yield mock_context, mock_progress, mock_temp_manager


@pytest.fixture(autouse=True)
def mock_external_services(mock_services):
    """Automatically mock external services for all tests."""
    patches = []
    
    for service_name, mock_service in mock_services.items():
        patch_path = f'src.tasks.tasks.{service_name}'
        patcher = patch(patch_path, mock_service)
        patches.append(patcher)
        patcher.start()
    
    yield
    
    # Stop all patches
    for patcher in patches:
        patcher.stop()


@pytest.fixture
def mock_file_system():
    """Mock file system operations."""
    with patch('os.path.exists') as mock_exists, \
         patch('os.path.getsize') as mock_getsize, \
         patch('os.unlink') as mock_unlink, \
         patch('shutil.rmtree') as mock_rmtree:
        
        mock_exists.return_value = True
        mock_getsize.return_value = 1000000  # 1MB
        
        yield {
            'exists': mock_exists,
            'getsize': mock_getsize,
            'unlink': mock_unlink,
            'rmtree': mock_rmtree
        }


# Test markers for categorizing tests
pytestmark = [
    pytest.mark.tasks,  # All tests in this module are task-related
]


# Custom assertions
def assert_job_status(job, expected_status):
    """Assert that a job has the expected status."""
    assert job.status == expected_status, f"Expected job status {expected_status}, got {job.status}"


def assert_task_result_success(result):
    """Assert that a task result indicates success."""
    assert result is not None, "Task result should not be None"
    assert isinstance(result, dict), "Task result should be a dictionary"
    assert result.get('success', False), f"Task should succeed, got result: {result}"


def assert_task_metrics(metrics, expected_files=None, expected_size=None):
    """Assert task metrics meet expectations."""
    if expected_files is not None:
        assert metrics.files_processed >= expected_files
    if expected_size is not None:
        assert metrics.total_size_processed >= expected_size