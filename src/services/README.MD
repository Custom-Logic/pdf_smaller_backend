


✅ COMPLETED - FileManagementService has been created as a unified service that combines:
        - File storage and retrieval (from file_manager.py)
        - File cleanup and retention policies (from cleanup_service.py) 
        - File downloads for job routes integration
        - Job-based file management with automatic cleanup
        
        This service simplifies the codebase by providing a single interface for all file-related
        operations while maintaining backward compatibility with existing functionality.
        
        Location: src/services/file_management_service.py


TODO - lets create a sub module for ai services this will allow easier integration with OpenRouter and pydantic_ai. 
this also means we plan to handle all ai related tasks in one module. with pydantic_ai we can handle prompting and tool calling 
and also easily integrate with OpenRouter for more advanced ai capabilities.

tools subfolder - this will contain all the tools we use for ai tasks, such as web scraping, data extraction, etc.

## Services Overview

### FileManagementService

**Location:** `src/services/file_management_service.py`

**Purpose:** Unified service for all file-related operations including storage, cleanup, and downloads.

**Key Features:**
- **File Storage:** Save files with unique IDs, handle file extensions, and manage upload folders
- **File Retrieval:** Get file paths, check file existence, and calculate file sizes
- **File Downloads:** Serve job result files through Flask responses with proper MIME types
- **Cleanup Operations:** 
  - Job-based cleanup with configurable retention periods
  - Temporary file cleanup based on age
  - Comprehensive cleanup statistics and reporting
- **Job Integration:** Direct integration with job routes for seamless file downloads

**Retention Policies:**
- Completed jobs: 24 hours
- Failed jobs: 24 hours  
- Pending jobs: 1 hour
- Processing jobs: 4 hours
- Temporary files: 1 hour

**Usage Example:**
```python
from src.services.file_management_service import FileManagementService

# Initialize service
file_service = FileManagementService()

# Save a file
file_id, file_path = file_service.save_file(file_data, "document.pdf")

# Get download response for job
response = file_service.get_job_download_response(job_id)

# Cleanup expired jobs and files
cleanup_summary = file_service.cleanup_expired_jobs()

# Get service statistics
stats = file_service.get_cleanup_statistics()
```

**Integration Points:**
- Replaces functionality from `file_manager.py` and `cleanup_service.py`
- Integrates with job routes for file downloads
- Uses existing database models and configuration
- Compatible with existing Celery tasks and services

**Benefits:**
- Single point of control for all file operations
- Consistent error handling and logging
- Comprehensive cleanup and retention management
- Simplified maintenance and testing
- Enhanced monitoring and statistics