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
    
    def __init__(self, config_params, file_service: Optional[FileManagementService] = None):
        # Initialize service with configuration and file management
        # Set up dependencies and validate requirements
        
    def process_job(self, job_data: Dict) -> Dict:
        # Main processing method
        # Returns standardized result format
        
    def validate_input(self, input_data: Dict) -> bool:
        # Input validation logic
        
    def cleanup_resources(self, job_id: str):
        # Resource cleanup after processing
```

### Centralized File Management

All processing services (OCRService, ConversionService, CompressionService) now use a centralized file management approach through the `FileManagementService`:

**Key Benefits**:
- **Consistency**: All services use the same file operations patterns
- **Maintainability**: Centralized file handling logic reduces code duplication
- **Security**: Unified file validation and security measures
- **Testing**: Easier to mock and test file operations
- **Error Handling**: Standardized error handling for file operations

**Implementation Pattern**:
```python
from src.services.file_management_service import FileManagementService

class ProcessingService:
    def __init__(self, file_service: Optional[FileManagementService] = None):
        self.file_service = file_service or FileManagementService()
        
    def _save_file_data(self, file_data: bytes, filename: str) -> Tuple[str, str]:
        """Save file data using centralized service"""
        return self.file_service.save_file(file_data, filename)
        
    def _cleanup_temp_files(self, file_paths: List[str]):
        """Clean up temporary files using centralized service"""
        for file_path in file_paths:
            self.file_service.delete_file(file_path)
```

**Migration Notes**:
- Services no longer accept `upload_folder` parameter directly
- File operations are delegated to `FileManagementService`
- Temporary file handling is more robust with proper cleanup
- File size operations are now consistent across all services

## Core Services

### CompressionService

**Location**: `src/services/compression_service.py`

**Purpose**: Handles PDF compression operations using Ghostscript

**Dependencies**:
- Ghostscript (external binary)
- FileManagementService (injected or auto-created)
- Configuration

**Key Methods**:

```python
def __init__(self, config: Config = None, file_service: Optional[FileManagementService] = None):
    """Initialize compression service with configuration and file management service
    
    Args:
        config: Configuration object (defaults to current app config)
        file_service: FileManagementService instance for file operations (creates new instance if None)
    """
    
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
from src.services.file_management_service import FileManagementService

# Option 1: Use default file service
service = CompressionService()

# Option 2: Inject custom file service
file_service = FileManagementService(upload_folder='/custom/path')
service = CompressionService(file_service=file_service)

result = service.compress_pdf(
    input_path='/path/to/input.pdf',
    output_path='/path/to/output.pdf',
    quality='medium'
)
```

### FileManagementService

**Location**: `src/services/file_management_service.py`

**Purpose**: Unified service for all file management operations including storage, retrieval, cleanup, and job-based file management

**Dependencies**:
- Configuration
- Database models
- File utilities
- Flask (for file downloads)

**Key Methods**:

```python
def __init__(self, upload_folder: str = None):
    """Initialize the file management service
    
    Args:
        upload_folder: Directory to store uploaded files. Defaults to Config.UPLOAD_FOLDER.
    """
    
def save_file(self, file_data: bytes, original_filename: str = None) -> Tuple[str, str]:
    """Save file data to disk with a unique filename
    
    Args:
        file_data: Binary file data to save
        original_filename: Original filename (used for extension)
        
    Returns:
        Tuple of (unique_id, file_path)
    """
    
def get_file_path(self, file_id: str, extension: str = '.pdf') -> str:
    """Get the full path for a file based on its ID
    
    Args:
        file_id: Unique file identifier
        extension: File extension (default: .pdf)
        
    Returns:
        Full file path
    """
    
def delete_file(self, file_path: str) -> bool:
    """Delete a file safely
    
    Args:
        file_path: Path to the file to delete
        
    Returns:
        True if file was deleted successfully, False otherwise
    """
    
def get_job_download_response(self, job_id: str):
    """Get Flask response for downloading job result file
    
    Args:
        job_id: Job identifier
        
    Returns:
        Flask response object or error response
    """
    
def cleanup_expired_jobs(self) -> Dict[str, Any]:
    """Clean up expired jobs and their associated files
    
    Returns:
        Summary of cleanup operations
    """
    
def cleanup_temp_files(self) -> Dict[str, Any]:
    """Clean up temporary files older than specified age
    
    Returns:
        Cleanup summary dictionary
    """
```

### InvoiceExtractionService

**Location**: `src/services/invoice_extraction_service.py`

**Purpose**: Extracts structured data from invoice PDF documents using AI

**Dependencies**:
- AIService (OpenAI integration)
- FileManagementService
- ExportService
- Configuration

**Key Methods**:

```python
def __init__(self, config: Config = None):
    """Initialize invoice extraction service with AI integration"""
    
def extract_invoice_data(self, file_path: str, export_format: str = 'json') -> Dict:
    """Extract structured data from invoice PDF
    
    Args:
        file_path: Path to invoice PDF file
        export_format: Output format ('json', 'csv', 'excel')
        
    Returns:
        Dict with extracted invoice data and export information
    """
    
