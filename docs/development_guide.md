# Development Guide

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Environment Setup](#development-environment-setup)
3. [Project Structure](#project-structure)
4. [Coding Standards](#coding-standards)
5. [Development Workflow](#development-workflow)
6. [Testing Guidelines](#testing-guidelines)
7. [Database Management](#database-management)
8. [API Development](#api-development)
9. [Service Layer Guidelines](#service-layer-guidelines)
10. [AI Service Configuration](#ai-service-configuration)
11. [Error Handling](#error-handling)
12. [Security Best Practices](#security-best-practices)
13. [Performance Considerations](#performance-considerations)
14. [Contribution Guidelines](#contribution-guidelines)
15. [Common Pitfalls](#common-pitfalls)
16. [Troubleshooting](#troubleshooting)

## Getting Started

### Prerequisites

- Python 3.8+
- Redis server
- SQLite (for development) or PostgreSQL (for production)
- Git
- Virtual environment tool (venv, virtualenv, or conda)

### Quick Setup

```bash
# Clone the repository
git clone <repository-url>
cd pdf_smaller_backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your configuration

# Initialize database
python manage_db.py init

# Run the application
python app.py
```

## Development Environment Setup

### Environment Configuration

1. **Environment Variables**: Always use `.env` files for configuration
   - Never commit sensitive data to version control
   - Use `.env.example` as a template
   - Document all required environment variables

2. **Database Setup**:
   ```bash
   # Development (SQLite)
   python manage_db.py init
   
   # Production (PostgreSQL)
   # Set DATABASE_URL in .env first
   python manage_db.py init --production
   ```

3. **Redis Configuration**:
   - Required for Celery task queue
   - Default: `redis://localhost:6379/0`
   - Configure in `.env`: `REDIS_URL=redis://localhost:6379/0`

### IDE Configuration

- **Recommended**: PyCharm, VS Code, or similar
- **Linting**: Use flake8 or pylint
- **Formatting**: Use black for code formatting
- **Type Checking**: Use mypy for static type checking

## Project Structure

```
src/
├── config/          # Configuration management
├── database/        # Database initialization and migrations
├── main/           # Application entry point
├── models/         # Database models
├── routes/         # API route definitions
├── services/       # Business logic layer
├── tasks/          # Celery background tasks
└── utils/          # Utility functions and helpers
```

### Key Principles

1. **Separation of Concerns**: Keep routes, services, and models separate
2. **Single Responsibility**: Each module should have one clear purpose
3. **Dependency Injection**: Use dependency injection for testability
4. **Configuration Management**: Centralize all configuration in `config/`

## Coding Standards

### Python Style Guide

- Follow PEP 8 style guidelines
- Use meaningful variable and function names
- Maximum line length: 88 characters (Black default)
- Use type hints for all function parameters and return values

### Code Organization

```python
# File structure template
"""Module docstring describing the purpose."""

# Standard library imports
import os
import sys

# Third-party imports
from flask import Flask, request
from celery import Celery

# Local imports
from src.config import Config
from src.utils import validation

# Constants
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

# Classes and functions
class ServiceClass:
    """Class docstring."""
    pass
```

### Documentation Standards

```python
def process_pdf(file_path: str, compression_level: str = 'medium') -> dict:
    """
    Process a PDF file with specified compression level.
    
    Args:
        file_path: Path to the PDF file to process
        compression_level: Compression level ('low', 'medium', 'high', 'maximum')
        
    Returns:
        Dictionary containing processing results with keys:
        - original_size: Original file size in bytes
        - compressed_size: Compressed file size in bytes
        - compression_ratio: Compression ratio as percentage
        - output_path: Path to the compressed file
        
    Raises:
        FileNotFoundError: If the input file doesn't exist
        ValidationError: If compression_level is invalid
        ProcessingError: If PDF processing fails
    """
    pass
```

## Development Workflow

### Branch Strategy

1. **main**: Production-ready code
2. **develop**: Integration branch for features
3. **feature/**: Feature development branches
4. **hotfix/**: Critical bug fixes

### Commit Guidelines

```
type(scope): description

Types:
- feat: New feature
- fix: Bug fix
- docs: Documentation changes
- style: Code style changes
- refactor: Code refactoring
- test: Test additions/modifications
- chore: Maintenance tasks

Examples:
feat(compression): add bulk compression support
fix(api): handle file upload validation errors
docs(readme): update installation instructions
```

### Code Review Process

1. Create feature branch from `develop`
2. Implement feature with tests
3. Create pull request to `develop`
4. Code review by team member
5. Address feedback and merge

## Testing Guidelines

### Test Structure

```
tests/
├── conftest.py          # Pytest configuration and fixtures
├── test_*.py           # Test modules
└── fixtures/           # Test data and fixtures
```

### Writing Tests

```python
import pytest
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
```

### Test Coverage

- Aim for 80%+ code coverage
- Focus on critical business logic
- Test error conditions and edge cases
- Use mocking for external dependencies

## Database Management

### Model Guidelines

```python
from src.models.base import BaseModel
from sqlalchemy import Column, String, Integer, DateTime

class CompressionJob(BaseModel):
    """Model for tracking compression jobs."""
    
    __tablename__ = 'compression_jobs'
    
    # Always include these fields
    id = Column(String, primary_key=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    
    # Business-specific fields
    status = Column(String, nullable=False)
    original_filename = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    
    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {
            'id': self.id,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
```

### Migration Guidelines

1. Always create migrations for schema changes
2. Test migrations on sample data
3. Include rollback procedures
4. Document breaking changes

## API Development

### Route Structure

```python
from src.services.compression_service import CompressionService
from src.services.file_management_service import FileManagementService
from src.utils.validation import validate_file
from src.utils.response_helpers import success_response, error_response

compression_bp = Blueprint('compression', __name__)

@compression_bp.route('/api/compress', methods=['POST'])
def compress_pdf():
    """Compress a PDF file."""
    try:
        # Validate request
        if 'file' not in request.files:
            return error_response('No file provided', 400)
        
        file = request.files['file']
        validate_file(file)
        
        # Process request with optional file service injection
        file_service = FileManagementService()  # Optional: for custom configuration
        service = CompressionService(file_service=file_service)
        result = service.compress_pdf_async(file)
        
        return success_response(result, 202)
        
    except ValidationError as e:
        return error_response(str(e), 400)
    except Exception as e:
        logger.error(f"Compression failed: {e}")
        return error_response('Internal server error', 500)
```

### Response Format Standards

```python
# Success Response
{
    "success": true,
    "data": {
        "job_id": "uuid-string",
        "status": "pending"
    },
    "message": "Job queued successfully"
}

# Error Response
{
    "success": false,
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "Invalid file format",
        "details": {
            "field": "file",
            "allowed_formats": ["pdf"]
        }
    }
}
```

## Service Layer Guidelines

### Service Structure

```python
from typing import Optional
from src.services.file_management_service import FileManagementService

class CompressionService:
    """Service for handling PDF compression operations."""
    
    def __init__(self, config: Config = None, file_service: Optional[FileManagementService] = None):
        self.config = config or Config()
        self.file_service = file_service or FileManagementService()
        
    def compress_pdf(self, file_path: str, options: dict) -> dict:
        """Synchronous PDF compression."""
        # Implementation
        pass
        
    def compress_pdf_async(self, file_path: str, options: dict) -> dict:
        """Asynchronous PDF compression using Celery."""
        from src.tasks.tasks import compress_pdf_task
        
        job_id = str(uuid.uuid4())
        task = compress_pdf_task.delay(job_id, file_path, options)
        
        return {
            'job_id': job_id,
            'task_id': task.id,
            'status': 'pending'
        }
```

### Service Best Practices

1. **Single Responsibility**: Each service handles one domain
2. **Dependency Injection**: Accept dependencies in constructor (especially FileManagementService)
3. **Centralized File Operations**: Use FileManagementService for all file operations
4. **Consistent Error Handling**: Use standardized exceptions and cleanup patterns
3. **Error Handling**: Use custom exceptions for business logic errors
4. **Logging**: Log important operations and errors
5. **Configuration**: Use configuration objects, not global variables

## AI Service Configuration

### Overview

The AI Service provides document processing capabilities including summarization and translation using various AI models through OpenRouter.

### Configuration

#### Environment Variables

Configure AI service in your `.env` file:

```bash
# OpenRouter Configuration
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_DEFAULT_MODEL=deepseek/deepseek-v3-free
OPENROUTER_MAX_TOKENS=4000
OPENROUTER_TIMEOUT=30
OPENROUTER_REFERER=https://www.pdfsmaller.site
OPENROUTER_TITLE=PDF Smaller
```

#### Available Models

The AI service supports multiple model providers through OpenRouter:

**DeepSeek Models** (Cost-effective):
- `deepseek/deepseek-v3` - Latest DeepSeek model
- `deepseek/deepseek-v3-free` - Free tier (default)
- `deepseek/deepseek-chat` - Optimized for conversations
- `deepseek/deepseek-coder` - Code-focused model
- `deepseek/deepseek-r1` - Reasoning-focused model

**Moonshot Models** (Good balance):
- `moonshot/moonshot-k2-free` - Free tier
- `moonshot/moonshot-k2-premium` - Premium version
- `moonshot/moonshot-v1-32k` - 32K context window
- `moonshot/moonshot-v1-128k` - 128K context window

**OpenAI Models**:
- `openai/gpt-4-turbo` - Latest GPT-4
- `openai/gpt-3.5-turbo` - Most affordable OpenAI option

**Anthropic Models**:
- `anthropic/claude-3-haiku` - Fastest and most affordable
- `anthropic/claude-3-sonnet` - Balanced performance
- `anthropic/claude-3-opus` - Highest capability

### Usage Examples

#### Basic Service Usage

```python
from src.services.ai_service import AIService

# Initialize service (uses environment configuration)
ai_service = AIService()

# Check available models
models = ai_service.get_available_models()
print(f"Available models: {len(models['openrouter'])}")

# Test connectivity
status = ai_service.test_connectivity()
if status['success']:
    print("AI service is ready")
else:
    print(f"AI service error: {status['error']}")
```

#### Document Summarization

```python
# Prepare summarization job
job_data = {
    'job_id': 'summary-123',
    'file_path': '/path/to/document.pdf',
    'style': 'professional',  # concise, detailed, academic, casual, professional
    'model': 'deepseek/deepseek-v3-free',  # Optional: override default
    'provider': 'openrouter'
}

# Process summarization
result = ai_service.process_summarization_job(job_data)

if result['success']:
    print(f"Summary: {result['summary']}")
    print(f"Word count: {result['metadata']['word_count']}")
else:
    print(f"Error: {result['error']}")
```

#### Document Translation

```python
# Prepare translation job
job_data = {
    'job_id': 'translate-456',
    'file_path': '/path/to/document.pdf',
    'target_language': 'es',  # Spanish
    'quality': 'balanced',  # fast, balanced, high_quality
    'preserve_formatting': True,
    'model': 'moonshot/moonshot-v1-32k',  # Good for longer documents
    'provider': 'openrouter'
}

# Process translation
result = ai_service.process_translation_job(job_data)

if result['success']:
    print(f"Translated text: {result['translated_text']}")
    print(f"Source language detected: {result['metadata']['source_language']}")
else:
    print(f"Error: {result['error']}")
```

### Model Selection Guidelines

#### Cost Considerations

```python
# Get cost guidance from ModelConfig
from src.services.ai_service import ModelConfig

model_config = ModelConfig()
cost_info = model_config.estimate_cost_considerations()

# Most cost-effective options
print("Most cost-effective:", cost_info['most_cost_effective'])
# Best value for capability
print("Best value:", cost_info['best_value'])
# Premium options
print("Premium capability:", cost_info['premium_capability'])
```

#### Task-Specific Recommendations

- **Quick summaries**: `deepseek/deepseek-v3-free`, `anthropic/claude-3-haiku`
- **Long documents**: `moonshot/moonshot-v1-128k`, `openai/gpt-4-turbo`
- **Technical content**: `deepseek/deepseek-coder`, `deepseek/deepseek-r1`
- **High accuracy**: `anthropic/claude-3-opus`, `openai/gpt-4-turbo`

### Error Handling

```python
from src.services.ai_service import AIService
from src.utils.exceptions import AIServiceError

try:
    ai_service = AIService()
    result = ai_service.process_summarization_job(job_data)
except AIServiceError as e:
    logger.error(f"AI service error: {e}")
    # Handle AI-specific errors (API limits, model unavailable, etc.)
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    # Handle general errors
```

### Best Practices

1. **Model Selection**: Choose models based on task requirements and cost constraints
2. **Error Handling**: Always handle API failures gracefully
3. **Rate Limiting**: Respect API rate limits and implement backoff strategies
4. **Monitoring**: Monitor API usage and costs
5. **Fallbacks**: Consider fallback models for high availability
6. **Caching**: Cache results when appropriate to reduce API calls

### Testing AI Service

```python
import pytest
from unittest.mock import Mock, patch
from src.services.ai_service import AIService

class TestAIService:
    """Test cases for AI Service."""
    
    @patch('requests.post')
    def test_summarization_success(self, mock_post):
        """Test successful summarization."""
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': '{"summary": "Test summary", "word_count": 50}'
                }
            }]
        }
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Test service
        service = AIService()
        result = service.process_summarization_job({
            'job_id': 'test-job',
            'text': 'Test document content',
            'style': 'concise'
        })
        
        assert result['success'] is True
        assert 'summary' in result
    
    def test_connectivity(self):
        """Test AI service connectivity."""
        service = AIService()
        status = service.test_connectivity()
        
        # Should return status dict with success field
        assert 'success' in status
        assert 'timestamp' in status
```

## Error Handling

### Custom Exceptions

```python
class PDFProcessingError(Exception):
    """Base exception for PDF processing errors."""
    pass

class ValidationError(PDFProcessingError):
    """Raised when input validation fails."""
    pass

class FileNotFoundError(PDFProcessingError):
    """Raised when required file is not found."""
    pass
```

### Error Handler Registration

```python
from flask import Flask
from src.utils.error_handlers import register_error_handlers

def create_app():
    app = Flask(__name__)
    register_error_handlers(app)
    return app
```

## Security Best Practices

### File Upload Security

1. **File Validation**: Always validate file types and sizes
2. **Sanitization**: Sanitize file names and paths
3. **Storage**: Store uploads outside web root
4. **Scanning**: Consider virus scanning for uploaded files

### API Security

1. **Rate Limiting**: Implement rate limiting on all endpoints
2. **Input Validation**: Validate all input parameters
3. **CORS**: Configure CORS appropriately
4. **Headers**: Set security headers

### Environment Security

1. **Secrets**: Never commit secrets to version control
2. **Environment Variables**: Use environment variables for sensitive data
3. **Permissions**: Set appropriate file and directory permissions

## Performance Considerations

### File Processing

1. **Async Processing**: Use Celery for long-running tasks
2. **File Cleanup**: Implement automatic file cleanup
3. **Memory Management**: Monitor memory usage for large files
4. **Caching**: Cache frequently accessed data

### Database Optimization

1. **Indexing**: Add indexes for frequently queried fields
2. **Connection Pooling**: Use connection pooling for database connections
3. **Query Optimization**: Optimize database queries
4. **Pagination**: Implement pagination for large result sets

## Contribution Guidelines

### Before Contributing

1. Read this development guide thoroughly
2. Set up the development environment
3. Run existing tests to ensure everything works
4. Check the issue tracker for open tasks

### Making Changes

1. Create a feature branch from `develop`
2. Write tests for new functionality
3. Ensure all tests pass
4. Update documentation if needed
5. Follow the commit message format
6. Create a pull request

### Code Review Checklist

- [ ] Code follows style guidelines
- [ ] Tests are included and passing
- [ ] Documentation is updated
- [ ] No security vulnerabilities introduced
- [ ] Performance impact considered
- [ ] Error handling is appropriate

## Common Pitfalls

### File Handling

❌ **Don't**:
```python
# Unsafe file handling
filename = request.files['file'].filename
file_path = f"/uploads/{filename}"
```

✅ **Do**:
```python
# Safe file handling with FileManagementService
from src.services.file_management_service import FileManagementService

file_service = FileManagementService()
file_path = file_service.save_file(request.files['file'])
```

### Service Instantiation

❌ **Don't**:
```python
# Direct instantiation without dependency injection
service = CompressionService()
service.upload_folder = "/some/path"  # Manual configuration
```

✅ **Do**:
```python
# Proper dependency injection
file_service = FileManagementService()  # Optional: for custom config
service = CompressionService(file_service=file_service)

# Or use default (recommended for most cases)
service = CompressionService()  # FileManagementService auto-created
```

### Database Operations

❌ **Don't**:
```python
# No error handling
job = CompressionJob.query.get(job_id)
result = job.to_dict()
```

✅ **Do**:
```python
# Proper error handling
job = CompressionJob.query.get(job_id)
if not job:
    raise JobNotFoundError(f"Job {job_id} not found")
result = job.to_dict()
```

### Exception Handling

❌ **Don't**:
```python
# Generic exception handling
try:
    result = process_file(file_path)
except Exception as e:
    logger.error(f"Processing failed: {e}")
    raise
```

✅ **Do**:
```python
# Specific exception handling with intelligent retry logic
from sqlalchemy.exc import DBAPIError, OperationalError, IntegrityError
from src.exceptions.extraction_exceptions import ExtractionError, ExtractionValidationError
from celery.exceptions import Ignore, Retry

try:
    result = process_file(file_path)
except (DBAPIError, OperationalError, IntegrityError) as db_e:
    logger.error(f"Database error: {db_e}")
    # Retry database errors with exponential backoff
    if self.request.retries < self.max_retries:
        raise self.retry(countdown=60 * (self.request.retries + 1))
    raise
except ExtractionValidationError as val_e:
    logger.error(f"Validation error: {val_e}")
    # Don't retry validation errors
    raise Ignore()
except ExtractionError as ext_e:
    logger.error(f"Extraction error: {ext_e}")
    # Retry extraction errors
    if self.request.retries < self.max_retries:
        raise self.retry(countdown=60 * (self.request.retries + 1))
    raise
except EnvironmentError as env_e:
    logger.error(f"Environment error: {env_e}")
    # Don't retry environment errors (missing dependencies)
    raise Ignore()
```

### Configuration

❌ **Don't**:
```python
# Hardcoded values
MAX_FILE_SIZE = 50 * 1024 * 1024
```

✅ **Do**:
```python
# Configuration-driven
MAX_FILE_SIZE = Config.get('MAX_FILE_SIZE', 50 * 1024 * 1024)
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Check Python path and virtual environment
2. **Database Connection**: Verify database configuration and connectivity
3. **Redis Connection**: Ensure Redis server is running
4. **File Permissions**: Check file and directory permissions
5. **Memory Issues**: Monitor memory usage during file processing

### Debugging Tips

1. **Logging**: Use appropriate log levels and structured logging
2. **Error Messages**: Provide clear, actionable error messages
3. **Stack Traces**: Include full stack traces in development
4. **Monitoring**: Use monitoring tools to track application health

### Getting Help

1. Check the troubleshooting guide
2. Review existing issues and documentation
3. Ask team members for guidance
4. Create detailed issue reports with reproduction steps

---

**Remember**: This guide is a living document. Update it as the project evolves and new patterns emerge. Good documentation prevents mistakes and accelerates development for everyone on the team.