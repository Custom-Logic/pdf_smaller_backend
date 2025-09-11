# PDF Smaller Backend API Documentation

## Overview

This API provides PDF compression and processing services. It allows users to upload PDF files, compress them with various settings, and download the compressed results.

## Base URL

```
http://localhost:5000/api
```

## Endpoints

### PDF Compression

#### Compress a PDF

```
POST /compress
```

**Description**: Upload a PDF file for compression. Returns a job ID immediately and processes the file asynchronously.

**Request**:
- Content-Type: `multipart/form-data`

**Form Parameters**:
- `file` (required): The PDF file to compress
- `compressionLevel` (optional): Compression level - `low`, `medium`, `high`, or `maximum` (default: `medium`)
- `imageQuality` (optional): Image quality for compression, 10-100 (default: 80)

**Response**:
```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Compression job queued successfully"
}
```

**Status Code**: 202 Accepted

#### Get Job Status

```
GET /jobs/{job_id}
```

**Description**: Check the status of a compression job.

**Path Parameters**:
- `job_id` (required): The job ID returned from the compression request

**Response (Pending/Processing)**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "task_type": "compression",
  "created_at": "2023-06-15T10:30:00.000Z",
  "updated_at": "2023-06-15T10:30:05.000Z"
}
```

**Response (Completed)**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "task_type": "compression",
  "created_at": "2023-06-15T10:30:00.000Z",
  "updated_at": "2023-06-15T10:31:00.000Z",
  "result": {
    "original_size": 1048576,
    "compressed_size": 524288,
    "compression_ratio": 50.0,
    "output_path": "/path/to/compressed/file.pdf",
    "original_filename": "document.pdf"
  },
  "download_url": "/api/jobs/550e8400-e29b-41d4-a716-446655440000/download"
}
```

