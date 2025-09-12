# Invoice and Bank Statement Extraction Features - Refactored Documentation

## Overview

This document provides refactored specifications for invoice and bank statement extraction features that align with the existing PDF Smaller backend architecture patterns. The implementation follows the established job-oriented architecture with async processing via Celery.

## Architecture Alignment

The features integrate seamlessly with existing components:
- **Job Model**: Uses `src/models/job.py` with JobStatus enum for tracking
- **AI Service**: Extends `src/services/ai_service.py` patterns for OpenRouter integration
- **Route Structure**: Follows `src/routes/pdf_suite.py` blueprint patterns
- **Task Processing**: Uses `src/tasks/tasks.py` Celery patterns
- **Response Helpers**: Leverages `src/utils/response_helpers.py` for consistent API responses
- **File Management**: Integrates with `src/services/file_management_service.py` for secure file handling
- **Error Handling**: Uses custom exceptions from `src/utils/exceptions.py`

## Feature 1: Invoice Extraction

### API Endpoints

#### Extract Invoice Data
```
POST /ai/invoice/extract
Content-Type: multipart/form-data

Parameters:
- file: PDF file (required)
- output_format: string (optional, default: "json", options: "json", "csv", "excel")
- extraction_mode: string (optional, default: "standard", options: "standard", "detailed")
- include_line_items: boolean (optional, default: true)
- validate_totals: boolean (optional, default: true)

Response (202 Accepted):
{
  "success": true,
  "message": "Invoice extraction job started",
  "job_id": "uuid-string",
  "status": "PENDING",
  "estimated_completion": "2024-01-15T10:30:00Z"
}
```

#### Get Invoice Extraction Capabilities
```
GET /ai/invoice/capabilities

Response (200 OK):
{
  "success": true,
  "data": {
    "supported_formats": ["pdf"],
    "output_formats": ["json", "csv", "excel"],
    "extraction_modes": ["standard", "detailed"],
    "max_file_size": "50MB",
    "supported_languages": ["en", "es", "fr", "de", "it"],
    "extractable_fields": {
      "header": ["invoice_number", "date", "due_date", "vendor_info", "customer_info"],
      "totals": ["subtotal", "tax_amount", "total_amount", "currency"],
      "line_items": ["description", "quantity", "unit_price", "total_price"]
    }
  }
}
```

### Service Implementation

#### InvoiceExtractionService Class

Location: `src/services/invoice_extraction_service.py`

```python
class InvoiceExtractionService:
    """Service for extracting structured data from invoice PDFs using AI."""
    
    def __init__(self):
        self.ai_service = AIService()
        self.file_service = FileManagementService()
        self.logger = logging.getLogger(__name__)
    
    def extract_invoice_data(self, file_path: str, options: dict) -> dict:
        """Extract structured data from invoice PDF."""
        
    def _prepare_extraction_prompt(self, extraction_mode: str, include_line_items: bool) -> str:
        """Prepare AI prompt for invoice extraction."""
        
    def _validate_extraction_result(self, result: dict, validate_totals: bool) -> dict:
        """Validate and clean extraction results."""
        
    def _export_to_format(self, data: dict, output_format: str, job_id: str) -> str:
        """Export extracted data to requested format."""
```

### Celery Task Implementation

Location: `src/tasks/tasks.py` (add to existing file)

```python
@celery_app.task(bind=True, max_retries=3)
def extract_invoice_task(self, job_id: str, file_path: str, options: dict):
    """Background task for invoice data extraction."""
    job = None
    try:
        # Update job status to processing
        job = Job.query.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        job.update_status(JobStatus.PROCESSING)
        
        # Initialize service
        extraction_service = InvoiceExtractionService()
        
        # Process extraction
        result = extraction_service.extract_invoice_data(file_path, options)
        
        # Update job with results
        job.update_status(JobStatus.COMPLETED, result=result)
        
        logger.info(f"Invoice extraction completed for job {job_id}")
        
    except Exception as e:
        logger.error(f"Invoice extraction failed for job {job_id}: {str(e)}")
        if job:
            job.update_status(JobStatus.FAILED, error=str(e))
        
        # Retry logic
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        raise e
```

