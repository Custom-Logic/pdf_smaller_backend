# PDF Smaller API Usage Guide

This guide provides comprehensive examples and best practices for using the PDF Smaller API.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [Single File Compression](#single-file-compression)
4. [Bulk File Compression](#bulk-file-compression)
5. [Subscription Management](#subscription-management)
6. [Error Handling](#error-handling)
7. [Rate Limiting](#rate-limiting)
8. [Best Practices](#best-practices)
9. [Code Examples](#code-examples)

## Getting Started

### Base URLs

- **Production**: `https://api.pdfsmaller.site`
- **Staging**: `https://staging-api.pdfsmaller.site`
- **Development**: `http://localhost:5000`

### Content Types

- **JSON requests**: `Content-Type: application/json`
- **File uploads**: `Content-Type: multipart/form-data`
- **Authentication**: `Authorization: Bearer <jwt_token>`

## Authentication

### User Registration

```bash
curl -X POST https://api.pdfsmaller.site/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!",
    "name": "John Doe"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "User registered successfully",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "name": "John Doe",
    "created_at": "2024-01-15T10:30:00Z",
    "is_active": true
  },
  "tokens": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "expires_in": 900
  }
}
```

### User Login

```bash
curl -X POST https://api.pdfsmaller.site/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "password": "SecurePass123!"
  }'
```

### Token Refresh

```bash
curl -X POST https://api.pdfsmaller.site/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
  }'
```

### Get User Profile

```bash
curl -X GET https://api.pdfsmaller.site/api/auth/profile \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
```

## Single File Compression

### Basic Compression

```bash
curl -X POST https://api.pdfsmaller.site/api/compress \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..." \
  -F "file=@document.pdf" \
  -F "compressionLevel=medium" \
  -F "imageQuality=80" \
  --output compressed_document.pdf
```

### Anonymous Compression (Limited)

```bash
curl -X POST https://api.pdfsmaller.site/api/compress \
  -F "file=@document.pdf" \
  -F "compressionLevel=medium" \
  --output compressed_document.pdf
```

### Get PDF Information

```bash
curl -X POST https://api.pdfsmaller.site/api/compress/info \
  -F "file=@document.pdf"
```

**Response:**
```json
{
  "Title": "Sample Document",
  "Author": "John Doe",
  "Creator": "Microsoft Word",
  "Producer": "Microsoft: Print To PDF",
  "CreationDate": "Mon Jan 15 10:30:00 2024",
  "ModDate": "Mon Jan 15 10:30:00 2024",
  "Pages": "5",
  "File size": "1024 bytes"
}
```

### Check Usage Statistics

```bash
curl -X GET https://api.pdfsmaller.site/api/compress/usage \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
```

## Bulk File Compression

### Start Bulk Compression Job

```bash
curl -X POST https://api.pdfsmaller.site/api/compress/bulk \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..." \
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
  "job_id": 456,
  "task_id": "task_789abc",
  "file_count": 3,
  "total_size_mb": 15.2,
  "status": "queued",
  "message": "Bulk compression job created with 3 files"
}
```

### Check Job Status

```bash
curl -X GET https://api.pdfsmaller.site/api/compress/bulk/jobs/456/status \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
```

**Response:**
```json
{
  "job_id": 456,
  "status": "processing",
  "job_type": "bulk",
  "file_count": 3,
  "completed_count": 2,
  "progress_percentage": 66.7,
  "created_at": "2024-01-15T10:30:00Z",
  "started_at": "2024-01-15T10:31:00Z",
  "is_completed": false,
  "is_successful": false,
  "error_message": null
}
```

### Download Bulk Results

```bash
curl -X GET https://api.pdfsmaller.site/api/compress/bulk/jobs/456/download \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..." \
  --output compressed_files.zip
```

### Get Bulk Job History

```bash
curl -X GET https://api.pdfsmaller.site/api/compress/bulk/jobs?limit=20 \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
```

## Subscription Management

### Get Available Plans

```bash
curl -X GET https://api.pdfsmaller.site/api/subscriptions/plans
```

**Response:**
```json
{
  "plans": [
    {
      "id": 1,
      "name": "free",
      "display_name": "Free Plan",
      "description": "Basic compression with daily limits",
      "price_monthly": 0.00,
      "price_yearly": 0.00,
      "features": {
        "daily_compressions": 10,
        "bulk_processing": false,
        "max_file_size_mb": 25,
        "max_bulk_files": 0,
        "api_access": false,
        "priority_processing": false
      }
    },
    {
      "id": 2,
      "name": "premium",
      "display_name": "Premium Plan",
      "description": "Advanced compression with bulk processing",
      "price_monthly": 9.99,
      "price_yearly": 99.99,
      "features": {
        "daily_compressions": 500,
        "bulk_processing": true,
        "max_file_size_mb": 100,
        "max_bulk_files": 20,
        "api_access": true,
        "priority_processing": true
      }
    }
  ]
}
```

### Create Subscription

```bash
curl -X POST https://api.pdfsmaller.site/api/subscriptions/create \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..." \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": 2,
    "payment_method_id": "pm_1234567890",
    "billing_cycle": "monthly"
  }'
```

### Get Subscription Info

```bash
curl -X GET https://api.pdfsmaller.site/api/subscriptions \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
```

### Cancel Subscription

```bash
curl -X POST https://api.pdfsmaller.site/api/subscriptions/cancel \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
```

## Error Handling

### Standard Error Response Format

All API errors follow this consistent format:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input provided",
    "details": {
      "missing_fields": ["email", "password"]
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123456789"
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid input or missing required fields |
| `UNAUTHORIZED` | 401 | Authentication required or invalid token |
| `FORBIDDEN` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMIT_EXCEEDED` | 429 | Rate limit exceeded |
| `USAGE_LIMIT_EXCEEDED` | 403 | Daily/monthly usage limit exceeded |
| `FILE_TOO_LARGE` | 413 | File exceeds size limit |
| `INVALID_FILE_TYPE` | 400 | File is not a valid PDF |
| `SUBSCRIPTION_REQUIRED` | 403 | Premium subscription required |
| `INTERNAL_SERVER_ERROR` | 500 | Unexpected server error |

### Error Handling Examples

#### Handle Rate Limiting

```bash
# Response includes Retry-After header
HTTP/1.1 429 Too Many Requests
Retry-After: 60

{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded",
    "details": {
      "limit": "10 per minute",
      "retry_after": 60
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123456789"
}
```

#### Handle Usage Limits

```json
{
  "error": {
    "code": "USAGE_LIMIT_EXCEEDED",
    "message": "Daily compression limit exceeded",
    "details": {
      "limit": 10,
      "used": 10,
      "reset_time": "2024-01-16T00:00:00Z"
    }
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123456789"
}
```

## Rate Limiting

### Rate Limits by User Tier

| User Tier | Rate Limit | Compression Limit |
|-----------|------------|-------------------|
| Anonymous | 10/minute | 5/day |
| Free | 20/minute | 10/day |
| Premium | 100/minute | 500/day |
| Pro | 500/minute | Unlimited |

### Rate Limit Headers

The API includes rate limit information in response headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642248000
```

## Best Practices

### 1. Authentication Management

- **Store tokens securely**: Never expose JWT tokens in client-side code
- **Implement token refresh**: Use refresh tokens to maintain sessions
- **Handle token expiration**: Implement automatic token refresh logic

```javascript
// Example token refresh logic
async function refreshTokenIfNeeded(token) {
  try {
    // Check if token is close to expiration
    const payload = JSON.parse(atob(token.split('.')[1]));
    const now = Date.now() / 1000;
    
    if (payload.exp - now < 300) { // Refresh if expires in 5 minutes
      const response = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken })
      });
      
      const data = await response.json();
      return data.tokens.access_token;
    }
    
    return token;
  } catch (error) {
    // Handle refresh error
    throw new Error('Token refresh failed');
  }
}
```

### 2. File Upload Optimization

- **Validate files client-side**: Check file type and size before upload
- **Use appropriate compression levels**: Balance quality vs. file size
- **Handle large files**: Consider chunked uploads for very large files

```javascript
// File validation example
function validatePDFFile(file) {
  const maxSize = 100 * 1024 * 1024; // 100MB
  const allowedTypes = ['application/pdf'];
  
  if (!allowedTypes.includes(file.type)) {
    throw new Error('Only PDF files are allowed');
  }
  
  if (file.size > maxSize) {
    throw new Error('File size exceeds 100MB limit');
  }
  
  return true;
}
```

### 3. Bulk Processing Workflow

- **Check permissions first**: Verify bulk processing is available
- **Monitor job progress**: Poll status endpoint for updates
- **Handle job failures**: Implement retry logic for failed jobs

```javascript
// Bulk processing workflow
async function processBulkFiles(files) {
  // 1. Validate permissions
  const permissions = await checkPermissions();
  if (!permissions.can_bulk_compress) {
    throw new Error('Bulk processing requires premium subscription');
  }
  
  // 2. Start bulk job
  const job = await startBulkJob(files);
  
  // 3. Monitor progress
  const result = await monitorJobProgress(job.job_id);
  
  // 4. Download results
  if (result.is_successful) {
    return await downloadBulkResult(job.job_id);
  } else {
    throw new Error(result.error_message);
  }
}

async function monitorJobProgress(jobId) {
  const maxAttempts = 60; // 5 minutes with 5-second intervals
  let attempts = 0;
  
  while (attempts < maxAttempts) {
    const status = await getBulkJobStatus(jobId);
    
    if (status.is_completed) {
      return status;
    }
    
    await new Promise(resolve => setTimeout(resolve, 5000)); // Wait 5 seconds
    attempts++;
  }
  
  throw new Error('Job monitoring timeout');
}
```

### 4. Error Handling Strategy

- **Implement exponential backoff**: For rate limit and server errors
- **Log request IDs**: Use request IDs for debugging and support
- **Provide user-friendly messages**: Convert technical errors to user-friendly text

```javascript
// Exponential backoff retry logic
async function apiRequestWithRetry(url, options, maxRetries = 3) {
  let attempt = 0;
  
  while (attempt < maxRetries) {
    try {
      const response = await fetch(url, options);
      
      if (response.status === 429) {
        const retryAfter = response.headers.get('Retry-After') || Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
        attempt++;
        continue;
      }
      
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.error.message);
      }
      
      return response;
    } catch (error) {
      if (attempt === maxRetries - 1) {
        throw error;
      }
      
      const delay = Math.pow(2, attempt) * 1000; // Exponential backoff
      await new Promise(resolve => setTimeout(resolve, delay));
      attempt++;
    }
  }
}
```

### 5. Usage Monitoring

- **Track usage proactively**: Monitor daily/monthly limits
- **Cache usage data**: Reduce API calls by caching usage statistics
- **Implement usage warnings**: Warn users before hitting limits

```javascript
// Usage monitoring example
class UsageMonitor {
  constructor() {
    this.usageCache = null;
    this.cacheExpiry = null;
  }
  
  async getUsageStats(forceRefresh = false) {
    const now = Date.now();
    
    if (!forceRefresh && this.usageCache && this.cacheExpiry > now) {
      return this.usageCache;
    }
    
    const response = await fetch('/api/compress/usage', {
      headers: { 'Authorization': `Bearer ${accessToken}` }
    });
    
    const usage = await response.json();
    
    this.usageCache = usage;
    this.cacheExpiry = now + (5 * 60 * 1000); // Cache for 5 minutes
    
    return usage;
  }
  
  async checkUsageBeforeCompression() {
    const usage = await this.getUsageStats();
    
    const remaining = usage.usage.daily_limit - usage.usage.compressions_today;
    
    if (remaining <= 0) {
      throw new Error('Daily compression limit exceeded');
    }
    
    if (remaining <= 2) {
      console.warn(`Only ${remaining} compressions remaining today`);
    }
    
    return true;
  }
}
```

## Code Examples

### Python Example

```python
import requests
import json
from typing import Optional

class PDFSmallerClient:
    def __init__(self, base_url: str = "https://api.pdfsmaller.site"):
        self.base_url = base_url
        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
    
    def login(self, email: str, password: str) -> dict:
        """Login and store tokens"""
        response = requests.post(
            f"{self.base_url}/api/auth/login",
            json={"email": email, "password": password}
        )
        response.raise_for_status()
        
        data = response.json()
        self.access_token = data["tokens"]["access_token"]
        self.refresh_token = data["tokens"]["refresh_token"]
        
        return data
    
    def compress_file(self, file_path: str, compression_level: str = "medium", 
                     image_quality: int = 80) -> bytes:
        """Compress a single PDF file"""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        with open(file_path, "rb") as f:
            files = {"file": f}
            data = {
                "compressionLevel": compression_level,
                "imageQuality": image_quality
            }
            
            response = requests.post(
                f"{self.base_url}/api/compress",
                headers=headers,
                files=files,
                data=data
            )
            response.raise_for_status()
            
            return response.content
    
    def start_bulk_compression(self, file_paths: list, compression_level: str = "medium",
                              image_quality: int = 80) -> dict:
        """Start bulk compression job"""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        files = [("files", open(path, "rb")) for path in file_paths]
        data = {
            "compressionLevel": compression_level,
            "imageQuality": image_quality
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/api/compress/bulk",
                headers=headers,
                files=files,
                data=data
            )
            response.raise_for_status()
            
            return response.json()
        finally:
            # Close all file handles
            for _, file_handle in files:
                file_handle.close()
    
    def get_bulk_job_status(self, job_id: int) -> dict:
        """Get bulk job status"""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        response = requests.get(
            f"{self.base_url}/api/compress/bulk/jobs/{job_id}/status",
            headers=headers
        )
        response.raise_for_status()
        
        return response.json()
    
    def download_bulk_result(self, job_id: int) -> bytes:
        """Download bulk compression results"""
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        response = requests.get(
            f"{self.base_url}/api/compress/bulk/jobs/{job_id}/download",
            headers=headers
        )
        response.raise_for_status()
        
        return response.content

# Usage example
client = PDFSmallerClient()
client.login("user@example.com", "password123")

# Single file compression
compressed_data = client.compress_file("document.pdf", "high", 70)
with open("compressed_document.pdf", "wb") as f:
    f.write(compressed_data)

# Bulk compression
job = client.start_bulk_compression(["doc1.pdf", "doc2.pdf", "doc3.pdf"])
print(f"Bulk job started: {job['job_id']}")

# Monitor job progress
import time
while True:
    status = client.get_bulk_job_status(job["job_id"])
    print(f"Progress: {status['progress_percentage']:.1f}%")
    
    if status["is_completed"]:
        if status["is_successful"]:
            # Download results
            result_data = client.download_bulk_result(job["job_id"])
            with open("bulk_results.zip", "wb") as f:
                f.write(result_data)
            print("Bulk compression completed successfully!")
        else:
            print(f"Bulk compression failed: {status['error_message']}")
        break
    
    time.sleep(5)  # Wait 5 seconds before checking again
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

class PDFSmallerClient {
  constructor(baseUrl = 'https://api.pdfsmaller.site') {
    this.baseUrl = baseUrl;
    this.accessToken = null;
    this.refreshToken = null;
  }

  async login(email, password) {
    try {
      const response = await axios.post(`${this.baseUrl}/api/auth/login`, {
        email,
        password
      });

      this.accessToken = response.data.tokens.access_token;
      this.refreshToken = response.data.tokens.refresh_token;

      return response.data;
    } catch (error) {
      throw new Error(`Login failed: ${error.response?.data?.error?.message || error.message}`);
    }
  }

  async compressFile(filePath, compressionLevel = 'medium', imageQuality = 80) {
    const formData = new FormData();
    formData.append('file', fs.createReadStream(filePath));
    formData.append('compressionLevel', compressionLevel);
    formData.append('imageQuality', imageQuality.toString());

    try {
      const response = await axios.post(`${this.baseUrl}/api/compress`, formData, {
        headers: {
          'Authorization': `Bearer ${this.accessToken}`,
          ...formData.getHeaders()
        },
        responseType: 'arraybuffer'
      });

      return response.data;
    } catch (error) {
      throw new Error(`Compression failed: ${error.response?.data?.error?.message || error.message}`);
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
        headers: {
          'Authorization': `Bearer ${this.accessToken}`,
          ...formData.getHeaders()
        }
      });

      return response.data;
    } catch (error) {
      throw new Error(`Bulk compression failed: ${error.response?.data?.error?.message || error.message}`);
    }
  }

  async getBulkJobStatus(jobId) {
    try {
      const response = await axios.get(`${this.baseUrl}/api/compress/bulk/jobs/${jobId}/status`, {
        headers: {
          'Authorization': `Bearer ${this.accessToken}`
        }
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to get job status: ${error.response?.data?.error?.message || error.message}`);
    }
  }

  async downloadBulkResult(jobId) {
    try {
      const response = await axios.get(`${this.baseUrl}/api/compress/bulk/jobs/${jobId}/download`, {
        headers: {
          'Authorization': `Bearer ${this.accessToken}`
        },
        responseType: 'arraybuffer'
      });

      return response.data;
    } catch (error) {
      throw new Error(`Failed to download results: ${error.response?.data?.error?.message || error.message}`);
    }
  }

  async monitorBulkJob(jobId, onProgress = null) {
    return new Promise((resolve, reject) => {
      const checkStatus = async () => {
        try {
          const status = await this.getBulkJobStatus(jobId);
          
          if (onProgress) {
            onProgress(status);
          }

          if (status.is_completed) {
            if (status.is_successful) {
              resolve(status);
            } else {
              reject(new Error(status.error_message));
            }
            return;
          }

          // Check again in 5 seconds
          setTimeout(checkStatus, 5000);
        } catch (error) {
          reject(error);
        }
      };

      checkStatus();
    });
  }
}

// Usage example
async function main() {
  const client = new PDFSmallerClient();
  
  try {
    // Login
    await client.login('user@example.com', 'password123');
    console.log('Logged in successfully');

    // Single file compression
    const compressedData = await client.compressFile('document.pdf', 'high', 70);
    fs.writeFileSync('compressed_document.pdf', compressedData);
    console.log('Single file compressed successfully');

    // Bulk compression
    const job = await client.startBulkCompression(['doc1.pdf', 'doc2.pdf', 'doc3.pdf']);
    console.log(`Bulk job started: ${job.job_id}`);

    // Monitor progress
    const finalStatus = await client.monitorBulkJob(job.job_id, (status) => {
      console.log(`Progress: ${status.progress_percentage.toFixed(1)}%`);
    });

    // Download results
    const resultData = await client.downloadBulkResult(job.job_id);
    fs.writeFileSync('bulk_results.zip', resultData);
    console.log('Bulk compression completed successfully!');

  } catch (error) {
    console.error('Error:', error.message);
  }
}

main();
```

This comprehensive API usage guide provides developers with everything they need to integrate with the PDF Smaller API effectively, including authentication, file compression, bulk processing, subscription management, and robust error handling strategies.