**Response (Failed)**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "task_type": "compression",
  "created_at": "2023-06-15T10:30:00.000Z",
  "updated_at": "2023-06-15T10:30:30.000Z",
  "error": "Failed to process PDF: Invalid file format"
}
```

**Status Code**: 200 OK

#### Download Compressed PDF

```
GET /jobs/{job_id}/download
```

**Description**: Download the compressed PDF file for a completed job.

**Path Parameters**:
- `job_id` (required): The job ID of the completed compression job

**Response**: The compressed PDF file as an attachment.

**Status Code**: 200 OK

### Bulk Compression

```
POST /bulk
```

**Description**: Upload multiple PDF files for compression. Returns a job ID immediately and processes the files asynchronously.

**Request**:
- Content-Type: `multipart/form-data`

**Form Parameters**:
- `files` (required): Multiple PDF files to compress
- `compressionLevel` (optional): Compression level - `low`, `medium`, `high`, or `maximum` (default: `medium`)
- `imageQuality` (optional): Image quality for compression, 10-100 (default: 80)

**Response**:
```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Bulk compression job queued successfully",
  "file_count": 3
}
```

**Status Code**: 202 Accepted

## Error Responses

### Bad Request (400)

```json
{
  "error": "No file provided"
}
```

### Not Found (404)

```json
{
  "error": "Job not found"
}
```

### Server Error (500)

```json
{
  "error": "Failed to create compression job: Internal server error"
}
```

### Extended Features

#### PDF Conversion

```
POST /convert
```

**Description**: Convert PDF to various formats (Word, Excel, Text, HTML). Returns a job ID immediately and processes the file asynchronously.

**Request**:
- Content-Type: `multipart/form-data`

**Form Parameters**:
- `file` (required): The PDF file to convert
- `format` (optional): Target format - `docx`, `xlsx`, `txt`, or `html` (default: `docx`)
- `options` (optional): JSON string with conversion options
- `job_id` (optional): Custom job ID (UUID format)

**Response**:
```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "celery-task-id",
  "status": "pending",
  "format": "docx",
  "message": "Conversion job queued successfully"
}
```

**Status Code**: 202 Accepted

#### PDF Conversion Preview

```
POST /convert/preview
```

**Description**: Get conversion preview and estimates. Returns a job ID for async processing.

**Request**: Same as `/convert`

**Response**: Same format as `/convert`

#### OCR Processing

```
POST /ocr
```

**Description**: Extract text from scanned PDFs and images using OCR. Returns a job ID immediately and processes the file asynchronously.

**Request**:
- Content-Type: `multipart/form-data`

**Form Parameters**:
- `file` (required): The PDF or image file (PDF, PNG, JPG, JPEG, TIFF, BMP)
- `options` (optional): JSON string with OCR options (language, quality, output format)
- `job_id` (optional): Custom job ID (UUID format)

**Response**:
```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "celery-task-id",
  "status": "pending",
  "message": "OCR job queued successfully"
}
```

**Status Code**: 202 Accepted

#### OCR Preview

```
POST /ocr/preview
```

**Description**: Get OCR preview and estimates. Returns a job ID for async processing.

**Request**: Same as `/ocr`

**Response**: Same format as `/ocr`

### AI-Powered Features

#### AI Text Summarization

```
POST /ai/summarize
```

**Description**: Summarize text content using AI. Returns a job ID immediately and processes asynchronously.

**Request**:
- Content-Type: `application/json`

**JSON Parameters**:
- `text` (required): Text content to summarize (max 100KB)
- `options` (optional): Summarization options (style, length, etc.)

**Response**:
```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "celery-task-id",
  "status": "pending",
  "message": "Summarization job queued successfully"
}
```

**Status Code**: 202 Accepted

#### AI Text Translation

```
POST /ai/translate
```

**Description**: Translate text using AI. Returns a job ID immediately and processes asynchronously.

**Request**:
- Content-Type: `application/json`

**JSON Parameters**:
- `text` (required): Text content to translate (max 100KB)
- `target_language` (optional): Target language code (default: 'en')
- `options` (optional): Translation options

**Response**:
```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "celery-task-id",
  "status": "pending",
  "message": "Translation job queued successfully"
}
```

**Status Code**: 202 Accepted

#### AI Text Extraction

```
POST /ai/extract-text
```

**Description**: Extract and analyze text content from PDF using AI. Returns a job ID immediately and processes asynchronously.

**Request**:
- Content-Type: `multipart/form-data`

**Form Parameters**:
- `file` (required): The PDF file
- `job_id` (optional): Custom job ID (UUID format)

**Response**:
```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "task_id": "celery-task-id",
  "status": "pending",
  "message": "Text extraction job queued successfully"
}
```

**Status Code**: 202 Accepted

### Cloud Integration

#### Exchange Cloud Token

```
POST /cloud/{provider}/token
```

**Description**: Exchange authorization code for access token with cloud providers.

**Path Parameters**:
- `provider` (required): Cloud provider (`google_drive`, `dropbox`, `onedrive`)

**Request**:
- Content-Type: `application/json`

**JSON Parameters**:
- `code` (required): Authorization code from OAuth flow
- `redirect_uri` (optional): Redirect URI used in OAuth flow

**Response**:
```json
{
  "success": true,
  "message": "Token exchange successful",
  "data": {
    "access_token": "token_value",
    "expires_in": 3600
  }
}
```

**Status Code**: 200 OK

#### Validate Cloud Token

```
GET /cloud/{provider}/validate
```

**Description**: Validate cloud provider access token.

**Path Parameters**:
- `provider` (required): Cloud provider (`google_drive`, `dropbox`, `onedrive`)

**Headers**:
- `Authorization`: Bearer token

**Response**:
```json
{
  "success": true,
  "message": "Token is valid",
  "data": {
    "valid": true
  }
}
```

**Status Code**: 200 OK

### System Status and Capabilities

#### Extended Features Status

```
GET /extended-features/status
```

**Description**: Get status of all extended features and system health.

**Response**:
```json
{
  "success": true,
  "message": "Extended features status retrieved successfully",
  "data": {
    "conversion": {
      "available": true,
      "supported_formats": ["docx", "xlsx", "txt", "html"],
      "max_file_size": "100MB",
      "async_processing": true
    },
    "ocr": {
      "available": true,
      "supported_formats": ["pdf", "png", "jpg", "jpeg", "tiff", "bmp"],
      "max_file_size": "50MB",
      "async_processing": true
    },
    "ai": {
      "available": true,
      "supported_formats": ["pdf"],
      "max_file_size": "25MB",
      "async_processing": true
    },
    "cloud": {
      "available": true,
      "supported_providers": ["google_drive", "dropbox", "onedrive"],
      "async_processing": false
    },
    "queue": {
      "redis_available": true,
      "job_processing": true
    }
  }
}
```

**Status Code**: 200 OK

#### Extended Features Capabilities

```
GET /extended-features/capabilities
```

**Description**: Get detailed capabilities and options for all extended features.

**Response**:
```json
{
  "success": true,
  "message": "Extended features capabilities retrieved successfully",
  "data": {
    "conversion": {
      "name": "PDF Conversion",
      "description": "Convert PDFs to Word, Excel, Text, and HTML formats",
      "features": ["format_conversion", "layout_preservation", "table_extraction"],
      "options": {
        "preserveLayout": "boolean",
        "extractTables": "boolean",
        "extractImages": "boolean",
        "quality": "string (low|medium|high)"
      },
      "processing_mode": "async"
    },
    "ocr": {
      "name": "Optical Character Recognition",
      "description": "Extract text from scanned PDFs and images",
      "features": ["text_extraction", "searchable_pdf", "language_support"],
      "options": {
        "language": "string",
        "quality": "string (fast|balanced|accurate)",
        "outputFormat": "string (searchable_pdf|text|json)"
      },
      "processing_mode": "async"
    },
    "ai": {
      "name": "AI-Powered Features",
      "description": "Summarize and translate PDF content using AI",
      "features": ["summarization", "translation", "multiple_languages"],
      "options": {
        "style": "string (concise|detailed|academic|casual|professional)",
        "maxLength": "string (short|medium|long)",
        "targetLanguage": "string (language code)"
      },
      "processing_mode": "async"
    },
    "cloud": {
      "name": "Cloud Integration",
      "description": "Save and load files from cloud storage providers",
      "features": ["file_upload", "file_download", "folder_management", "oauth_authentication"],
      "providers": ["google_drive", "dropbox", "onedrive"],
      "processing_mode": "sync"
    }
  }
}
```

**Status Code**: 200 OK

### Health Check Endpoints

#### Main Health Check

```
GET /health
```

**Description**: Basic health check for the API service.

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2023-06-15T10:30:00.000Z",
  "version": "1.0.0"
}
```

**Status Code**: 200 OK

#### Compression Service Health

```
GET /compress/health
```

**Description**: Health check specifically for compression services.

**Response**:
```json
{
  "status": "healthy",
  "service": "compression",
  "timestamp": "2023-06-15T10:30:00.000Z"
}
```

**Status Code**: 200 OK

## File Size Limits

- **PDF Compression**: No specific limit (handled by server configuration)
- **PDF Conversion**: 100MB maximum
- **OCR Processing**: 50MB maximum  
- **AI Features**: 25MB maximum
- **AI Text Input**: 100KB maximum for direct text input

## Supported File Formats

### Input Formats
- **Compression**: PDF
- **Conversion**: PDF
- **OCR**: PDF, PNG, JPG, JPEG, TIFF, BMP
- **AI Features**: PDF (for file upload), plain text (for direct input)

### Output Formats
- **Compression**: PDF
- **Conversion**: DOCX, XLSX, TXT, HTML
- **OCR**: Searchable PDF, plain text, JSON
- **AI Features**: JSON (structured responses)

## Rate Limiting

The API has a default rate limit of 100 requests per hour. If you exceed this limit, you'll receive a 429 Too Many Requests response.

## CORS

Cross-Origin Resource Sharing is enabled for specific origins configured in the application.