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

## Rate Limiting

The API has a default rate limit of 100 requests per hour. If you exceed this limit, you'll receive a 429 Too Many Requests response.

## CORS

Cross-Origin Resource Sharing is enabled for specific origins configured in the application.