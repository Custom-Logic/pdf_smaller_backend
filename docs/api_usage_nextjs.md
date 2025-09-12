# PDF Smaller API Usage Guide - Next.js TypeScript

This guide provides comprehensive examples and best practices for integrating the PDF Smaller API with Next.js TypeScript applications.

## Table of Contents

1. [Setup and Configuration](#setup-and-configuration)
2. [API Client Setup](#api-client-setup)
3. [File Upload Components](#file-upload-components)
4. [PDF Compression](#pdf-compression)
5. [AI Document Extraction](#ai-document-extraction)
6. [Extended Features](#extended-features)
7. [Job Management](#job-management)
8. [Error Handling](#error-handling)
9. [Best Practices](#best-practices)
10. [Example Components](#example-components)

## Setup and Configuration

### Environment Variables

Create a `.env.local` file in your Next.js project root:

```bash
# PDF Smaller API Configuration
NEXT_PUBLIC_PDF_API_BASE_URL=http://localhost:5000
NEXT_PUBLIC_PDF_API_TIMEOUT=300000
PDF_API_INTERNAL_URL=http://localhost:5000
```

### TypeScript Types

Create `types/pdf-api.ts`:

```typescript
// API Response Types
export interface ApiResponse<T = any> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: Record<string, any>;
  };
  timestamp?: string;
  request_id?: string;
}

// Job Management Types
export interface Job {
  job_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  task_type: 'compress' | 'bulk_compress' | 'convert' | 'ocr' | 'ai_summarize' | 'ai_translate' | 'extract_invoice' | 'extract_bank_statement';
  created_at: string;
  updated_at: string;
  completed_at?: string;
  progress?: number;
  result?: any;
  error?: string;
  download_url?: string;
}

// Compression Types
export interface CompressionOptions {
  compressionLevel?: 'low' | 'medium' | 'high' | 'maximum';
  imageQuality?: number; // 10-100
  job_id?: string;
}

export interface CompressionResult {
  original_size: number;
  compressed_size: number;
  compression_ratio: number;
  output_path: string;
  original_filename: string;
}

// AI Extraction Types
export interface ExtractionOptions {
  export_format?: 'json' | 'csv' | 'excel';
  export_filename?: string;
  include_confidence?: boolean;
  validate_data?: boolean;
}

export interface InvoiceData {
  invoice_number: string;
  date: string;
  due_date?: string;
  vendor_name: string;
  vendor_address?: string;
  vendor_contact?: {
    email?: string;
    phone?: string;
  };
  customer_name: string;
  customer_address?: string;
  items: Array<{
    description: string;
    quantity: number;
    unit_price: number;
    total: number;
  }>;
  subtotal: number;
  tax_rate?: number;
  tax_amount?: number;
  total_amount: number;
  currency: string;
  payment_terms?: string;
  notes?: string;
}

export interface BankStatementData {
  account_info: {
    account_number: string;
    account_type: string;
    account_holder: string;
    bank_name?: string;
    routing_number?: string;
  };
  statement_period: {
    start_date: string;
    end_date: string;
  };
  opening_balance: number;
  closing_balance: number;
  transactions: Array<{
    date: string;
    description: string;
    amount: number;
    type: 'credit' | 'debit';
    balance: number;
    category?: string;
  }>;
  summary: {
    total_credits: number;
    total_debits: number;
    net_change: number;
    transaction_count: number;
  };
}

// Extended Features Types
export interface ConversionOptions {
  format: 'docx' | 'txt' | 'html' | 'images';
  preserveLayout?: boolean;
  extractTables?: boolean;
  extractImages?: boolean;
  quality?: 'low' | 'medium' | 'high';
}

export interface OCROptions {
  language?: 'eng' | 'spa' | 'fra' | 'deu' | 'ita' | 'por' | 'rus' | 'jpn' | 'kor' | 'chi_sim' | 'ara' | 'hin';
  quality?: 'fast' | 'balanced' | 'accurate';
  outputFormat?: 'searchable_pdf' | 'text' | 'json';
}

export interface AIOptions {
  style?: 'concise' | 'detailed' | 'academic' | 'casual' | 'professional';
  maxLength?: number;
  targetLanguage?: string;
  provider?: 'openrouter' | 'openai' | 'anthropic';
  model?: string;
}

// Error Types
export interface PDFApiError extends Error {
  code?: string;
  status?: number;
  details?: Record<string, any>;
}

// Upload Progress
export interface UploadProgress {
  loaded: number;
  total: number;
  percentage: number;
}
```

### Dependencies

Install required packages:

```bash
npm install axios
npm install --save-dev @types/node
```

## API Client Setup

Create `lib/pdf-api-client.ts`:

```typescript
import axios, { AxiosInstance, AxiosProgressEvent } from 'axios';
import type {
  ApiResponse,
  Job,
  CompressionOptions,
  ExtractionOptions,
  ConversionOptions,
  OCROptions,
  AIOptions,
  PDFApiError,
  UploadProgress
} from '@/types/pdf-api';

class PDFApiClient {
  private api: AxiosInstance;
  private baseURL: string;

  constructor() {
    this.baseURL = process.env.NEXT_PUBLIC_PDF_API_BASE_URL || 'http://localhost:5000';
    
    this.api = axios.create({
      baseURL: this.baseURL,
      timeout: parseInt(process.env.NEXT_PUBLIC_PDF_API_TIMEOUT || '300000'),
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor
    this.api.interceptors.request.use(
      (config) => {
        console.log(`Making request to: ${config.method?.toUpperCase()} ${config.url}`);
        return config;
      },
      (error) => Promise.reject(this.handleError(error))
    );

    // Response interceptor
    this.api.interceptors.response.use(
      (response) => response,
      (error) => Promise.reject(this.handleError(error))
    );
  }

  private handleError(error: any): PDFApiError {
    const apiError: PDFApiError = new Error(
      error.response?.data?.error?.message || error.message || 'Unknown API error'
    );
    
    apiError.code = error.response?.data?.error?.code || 'UNKNOWN_ERROR';
    apiError.status = error.response?.status;
    apiError.details = error.response?.data?.error?.details;
    
    return apiError;
  }

  // Helper method to create FormData
  private createFormData(file: File, additionalData?: Record<string, any>): FormData {
    const formData = new FormData();
    formData.append('file', file);
    
    if (additionalData) {
      Object.entries(additionalData).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          formData.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
        }
      });
    }
    
    return formData;
  }

  // Helper method to create FormData for multiple files
  private createBulkFormData(files: File[], additionalData?: Record<string, any>): FormData {
    const formData = new FormData();
    
    files.forEach((file) => {
      formData.append('files', file);
    });
    
    if (additionalData) {
      Object.entries(additionalData).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          formData.append(key, typeof value === 'object' ? JSON.stringify(value) : String(value));
        }
      });
    }
    
    return formData;
  }

  // PDF Compression Methods
  async compressPDF(
    file: File, 
    options: CompressionOptions = {},
    onProgress?: (progress: UploadProgress) => void
  ): Promise<Job> {
    const formData = this.createFormData(file, options);
    
    const response = await this.api.post<ApiResponse<Job>>('/api/compress', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress: UploadProgress = {
            loaded: progressEvent.loaded,
            total: progressEvent.total,
            percentage: Math.round((progressEvent.loaded * 100) / progressEvent.total)
          };
          onProgress(progress);
        }
      }
    });
    
    return response.data.data || response.data as Job;
  }

  async compressBulkPDF(
    files: File[], 
    options: CompressionOptions = {},
    onProgress?: (progress: UploadProgress) => void
  ): Promise<Job> {
    const formData = this.createBulkFormData(files, options);
    
    const response = await this.api.post<ApiResponse<Job>>('/api/compress/bulk', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress: UploadProgress = {
            loaded: progressEvent.loaded,
            total: progressEvent.total,
            percentage: Math.round((progressEvent.loaded * 100) / progressEvent.total)
          };
          onProgress(progress);
        }
      }
    });
    
    return response.data.data || response.data as Job;
  }

  // AI Extraction Methods
  async extractInvoice(
    file: File, 
    options: ExtractionOptions = {},
    onProgress?: (progress: UploadProgress) => void
  ): Promise<Job> {
    const formData = this.createFormData(file, options);
    
    const response = await this.api.post<ApiResponse<Job>>('/api/pdf-suite/extract/invoice', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress: UploadProgress = {
            loaded: progressEvent.loaded,
            total: progressEvent.total,
            percentage: Math.round((progressEvent.loaded * 100) / progressEvent.total)
          };
          onProgress(progress);
        }
      }
    });
    
    return response.data.data || response.data as Job;
  }

  async extractBankStatement(
    file: File, 
    options: ExtractionOptions = {},
    onProgress?: (progress: UploadProgress) => void
  ): Promise<Job> {
    const formData = this.createFormData(file, options);
    
    const response = await this.api.post<ApiResponse<Job>>('/api/pdf-suite/extract/bank-statement', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress: UploadProgress = {
            loaded: progressEvent.loaded,
            total: progressEvent.total,
            percentage: Math.round((progressEvent.loaded * 100) / progressEvent.total)
          };
          onProgress(progress);
        }
      }
    });
    
    return response.data.data || response.data as Job;
  }

  // Extended Features Methods
  async convertPDF(
    file: File, 
    options: ConversionOptions,
    onProgress?: (progress: UploadProgress) => void
  ): Promise<Job> {
    const formData = this.createFormData(file, options);
    
    const response = await this.api.post<ApiResponse<Job>>('/api/extended-features/convert', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress: UploadProgress = {
            loaded: progressEvent.loaded,
            total: progressEvent.total,
            percentage: Math.round((progressEvent.loaded * 100) / progressEvent.total)
          };
          onProgress(progress);
        }
      }
    });
    
    return response.data.data || response.data as Job;
  }

  async processOCR(
    file: File, 
    options: OCROptions = {},
    onProgress?: (progress: UploadProgress) => void
  ): Promise<Job> {
    const formData = this.createFormData(file, options);
    
    const response = await this.api.post<ApiResponse<Job>>('/api/extended-features/ocr', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress: UploadProgress = {
            loaded: progressEvent.loaded,
            total: progressEvent.total,
            percentage: Math.round((progressEvent.loaded * 100) / progressEvent.total)
          };
          onProgress(progress);
        }
      }
    });
    
    return response.data.data || response.data as Job;
  }

  async summarizePDF(
    file: File, 
    options: AIOptions = {},
    onProgress?: (progress: UploadProgress) => void
  ): Promise<Job> {
    const formData = this.createFormData(file, options);
    
    const response = await this.api.post<ApiResponse<Job>>('/api/extended-features/ai/summarize', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress: UploadProgress = {
            loaded: progressEvent.loaded,
            total: progressEvent.total,
            percentage: Math.round((progressEvent.loaded * 100) / progressEvent.total)
          };
          onProgress(progress);
        }
      }
    });
    
    return response.data.data || response.data as Job;
  }

  async translatePDF(
    file: File, 
    targetLanguage: string,
    options: AIOptions = {},
    onProgress?: (progress: UploadProgress) => void
  ): Promise<Job> {
    const formData = this.createFormData(file, { ...options, targetLanguage });
    
    const response = await this.api.post<ApiResponse<Job>>('/api/extended-features/ai/translate', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent: AxiosProgressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress: UploadProgress = {
            loaded: progressEvent.loaded,
            total: progressEvent.total,
            percentage: Math.round((progressEvent.loaded * 100) / progressEvent.total)
          };
          onProgress(progress);
        }
      }
    });
    
    return response.data.data || response.data as Job;
  }

  // Job Management Methods
  async getJobStatus(jobId: string): Promise<Job> {
    const response = await this.api.get<Job>(`/api/jobs/${jobId}`);
    return response.data;
  }

  async downloadJobResult(jobId: string): Promise<Blob> {
    const response = await this.api.get(`/api/jobs/${jobId}/download`, {
      responseType: 'blob'
    });
    return response.data;
  }

  // Utility Methods
  async getSystemCapabilities(): Promise<any> {
    const response = await this.api.get('/api/extended-features/capabilities');
    return response.data;
  }

  async getSystemStatus(): Promise<any> {
    const response = await this.api.get('/api/extended-features/status');
    return response.data;
  }

  async healthCheck(): Promise<any> {
    const response = await this.api.get('/api/health');
    return response.data;
  }

  // Job Monitoring with Polling
  async monitorJob(
    jobId: string,
    onProgress?: (job: Job) => void,
    pollInterval: number = 2000,
    timeout: number = 300000
  ): Promise<Job> {
    const startTime = Date.now();
    
    return new Promise((resolve, reject) => {
      const poll = async () => {
        try {
          if (Date.now() - startTime > timeout) {
            reject(new Error('Job monitoring timeout'));
            return;
          }

          const job = await this.getJobStatus(jobId);
          
          if (onProgress) {
            onProgress(job);
          }

          if (job.status === 'completed') {
            resolve(job);
          } else if (job.status === 'failed') {
            reject(new Error(job.error || 'Job failed'));
          } else {
            setTimeout(poll, pollInterval);
          }
        } catch (error) {
          reject(error);
        }
      };

      poll();
    });
  }
}

// Create singleton instance
const pdfApiClient = new PDFApiClient();
export default pdfApiClient;
```

## File Upload Components

Create `components/FileUpload.tsx`:

```typescript
import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import type { UploadProgress } from '@/types/pdf-api';

interface FileUploadProps {
  onFileSelect: (files: File[]) => void;
  accept?: Record<string, string[]>;
  multiple?: boolean;
  maxSize?: number;
  maxFiles?: number;
  disabled?: boolean;
  progress?: UploadProgress | null;
}

const FileUpload: React.FC<FileUploadProps> = ({
  onFileSelect,
  accept = { 'application/pdf': ['.pdf'] },
  multiple = false,
  maxSize = 50 * 1024 * 1024, // 50MB
  maxFiles = 10,
  disabled = false,
  progress = null
}) => {
  const [uploadError, setUploadError] = useState<string | null>(null);

  const onDrop = useCallback((acceptedFiles: File[], rejectedFiles: any[]) => {
    setUploadError(null);

    if (rejectedFiles.length > 0) {
      const errors = rejectedFiles.map(file => 
        file.errors.map((error: any) => error.message).join(', ')
      ).join('; ');
      setUploadError(errors);
      return;
    }

    if (acceptedFiles.length > 0) {
      onFileSelect(acceptedFiles);
    }
  }, [onFileSelect]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept,
    multiple,
    maxSize,
    maxFiles,
    disabled: disabled || progress !== null
  });

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };

  return (
    <div className="w-full">
      <div
        {...getRootProps()}
        className={`
          border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors
          ${isDragActive ? 'border-blue-400 bg-blue-50' : 'border-gray-300'}
          ${disabled || progress ? 'opacity-50 cursor-not-allowed' : 'hover:border-blue-400 hover:bg-gray-50'}
        `}
      >
        <input {...getInputProps()} />
        
        {progress ? (
          <div className="space-y-2">
            <div className="text-sm text-gray-600">Uploading...</div>
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
                style={{ width: `${progress.percentage}%` }}
              />
            </div>
            <div className="text-xs text-gray-500">
              {formatFileSize(progress.loaded)} / {formatFileSize(progress.total)} ({progress.percentage}%)
            </div>
          </div>
        ) : (
          <div className="space-y-2">
            <svg className="mx-auto h-12 w-12 text-gray-400" stroke="currentColor" fill="none" viewBox="0 0 48 48">
              <path d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            
            {isDragActive ? (
              <p className="text-blue-600">Drop the files here...</p>
            ) : (
              <div>
                <p className="text-gray-600">
                  Drag & drop {multiple ? 'files' : 'a file'} here, or{' '}
                  <span className="text-blue-600 underline">browse</span>
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  {Object.values(accept).flat().join(', ')} • Max {formatFileSize(maxSize)}
                  {multiple && ` • Up to ${maxFiles} files`}
                </p>
              </div>
            )}
          </div>
        )}
      </div>
      
      {uploadError && (
        <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-red-600 text-sm">
          {uploadError}
        </div>
      )}
    </div>
  );
};

export default FileUpload;
```

Create `components/JobProgress.tsx`:

```typescript
import React from 'react';
import type { Job } from '@/types/pdf-api';

interface JobProgressProps {
  job: Job;
  onDownload?: () => void;
  onRetry?: () => void;
}

const JobProgress: React.FC<JobProgressProps> = ({ job, onDownload, onRetry }) => {
  const getStatusColor = (status: Job['status']): string => {
    switch (status) {
      case 'pending': return 'text-yellow-600 bg-yellow-50';
      case 'processing': return 'text-blue-600 bg-blue-50';
      case 'completed': return 'text-green-600 bg-green-50';
      case 'failed': return 'text-red-600 bg-red-50';
      default: return 'text-gray-600 bg-gray-50';
    }
  };

  const getStatusIcon = (status: Job['status']) => {
    switch (status) {
      case 'pending':
        return (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
          </svg>
        );
      case 'processing':
        return (
          <svg className="w-5 h-5 animate-spin" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z" clipRule="evenodd" />
          </svg>
        );
      case 'completed':
        return (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
          </svg>
        );
      case 'failed':
        return (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
          </svg>
        );
    }
  };

  return (
    <div className="border rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <div className={`p-1 rounded ${getStatusColor(job.status)}`}>
            {getStatusIcon(job.status)}
          </div>
          <div>
            <p className="font-medium text-sm">Job {job.job_id.slice(0, 8)}...</p>
            <p className="text-xs text-gray-500 capitalize">{job.task_type.replace('_', ' ')}</p>
          </div>
        </div>
        
        <div className="text-right">
          <p className={`text-sm font-medium capitalize ${getStatusColor(job.status)}`}>
            {job.status}
          </p>
          {job.progress !== undefined && job.status === 'processing' && (
            <p className="text-xs text-gray-500">{job.progress}%</p>
          )}
        </div>
      </div>

      {job.status === 'processing' && job.progress !== undefined && (
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div 
            className="bg-blue-600 h-2 rounded-full transition-all duration-300" 
            style={{ width: `${job.progress}%` }}
          />
        </div>
      )}

      {job.status === 'completed' && job.result && (
        <div className="bg-green-50 p-3 rounded border border-green-200">
          <p className="text-sm text-green-800 mb-2">Processing completed successfully!</p>
          {job.result.compression_ratio && (
            <p className="text-xs text-green-600">
              Compression ratio: {(job.result.compression_ratio * 100).toFixed(1)}%
            </p>
          )}
          {onDownload && (
            <button
              onClick={onDownload}
              className="mt-2 bg-green-600 text-white px-3 py-1 rounded text-sm hover:bg-green-700 transition-colors"
            >
              Download Result
            </button>
          )}
        </div>
      )}

      {job.status === 'failed' && (
        <div className="bg-red-50 p-3 rounded border border-red-200">
          <p className="text-sm text-red-800 mb-1">Processing failed</p>
          {job.error && (
            <p className="text-xs text-red-600 mb-2">{job.error}</p>
          )}
          {onRetry && (
            <button
              onClick={onRetry}
              className="bg-red-600 text-white px-3 py-1 rounded text-sm hover:bg-red-700 transition-colors"
            >
              Retry
            </button>
          )}
        </div>
      )}

      <div className="text-xs text-gray-400 border-t pt-2">
        <p>Created: {new Date(job.created_at).toLocaleString()}</p>
        <p>Updated: {new Date(job.updated_at).toLocaleString()}</p>
      </div>
    </div>
  );
};

export default JobProgress;
```

## PDF Compression

Create `components/PDFCompressor.tsx`:

```typescript
import React, { useState, useCallback } from 'react';
import pdfApiClient from '@/lib/pdf-api-client';
import FileUpload from '@/components/FileUpload';
import JobProgress from '@/components/JobProgress';
import type { Job, CompressionOptions, UploadProgress } from '@/types/pdf-api';

const PDFCompressor: React.FC = () => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [compressionOptions, setCompressionOptions] = useState<CompressionOptions>({
    compressionLevel: 'medium',
    imageQuality: 80
  });
  const [isProcessing, setIsProcessing] = useState(false);

  const handleFileSelect = useCallback((files: File[]) => {
    setSelectedFiles(files);
  }, []);

  const handleCompress = async () => {
    if (selectedFiles.length === 0) return;

    setIsProcessing(true);
    setUploadProgress(null);

    try {
      let job: Job;
      
      if (selectedFiles.length === 1) {
        job = await pdfApiClient.compressPDF(
          selectedFiles[0],
          compressionOptions,
          setUploadProgress
        );
      } else {
        job = await pdfApiClient.compressBulkPDF(
          selectedFiles,
          compressionOptions,
          setUploadProgress
        );
      }

      setJobs(prev => [job, ...prev]);
      setUploadProgress(null);
      
      // Start monitoring the job
      pdfApiClient.monitorJob(
        job.job_id,
        (updatedJob) => {
          setJobs(prev => prev.map(j => j.job_id === updatedJob.job_id ? updatedJob : j));
        }
      ).catch(console.error);
      
    } catch (error) {
      console.error('Compression failed:', error);
      alert(`Compression failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsProcessing(false);
      setSelectedFiles([]);
    }
  };

  const handleDownload = async (jobId: string) => {
    try {
      const blob = await pdfApiClient.downloadJobResult(jobId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `compressed-${jobId.slice(0, 8)}.pdf`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download failed:', error);
      alert('Download failed. Please try again.');
    }
  };

  const handleRetry = (failedJob: Job) => {
    // Remove failed job and retry
    setJobs(prev => prev.filter(j => j.job_id !== failedJob.job_id));
    // Re-trigger compression with same settings
    handleCompress();
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-bold mb-4">PDF Compression</h2>
        
        {/* Compression Options */}
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <h3 className="text-lg font-medium mb-3">Compression Settings</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Compression Level
              </label>
              <select
                value={compressionOptions.compressionLevel}
                onChange={(e) => setCompressionOptions(prev => ({ 
                  ...prev, 
                  compressionLevel: e.target.value as any 
                }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="low">Low (Larger file, better quality)</option>
                <option value="medium">Medium (Balanced)</option>
                <option value="high">High (Smaller file, good quality)</option>
                <option value="maximum">Maximum (Smallest file)</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Image Quality: {compressionOptions.imageQuality}%
              </label>
              <input
                type="range"
                min="10"
                max="100"
                value={compressionOptions.imageQuality}
                onChange={(e) => setCompressionOptions(prev => ({ 
                  ...prev, 
                  imageQuality: parseInt(e.target.value) 
                }))}
                className="w-full"
              />
            </div>
          </div>
        </div>

        {/* File Upload */}
        <FileUpload
          onFileSelect={handleFileSelect}
          multiple={true}
          maxFiles={10}
          disabled={isProcessing}
          progress={uploadProgress}
        />

        {/* Selected Files */}
        {selectedFiles.length > 0 && (
          <div className="mt-4">
            <h4 className="text-sm font-medium text-gray-700 mb-2">
              Selected Files ({selectedFiles.length})
            </h4>
            <div className="space-y-1">
              {selectedFiles.map((file, index) => (
                <div key={index} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                  <span className="text-sm">{file.name}</span>
                  <span className="text-xs text-gray-500">
                    {(file.size / 1024 / 1024).toFixed(2)} MB
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Compress Button */}
        <div className="mt-6">
          <button
            onClick={handleCompress}
            disabled={selectedFiles.length === 0 || isProcessing}
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isProcessing ? 'Compressing...' : `Compress ${selectedFiles.length} File${selectedFiles.length !== 1 ? 's' : ''}`}
          </button>
        </div>
      </div>

      {/* Jobs List */}
      {jobs.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium mb-4">Compression Jobs</h3>
          <div className="space-y-3">
            {jobs.map((job) => (
              <JobProgress
                key={job.job_id}
                job={job}
                onDownload={() => handleDownload(job.job_id)}
                onRetry={() => handleRetry(job)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default PDFCompressor;
```

## AI Document Extraction

Create `components/DocumentExtractor.tsx`:

```typescript
import React, { useState, useCallback } from 'react';
import pdfApiClient from '@/lib/pdf-api-client';
import FileUpload from '@/components/FileUpload';
import JobProgress from '@/components/JobProgress';
import type { Job, ExtractionOptions, InvoiceData, BankStatementData, UploadProgress } from '@/types/pdf-api';

type ExtractionType = 'invoice' | 'bank_statement';

const DocumentExtractor: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [extractionType, setExtractionType] = useState<ExtractionType>('invoice');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [extractionOptions, setExtractionOptions] = useState<ExtractionOptions>({
    export_format: 'json',
    include_confidence: true,
    validate_data: true
  });
  const [isProcessing, setIsProcessing] = useState(false);
  const [extractedData, setExtractedData] = useState<InvoiceData | BankStatementData | null>(null);

  const handleFileSelect = useCallback((files: File[]) => {
    setSelectedFile(files[0] || null);
  }, []);

  const handleExtract = async () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    setUploadProgress(null);
    setExtractedData(null);

    try {
      let job: Job;
      
      if (extractionType === 'invoice') {
        job = await pdfApiClient.extractInvoice(
          selectedFile,
          extractionOptions,
          setUploadProgress
        );
      } else {
        job = await pdfApiClient.extractBankStatement(
          selectedFile,
          extractionOptions,
          setUploadProgress
        );
      }

      setJobs(prev => [job, ...prev]);
      setUploadProgress(null);
      
      // Start monitoring the job
      pdfApiClient.monitorJob(
        job.job_id,
        (updatedJob) => {
          setJobs(prev => prev.map(j => j.job_id === updatedJob.job_id ? updatedJob : j));
          
          // If completed, extract the data for display
          if (updatedJob.status === 'completed' && updatedJob.result?.extracted_data) {
            setExtractedData(updatedJob.result.extracted_data);
          }
        }
      ).catch(console.error);
      
    } catch (error) {
      console.error('Extraction failed:', error);
      alert(`Extraction failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDownload = async (jobId: string) => {
    try {
      const blob = await pdfApiClient.downloadJobResult(jobId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      
      const job = jobs.find(j => j.job_id === jobId);
      const extension = job?.result?.export_info?.format === 'excel' ? 'xlsx' : 
                      job?.result?.export_info?.format === 'csv' ? 'csv' : 'json';
      
      a.download = `extracted-${extractionType}-${jobId.slice(0, 8)}.${extension}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download failed:', error);
      alert('Download failed. Please try again.');
    }
  };

  const renderExtractedData = () => {
    if (!extractedData) return null;

    if (extractionType === 'invoice') {
      const invoice = extractedData as InvoiceData;
      return (
        <div className="bg-white rounded-lg shadow p-6 mt-6">
          <h3 className="text-lg font-medium mb-4">Extracted Invoice Data</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-medium text-gray-900 mb-2">Invoice Information</h4>
              <div className="space-y-1 text-sm">
                <p><span className="font-medium">Invoice #:</span> {invoice.invoice_number}</p>
                <p><span className="font-medium">Date:</span> {invoice.date}</p>
                {invoice.due_date && (
                  <p><span className="font-medium">Due Date:</span> {invoice.due_date}</p>
                )}
                <p><span className="font-medium">Total:</span> {invoice.currency} {invoice.total_amount}</p>
              </div>
            </div>
            
            <div>
              <h4 className="font-medium text-gray-900 mb-2">Vendor Information</h4>
              <div className="space-y-1 text-sm">
                <p><span className="font-medium">Name:</span> {invoice.vendor_name}</p>
                {invoice.vendor_address && (
                  <p><span className="font-medium">Address:</span> {invoice.vendor_address}</p>
                )}
                {invoice.vendor_contact?.email && (
                  <p><span className="font-medium">Email:</span> {invoice.vendor_contact.email}</p>
                )}
              </div>
            </div>
          </div>
          
          {invoice.items && invoice.items.length > 0 && (
            <div className="mt-4">
              <h4 className="font-medium text-gray-900 mb-2">Line Items</h4>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Qty</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Unit Price</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Total</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {invoice.items.map((item, index) => (
                      <tr key={index}>
                        <td className="px-3 py-2 text-sm text-gray-900">{item.description}</td>
                        <td className="px-3 py-2 text-sm text-gray-900">{item.quantity}</td>
                        <td className="px-3 py-2 text-sm text-gray-900">{invoice.currency} {item.unit_price}</td>
                        <td className="px-3 py-2 text-sm text-gray-900">{invoice.currency} {item.total}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      );
    } else {
      const statement = extractedData as BankStatementData;
      return (
        <div className="bg-white rounded-lg shadow p-6 mt-6">
          <h3 className="text-lg font-medium mb-4">Extracted Bank Statement Data</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <h4 className="font-medium text-gray-900 mb-2">Account Information</h4>
              <div className="space-y-1 text-sm">
                <p><span className="font-medium">Account #:</span> {statement.account_info.account_number}</p>
                <p><span className="font-medium">Type:</span> {statement.account_info.account_type}</p>
                <p><span className="font-medium">Holder:</span> {statement.account_info.account_holder}</p>
              </div>
            </div>
            
            <div>
              <h4 className="font-medium text-gray-900 mb-2">Statement Period</h4>
              <div className="space-y-1 text-sm">
                <p><span className="font-medium">Period:</span> {statement.statement_period.start_date} to {statement.statement_period.end_date}</p>
                <p><span className="font-medium">Opening Balance:</span> ${statement.opening_balance}</p>
                <p><span className="font-medium">Closing Balance:</span> ${statement.closing_balance}</p>
              </div>
            </div>
          </div>
          
          <div className="mt-4">
            <h4 className="font-medium text-gray-900 mb-2">Summary</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div className="bg-green-50 p-3 rounded">
                <p className="font-medium text-green-800">Total Credits</p>
                <p className="text-green-600">${statement.summary.total_credits}</p>
              </div>
              <div className="bg-red-50 p-3 rounded">
                <p className="font-medium text-red-800">Total Debits</p>
                <p className="text-red-600">${Math.abs(statement.summary.total_debits)}</p>
              </div>
              <div className="bg-blue-50 p-3 rounded">
                <p className="font-medium text-blue-800">Net Change</p>
                <p className="text-blue-600">${statement.summary.net_change}</p>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <p className="font-medium text-gray-800">Transactions</p>
                <p className="text-gray-600">{statement.summary.transaction_count}</p>
              </div>
            </div>
          </div>
          
          {statement.transactions && statement.transactions.length > 0 && (
            <div className="mt-4">
              <h4 className="font-medium text-gray-900 mb-2">Recent Transactions (First 10)</h4>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Amount</th>
                      <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 uppercase">Balance</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {statement.transactions.slice(0, 10).map((transaction, index) => (
                      <tr key={index}>
                        <td className="px-3 py-2 text-sm text-gray-900">{transaction.date}</td>
                        <td className="px-3 py-2 text-sm text-gray-900">{transaction.description}</td>
                        <td className={`px-3 py-2 text-sm ${
                          transaction.type === 'credit' ? 'text-green-600' : 'text-red-600'
                        }`}>
                          {transaction.type === 'credit' ? '+' : '-'}${Math.abs(transaction.amount)}
                        </td>
                        <td className="px-3 py-2 text-sm text-gray-900">${transaction.balance}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      );
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-bold mb-4">AI Document Extraction</h2>
        
        {/* Extraction Type Selection */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Document Type
          </label>
          <div className="flex space-x-4">
            <label className="flex items-center">
              <input
                type="radio"
                value="invoice"
                checked={extractionType === 'invoice'}
                onChange={(e) => setExtractionType(e.target.value as ExtractionType)}
                className="mr-2"
              />
              Invoice
            </label>
            <label className="flex items-center">
              <input
                type="radio"
                value="bank_statement"
                checked={extractionType === 'bank_statement'}
                onChange={(e) => setExtractionType(e.target.value as ExtractionType)}
                className="mr-2"
              />
              Bank Statement
            </label>
          </div>
        </div>

        {/* Extraction Options */}
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <h3 className="text-lg font-medium mb-3">Extraction Settings</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Export Format
              </label>
              <select
                value={extractionOptions.export_format}
                onChange={(e) => setExtractionOptions(prev => ({ 
                  ...prev, 
                  export_format: e.target.value as any 
                }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="json">JSON</option>
                <option value="csv">CSV</option>
                <option value="excel">Excel</option>
              </select>
            </div>
            
            <div className="flex items-center">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={extractionOptions.include_confidence || false}
                  onChange={(e) => setExtractionOptions(prev => ({ 
                    ...prev, 
                    include_confidence: e.target.checked 
                  }))}
                  className="mr-2"
                />
                Include Confidence Scores
              </label>
            </div>
            
            <div className="flex items-center">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={extractionOptions.validate_data || false}
                  onChange={(e) => setExtractionOptions(prev => ({ 
                    ...prev, 
                    validate_data: e.target.checked 
                  }))}
                  className="mr-2"
                />
                Validate Extracted Data
              </label>
            </div>
          </div>
        </div>

        {/* File Upload */}
        <FileUpload
          onFileSelect={handleFileSelect}
          multiple={false}
          disabled={isProcessing}
          progress={uploadProgress}
        />

        {/* Extract Button */}
        <div className="mt-6">
          <button
            onClick={handleExtract}
            disabled={!selectedFile || isProcessing}
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isProcessing ? 'Extracting...' : `Extract ${extractionType.replace('_', ' ')} Data`}
          </button>
        </div>
      </div>

      {/* Jobs List */}
      {jobs.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium mb-4">Extraction Jobs</h3>
          <div className="space-y-3">
            {jobs.map((job) => (
              <JobProgress
                key={job.job_id}
                job={job}
                onDownload={() => handleDownload(job.job_id)}
              />
            ))}
          </div>
        </div>
      )}

      {/* Extracted Data Display */}
      {renderExtractedData()}
    </div>
  );
};

export default DocumentExtractor;
```

## Extended Features

Create `components/ExtendedFeatures.tsx`:

```typescript
import React, { useState, useCallback } from 'react';
import pdfApiClient from '@/lib/pdf-api-client';
import FileUpload from '@/components/FileUpload';
import JobProgress from '@/components/JobProgress';
import type { Job, ConversionOptions, OCROptions, AIOptions, UploadProgress } from '@/types/pdf-api';

type FeatureType = 'convert' | 'ocr' | 'summarize' | 'translate';

const ExtendedFeatures: React.FC = () => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [featureType, setFeatureType] = useState<FeatureType>('convert');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  
  // Feature-specific options
  const [conversionOptions, setConversionOptions] = useState<ConversionOptions>({
    format: 'docx',
    preserveLayout: true,
    extractTables: true,
    extractImages: false,
    quality: 'medium'
  });
  
  const [ocrOptions, setOCROptions] = useState<OCROptions>({
    language: 'eng',
    quality: 'balanced',
    outputFormat: 'searchable_pdf'
  });
  
  const [aiOptions, setAIOptions] = useState<AIOptions>({
    style: 'professional',
    maxLength: 500,
    provider: 'openrouter',
    model: 'deepseek/deepseek-v3-free'
  });
  
  const [targetLanguage, setTargetLanguage] = useState('Spanish');

  const handleFileSelect = useCallback((files: File[]) => {
    setSelectedFile(files[0] || null);
  }, []);

  const handleProcess = async () => {
    if (!selectedFile) return;

    setIsProcessing(true);
    setUploadProgress(null);

    try {
      let job: Job;
      
      switch (featureType) {
        case 'convert':
          job = await pdfApiClient.convertPDF(
            selectedFile,
            conversionOptions,
            setUploadProgress
          );
          break;
        case 'ocr':
          job = await pdfApiClient.processOCR(
            selectedFile,
            ocrOptions,
            setUploadProgress
          );
          break;
        case 'summarize':
          job = await pdfApiClient.summarizePDF(
            selectedFile,
            aiOptions,
            setUploadProgress
          );
          break;
        case 'translate':
          job = await pdfApiClient.translatePDF(
            selectedFile,
            targetLanguage,
            aiOptions,
            setUploadProgress
          );
          break;
        default:
          throw new Error('Invalid feature type');
      }

      setJobs(prev => [job, ...prev]);
      setUploadProgress(null);
      
      // Start monitoring the job
      pdfApiClient.monitorJob(
        job.job_id,
        (updatedJob) => {
          setJobs(prev => prev.map(j => j.job_id === updatedJob.job_id ? updatedJob : j));
        }
      ).catch(console.error);
      
    } catch (error) {
      console.error('Processing failed:', error);
      alert(`Processing failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDownload = async (jobId: string) => {
    try {
      const blob = await pdfApiClient.downloadJobResult(jobId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      
      const job = jobs.find(j => j.job_id === jobId);
      let extension = 'pdf';
      
      if (job?.task_type === 'convert') {
        extension = conversionOptions.format === 'docx' ? 'docx' : 
                   conversionOptions.format === 'txt' ? 'txt' : 
                   conversionOptions.format === 'html' ? 'html' : 'pdf';
      }
      
      a.download = `processed-${featureType}-${jobId.slice(0, 8)}.${extension}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (error) {
      console.error('Download failed:', error);
      alert('Download failed. Please try again.');
    }
  };

  const renderFeatureOptions = () => {
    switch (featureType) {
      case 'convert':
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Output Format
              </label>
              <select
                value={conversionOptions.format}
                onChange={(e) => setConversionOptions(prev => ({ 
                  ...prev, 
                  format: e.target.value as any 
                }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="docx">Word Document (.docx)</option>
                <option value="txt">Plain Text (.txt)</option>
                <option value="html">HTML (.html)</option>
                <option value="images">Images (PNG)</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Quality
              </label>
              <select
                value={conversionOptions.quality}
                onChange={(e) => setConversionOptions(prev => ({ 
                  ...prev, 
                  quality: e.target.value as any 
                }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="low">Low (Faster)</option>
                <option value="medium">Medium (Balanced)</option>
                <option value="high">High (Better quality)</option>
              </select>
            </div>
            
            <div className="md:col-span-2 space-y-2">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={conversionOptions.preserveLayout || false}
                  onChange={(e) => setConversionOptions(prev => ({ 
                    ...prev, 
                    preserveLayout: e.target.checked 
                  }))}
                  className="mr-2"
                />
                Preserve Layout
              </label>
              
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={conversionOptions.extractTables || false}
                  onChange={(e) => setConversionOptions(prev => ({ 
                    ...prev, 
                    extractTables: e.target.checked 
                  }))}
                  className="mr-2"
                />
                Extract Tables
              </label>
              
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={conversionOptions.extractImages || false}
                  onChange={(e) => setConversionOptions(prev => ({ 
                    ...prev, 
                    extractImages: e.target.checked 
                  }))}
                  className="mr-2"
                />
                Extract Images
              </label>
            </div>
          </div>
        );
        
      case 'ocr':
        return (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Language
              </label>
              <select
                value={ocrOptions.language}
                onChange={(e) => setOCROptions(prev => ({ 
                  ...prev, 
                  language: e.target.value as any 
                }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="eng">English</option>
                <option value="spa">Spanish</option>
                <option value="fra">French</option>
                <option value="deu">German</option>
                <option value="ita">Italian</option>
                <option value="por">Portuguese</option>
                <option value="rus">Russian</option>
                <option value="jpn">Japanese</option>
                <option value="kor">Korean</option>
                <option value="chi_sim">Chinese (Simplified)</option>
                <option value="ara">Arabic</option>
                <option value="hin">Hindi</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Quality
              </label>
              <select
                value={ocrOptions.quality}
                onChange={(e) => setOCROptions(prev => ({ 
                  ...prev, 
                  quality: e.target.value as any 
                }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="fast">Fast</option>
                <option value="balanced">Balanced</option>
                <option value="accurate">Accurate</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Output Format
              </label>
              <select
                value={ocrOptions.outputFormat}
                onChange={(e) => setOCROptions(prev => ({ 
                  ...prev, 
                  outputFormat: e.target.value as any 
                }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="searchable_pdf">Searchable PDF</option>
                <option value="text">Plain Text</option>
                <option value="json">JSON</option>
              </select>
            </div>
          </div>
        );
        
      case 'summarize':
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Summary Style
              </label>
              <select
                value={aiOptions.style}
                onChange={(e) => setAIOptions(prev => ({ 
                  ...prev, 
                  style: e.target.value as any 
                }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="concise">Concise</option>
                <option value="detailed">Detailed</option>
                <option value="academic">Academic</option>
                <option value="casual">Casual</option>
                <option value="professional">Professional</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Length (words): {aiOptions.maxLength}
              </label>
              <input
                type="range"
                min="100"
                max="2000"
                value={aiOptions.maxLength}
                onChange={(e) => setAIOptions(prev => ({ 
                  ...prev, 
                  maxLength: parseInt(e.target.value) 
                }))}
                className="w-full"
              />
            </div>
          </div>
        );
        
      case 'translate':
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Target Language
              </label>
              <select
                value={targetLanguage}
                onChange={(e) => setTargetLanguage(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="Spanish">Spanish</option>
                <option value="French">French</option>
                <option value="German">German</option>
                <option value="Italian">Italian</option>
                <option value="Portuguese">Portuguese</option>
                <option value="Russian">Russian</option>
                <option value="Japanese">Japanese</option>
                <option value="Korean">Korean</option>
                <option value="Chinese">Chinese</option>
                <option value="Arabic">Arabic</option>
                <option value="Hindi">Hindi</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                AI Model
              </label>
              <select
                value={aiOptions.model}
                onChange={(e) => setAIOptions(prev => ({ 
                  ...prev, 
                  model: e.target.value 
                }))}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="deepseek/deepseek-v3-free">DeepSeek V3 Free</option>
                <option value="deepseek/deepseek-v3">DeepSeek V3</option>
                <option value="moonshot/moonshot-k2-free">Moonshot K2 Free</option>
                <option value="moonshot/moonshot-k2-premium">Moonshot K2 Premium</option>
                <option value="openai/gpt-4-turbo">GPT-4 Turbo</option>
                <option value="anthropic/claude-3-sonnet">Claude 3 Sonnet</option>
              </select>
            </div>
          </div>
        );
        
      default:
        return null;
    }
  };

  const getAcceptedFormats = () => {
    switch (featureType) {
      case 'ocr':
        return {
          'application/pdf': ['.pdf'],
          'image/png': ['.png'],
          'image/jpeg': ['.jpg', '.jpeg'],
          'image/tiff': ['.tiff', '.tif'],
          'image/bmp': ['.bmp']
        };
      default:
        return { 'application/pdf': ['.pdf'] };
    }
  };

  return (
    <div className="max-w-4xl mx-auto p-6 space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-2xl font-bold mb-4">Extended Features</h2>
        
        {/* Feature Type Selection */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Feature
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <label className="flex items-center p-3 border rounded cursor-pointer hover:bg-gray-50">
              <input
                type="radio"
                value="convert"
                checked={featureType === 'convert'}
                onChange={(e) => setFeatureType(e.target.value as FeatureType)}
                className="mr-2"
              />
              <div>
                <div className="font-medium">Convert</div>
                <div className="text-xs text-gray-500">PDF to Word/Text</div>
              </div>
            </label>
            
            <label className="flex items-center p-3 border rounded cursor-pointer hover:bg-gray-50">
              <input
                type="radio"
                value="ocr"
                checked={featureType === 'ocr'}
                onChange={(e) => setFeatureType(e.target.value as FeatureType)}
                className="mr-2"
              />
              <div>
                <div className="font-medium">OCR</div>
                <div className="text-xs text-gray-500">Text Recognition</div>
              </div>
            </label>
            
            <label className="flex items-center p-3 border rounded cursor-pointer hover:bg-gray-50">
              <input
                type="radio"
                value="summarize"
                checked={featureType === 'summarize'}
                onChange={(e) => setFeatureType(e.target.value as FeatureType)}
                className="mr-2"
              />
              <div>
                <div className="font-medium">Summarize</div>
                <div className="text-xs text-gray-500">AI Summary</div>
              </div>
            </label>
            
            <label className="flex items-center p-3 border rounded cursor-pointer hover:bg-gray-50">
              <input
                type="radio"
                value="translate"
                checked={featureType === 'translate'}
                onChange={(e) => setFeatureType(e.target.value as FeatureType)}
                className="mr-2"
              />
              <div>
                <div className="font-medium">Translate</div>
                <div className="text-xs text-gray-500">AI Translation</div>
              </div>
            </label>
          </div>
        </div>

        {/* Feature Options */}
        <div className="mb-6 p-4 bg-gray-50 rounded-lg">
          <h3 className="text-lg font-medium mb-3">Settings</h3>
          {renderFeatureOptions()}
        </div>

        {/* File Upload */}
        <FileUpload
          onFileSelect={handleFileSelect}
          accept={getAcceptedFormats()}
          multiple={false}
          disabled={isProcessing}
          progress={uploadProgress}
        />

        {/* Process Button */}
        <div className="mt-6">
          <button
            onClick={handleProcess}
            disabled={!selectedFile || isProcessing}
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {isProcessing ? 'Processing...' : `${featureType.charAt(0).toUpperCase() + featureType.slice(1)} Document`}
          </button>
        </div>
      </div>

      {/* Jobs List */}
      {jobs.length > 0 && (
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium mb-4">Processing Jobs</h3>
          <div className="space-y-3">
            {jobs.map((job) => (
              <JobProgress
                key={job.job_id}
                job={job}
                onDownload={() => handleDownload(job.job_id)}
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ExtendedFeatures;
```

## Best Practices

### Error Handling

```typescript
// lib/error-handler.ts
import type { PDFApiError } from '@/types/pdf-api';

export const handleApiError = (error: PDFApiError): string => {
  // Rate limiting
  if (error.status === 429) {
    return 'Rate limit exceeded. Please try again later.';
  }
  
  // File size errors
  if (error.status === 413) {
    return 'File is too large. Please use a smaller file.';
  }
  
  // Validation errors
  if (error.status === 400) {
    return error.message || 'Invalid request. Please check your input.';
  }
  
  // Server errors
  if (error.status && error.status >= 500) {
    return 'Server error. Please try again later.';
  }
  
  return error.message || 'An unexpected error occurred.';
};

export const withErrorHandling = <T extends any[], R>(
  fn: (...args: T) => Promise<R>
) => {
  return async (...args: T): Promise<R> => {
    try {
      return await fn(...args);
    } catch (error) {
      const message = handleApiError(error as PDFApiError);
      throw new Error(message);
    }
  };
};
```

### File Validation

```typescript
// lib/file-validation.ts
export const validateFile = (file: File, options: {
  maxSize?: number;
  allowedTypes?: string[];
  maxCount?: number;
} = {}): string | null => {
  const { 
    maxSize = 50 * 1024 * 1024, // 50MB
    allowedTypes = ['application/pdf'],
    maxCount = 10 
  } = options;
  
  if (!allowedTypes.includes(file.type)) {
    return `Invalid file type. Allowed: ${allowedTypes.join(', ')}`;
  }
  
  if (file.size > maxSize) {
    const sizeMB = (maxSize / 1024 / 1024).toFixed(0);
    return `File too large. Maximum size: ${sizeMB}MB`;
  }
  
  return null;
};

export const validateFiles = (files: File[], options: {
  maxSize?: number;
  allowedTypes?: string[];
  maxCount?: number;
} = {}): string | null => {
  const { maxCount = 10 } = options;
  
  if (files.length > maxCount) {
    return `Too many files. Maximum: ${maxCount}`;
  }
  
  for (const file of files) {
    const error = validateFile(file, options);
    if (error) return error;
  }
  
  return null;
};
```

### Performance Optimization

```typescript
// hooks/useJobMonitoring.ts
import { useState, useEffect, useCallback } from 'react';
import pdfApiClient from '@/lib/pdf-api-client';
import type { Job } from '@/types/pdf-api';

export const useJobMonitoring = (jobId: string | null) => {
  const [job, setJob] = useState<Job | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pollJob = useCallback(async () => {
    if (!jobId) return;
    
    try {
      setLoading(true);
      setError(null);
      
      const updatedJob = await pdfApiClient.getJobStatus(jobId);
      setJob(updatedJob);
      
      // Continue polling if not terminal
      if (!['completed', 'failed'].includes(updatedJob.status)) {
        setTimeout(pollJob, 2000);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    if (jobId) {
      pollJob();
    }
  }, [jobId, pollJob]);

  return { job, loading, error, refetch: pollJob };
};
```

### Server-Side Integration

```typescript
// pages/api/pdf/compress.ts (API Route)
import type { NextApiRequest, NextApiResponse } from 'next';
import formidable from 'formidable';
import fs from 'fs';

export const config = {
  api: {
    bodyParser: false,
  },
};

export default async function handler(
  req: NextApiRequest,
  res: NextApiResponse
) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const form = formidable({ 
      maxFileSize: 50 * 1024 * 1024, // 50MB
      maxFiles: 10 
    });
    
    const [fields, files] = await form.parse(req);
    
    // Forward to PDF API
    const formData = new FormData();
    
    // Add files
    const fileArray = Array.isArray(files.file) ? files.file : [files.file];
    for (const file of fileArray) {
      if (file) {
        const fileBuffer = fs.readFileSync(file.filepath);
        formData.append('files', new Blob([fileBuffer]), file.originalFilename || 'document.pdf');
      }
    }
    
    // Add options
    if (fields.compressionLevel) {
      formData.append('compressionLevel', Array.isArray(fields.compressionLevel) 
        ? fields.compressionLevel[0] 
        : fields.compressionLevel
      );
    }
    
    const apiUrl = process.env.PDF_API_INTERNAL_URL || 'http://localhost:5000';
    const response = await fetch(`${apiUrl}/api/compress`, {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      throw new Error(`API responded with status ${response.status}`);
    }
    
    const result = await response.json();
    res.status(202).json(result);
    
  } catch (error) {
    console.error('Compression API error:', error);
    res.status(500).json({ 
      error: 'Internal server error',
      message: error instanceof Error ? error.message : 'Unknown error'
    });
  }
}
```

## Example Usage in a Page

```typescript
// pages/index.tsx
import { useState } from 'react';
import Head from 'next/head';
import PDFCompressor from '@/components/PDFCompressor';
import DocumentExtractor from '@/components/DocumentExtractor';
import ExtendedFeatures from '@/components/ExtendedFeatures';

type TabType = 'compress' | 'extract' | 'features';

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabType>('compress');

  return (
    <>
      <Head>
        <title>PDF Smaller - Next.js Demo</title>
        <meta name="description" content="PDF processing with AI-powered features" />
      </Head>
      
      <div className="min-h-screen bg-gray-100">
        <header className="bg-white shadow">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex justify-between items-center h-16">
              <h1 className="text-xl font-bold text-gray-900">PDF Smaller</h1>
              
              <nav className="flex space-x-8">
                <button
                  onClick={() => setActiveTab('compress')}
                  className={`px-3 py-2 rounded-md text-sm font-medium ${
                    activeTab === 'compress'
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Compression
                </button>
                
                <button
                  onClick={() => setActiveTab('extract')}
                  className={`px-3 py-2 rounded-md text-sm font-medium ${
                    activeTab === 'extract'
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  AI Extraction
                </button>
                
                <button
                  onClick={() => setActiveTab('features')}
                  className={`px-3 py-2 rounded-md text-sm font-medium ${
                    activeTab === 'features'
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-500 hover:text-gray-700'
                  }`}
                >
                  Extended Features
                </button>
              </nav>
            </div>
          </div>
        </header>
        
        <main className="py-8">
          {activeTab === 'compress' && <PDFCompressor />}
          {activeTab === 'extract' && <DocumentExtractor />}
          {activeTab === 'features' && <ExtendedFeatures />}
        </main>
      </div>
    </>
  );
}
```

This comprehensive guide provides everything needed to integrate the PDF Smaller API with Next.js TypeScript applications, including type safety, error handling, file uploads, job monitoring, and real-world UI components.
