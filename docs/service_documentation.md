# PDF Smaller Backend - Service Documentation

This document provides comprehensive documentation for all service classes in the PDF Smaller backend, including their methods, dependencies, and usage patterns.

## Table of Contents

1. [Service Architecture Overview](#service-architecture-overview)
2. [Core Services](#core-services)
3. [Processing Services](#processing-services)
4. [Utility Services](#utility-services)
5. [Service Dependencies](#service-dependencies)
6. [Usage Patterns](#usage-patterns)
7. [Error Handling](#error-handling)
8. [Testing Services](#testing-services)

## Service Architecture Overview

### Design Principles

All services in the PDF Smaller backend follow a consistent job-oriented architecture:

- **Stateless Design**: Services don't maintain state between operations
- **Job-Oriented Processing**: All operations are modeled as jobs with unique identifiers
- **Dependency Injection**: Services accept configuration and dependencies through constructors
- **Error Handling**: Comprehensive error handling with custom exceptions
- **Logging**: Structured logging for debugging and monitoring

### Service Pattern

```python
class ServiceName:
    """Service description and purpose"""
    
    def __init__(self, config_params):
        # Initialize service with configuration
        # Set up dependencies and validate requirements
        
    def process_job(self, job_data: Dict) -> Dict:
        # Main processing method
        # Returns standardized result format
        
    def validate_input(self, input_data: Dict) -> bool:
        # Input validation logic
        
    def cleanup_resources(self, job_id: str):
        # Resource cleanup after processing
```

## Core Services

### CompressionService

**Location**: `src/services/compression_service.py`

**Purpose**: Handles PDF compression operations using Ghostscript

**Dependencies**:
- Ghostscript (external binary)
- FileManager
- Configuration

**Key Methods**:

```python
def __init__(self, config: Config = None):
    """Initialize compression service with configuration"""
    
def compress_pdf(self, input_path: str, output_path: str, quality: str = 'medium') -> Dict:
    """Compress PDF file synchronously
    
    Args:
        input_path: Path to input PDF file
        output_path: Path for compressed output
        quality: Compression quality ('low', 'medium', 'high')
        
    Returns:
        Dict with compression results and metadata
    """
    
def compress_pdf_async(self, job_id: str, input_path: str, options: Dict) -> str:
    """Start asynchronous PDF compression job
    
    Args:
        job_id: Unique job identifier
        input_path: Path to input PDF
        options: Compression options
        
    Returns:
        Task ID for tracking
    """
    
def get_compression_info(self, file_path: str) -> Dict:
    """Get PDF file information for compression analysis
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        Dict with file metadata and compression potential
    """
```

**Configuration Options**:
- `quality_settings`: Ghostscript quality parameters
- `max_file_size`: Maximum input file size
- `timeout`: Processing timeout in seconds

**Usage Example**:
```python
from src.services.compression_service import CompressionService

service = CompressionService()
result = service.compress_pdf(
    input_path='/path/to/input.pdf',
    output_path='/path/to/output.pdf',
    quality='medium'
)
```

### FileManager

**Location**: `src/services/file_manager.py`

**Purpose**: Manages file operations, storage, and cleanup

**Dependencies**:
- Configuration
- File utilities

**Key Methods**:

```python
def __init__(self, upload_folder: str = None):
    """Initialize file manager with upload directory"""
    
def save_file(self, file_data: bytes, original_filename: str = None) -> Tuple[str, str]:
    """Save file data with unique filename
    
    Args:
        file_data: Binary file data
        original_filename: Original filename for extension
        
    Returns:
        Tuple of (unique_id, file_path)
    """
    
def get_file_path(self, file_id: str) -> str:
    """Get full path for file by ID
    
    Args:
        file_id: Unique file identifier
        
    Returns:
        Full file path
    """
    
def delete_file(self, file_path: str) -> bool:
    """Delete file from storage
    
    Args:
        file_path: Path to file to delete
        
    Returns:
        True if successful, False otherwise
    """
    
def cleanup_old_files(self, max_age_hours: int = 24) -> int:
    """Clean up files older than specified age
    
    Args:
        max_age_hours: Maximum file age in hours
        
    Returns:
        Number of files deleted
    """
```

## Processing Services

### OCRService

**Location**: `src/services/ocr_service.py`

**Purpose**: Optical Character Recognition for PDFs and images

**Dependencies**:
- Tesseract OCR (external)
- PyMuPDF (fitz)
- PIL/Pillow
- FileManager

**Key Methods**:

```python
def __init__(self, upload_folder: str = None):
    """Initialize OCR service with processing directory"""
    
def process_ocr_job(self, job_data: Dict) -> Dict:
    """Process OCR job on PDF or image
    
    Args:
        job_data: Job configuration with file path and options
        
    Returns:
        Dict with OCR results and metadata
    """
    
def extract_text_from_pdf(self, pdf_path: str, language: str = 'eng') -> str:
    """Extract text from PDF using OCR
    
    Args:
        pdf_path: Path to PDF file
        language: OCR language code
        
    Returns:
        Extracted text content
    """
    
def create_searchable_pdf(self, input_path: str, output_path: str, language: str = 'eng') -> Dict:
    """Create searchable PDF from image-based PDF
    
    Args:
        input_path: Path to input PDF
        output_path: Path for searchable output
        language: OCR language
        
    Returns:
        Processing results and statistics
    """
```

**Supported Languages**:
- English (eng), Spanish (spa), French (fra), German (deu)
- Italian (ita), Portuguese (por), Russian (rus), Japanese (jpn)
- Korean (kor), Chinese Simplified (chi_sim), Arabic (ara), Hindi (hin)

**Quality Levels**:
- `fast`: Quick processing with basic accuracy
- `balanced`: Good balance of speed and accuracy
- `accurate`: Highest accuracy, slower processing

### AIService

**Location**: `src/services/ai_service.py`

**Purpose**: AI-powered document processing (summarization, translation)

**Dependencies**:
- OpenRouter API
- OpenAI API (optional)
- Anthropic API (optional)
- ConversionService

**Key Methods**:

```python
def __init__(self):
    """Initialize AI service with API configurations"""
    
def process_summarization_job(self, job_data: Dict) -> Dict:
    """Generate document summary using AI
    
    Args:
        job_data: Job with file path and summarization options
        
    Returns:
        Dict with summary and metadata
    """
    
def process_translation_job(self, job_data: Dict) -> Dict:
    """Translate document content using AI
    
    Args:
        job_data: Job with file path and translation options
        
    Returns:
        Dict with translated content and metadata
    """
    
def get_available_models(self) -> List[Dict[str, Any]]:
    """Get list of available AI models
    
    Returns:
        List of model information dictionaries
    """
```

**Supported AI Providers**:
- OpenRouter (primary)
- OpenAI (direct)
- Anthropic (direct)

**Available Models**:
- GPT-4 Turbo, GPT-4, GPT-3.5 Turbo
- Claude-3 Opus, Sonnet, Haiku
- Gemini Pro, Mistral Large, Llama-3 70B

### ConversionService

**Location**: `src/services/conversion_service.py`

**Purpose**: Convert PDFs to various formats (DOCX, TXT, HTML, Images)

**Dependencies**:
- PyMuPDF (fitz)
- python-docx
- pdfplumber
- PIL/Pillow

**Key Methods**:

```python
def __init__(self, upload_folder: str = None):
    """Initialize conversion service"""
    
def process_conversion_job(self, job_data: Dict) -> Dict:
    """Convert PDF to specified format
    
    Args:
        job_data: Job with file path and conversion options
        
    Returns:
        Dict with conversion results
    """
    
def convert_to_docx(self, pdf_path: str, output_path: str) -> Dict:
    """Convert PDF to Word document
    
    Args:
        pdf_path: Input PDF path
        output_path: Output DOCX path
        
    Returns:
        Conversion results and metadata
    """
    
def convert_to_images(self, pdf_path: str, output_dir: str, format: str = 'png') -> Dict:
    """Convert PDF pages to images
    
    Args:
        pdf_path: Input PDF path
        output_dir: Directory for image files
        format: Image format (png, jpg, tiff)
        
    Returns:
        List of generated image files
    """
```

**Supported Output Formats**:
- DOCX (Word documents)
- TXT (plain text)
- HTML (web format)
- Images (PNG, JPG, TIFF)

### BulkCompressionService

**Location**: `src/services/bulk_compression_service.py`

**Purpose**: Handle bulk PDF compression operations

**Dependencies**:
- CompressionService
- FileManager
- Celery (for task management)

**Key Methods**:

```python
def __init__(self):
    """Initialize bulk compression service"""
    
def process_bulk_job(self, job_data: Dict) -> Dict:
    """Process multiple PDF files for compression
    
    Args:
        job_data: Job with file list and compression options
        
    Returns:
        Dict with bulk processing results
    """
    
def validate_bulk_request(self, files: List, options: Dict) -> Dict:
    """Validate bulk compression request
    
    Args:
        files: List of files to process
        options: Compression options
        
    Returns:
        Validation results
    """
```

**Limits**:
- Maximum 100 files per bulk job
- Maximum 50MB per individual file
- Maximum 1GB total size per bulk job

## Utility Services

### CleanupService

**Location**: `src/services/cleanup_service.py`

**Purpose**: Manage file retention and automated cleanup

**Dependencies**:
- Database models
- FileManager

**Key Methods**:

```python
@staticmethod
def cleanup_expired_jobs() -> Dict[str, Any]:
    """Clean up expired jobs and associated files
    
    Returns:
        Cleanup summary with statistics
    """
    
@staticmethod
def cleanup_temp_files() -> Dict[str, Any]:
    """Clean up temporary files older than threshold
    
    Returns:
        Cleanup results
    """
    
@staticmethod
def get_cleanup_status() -> Dict[str, Any]:
    """Get current cleanup service status
    
    Returns:
        Status information and statistics
    """
```

**Retention Policies**:
- Completed jobs: 24 hours
- Failed jobs: 24 hours
- Pending jobs: 1 hour
- Processing jobs: 4 hours
- Temporary files: 1 hour

### CloudIntegrationService

**Location**: `src/services/cloud_integration_service.py`

**Purpose**: Integration with cloud storage providers

**Dependencies**:
- Cloud provider SDKs
- Configuration

**Key Methods**:

```python
def __init__(self):
    """Initialize cloud integration service"""
    
def upload_to_cloud(self, file_path: str, provider: str, options: Dict) -> Dict:
    """Upload file to cloud storage
    
    Args:
        file_path: Local file path
        provider: Cloud provider name
        options: Upload options
        
    Returns:
        Upload results with cloud URLs
    """
    
def download_from_cloud(self, cloud_url: str, local_path: str) -> Dict:
    """Download file from cloud storage
    
    Args:
        cloud_url: Cloud file URL
        local_path: Local destination path
        
    Returns:
        Download results
    """
```

**Supported Providers**:
- AWS S3
- Google Cloud Storage
- Azure Blob Storage
- Dropbox

### EnhancedCompressionService (Deprecated)

**Location**: `src/services/enhanced_compression_service.py`

**Status**: Deprecated - Use CompressionService instead

**Purpose**: Legacy enhanced compression features

## Service Dependencies

### Dependency Graph

```
CompressionService
├── Ghostscript (external)
├── FileManager
└── Configuration

OCRService
├── Tesseract (external)
├── PyMuPDF
├── PIL/Pillow
└── FileManager

AIService
├── OpenRouter API
├── OpenAI API (optional)
├── Anthropic API (optional)
└── ConversionService

ConversionService
├── PyMuPDF
├── pdfplumber
├── python-docx
└── FileManager

BulkCompressionService
├── CompressionService
├── FileManager
└── Celery

CleanupService
├── Database Models
└── FileManager

CloudIntegrationService
├── boto3 (AWS)
├── google-cloud-storage
├── azure-storage-blob
└── dropbox

FileManager
├── Configuration
└── File Utilities
```

### External Dependencies

**System Requirements**:
- Ghostscript 9.50+ (PDF compression)
- Tesseract 4.0+ (OCR)
- Redis 6+ (task queue)
- Python 3.11+

**Python Packages**:
- Flask (web framework)
- Celery (task queue)
- SQLAlchemy (database)
- PyMuPDF (PDF processing)
- Pillow (image processing)
- requests (HTTP client)

## Usage Patterns

### Synchronous Processing

```python
# Direct service usage for immediate results
from src.services.compression_service import CompressionService

service = CompressionService()
result = service.compress_pdf(
    input_path='/path/to/input.pdf',
    output_path='/path/to/output.pdf',
    quality='medium'
)

if result['success']:
    print(f"Compression ratio: {result['compression_ratio']}")
    print(f"File size reduced by: {result['size_reduction']}%")
```

### Asynchronous Processing

```python
# Job-based processing for long-running operations
from src.services.ocr_service import OCRService
from src.tasks.tasks import process_ocr_task

# Create job
job_data = {
    'job_id': 'unique-job-id',
    'file_path': '/path/to/document.pdf',
    'language': 'eng',
    'quality': 'balanced',
    'output_format': 'searchable_pdf'
}

# Start asynchronous processing
task = process_ocr_task.delay(job_data)

# Check status later
result = task.get(timeout=300)  # 5 minute timeout
```

### Service Configuration

```python
# Configure services with custom settings
from src.config import Config
from src.services.compression_service import CompressionService

config = Config()
config.COMPRESSION_QUALITY = 'high'
config.MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

service = CompressionService(config=config)
```

### Error Handling Pattern

```python
from src.services.ai_service import AIService
from src.exceptions import ServiceError, ValidationError

try:
    service = AIService()
    result = service.process_summarization_job(job_data)
    
    if result['success']:
        summary = result['summary']
        print(f"Generated summary: {summary}")
    else:
        print(f"Processing failed: {result['error']}")
        
except ValidationError as e:
    print(f"Invalid input: {e}")
except ServiceError as e:
    print(f"Service error: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
```

## Error Handling

### Custom Exceptions

```python
# src/exceptions.py
class ServiceError(Exception):
    """Base exception for service errors"""
    pass

class ValidationError(ServiceError):
    """Input validation errors"""
    pass

class ProcessingError(ServiceError):
    """Processing operation errors"""
    pass

class ExternalServiceError(ServiceError):
    """External service integration errors"""
    pass
```

### Error Response Format

```python
# Standard error response format
{
    'success': False,
    'error': {
        'code': 'PROCESSING_FAILED',
        'message': 'Human-readable error message',
        'details': {
            'service': 'CompressionService',
            'operation': 'compress_pdf',
            'timestamp': '2024-01-15T10:30:00Z'
        }
    }
}
```

### Logging Standards

```python
import logging

logger = logging.getLogger(__name__)

class ExampleService:
    def process_job(self, job_data):
        job_id = job_data.get('job_id')
        
        logger.info(f"Starting job processing: {job_id}")
        
        try:
            # Processing logic
            result = self._do_processing(job_data)
            
            logger.info(f"Job completed successfully: {job_id}")
            return result
            
        except Exception as e:
            logger.error(f"Job failed: {job_id}, error: {str(e)}")
            raise ProcessingError(f"Processing failed: {str(e)}")
```

## Testing Services

### Unit Testing Pattern

```python
import unittest
from unittest.mock import Mock, patch
from src.services.compression_service import CompressionService

class TestCompressionService(unittest.TestCase):
    
    def setUp(self):
        self.service = CompressionService()
        
    @patch('src.services.compression_service.subprocess.run')
    def test_compress_pdf_success(self, mock_subprocess):
        # Mock successful Ghostscript execution
        mock_subprocess.return_value.returncode = 0
        
        result = self.service.compress_pdf(
            input_path='/test/input.pdf',
            output_path='/test/output.pdf'
        )
        
        self.assertTrue(result['success'])
        self.assertIn('compression_ratio', result)
        
    def test_compress_pdf_invalid_input(self):
        with self.assertRaises(ValidationError):
            self.service.compress_pdf(
                input_path='/nonexistent/file.pdf',
                output_path='/test/output.pdf'
            )
```

### Integration Testing

```python
import tempfile
import os
from src.services.file_manager import FileManager
from src.services.compression_service import CompressionService

class TestServiceIntegration(unittest.TestCase):
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.file_manager = FileManager(upload_folder=self.temp_dir)
        self.compression_service = CompressionService()
        
    def tearDown(self):
        # Cleanup test files
        import shutil
        shutil.rmtree(self.temp_dir)
        
    def test_full_compression_workflow(self):
        # Create test PDF file
        test_pdf_data = b'%PDF-1.4\n...'
        file_id, file_path = self.file_manager.save_file(
            test_pdf_data, 
            'test.pdf'
        )
        
        # Compress the file
        output_path = os.path.join(self.temp_dir, 'compressed.pdf')
        result = self.compression_service.compress_pdf(
            input_path=file_path,
            output_path=output_path
        )
        
        # Verify results
        self.assertTrue(result['success'])
        self.assertTrue(os.path.exists(output_path))
```

### Mock External Dependencies

```python
from unittest.mock import Mock, patch

class TestAIService(unittest.TestCase):
    
    @patch('requests.post')
    def test_openrouter_api_call(self, mock_post):
        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{
                'message': {
                    'content': 'Test summary content'
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
        
        self.assertTrue(result['success'])
        self.assertEqual(result['summary'], 'Test summary content')
```

---

## Service Development Guidelines

### Adding New Services

1. **Create Service Class**:
   ```python
   # src/services/new_service.py
   class NewService:
       """Service description and purpose"""
       
       def __init__(self, config=None):
           self.config = config or Config()
           # Initialize dependencies
           
       def process_job(self, job_data: Dict) -> Dict:
           # Main processing logic
           pass
   ```

2. **Follow Naming Conventions**:
   - Service classes: `ServiceNameService`
   - Methods: `snake_case`
   - Constants: `UPPER_CASE`

3. **Implement Standard Methods**:
   - `__init__()`: Service initialization
   - `process_job()`: Main processing method
   - `validate_input()`: Input validation
   - `cleanup_resources()`: Resource cleanup

4. **Add Error Handling**:
   - Use custom exceptions
   - Log errors appropriately
   - Return standardized error responses

5. **Write Tests**:
   - Unit tests for all methods
   - Integration tests for workflows
   - Mock external dependencies

6. **Update Documentation**:
   - Add service to this documentation
   - Update API documentation
   - Include usage examples

### Service Best Practices

- **Single Responsibility**: Each service handles one domain
- **Dependency Injection**: Accept dependencies in constructor
- **Configuration**: Use configuration objects, not global variables
- **Logging**: Log important operations and errors
- **Validation**: Validate all inputs thoroughly
- **Cleanup**: Always clean up resources
- **Testing**: Write comprehensive tests
- **Documentation**: Keep documentation up to date

---

*This service documentation should be updated whenever services are modified or new services are added. Always keep documentation in sync with code changes.*