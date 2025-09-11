# PDF Smaller Backend - Architecture Guide

This guide provides a comprehensive overview of the PDF Smaller Backend architecture, designed to help developers understand the system design, service interactions, and data flow patterns.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [Core Components](#core-components)
4. [Service Layer Architecture](#service-layer-architecture)
5. [Data Flow Patterns](#data-flow-patterns)
6. [Job Processing Pipeline](#job-processing-pipeline)
7. [Database Design](#database-design)
8. [File Management Strategy](#file-management-strategy)
9. [Error Handling Architecture](#error-handling-architecture)
10. [Scalability Considerations](#scalability-considerations)
11. [Security Architecture](#security-architecture)
12. [Development Guidelines](#development-guidelines)

## System Overview

### High-Level Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend API   │    │   Task Queue    │
│   (External)    │◄──►│   (Flask)       │◄──►│   (Celery)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   Database      │    │   File Storage  │
                       │   (SQLite)      │    │   (Local Disk)  │
                       └─────────────────┘    └─────────────────┘
```

### Technology Stack

- **Web Framework**: Flask with SQLAlchemy ORM
- **Task Queue**: Celery with Redis broker
- **Database**: SQLite (development and production)
- **File Storage**: Local filesystem with organized directory structure
- **PDF Processing**: Ghostscript, PyMuPDF, pdfplumber
- **AI Integration**: OpenRouter, OpenAI, Anthropic APIs
- **OCR**: Tesseract with pytesseract wrapper

## Architecture Principles

### 1. Job-Oriented Design
- All operations are modeled as jobs with unique identifiers
- Asynchronous processing with immediate job ID return
- Status tracking throughout the job lifecycle
- Consistent job state management

### 2. Service-Oriented Architecture
- Clear separation of concerns through dedicated service classes
- Each service handles a specific domain (compression, OCR, AI, etc.)
- Services are stateless and can be easily tested
- Dependency injection for service configuration

### 3. Stateless API Design
- No user sessions or authentication state
- Each request is self-contained
- Job tracking through unique identifiers
- RESTful endpoint design

### 4. Fail-Safe Processing
- Comprehensive error handling at all levels
- Graceful degradation when optional services are unavailable
- Automatic cleanup of temporary files
- Job status updates even on failures

## Core Components

### 1. Flask Application (`app.py`)
```python
# Main application entry point
# - Route registration
# - Middleware configuration
# - Error handler setup
# - Database initialization
```

### 2. Route Handlers (`src/routes/`)
- **compression_routes.py**: Core PDF compression endpoints
- **extended_features_routes.py**: Advanced features (OCR, AI, conversion)
- **jobs_routes.py**: Job status and download endpoints
- **enhanced_compression_routes.py**: Deprecated enhanced compression

### 3. Service Layer (`src/services/`)
- **compression_service.py**: PDF compression logic
- **ocr_service.py**: Optical Character Recognition
- **ai_service.py**: AI-powered summarization and translation
- **conversion_service.py**: PDF format conversion
- **bulk_compression_service.py**: Bulk file processing
- **cloud_integration_service.py**: Cloud storage integration
- **file_manager.py**: File operations and cleanup
- **cleanup_service.py**: Automated cleanup tasks

### 4. Task Processing (`src/tasks/`)
- **tasks.py**: Celery task definitions
- **app_context.py**: Flask application context for tasks

### 5. Data Models (`src/models/`)
- **job.py**: Base job model with status tracking
- **compression_job.py**: Compression-specific job data
- **base.py**: Common model functionality

## Service Layer Architecture

### Service Design Pattern

Each service follows a consistent pattern:

```python
class ServiceName:
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

### Service Dependencies

```
CompressionService
├── Ghostscript (external)
├── FileManager
└── ValidationUtils

OCRService
├── Tesseract (external)
├── PyMuPDF
├── PIL/Pillow
└── FileManager

AIService
├── OpenRouter API
├── OpenAI API
├── Anthropic API
└── ConversionService

ConversionService
├── PyMuPDF
├── pdfplumber
├── python-docx
└── FileManager
```

## Data Flow Patterns

### 1. Synchronous Request Flow

```
Client Request → Route Handler → Validation → Job Creation → Task Enqueue → Response
```

### 2. Asynchronous Processing Flow

```
Celery Worker → Task Execution → Service Processing → Result Storage → Status Update
```

### 3. Job Status Polling Flow

```
Client Poll → Route Handler → Database Query → Status Response
```

### 4. File Download Flow

```
Download Request → Job Validation → File Location → Stream Response
```

## Job Processing Pipeline

### Job Lifecycle States

```
PENDING → PROCESSING → (COMPLETED | FAILED)
```

### Processing Pipeline

1. **Job Creation**
   - Generate unique job ID
   - Store job metadata in database
   - Save input file to temporary location
   - Enqueue processing task

2. **Task Execution**
   - Worker picks up task from queue
   - Load job data and input file
   - Execute appropriate service method
   - Handle errors and update status

3. **Result Handling**
   - Store processed file in output location
   - Update job status and metadata
   - Schedule cleanup tasks
   - Notify completion (if configured)

4. **Cleanup**
   - Remove temporary files after TTL
   - Clean up database records (optional)
   - Free up storage space

### Error Handling in Pipeline

```python
try:
    # Process job
    result = service.process_job(job_data)
    job.status = JobStatus.COMPLETED
    job.result_data = result
except ValidationError as e:
    job.status = JobStatus.FAILED
    job.error_message = f"Validation failed: {str(e)}"
except ProcessingError as e:
    job.status = JobStatus.FAILED
    job.error_message = f"Processing failed: {str(e)}"
except Exception as e:
    job.status = JobStatus.FAILED
    job.error_message = f"Unexpected error: {str(e)}"
    logger.error(f"Job {job.job_id} failed: {str(e)}")
finally:
    job.updated_at = datetime.utcnow()
    db.session.commit()
```

## Database Design

### Job Table Schema

```sql
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id VARCHAR(36) UNIQUE NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    input_data TEXT,  -- JSON
    result_data TEXT, -- JSON
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP
);
```

### Compression Job Table Schema

```sql
CREATE TABLE compression_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id VARCHAR(36) UNIQUE NOT NULL,
    original_filename VARCHAR(255),
    original_size INTEGER,
    compressed_size INTEGER,
    compression_ratio REAL,
    compression_level VARCHAR(20),
    image_quality INTEGER,
    processing_time REAL,
    FOREIGN KEY (job_id) REFERENCES jobs (job_id)
);
```

### Database Relationships

```
Jobs (1) ←→ (1) CompressionJobs
     ↓
   Indexes on job_id, status, created_at
```

## File Management Strategy

### Directory Structure

```
uploads/
├── temp/           # Temporary input files
│   └── {job_id}/
├── processing/     # Files being processed
│   └── {job_id}/
├── results/        # Completed job results
│   └── {job_id}/
└── archive/        # Long-term storage (optional)
    └── {date}/
```

### File Lifecycle Management

1. **Upload**: Files stored in `temp/{job_id}/`
2. **Processing**: Moved to `processing/{job_id}/`
3. **Completion**: Results stored in `results/{job_id}/`
4. **Cleanup**: Files removed after TTL expires

### Storage Optimization

- Automatic cleanup of expired files
- Compression of archived files
- Monitoring of disk space usage
- Configurable retention policies

## Error Handling Architecture

### Error Categories

1. **Validation Errors**: Input validation failures
2. **Processing Errors**: Service-specific failures
3. **System Errors**: Infrastructure failures
4. **External Errors**: Third-party service failures

### Error Response Format

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {
      "field": "specific error details"
    },
    "timestamp": "2023-06-15T10:30:00.000Z"
  }
}
```

### Error Handling Best Practices

- Always log errors with context
- Provide meaningful error messages
- Clean up resources on errors
- Update job status appropriately
- Never expose internal system details

## Scalability Considerations

### Horizontal Scaling

- **API Servers**: Multiple Flask instances behind load balancer
- **Workers**: Scale Celery workers based on queue length
- **Database**: SQLite limitations require migration to PostgreSQL for high load
- **File Storage**: Consider distributed storage for large deployments

### Performance Optimization

- **Caching**: Redis for frequently accessed data
- **Connection Pooling**: Database connection management
- **Async Processing**: Non-blocking task execution
- **Resource Limits**: Memory and CPU usage controls

### Monitoring Points

- API response times
- Queue length and processing times
- Database query performance
- File storage usage
- Error rates by service

## Security Architecture

### Input Validation

- File type validation
- File size limits
- Content scanning for malicious files
- Parameter sanitization

### Data Protection

- Temporary file encryption (optional)
- Secure file deletion
- Access logging
- Rate limiting

### External Service Security

- API key management
- Request signing
- SSL/TLS for all external calls
- Timeout and retry policies

## Development Guidelines

### Adding New Services

1. Create service class in `src/services/`
2. Follow the standard service pattern
3. Add comprehensive error handling
4. Include input validation
5. Write unit tests
6. Update documentation

### Adding New Endpoints

1. Create route in appropriate blueprint
2. Follow RESTful conventions
3. Use consistent response formats
4. Add request validation
5. Include error handling
6. Update API documentation

### Code Quality Standards

- Follow PEP 8 style guidelines
- Use type hints where possible
- Write comprehensive docstrings
- Include error handling in all methods
- Add logging for debugging
- Write tests for new functionality

### Testing Strategy

- Unit tests for all services
- Integration tests for API endpoints
- Mock external dependencies
- Test error conditions
- Performance testing for critical paths

---

*This architecture guide should be updated as the system evolves. Always keep documentation in sync with code changes.*