def validate_invoice_data(self, extracted_data: Dict) -> Dict:
    """Validate extracted invoice data for completeness
    
    Args:
        extracted_data: Raw extracted data from AI
        
    Returns:
        Dict with validation results and cleaned data
    """
    
def get_extraction_capabilities(self) -> Dict:
    """Get invoice extraction capabilities and supported features
    
    Returns:
        Dict with supported formats, features, and limitations
    """
```

### BankStatementExtractionService

**Location**: `src/services/bank_statement_extraction_service.py`

**Purpose**: Extracts transaction data and account information from bank statement PDFs

**Dependencies**:
- AIService (OpenAI integration)
- FileManagementService
- ExportService
- Configuration

**Key Methods**:

```python
def __init__(self, config: Config = None):
    """Initialize bank statement extraction service with AI integration"""
    
def extract_bank_statement_data(self, file_path: str, export_format: str = 'json') -> Dict:
    """Extract structured data from bank statement PDF
    
    Args:
        file_path: Path to bank statement PDF file
        export_format: Output format ('json', 'csv', 'excel')
        
    Returns:
        Dict with extracted bank statement data and export information
    """
    
def validate_bank_statement_data(self, extracted_data: Dict) -> Dict:
    """Validate extracted bank statement data
    
    Args:
        extracted_data: Raw extracted data from AI
        
    Returns:
        Dict with validation results and cleaned data
    """
    
def get_extraction_capabilities(self) -> Dict:
    """Get bank statement extraction capabilities
    
    Returns:
        Dict with supported formats, features, and limitations
    """
```

### ExportService

**Location**: `src/services/export_service.py`

**Purpose**: Handles export of extracted data to various formats (JSON, CSV, Excel)

**Dependencies**:
- FileManagementService
- pandas (for CSV/Excel export)
- Configuration

**Key Methods**:

```python
def __init__(self, config: Config = None):
    """Initialize export service with format support"""
    
def export_invoice_to_json(self, data: Dict, output_path: str) -> Dict:
    """Export invoice data to JSON format
    
    Args:
        data: Extracted invoice data
        output_path: Path for JSON output file
        
    Returns:
        Dict with export results and file information
    """
    
def export_invoice_to_csv(self, data: Dict, output_path: str) -> Dict:
    """Export invoice data to CSV format
    
    Args:
        data: Extracted invoice data
        output_path: Path for CSV output file
        
    Returns:
        Dict with export results and file information
    """
    
def export_invoice_to_excel(self, data: Dict, output_path: str) -> Dict:
    """Export invoice data to Excel format with multiple sheets
    
    Args:
        data: Extracted invoice data
        output_path: Path for Excel output file
        
    Returns:
        Dict with export results and file information
    """
    
def export_bank_statement_to_json(self, data: Dict, output_path: str) -> Dict:
    """Export bank statement data to JSON format"""
    
def export_bank_statement_to_csv(self, data: Dict, output_path: str) -> Dict:
    """Export bank statement data to CSV format"""
    
def export_bank_statement_to_excel(self, data: Dict, output_path: str) -> Dict:
    """Export bank statement data to Excel format"""
    
def get_export_capabilities(self) -> Dict:
    """Get supported export formats and capabilities"""
    
def cleanup_export_files(self, file_paths: List[str]) -> Dict:
    """Clean up temporary export files"""
```

## Processing Services

### OCRService

**Location**: `src/services/ocr_service.py`

**Purpose**: Optical Character Recognition for PDFs and images

**Dependencies**:
- Tesseract OCR (external)
- PyMuPDF (fitz)
- PIL/Pillow
- FileManagementService (injected or auto-created)

**Key Methods**:

```python
def __init__(self, file_service: Optional[FileManagementService] = None):
    """Initialize OCR service with file management service
    
    Args:
        file_service: FileManagementService instance for file operations (creates new instance if None)
    """
    
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
- **DeepSeek V3 Models**: deepseek-v3, deepseek-v3-free, deepseek-chat, deepseek-coder, deepseek-r1 (and distilled variants)
- **Moonshot K2 Models**: moonshot-k2-free, moonshot-k2-premium, moonshot-v1-8k/32k/128k
- **OpenAI Models**: GPT-4 Turbo, GPT-4, GPT-3.5 Turbo
- **Anthropic Models**: Claude-3 Opus, Sonnet, Haiku
- **Other Models**: Gemini Pro, Mistral Large, Llama-3 70B

**Default Model**: `deepseek/deepseek-v3-free` (cost-effective option)

### ConversionService

**Location**: `src/services/conversion_service.py`

**Purpose**: Convert PDFs to various formats (DOCX, TXT, HTML, Images)

**Dependencies**:
- PyMuPDF (fitz)
- python-docx
- pdfplumber
- PIL/Pillow
- FileManagementService (injected or auto-created)

**Key Methods**:

