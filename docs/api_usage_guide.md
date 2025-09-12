# PDF Smaller API Usage Guide

This guide provides comprehensive examples and best practices for using the PDF Smaller API.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Single File Compression](#single-file-compression)
3. [Bulk File Compression](#bulk-file-compression)
4. [Job Management](#job-management)
5. [Error Handling](#error-handling)
6. [Rate Limiting](#rate-limiting)
7. [Best Practices](#best-practices)
8. [Code Examples](#code-examples)

## Getting Started

### Base URL

- **Development**: `http://localhost:5000`

### Content Types

- **JSON responses**: `Content-Type: application/json`
- **File uploads**: `Content-Type: multipart/form-data`
- **File downloads**: `Content-Type: application/pdf` or `application/zip`

### Health Check

```bash
curl -X GET http://localhost:5000/api/health
```

**Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "database_type": "sqlite"
}
```

## Single File Compression

### Basic Compression

```bash
curl -X POST http://localhost:5000/api/compress \
  -F "file=@document.pdf" \
  -F "compressionLevel=medium" \
  -F "imageQuality=80"
```

**Response:**
```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Compression job queued successfully"
}
```

### Compression Parameters

| Parameter | Type | Values | Default | Description |
|-----------|------|--------|---------|-------------|
| `file` | binary | - | Required | PDF file to compress |
| `compressionLevel` | string | `low`, `medium`, `high`, `maximum` | `medium` | Compression intensity |
| `imageQuality` | integer | 10-100 | 80 | Image quality percentage |

## Bulk File Compression

### Start Bulk Compression Job

```bash
curl -X POST http://localhost:5000/api/compress/bulk \
  -F "files=@document1.pdf" \
  -F "files=@document2.pdf" \
  -F "files=@document3.pdf" \
  -F "compressionLevel=high" \
  -F "imageQuality=70"
```

**Response:**
```json
{
  "success": true,
  "job_id": "550e8400-e29b-41d4-a716-446655440001",
  "status": "pending",
  "message": "Bulk compression job queued successfully",
  "file_count": 3
}
```

## Job Management

### Check Job Status

```bash
curl -X GET http://localhost:5000/api/jobs/550e8400-e29b-41d4-a716-446655440000
```

**Response (Pending):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "task_type": "compression",
  "created_at": "2023-06-15T10:30:00.000Z",
  "updated_at": "2023-06-15T10:30:00.000Z"
}
```

**Response (Completed):**
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

**Response (Failed):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "task_type": "compression",
  "created_at": "2023-06-15T10:30:00.000Z",
  "updated_at": "2023-06-15T10:31:00.000Z",
  "error": "Failed to process PDF: Invalid file format"
}
```

### Job Status Values

| Status | Description |
|--------|-------------|
| `pending` | Job is queued and waiting to be processed |
| `processing` | Job is currently being processed |
| `completed` | Job completed successfully |
| `failed` | Job failed with an error |

### Download Compressed File

```bash
curl -X GET http://localhost:5000/api/jobs/550e8400-e29b-41d4-a716-446655440000/download \
  --output compressed_document.pdf
```

## Error Handling

### Standard Error Response Format

All API errors follow this consistent format:

```json
{
  "error": "Invalid request"
}
```

### Common Error Codes

| HTTP Status | Description |
|-------------|-------------|
| `400` | Bad request - invalid input or missing required fields |
| `404` | Resource not found (job or file) |
| `410` | File has been cleaned up and is no longer available |
| `413` | File too large |
| `429` | Rate limit exceeded |
| `500` | Internal server error |

### Error Handling Examples

#### Handle Rate Limiting

```bash
# Response includes rate limit information
HTTP/1.1 429 Too Many Requests

{
  "error": "Rate limit exceeded"
}
```

#### Handle File Not Found

```json
{
  "error": "Job not found"
}
```

#### Handle Invalid File

```json
{
  "error": "Invalid file type. Only PDF files are allowed."
}
```

## Rate Limiting

### Rate Limits

All endpoints are rate-limited to **100 requests per hour** for all users.

### Rate Limit Best Practices

- Implement exponential backoff for 429 responses
- Cache job status responses to reduce API calls
- Poll job status at reasonable intervals (5-10 seconds)

## Best Practices

### 1. File Upload Optimization

- **Validate files client-side**: Check file type and size before upload
- **Use appropriate compression levels**: Balance quality vs. file size
- **Handle large files**: Be aware of server file size limits

```javascript
// File validation example
function validatePDFFile(file) {
  const maxSize = 100 * 1024 * 1024; // 100MB (adjust based on server limits)
  const allowedTypes = ['application/pdf'];
  
  if (!allowedTypes.includes(file.type)) {
    throw new Error('Only PDF files are allowed');
  }
  
  if (file.size > maxSize) {
    throw new Error('File size exceeds limit');
  }
  
  return true;
}
```

### 2. Job Status Polling

- **Use reasonable intervals**: Poll every 5-10 seconds
- **Implement timeout**: Don't poll indefinitely
- **Handle all status states**: pending, processing, completed, failed

```javascript
// Job monitoring with timeout
async function monitorJob(jobId, timeoutMs = 300000) { // 5 minute timeout
  const startTime = Date.now();
  const pollInterval = 5000; // 5 seconds
  
  while (Date.now() - startTime < timeoutMs) {
    const response = await fetch(`/api/jobs/${jobId}`);
    const job = await response.json();
    
    if (job.status === 'completed') {
      return job;
    } else if (job.status === 'failed') {
      throw new Error(job.error || 'Job failed');
    }
    
    await new Promise(resolve => setTimeout(resolve, pollInterval));
  }
  
  throw new Error('Job monitoring timeout');
}
```

### 3. Error Handling Strategy

- **Implement retry logic**: For rate limits and temporary errors
- **Provide user-friendly messages**: Convert technical errors to readable text
- **Log errors appropriately**: For debugging and monitoring

```javascript
// Retry logic with exponential backoff
async function apiRequestWithRetry(url, options, maxRetries = 3) {
  let attempt = 0;
  
  while (attempt < maxRetries) {
    try {
      const response = await fetch(url, options);
      
      if (response.status === 429) {
        const delay = Math.pow(2, attempt) * 1000; // Exponential backoff
        await new Promise(resolve => setTimeout(resolve, delay));
        attempt++;
        continue;
      }
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error);
      }
      
      return response;
    } catch (error) {
      if (attempt === maxRetries - 1) {
        throw error;
      }
      
      const delay = Math.pow(2, attempt) * 1000;
      await new Promise(resolve => setTimeout(resolve, delay));
      attempt++;
    }
  }
}
```

### 4. Bulk Processing Workflow

- **Monitor job progress**: Poll status endpoint for updates
- **Handle job failures**: Implement appropriate error handling
- **Download results promptly**: Files may be cleaned up after a period

```javascript
// Complete bulk processing workflow
async function processBulkFiles(files) {
  // 1. Start bulk job
  const formData = new FormData();
  files.forEach(file => formData.append('files', file));
  formData.append('compressionLevel', 'medium');
  
  const response = await fetch('/api/compress/bulk', {
    method: 'POST',
    body: formData
  });
  
  const job = await response.json();
  
  // 2. Monitor progress
  const result = await monitorJob(job.job_id);
  
  // 3. Download results
  if (result.status === 'completed') {
    const downloadResponse = await fetch(`/api/jobs/${job.job_id}/download`);
    return await downloadResponse.blob();
  } else {
    throw new Error(result.error);
  }
}
```

## Code Examples

### Python Example

```python
import requests
import time
from typing import Optional

class PDFSmallerClient:
    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
    
    def compress_file(self, file_path: str, compression_level: str = "medium", 
                     image_quality: int = 80) -> dict:
        """Start compression job for a single PDF file"""
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {
                "compressionLevel": compression_level,
                "imageQuality": image_quality
            }
            
            response = requests.post(
                f"{self.base_url}/api/compress",
                files=files,
                data=data
            )
            response.raise_for_status()
            
            return response.json()
    
    def start_bulk_compression(self, file_paths: list, compression_level: str = "medium",
                              image_quality: int = 80) -> dict:
        """Start bulk compression job"""
        files = [("files", open(path, "rb")) for path in file_paths]
        data = {
            "compressionLevel": compression_level,
            "imageQuality": image_quality
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/compress/bulk",
                files=files,
                data=data
            )
            response.raise_for_status()
            
            return response.json()
        finally:
            # Close all file handles
            for _, file_handle in files:
                file_handle.close()
    
    def get_job_status(self, job_id: str) -> dict:
        """Get job status"""
        response = requests.get(f"{self.base_url}/api/jobs/{job_id}")
        response.raise_for_status()
        return response.json()
    
    def download_file(self, job_id: str) -> bytes:
        """Download compressed file"""
        response = requests.get(f"{self.base_url}/api/jobs/{job_id}/download")
        response.raise_for_status()
        return response.content
    
    def monitor_job(self, job_id: str, timeout: int = 300) -> dict:
        """Monitor job until completion or timeout"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = self.get_job_status(job_id)
            
            if status["status"] == "completed":
                return status
            elif status["status"] == "failed":
                raise Exception(f"Job failed: {status.get('error', 'Unknown error')}")
            
            time.sleep(5)  # Wait 5 seconds before checking again
        
        raise TimeoutError("Job monitoring timeout")

# Usage example
client = PDFSmallerClient()

# Single file compression
job = client.compress_file("document.pdf", "high", 70)
print(f"Job started: {job['job_id']}")

# Monitor job
result = client.monitor_job(job["job_id"])
print(f"Compression completed. Ratio: {result['result']['compression_ratio']}%")

# Download compressed file
compressed_data = client.download_file(job["job_id"])
with open("compressed_document.pdf", "wb") as f:
    f.write(compressed_data)

# Bulk compression
bulk_job = client.start_bulk_compression(["doc1.pdf", "doc2.pdf", "doc3.pdf"])
print(f"Bulk job started: {bulk_job['job_id']} with {bulk_job['file_count']} files")

# Monitor bulk job
bulk_result = client.monitor_job(bulk_job["job_id"])
print("Bulk compression completed!")

# Download bulk results (ZIP file)
bulk_data = client.download_file(bulk_job["job_id"])
with open("bulk_results.zip", "wb") as f:
    f.write(bulk_data)
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

class PDFSmallerClient {
  constructor(baseUrl = 'http://localhost:5000') {
    this.baseUrl = baseUrl;
  }

  async compressFile(filePath, compressionLevel = 'medium', imageQuality = 80) {
    const formData = new FormData();
    formData.append('file', fs.createReadStream(filePath));
    formData.append('compressionLevel', compressionLevel);
    formData.append('imageQuality', imageQuality.toString());

    try {
      const response = await axios.post(`${this.baseUrl}/api/compress`, formData, {
        headers: formData.getHeaders()
      });

      return response.data;
    } catch (error) {
      throw new Error(`Compression failed: ${error.response?.data?.error || error.message}`);
    }
  }

  async startBulkCompression(filePaths, compressionLevel = 'medium', imageQuality = 80) {
    const formData = new FormData();
    
    filePaths.forEach(filePath => {
      formData.append('files', fs.createReadStream(filePath));
    });
    
    formData.append('compressionLevel', compressionLevel);
    formData.append('imageQuality', imageQuality.toString());

    try {
      const response = await axios.post(`${this.baseUrl}/api/compress/bulk`, formData, {
        headers: formData.getHeaders()
      });

      return response.data;
    } catch (error) {
      throw new Error(`Bulk compression failed: ${error.response?.data?.error || error.message}`);
    }
  }

  async getJobStatus(jobId) {
    try {
      const response = await axios.get(`${this.baseUrl}/api/jobs/${jobId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get job status: ${error.response?.data?.error || error.message}`);
    }
  }

  async downloadFile(jobId) {
    try {
      const response = await axios.get(`${this.baseUrl}/api/jobs/${jobId}/download`, {
        responseType: 'arraybuffer'
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to download file: ${error.response?.data?.error || error.message}`);
    }
  }

  async monitorJob(jobId, timeoutMs = 300000) {
    const startTime = Date.now();
    const pollInterval = 5000; // 5 seconds
    
    while (Date.now() - startTime < timeoutMs) {
      const status = await this.getJobStatus(jobId);
      
      if (status.status === 'completed') {
        return status;
      } else if (status.status === 'failed') {
        throw new Error(status.error || 'Job failed');
      }
      
      await new Promise(resolve => setTimeout(resolve, pollInterval));
    }
    
    throw new Error('Job monitoring timeout');
  }
}

// Usage example
async function main() {
  const client = new PDFSmallerClient();
  
  try {
    // Single file compression
    const job = await client.compressFile('document.pdf', 'high', 70);
    console.log(`Job started: ${job.job_id}`);

    // Monitor job
    const result = await client.monitorJob(job.job_id);
    console.log(`Compression completed. Ratio: ${result.result.compression_ratio}%`);

    // Download compressed file
    const compressedData = await client.downloadFile(job.job_id);
    fs.writeFileSync('compressed_document.pdf', compressedData);
    console.log('File downloaded successfully');

    // Bulk compression
    const bulkJob = await client.startBulkCompression(['doc1.pdf', 'doc2.pdf', 'doc3.pdf']);
    console.log(`Bulk job started: ${bulkJob.job_id} with ${bulkJob.file_count} files`);

    // Monitor bulk job
    const bulkResult = await client.monitorJob(bulkJob.job_id);
    console.log('Bulk compression completed!');

    // Download bulk results
    const bulkData = await client.downloadFile(bulkJob.job_id);
    fs.writeFileSync('bulk_results.zip', bulkData);
    console.log('Bulk results downloaded successfully');

  } catch (error) {
    console.error('Error:', error.message);
  }
}

main();
```

### Browser JavaScript Example

```html
<!DOCTYPE html>
<html>
<head>
    <title>PDF Smaller Client</title>
</head>
<body>
    <input type="file" id="fileInput" accept=".pdf" multiple>
    <button onclick="compressFiles()">Compress Files</button>
    <div id="status"></div>
    <div id="results"></div>

    <script>
        class PDFSmallerClient {
            constructor(baseUrl = 'http://localhost:5000') {
                this.baseUrl = baseUrl;
            }

            async compressFile(file, compressionLevel = 'medium', imageQuality = 80) {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('compressionLevel', compressionLevel);
                formData.append('imageQuality', imageQuality);

                const response = await fetch(`${this.baseUrl}/api/compress`, {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error);
                }

                return response.json();
            }

            async startBulkCompression(files, compressionLevel = 'medium', imageQuality = 80) {
                const formData = new FormData();
                
                files.forEach(file => {
                    formData.append('files', file);
                });
                
                formData.append('compressionLevel', compressionLevel);
                formData.append('imageQuality', imageQuality);

                const response = await fetch(`${this.baseUrl}/api/compress/bulk`, {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error);
                }

                return response.json();
            }

            async getJobStatus(jobId) {
                const response = await fetch(`${this.baseUrl}/api/jobs/${jobId}`);
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error);
                }

                return response.json();
            }

            async downloadFile(jobId) {
                const response = await fetch(`${this.baseUrl}/api/jobs/${jobId}/download`);
                
                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.error);
                }

                return response.blob();
            }

            async monitorJob(jobId, onProgress = null) {
                const startTime = Date.now();
                const timeout = 300000; // 5 minutes
                const pollInterval = 5000; // 5 seconds
                
                while (Date.now() - startTime < timeout) {
                    const status = await this.getJobStatus(jobId);
                    
                    if (onProgress) {
                        onProgress(status);
                    }
                    
                    if (status.status === 'completed') {
                        return status;
                    } else if (status.status === 'failed') {
                        throw new Error(status.error || 'Job failed');
                    }
                    
                    await new Promise(resolve => setTimeout(resolve, pollInterval));
                }
                
                throw new Error('Job monitoring timeout');
            }
        }

        const client = new PDFSmallerClient();

        async function compressFiles() {
            const fileInput = document.getElementById('fileInput');
            const statusDiv = document.getElementById('status');
            const resultsDiv = document.getElementById('results');
            
            const files = Array.from(fileInput.files);
            
            if (files.length === 0) {
                alert('Please select at least one PDF file');
                return;
            }

            try {
                statusDiv.innerHTML = 'Starting compression...';
                
                let job;
                if (files.length === 1) {
                    job = await client.compressFile(files[0]);
                } else {
                    job = await client.startBulkCompression(files);
                }
                
                statusDiv.innerHTML = `Job started: ${job.job_id}`;
                
                // Monitor job progress
                const result = await client.monitorJob(job.job_id, (status) => {
                    statusDiv.innerHTML = `Status: ${status.status}`;
                });
                
                statusDiv.innerHTML = 'Compression completed! Downloading...';
                
                // Download result
                const blob = await client.downloadFile(job.job_id);
                const url = URL.createObjectURL(blob);
                
                const downloadLink = document.createElement('a');
                downloadLink.href = url;
                downloadLink.download = files.length === 1 ? 'compressed.pdf' : 'compressed_files.zip';
                downloadLink.textContent = 'Download Compressed File(s)';
                
                resultsDiv.innerHTML = '';
                resultsDiv.appendChild(downloadLink);
                
                statusDiv.innerHTML = 'Ready for download!';
                
            } catch (error) {
                statusDiv.innerHTML = `Error: ${error.message}`;
                console.error('Compression error:', error);
            }
        }
    </script>
</body>
</html>
```

This comprehensive API usage guide provides developers with everything they need to integrate with the PDF Smaller API effectively, including file compression, job monitoring, bulk processing, and robust error handling strategies.
