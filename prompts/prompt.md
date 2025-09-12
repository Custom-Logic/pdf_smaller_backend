I have created the following plan after thorough exploration and analysis of the codebase. Follow the below plan verbatim. Trust the files and references. Do not re-verify what's written in the plan. Explore only when absolutely necessary. First implement all the proposed file changes and then I'll review all the changes together at the end.

### Observations

I analyzed the current service architecture and found that while some services (InvoiceExtractionService, BankStatementExtractionService, ExportService) already use the FileManagementService properly, others (OCRService, ConversionService, CompressionService) handle file operations directly with their own custom methods. There's also a legacy FileManager class that should be replaced. The goal is to standardize all services to use the unified FileManagementService for consistent file handling, cleanup, and management across the entire application.

### Approach

I will create a comprehensive specification document that outlines the refactoring plan to standardize file handling across all services. The spec will include current state analysis, target architecture, specific refactoring tasks for each service, implementation guidelines, and expected benefits. This will be placed in a new subfolder within the prompts directory as requested.

### Reasoning

I examined the project structure and identified all services in the `src/services` directory. I analyzed the InvoiceExtractionService and FileManagementService to understand the proper pattern, then examined other services (OCRService, ConversionService, CompressionService, ExportService, BankStatementExtractionService, FileManager) to identify which ones follow the pattern and which need refactoring. I found clear inconsistencies in file handling approaches that need to be standardized.

## Proposed File Changes

### prompts\service_refactoring(NEW)

Create a new subfolder within the prompts directory to contain the service refactoring specifications.

### prompts\service_refactoring\file_management_standardization_spec.md(NEW)

Create a comprehensive specification document that outlines the refactoring plan to standardize file handling across all services. The document will include:

## Current State Analysis
- Document which services already use FileManagementService properly (`InvoiceExtractionService`, `BankStatementExtractionService`, `ExportService`)
- Identify services that need refactoring (`OCRService`, `ConversionService`, `CompressionService`)
- Document the legacy `FileManager` class that should be replaced

## Target Architecture
- Define the standard pattern: all services should initialize `self.file_service = FileManagementService()` in their `__init__` method
- Specify which FileManagementService methods should replace direct file operations
- Outline the unified approach to file cleanup and management

## Service-Specific Refactoring Tasks

### OCRService Refactoring
- Replace `self.upload_folder = Path(upload_folder or tempfile.mkdtemp(prefix="ocr_"))` with FileManagementService usage
- Replace `_save_file_data()` method with `self.file_service.save_file()`
- Replace `cleanup_temp_files()` with FileManagementService cleanup methods
- Update file existence checks to use `self.file_service.file_exists()`

### ConversionService Refactoring
- Replace `self.upload_folder = Path(upload_folder or tempfile.mkdtemp(prefix="pdf_conv_"))` with FileManagementService usage
- Replace `_save_file_data()` method with `self.file_service.save_file()`
- Replace `cleanup_temp_files()` with FileManagementService cleanup methods
- Update file operations to use FileManagementService methods

### CompressionService Refactoring
- Replace direct `upload_folder` management with FileManagementService
- Replace `cleanup_job_files()` with FileManagementService cleanup methods
- Update file size operations to use `self.file_service.get_file_size()`
- Standardize file path handling through FileManagementService

### FileManager Deprecation
- Mark the legacy `FileManager` class as deprecated
- Create migration guide for any code still using FileManager
- Plan for eventual removal of the FileManager class

## Implementation Guidelines
- Step-by-step refactoring process for each service
- Testing requirements to ensure functionality is preserved
- Backward compatibility considerations
- Error handling and logging standards

## Benefits and Expected Outcomes
- Unified file management approach across all services
- Consistent cleanup and retention policies
- Reduced code duplication
- Easier maintenance and debugging
- Better job-based file management
- Improved error handling and logging

## Migration Strategy
- Phased approach to minimize disruption
- Testing strategy for each refactored service
- Rollback plan if issues arise

The specification will reference the existing implementations in `src/services/invoice_extraction_service.py`, `src/services/bank_statement_extraction_service.py`, and `src/services/file_management_service.py` as examples of the target pattern, while identifying the specific changes needed in `src/services/ocr_service.py`, `src/services/conversion_service.py`, `src/services/compression_service.py`, and `src/services/file_manager.py`.