### Route Implementation

Location: `src/routes/pdf_suite.py` (add to existing blueprint)

```python
@pdf_suite_bp.route('/ai/invoice/extract', methods=['POST'])
def extract_invoice():
    """Extract structured data from invoice PDF."""
    try:
        # Validate file and options
        file, options = get_file_and_validate(
            request, 
            allowed_extensions=['pdf'],
            max_file_size=50 * 1024 * 1024  # 50MB
        )
        
        # Validate extraction options
        extraction_options = {
            'output_format': request.form.get('output_format', 'json'),
            'extraction_mode': request.form.get('extraction_mode', 'standard'),
            'include_line_items': request.form.get('include_line_items', 'true').lower() == 'true',
            'validate_totals': request.form.get('validate_totals', 'true').lower() == 'true'
        }
        
        # Validate options
        if extraction_options['output_format'] not in ['json', 'csv', 'excel']:
            return error_response('Invalid output format', 400)
        
        if extraction_options['extraction_mode'] not in ['standard', 'detailed']:
            return error_response('Invalid extraction mode', 400)
        
        # Create job
        job_id = str(uuid.uuid4())
        job = Job(
            job_id=job_id,
            task_type=TaskType.AI_INVOICE_EXTRACTION,
            status=JobStatus.PENDING,
            input_data={
                'filename': file.filename,
                'options': extraction_options
            }
        )
        db.session.add(job)
        db.session.commit()
        
        # Save file
        file_path = file_service.save_uploaded_file(file, job_id)
        
        # Enqueue task
        extract_invoice_task.delay(job_id, file_path, extraction_options)
        
        return success_response(
            message="Invoice extraction job started",
            data={
                'job_id': job_id,
                'status': job.status.value,
                'estimated_completion': (datetime.utcnow() + timedelta(minutes=5)).isoformat() + 'Z'
            },
            status_code=202
        )
        
    except Exception as e:
        logger.error(f"Invoice extraction request failed: {str(e)}")
        return error_response(f"Failed to start invoice extraction: {str(e)}")

@pdf_suite_bp.route('/ai/invoice/capabilities', methods=['GET'])
def get_invoice_capabilities():
    """Get invoice extraction capabilities."""
    capabilities = {
        'supported_formats': ['pdf'],
        'output_formats': ['json', 'csv', 'excel'],
        'extraction_modes': ['standard', 'detailed'],
        'max_file_size': '50MB',
        'supported_languages': ['en', 'es', 'fr', 'de', 'it'],
        'extractable_fields': {
            'header': ['invoice_number', 'date', 'due_date', 'vendor_info', 'customer_info'],
            'totals': ['subtotal', 'tax_amount', 'total_amount', 'currency'],
            'line_items': ['description', 'quantity', 'unit_price', 'total_price']
        }
    }
    
    return success_response(
        message="Invoice extraction capabilities retrieved",
        data=capabilities
    )
```

## Feature 2: Bank Statement Extraction

### API Endpoints

#### Extract Bank Statement Data
```
POST /ai/bank-statement/extract
Content-Type: multipart/form-data

Parameters:
- file: PDF file (required)
- output_format: string (optional, default: "json", options: "json", "csv", "excel")
- extraction_mode: string (optional, default: "standard", options: "standard", "detailed")
- include_balance_tracking: boolean (optional, default: true)
- categorize_transactions: boolean (optional, default: false)

Response (202 Accepted):
{
  "success": true,
  "message": "Bank statement extraction job started",
  "job_id": "uuid-string",
  "status": "PENDING",
  "estimated_completion": "2024-01-15T10:35:00Z"
}
```

