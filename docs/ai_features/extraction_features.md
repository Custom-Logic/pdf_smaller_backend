# AI Extraction Features

This document provides comprehensive information about the AI-powered document extraction capabilities in the PDF Suite Backend.

## Overview

The PDF Suite Backend now includes advanced AI extraction services that can automatically extract structured data from invoices and bank statements. These services leverage multiple AI providers through OpenRouter, including DeepSeek, Moonshot, OpenAI, and Anthropic models to intelligently parse and extract relevant information from PDF documents.

## Supported Document Types

### Invoice Extraction
- **Purpose**: Extract structured data from invoices, receipts, and billing documents
- **Supported Formats**: PDF files up to 10MB
- **Processing Mode**: Asynchronous with job tracking

### Bank Statement Extraction
- **Purpose**: Extract transaction data and account information from bank statements
- **Supported Formats**: PDF files up to 10MB
- **Processing Mode**: Asynchronous with job tracking

## Features

### Core Capabilities
- **Intelligent Text Recognition**: Advanced OCR and text extraction from PDF documents
- **AI-Powered Parsing**: Uses advanced AI models (DeepSeek, Moonshot, GPT, Claude) to understand document structure and extract relevant data
- **Data Validation**: Validates extracted data for completeness and accuracy
- **Multiple Export Formats**: Export extracted data in JSON, CSV, or Excel formats
- **Async Processing**: Non-blocking processing with real-time job status updates
- **Error Handling**: Comprehensive error handling with detailed error messages

### Invoice Extraction Features
- Extract invoice number, date, and due date
- Vendor and customer information extraction
- Line item details with descriptions, quantities, and amounts
- Tax information and total calculations
- Payment terms and conditions
- Custom field extraction based on document structure

### Bank Statement Extraction Features
- Account information (number, type, holder name)
- Statement period and balance information
- Transaction details (date, description, amount, type)
- Running balance calculations
- Transaction categorization
- Summary statistics

## API Endpoints

### Invoice Extraction

#### Start Invoice Extraction
```http
POST /api/pdf-suite/extract/invoice
Content-Type: multipart/form-data

file: [PDF file]
export_format: json|csv|excel (optional, default: json)
```

**Response:**
```json
{
  "success": true,
  "job_id": "extract_invoice_abc123",
  "message": "Invoice extraction started",
  "estimated_time": "30-60 seconds"
}
```

#### Get Invoice Extraction Capabilities
```http
GET /api/pdf-suite/extract/invoice/capabilities
```

**Response:**
```json
{
  "supported_formats": ["pdf"],
  "max_file_size": "10MB",
  "processing_mode": "async",
  "features": [
    "invoice_number_extraction",
    "vendor_information",
    "line_items",
    "tax_calculation",
    "multiple_export_formats"
  ],
  "export_formats": ["json", "csv", "excel"]
}
```

### Bank Statement Extraction

#### Start Bank Statement Extraction
```http
POST /api/pdf-suite/extract/bank-statement
Content-Type: multipart/form-data

file: [PDF file]
export_format: json|csv|excel (optional, default: json)
```

**Response:**
```json
{
  "success": true,
  "job_id": "extract_bank_abc123",
  "message": "Bank statement extraction started",
  "estimated_time": "30-60 seconds"
}
```

#### Get Bank Statement Extraction Capabilities
```http
GET /api/pdf-suite/extract/bank-statement/capabilities
```

**Response:**
```json
{
  "supported_formats": ["pdf"],
  "max_file_size": "10MB",
  "processing_mode": "async",
  "features": [
    "account_information",
    "transaction_extraction",
    "balance_tracking",
    "date_range_processing",
    "multiple_export_formats"
  ],
  "export_formats": ["json", "csv", "excel"]
}
```

## Data Structures

### Invoice Extraction Output

```json
{
  "invoice_number": "INV-2024-001",
  "date": "2024-01-15",
  "due_date": "2024-02-15",
  "vendor_name": "ABC Company Ltd",
  "vendor_address": "123 Business St, City, State 12345",
  "vendor_contact": {
    "email": "billing@abccompany.com",
    "phone": "+1-555-0123"
  },
  "customer_name": "XYZ Corporation",
  "customer_address": "456 Client Ave, City, State 67890",
  "items": [
    {
      "description": "Professional Services",
      "quantity": 10,
      "unit_price": 150.00,
      "total": 1500.00
    }
  ],
  "subtotal": 1500.00,
  "tax_rate": 0.08,
  "tax_amount": 120.00,
  "total_amount": 1620.00,
  "currency": "USD",
  "payment_terms": "Net 30",
  "notes": "Thank you for your business"
}
```

### Bank Statement Extraction Output

