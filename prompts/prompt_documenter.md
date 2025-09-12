# Documentation Update Prompt for Service Refactoring

## Overview
This prompt is for the documenter agent to update documentation based on the service refactoring changes that have been completed. The refactoring involved standardizing file management operations across multiple services to use the centralized FileManagementService.

## Changes Made

### 1. OCRService Refactoring
**File:** `src/services/ocr_service.py`

**Changes:**
- Updated constructor to accept `file_service: Optional[FileManagementService] = None` instead of `upload_folder`
- Replaced direct file operations with `file_service` methods:
  - `_save_file_data()` now uses `file_service.save_file()`
  - File cleanup uses `file_service.delete_file()` instead of `unlink()`
  - File size operations use `file_service.get_file_size()` instead of `stat().st_size`
- Removed `tempfile` import and related setup
- Updated `cleanup_temp_files()` to delegate to `file_service.cleanup_temp_files()`

### 2. ConversionService Refactoring
**File:** `src/services/conversion_service.py`

**Changes:**
- Updated constructor to accept `file_service: Optional[FileManagementService] = None` instead of `upload_folder`
- Replaced direct file operations with `file_service` methods:
  - `_save_file_data()` now uses `file_service.save_file()`
  - File cleanup uses `file_service.delete_file()` instead of `unlink()`
  - File size operations use `file_service.get_file_size()` instead of `stat().st_size`
- Updated conversion methods:
  - `_convert_to_txt()` now uses `file_service.save_file()` for output
  - `_convert_to_html()` now uses `file_service.save_file()` for output
  - `_convert_to_docx()` and `_convert_to_xlsx()` use temporary files then save through `file_service`
  - `_convert_to_images()` saves image data through `file_service`
- Removed `tempfile` import from main imports
- Removed `@staticmethod` decorator from `_convert_to_txt()` to access `self.file_service`

### 3. CompressionService Refactoring
**File:** `src/services/compression_service.py`

**Changes:**
- Updated constructor to accept `file_service: Optional[FileManagementService] = None` instead of `upload_folder`
- Replaced direct file operations with `file_service` methods:
  - Input files saved using `file_service.save_file()`
  - Output files saved using `file_service.save_file()`
  - File cleanup uses `file_service.delete_file()`
  - File size operations use `file_service.get_file_size()` instead of `os.path.getsize()`
- Updated `process_file_data()` method to use temporary files for Ghostscript processing then save results through `file_service`
- Removed imports: `secure_filename`, `get_file_size` from `src.utils.file_utils`
- Added import: `FileManagementService` from `src.services.file_management_service`

## Documentation Tasks

### 1. Update API Documentation
- Update constructor signatures in API documentation for all three services
- Document the new `file_service` parameter and its default behavior
- Update method signatures where applicable (e.g., `_convert_to_txt` no longer static)

### 2. Update Architecture Documentation
- Document the centralized file management approach
- Explain how services now delegate file operations to `FileManagementService`
- Update service dependency diagrams to show the relationship with `FileManagementService`

### 3. Update Development Guide
- Add guidance on using `FileManagementService` in new services
- Document the pattern for temporary file handling during processing
- Update examples of service instantiation

### 4. Update Service Documentation
- Update individual service documentation files
- Document the improved error handling and cleanup mechanisms
- Update code examples to reflect new constructor signatures

### 5. Update Deployment Guide
- Ensure deployment documentation reflects any changes in service initialization
- Update configuration examples if needed

### 6. Update Testing Guide
- Document how to mock `FileManagementService` in tests
- Update test examples to use new constructor signatures
- Add guidance on testing file operations through the service layer

## Files to Update

### Primary Documentation Files
- `docs/api_documentation.md`
- `docs/architecture_guide.md`
- `docs/development_guide.md`
- `docs/service_documentation.md`
- `docs/deployment_guide.md`
- `docs/testing_guide.md`

### Service-Specific Documentation
- Any existing documentation for OCRService
- Any existing documentation for ConversionService
- Any existing documentation for CompressionService

## Key Points to Emphasize

1. **Consistency**: All services now use the same file management approach
2. **Maintainability**: Centralized file operations make the codebase easier to maintain
3. **Error Handling**: Improved cleanup and error handling through standardized service
4. **Testing**: Easier to mock and test file operations
5. **Security**: Centralized file validation and security measures

## Implementation Notes

- The refactoring maintains backward compatibility where possible
- Services default to creating their own `FileManagementService` instance if none provided
- Temporary file handling is now more robust with proper cleanup
- File size operations are now consistent across all services

Please update all relevant documentation to reflect these changes and ensure developers understand the new patterns for file management in the application.