```python
def __init__(self, file_service: Optional[FileManagementService] = None):
    """Initialize conversion service with file management service
    
    Args:
        file_service: FileManagementService instance for file operations (creates new instance if None)
    """
    
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
- FileManagementService
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

**Retention Policies** (FileManagementService):
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
├── FileManagementService
└── Configuration

OCRService
├── Tesseract (external)
├── PyMuPDF
├── PIL/Pillow
└── FileManagementService

AIService
├── OpenRouter API
├── OpenAI API (optional)
├── Anthropic API (optional)
└── ConversionService

ConversionService
├── PyMuPDF
├── pdfplumber
├── python-docx
└── FileManagementService

BulkCompressionService
├── CompressionService
├── FileManagementService
└── Celery

FileManagementService (includes cleanup)
├── Database Models
├── Configuration
└── File Utilities

CloudIntegrationService
├── boto3 (AWS)
├── google-cloud-storage
├── azure-storage-blob
└── dropbox

FileManagementService
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
from src.services.file_management_service import FileManagementService

# Option 1: Use default file service
service = CompressionService()

# Option 2: Use custom file service (recommended for testing)
file_service = FileManagementService(upload_folder='/custom/path')
service = CompressionService(file_service=file_service)

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
from src.services.file_management_service import FileManagementService

config = Config()
config.COMPRESSION_QUALITY = 'high'
config.MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB

# Configure file service with custom upload folder
file_service = FileManagementService(upload_folder='/custom/uploads')

# Inject both config and file service
service = CompressionService(config=config, file_service=file_service)
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

### Exception Hierarchy

The service layer uses a comprehensive exception hierarchy for different error scenarios:

```python
# Database-related exceptions (from SQLAlchemy)
from sqlalchemy.exc import DBAPIError, OperationalError, IntegrityError

# Service-specific exceptions
from src.exceptions.extraction_exceptions import (
    ExtractionError,           # Base extraction error
    ExtractionValidationError, # Input validation errors
    ExtractionTimeoutError,    # Processing timeout errors
    ExtractionFormatError      # Unsupported format errors
)

# Celery task exceptions
from celery.exceptions import Ignore, Retry

# Environment and system exceptions
EnvironmentError  # Missing dependencies, system issues
FileNotFoundError # File system errors
PermissionError   # Access permission errors
```

### Intelligent Exception Handling

Services implement intelligent exception handling with different strategies based on error type:

```python
def process_with_intelligent_retry(self, job_data: Dict) -> Dict:
    """Process job with intelligent exception handling and retry logic"""
    try:
        return self._do_processing(job_data)
        
    except (DBAPIError, OperationalError, IntegrityError) as db_e:
        logger.error(f"Database error in job {job_data['job_id']}: {db_e}")
        # Retry database errors with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 60 * (self.request.retries + 1)  # 60s, 120s, 180s...
            raise self.retry(countdown=countdown)
        raise
        
    except ExtractionValidationError as val_e:
        logger.error(f"Validation error in job {job_data['job_id']}: {val_e}")
        # Don't retry validation errors - they won't succeed on retry
        raise Ignore()
        
    except ExtractionTimeoutError as timeout_e:
        logger.error(f"Timeout error in job {job_data['job_id']}: {timeout_e}")
        # Retry timeout errors with longer countdown
        if self.request.retries < self.max_retries:
            countdown = 120 * (self.request.retries + 1)  # 2min, 4min, 6min...
            raise self.retry(countdown=countdown)
        raise
        
    except ExtractionError as ext_e:
        logger.error(f"Extraction error in job {job_data['job_id']}: {ext_e}")
        # Retry general extraction errors
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1))
        raise
        
    except EnvironmentError as env_e:
        logger.error(f"Environment error in job {job_data['job_id']}: {env_e}")
        # Don't retry environment errors (missing dependencies, etc.)
        raise Ignore()
        
    except (FileNotFoundError, PermissionError) as file_e:
        logger.error(f"File system error in job {job_data['job_id']}: {file_e}")
        # Clean up any partial files and don't retry
        self.file_service.cleanup_temp_files([job_data.get('temp_files', [])])
        raise Ignore()
```

### Exception Categories and Retry Strategies

| Exception Type | Retry Strategy | Reason |
|----------------|----------------|--------|
| Database errors (DBAPIError, OperationalError) | Exponential backoff retry | Temporary connectivity issues |
| Validation errors (ExtractionValidationError) | No retry (Ignore) | Input won't change on retry |
| Timeout errors (ExtractionTimeoutError) | Longer countdown retry | May succeed with more time |
| General extraction errors (ExtractionError) | Standard retry | May be temporary processing issues |
| Environment errors (EnvironmentError) | No retry (Ignore) | System configuration issues |
| File system errors (FileNotFoundError, PermissionError) | No retry + cleanup | File access issues |

### Legacy Exception Support

For backward compatibility, the following exceptions are still supported:

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
from src.services.file_management_service import FileManagementService
from src.services.compression_service import CompressionService

class TestServiceIntegration(unittest.TestCase):
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.file_service = FileManagementService(upload_folder=self.temp_dir)
        self.compression_service = CompressionService()
        
    def tearDown(self):
        # Cleanup test files
        import shutil
        shutil.rmtree(self.temp_dir)
        
    def test_full_compression_workflow(self):
        # Create test PDF file
        test_pdf_data = b'%PDF-1.4\n...'
        file_id, file_path = self.file_service.save_file(
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