```json
{
  "account_info": {
    "account_number": "****1234",
    "account_type": "Checking",
    "account_holder": "John Doe",
    "bank_name": "First National Bank",
    "routing_number": "123456789"
  },
  "statement_period": {
    "start_date": "2024-01-01",
    "end_date": "2024-01-31"
  },
  "opening_balance": 5000.00,
  "closing_balance": 4750.00,
  "transactions": [
    {
      "date": "2024-01-02",
      "description": "Direct Deposit - Salary",
      "amount": 3000.00,
      "type": "credit",
      "balance": 8000.00,
      "category": "income"
    },
    {
      "date": "2024-01-03",
      "description": "ATM Withdrawal",
      "amount": -200.00,
      "type": "debit",
      "balance": 7800.00,
      "category": "cash_withdrawal"
    }
  ],
  "summary": {
    "total_credits": 3500.00,
    "total_debits": -3750.00,
    "net_change": -250.00,
    "transaction_count": 25
  }
}
```

## Export Formats

### JSON Export
- **Use Case**: API integration, data processing
- **Features**: Preserves full data structure, nested objects
- **File Extension**: `.json`

### CSV Export
- **Use Case**: Spreadsheet analysis, data import
- **Features**: Flattened structure, Excel-compatible
- **File Extension**: `.csv`
- **Note**: Complex nested data is flattened into columns

### Excel Export
- **Use Case**: Business reporting, advanced analysis
- **Features**: Multiple sheets, formatting, formulas
- **File Extension**: `.xlsx`
- **Sheets**: Summary sheet + detailed data sheets

## Error Handling

### Common Error Types

#### ExtractionError
- **Cause**: General extraction processing errors
- **Examples**: AI service unavailable, processing timeout
- **HTTP Status**: 500

#### ExtractionValidationError
- **Cause**: Invalid input data or extraction results
- **Examples**: Unsupported file format, corrupted PDF
- **HTTP Status**: 400

#### FileValidationError
- **Cause**: File upload or validation issues
- **Examples**: File too large, invalid file type
- **HTTP Status**: 400

### Error Response Format

```json
{
  "success": false,
  "error": {
    "type": "ExtractionError",
    "message": "Failed to extract data from document",
    "details": "The document appears to be corrupted or unreadable",
    "code": "EXTRACTION_FAILED"
  },
  "job_id": "extract_invoice_abc123"
}
```

## Configuration

### Environment Variables

```bash
# AI Service Configuration (OpenRouter)
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_DEFAULT_MODEL=deepseek/deepseek-v3-free
OPENROUTER_MAX_TOKENS=4000
OPENROUTER_TIMEOUT=30
OPENROUTER_REFERER=https://www.pdfsmaller.site
OPENROUTER_TITLE=PDF Smaller

# Extraction Service Configuration
EXTRACTION_MAX_FILE_SIZE=10485760  # 10MB
EXTRACTION_TIMEOUT=300  # 5 minutes
EXTRACTION_RETRY_ATTEMPTS=3

# Export Configuration
EXPORT_MAX_RECORDS=10000
EXPORT_FORMATS=json,csv,excel
```

### Service Configuration

```python
# config/config.py
class Config:
    # AI Extraction Settings
    EXTRACTION_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    EXTRACTION_TIMEOUT = 300  # 5 minutes
    EXTRACTION_RETRY_ATTEMPTS = 3
    
    # Export Settings
    EXPORT_MAX_RECORDS = 10000
    EXPORT_FORMATS = ['json', 'csv', 'excel']
    
    # AI Model Settings (OpenRouter)
    OPENROUTER_DEFAULT_MODEL = 'deepseek/deepseek-v3-free'
    OPENROUTER_MAX_TOKENS = 4000
    OPENROUTER_TIMEOUT = 30
    OPENROUTER_TEMPERATURE = 0.1
```

### Available AI Models

The extraction service supports multiple AI models through OpenRouter:

**DeepSeek Models** (Cost-effective, recommended for most extractions):
- `deepseek/deepseek-v3` - Latest DeepSeek model with high accuracy
- `deepseek/deepseek-v3-free` - Free tier, excellent for basic extractions (default)
- `deepseek/deepseek-chat` - Optimized for conversational understanding
- `deepseek/deepseek-coder` - Enhanced for technical document processing
- `deepseek/deepseek-r1` - Advanced reasoning for complex document structures

**Moonshot Models** (Good balance of cost and capability):
- `moonshot/moonshot-k2-free` - Free tier with good performance
- `moonshot/moonshot-k2-premium` - Premium version with enhanced accuracy
- `moonshot/moonshot-v1-32k` - 32K context window for longer documents
- `moonshot/moonshot-v1-128k` - 128K context window for very large documents