#### Get Bank Statement Extraction Capabilities
```
GET /ai/bank-statement/capabilities

Response (200 OK):
{
  "success": true,
  "data": {
    "supported_formats": ["pdf"],
    "output_formats": ["json", "csv", "excel"],
    "extraction_modes": ["standard", "detailed"],
    "max_file_size": "50MB",
    "supported_languages": ["en", "es", "fr", "de", "it"],
    "extractable_fields": {
      "account_info": ["account_number", "account_holder", "bank_name", "statement_period"],
      "balances": ["opening_balance", "closing_balance", "currency"],
      "transactions": ["date", "description", "amount", "balance", "transaction_type"]
    }
  }
}
```

### Service Implementation

#### BankStatementExtractionService Class

Location: `src/services/bank_statement_extraction_service.py`

```python
class BankStatementExtractionService:
    """Service for extracting structured data from bank statement PDFs using AI."""
    
    def __init__(self):
        self.ai_service = AIService()
        self.file_service = FileManagementService()
        self.logger = logging.getLogger(__name__)
    
    def extract_statement_data(self, file_path: str, options: dict) -> dict:
        """Extract structured data from bank statement PDF."""
        
    def _prepare_extraction_prompt(self, extraction_mode: str, categorize_transactions: bool) -> str:
        """Prepare AI prompt for bank statement extraction."""
        
    def _validate_extraction_result(self, result: dict, include_balance_tracking: bool) -> dict:
        """Validate and clean extraction results."""
        
    def _categorize_transactions(self, transactions: list) -> list:
        """Categorize transactions using AI."""
        
    def _export_to_format(self, data: dict, output_format: str, job_id: str) -> str:
        """Export extracted data to requested format."""
```

### Celery Task Implementation

Location: `src/tasks/tasks.py` (add to existing file)

```python
@celery_app.task(bind=True, max_retries=3)
def extract_bank_statement_task(self, job_id: str, file_path: str, options: dict):
    """Background task for bank statement data extraction."""
    job = None
    try:
        # Update job status to processing
        job = Job.query.get(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        job.update_status(JobStatus.PROCESSING)
        
        # Initialize service
        extraction_service = BankStatementExtractionService()
        
        # Process extraction
        result = extraction_service.extract_statement_data(file_path, options)
        
        # Update job with results
        job.update_status(JobStatus.COMPLETED, result=result)
        
        logger.info(f"Bank statement extraction completed for job {job_id}")
        
    except Exception as e:
        logger.error(f"Bank statement extraction failed for job {job_id}: {str(e)}")
        if job:
            job.update_status(JobStatus.FAILED, error=str(e))
        
        # Retry logic
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        raise e
```

### Route Implementation

Location: `src/routes/pdf_suite.py` (add to existing blueprint)