**OpenAI Models** (High accuracy, higher cost):
- `openai/gpt-4-turbo` - Latest GPT-4 with excellent extraction capabilities
- `openai/gpt-3.5-turbo` - Most affordable OpenAI option

**Anthropic Models** (Excellent for complex documents):
- `anthropic/claude-3-haiku` - Fastest and most affordable Claude model
- `anthropic/claude-3-sonnet` - Balanced performance and cost
- `anthropic/claude-3-opus` - Highest capability for complex extractions

### Model Selection Guidelines

**For Invoice Extraction:**
- **Simple invoices**: `deepseek/deepseek-v3-free`, `moonshot/moonshot-k2-free`
- **Complex invoices**: `deepseek/deepseek-v3`, `anthropic/claude-3-sonnet`
- **High accuracy required**: `openai/gpt-4-turbo`, `anthropic/claude-3-opus`

**For Bank Statement Extraction:**
- **Standard statements**: `deepseek/deepseek-v3-free`, `moonshot/moonshot-k2-premium`
- **Multi-page statements**: `moonshot/moonshot-v1-128k`, `openai/gpt-4-turbo`
- **Complex formats**: `deepseek/deepseek-r1`, `anthropic/claude-3-opus`

## Performance Considerations

### Processing Times
- **Small documents** (1-2 pages): 15-30 seconds
- **Medium documents** (3-10 pages): 30-60 seconds
- **Large documents** (10+ pages): 60-120 seconds

### Optimization Tips
- Use high-quality PDF files for better extraction accuracy
- Ensure documents are text-based rather than image-only
- Consider file size limits for optimal processing speed
- Use appropriate export formats based on data complexity

### Rate Limits
- **Concurrent extractions**: 5 per user
- **Daily extraction limit**: 100 per user
- **File size limit**: 10MB per file

## Security Considerations

### Data Privacy
- Uploaded files are processed in memory and not permanently stored
- Extracted data is temporarily cached for job status tracking
- All data is purged after job completion or timeout

### Access Control
- API endpoints require valid authentication
- File upload validation prevents malicious files
- Rate limiting prevents abuse

### Compliance
- GDPR compliant data processing
- No persistent storage of sensitive document content
- Audit logging for all extraction operations

## Troubleshooting

### Common Issues

#### Low Extraction Accuracy
- **Cause**: Poor document quality, complex layouts
- **Solution**: Use high-quality scanned documents, check for text layer

#### Processing Timeouts
- **Cause**: Large files, complex documents
- **Solution**: Reduce file size, split large documents

#### Export Failures
- **Cause**: Invalid data structure, disk space issues
- **Solution**: Check extracted data format, verify system resources

### Debug Information

Enable debug logging to get detailed extraction information:

```python
import logging
logging.getLogger('extraction_service').setLevel(logging.DEBUG)
```

## Integration Examples

### Python Client Example

```python
import requests
import time

# Upload and start extraction
with open('invoice.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:5000/api/pdf-suite/extract/invoice',
        files={'file': f},
        data={'export_format': 'json'}
    )

job_data = response.json()
job_id = job_data['job_id']

# Poll for completion
while True:
    status_response = requests.get(f'http://localhost:5000/api/jobs/{job_id}')
    status_data = status_response.json()
    
    if status_data['status'] == 'completed':
        extracted_data = status_data['result']
        break
    elif status_data['status'] == 'failed':
        print(f"Extraction failed: {status_data['error']}")
        break
    
    time.sleep(2)
```

### JavaScript Client Example

```javascript
// Upload and start extraction
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('export_format', 'json');

const response = await fetch('/api/pdf-suite/extract/invoice', {
    method: 'POST',
    body: formData
});

const jobData = await response.json();
const jobId = jobData.job_id;

// Poll for completion
const pollStatus = async () => {
    const statusResponse = await fetch(`/api/jobs/${jobId}`);
    const statusData = await statusResponse.json();
    
    if (statusData.status === 'completed') {
        console.log('Extracted data:', statusData.result);
    } else if (statusData.status === 'failed') {
        console.error('Extraction failed:', statusData.error);
    } else {
        setTimeout(pollStatus, 2000);
    }
};

pollStatus();
```

## Future Enhancements

### Planned Features
- Support for additional document types (receipts, purchase orders)
- Batch processing capabilities
- Custom extraction templates
- Machine learning model fine-tuning
- Real-time extraction progress updates

### API Versioning
- Current version: v1
- Backward compatibility guaranteed for major versions
- Deprecation notices provided 6 months in advance

## Support

For technical support or questions about the AI extraction features:
- Check the troubleshooting guide
- Review API documentation
- Contact the development team
- Submit issues through the project repository