```python
@pdf_suite_bp.route('/ai/bank-statement/extract', methods=['POST'])
def extract_bank_statement():
    """Extract structured data from bank statement PDF."""
    try:
        # Validate file and options
        file, options = get_file_and_validate(
            request, 
            allowed_extensions=['pdf'],
            max_file_size=50 * 1024 * 1024  # 50MB
        )
        
        # Validate extraction options
        extraction_options = {
            'output_format': request.form.get('output_format', 'json'),
            'extraction_mode': request.form.get('extraction_mode', 'standard'),
            'include_balance_tracking': request.form.get('include_balance_tracking', 'true').lower() == 'true',
            'categorize_transactions': request.form.get('categorize_transactions', 'false').lower() == 'true'
        }
        
        # Validate options
        if extraction_options['output_format'] not in ['json', 'csv', 'excel']:
            return error_response('Invalid output format', 400)
        
        if extraction_options['extraction_mode'] not in ['standard', 'detailed']:
            return error_response('Invalid extraction mode', 400)
        
        # Create job
        job_id = str(uuid.uuid4())
        job = Job(
            job_id=job_id,
            task_type=TaskType.AI_BANK_STATEMENT_EXTRACTION,
            status=JobStatus.PENDING,
            input_data={
                'filename': file.filename,
                'options': extraction_options
            }
        )
        db.session.add(job)
        db.session.commit()
        
        # Save file
        file_path = file_service.save_uploaded_file(file, job_id)
        
        # Enqueue task
        extract_bank_statement_task.delay(job_id, file_path, extraction_options)
        
        return success_response(
            message="Bank statement extraction job started",
            data={
                'job_id': job_id,
                'status': job.status.value,
                'estimated_completion': (datetime.utcnow() + timedelta(minutes=7)).isoformat() + 'Z'
            },
            status_code=202
        )
        
    except Exception as e:
        logger.error(f"Bank statement extraction request failed: {str(e)}")
        return error_response(f"Failed to start bank statement extraction: {str(e)}")

@pdf_suite_bp.route('/ai/bank-statement/capabilities', methods=['GET'])
def get_bank_statement_capabilities():
    """Get bank statement extraction capabilities."""
    capabilities = {
        'supported_formats': ['pdf'],
        'output_formats': ['json', 'csv', 'excel'],
        'extraction_modes': ['standard', 'detailed'],
        'max_file_size': '50MB',
        'supported_languages': ['en', 'es', 'fr', 'de', 'it'],
        'extractable_fields': {
            'account_info': ['account_number', 'account_holder', 'bank_name', 'statement_period'],
            'balances': ['opening_balance', 'closing_balance', 'currency'],
            'transactions': ['date', 'description', 'amount', 'balance', 'transaction_type']
        }
    }
    
    return success_response(
        message="Bank statement extraction capabilities retrieved",
        data=capabilities
    )
```

## Model Extensions

### TaskType Enum Extension

Location: `src/models/job.py` (add to existing enum)

```python
class TaskType(Enum):
    # ... existing task types ...
    AI_INVOICE_EXTRACTION = "ai_invoice_extraction"
    AI_BANK_STATEMENT_EXTRACTION = "ai_bank_statement_extraction"
```

## Configuration Requirements

### Environment Variables

Add to `.env.example` and configuration:

```
# AI Extraction Features
INVOICE_EXTRACTION_ENABLED=true
BANK_STATEMENT_EXTRACTION_ENABLED=true
EXTRACTION_MAX_FILE_SIZE=52428800  # 50MB
EXTRACTION_TIMEOUT=300  # 5 minutes
```

## Error Handling

### Custom Exceptions

Location: `src/utils/exceptions.py` (add to existing file)

```python
class ExtractionError(Exception):
    """Raised when AI extraction fails."""
    pass

class ExtractionValidationError(ExtractionError):
    """Raised when extraction result validation fails."""
    pass

class ExportFormatError(Exception):
    """Raised when export format is invalid or export fails."""
    pass
```

## Testing Requirements

### Unit Tests
- Service class methods
- Route endpoint validation
- Task execution logic
- Export functionality

### Integration Tests
- End-to-end extraction workflow
- File upload and processing
- Job status tracking
- Download functionality

### Test Fixtures
- Sample invoice PDFs
- Sample bank statement PDFs
- Expected extraction results
- Mock AI service responses

## Documentation Updates Required

After implementation, update:
1. `docs/api_documentation.md` - Add new endpoints
2. `docs/service_documentation.md` - Document new services
3. `docs/architecture_guide.md` - Update with new components
4. `README.md` - Add feature descriptions

## Deployment Considerations

1. **Resource Requirements**: AI extraction tasks are CPU/memory intensive
2. **Scaling**: Consider dedicated Celery workers for extraction tasks
3. **Monitoring**: Add specific metrics for extraction success rates
4. **File Storage**: Ensure adequate storage for uploaded files and exports
5. **Security**: Validate file contents and sanitize extracted data

This refactored documentation aligns with the existing PDF Smaller backend architecture while providing comprehensive specifications for implementing invoice and bank statement extraction features.
