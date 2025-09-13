I have created the following plan after thorough exploration and analysis of the codebase. Follow the below plan verbatim. Trust the files and references. Do not re-verify what's written in the plan. Explore only when absolutely necessary. First implement all the proposed file changes and then I'll review all the changes together at the end.

### Observations

I've completed a comprehensive exploration of the codebase and understand the current architecture:

**Current State:**
- Job management infrastructure exists with `JobOperations` (enhanced) and `JobStatusManager` (legacy)
- Four services (OCR, Conversion, Compression, AI) use `FileManagementService` but have inconsistent job management
- Celery tasks in `tasks.py` orchestrate services but use mixed job management approaches
- Routes create jobs and enqueue tasks, but some use `JobStatusManager` directly
- The `Job` model has proper state management methods and validation

**Key Findings:**
- Services already work functionally and integrate with `FileManagementService`
- `JobOperations` provides transaction-safe, enhanced job management
- Tasks use `ProgressReporter` and `TemporaryFileManager` for execution context
- Routes follow consistent patterns but need standardization on job creation
- Some services have redundant job creation methods that bypass the centralized system

### Approach

The migration will standardize all services to use `JobOperations` for job lifecycle management while maintaining full compatibility with existing tasks and file management. The approach focuses on:

1. **Centralized Job Creation**: Replace all service-specific job creation with `JobOperations.create_job_safely`
2. **Standardized Status Updates**: Migrate all job status changes to use `JobOperations.update_job_status_safely`
3. **Enhanced Progress Reporting**: Update `ProgressReporter` to use `JobOperations.execute_job_operation` for thread-safe updates
4. **Service Cleanup**: Remove redundant job management code from services while preserving their core functionality
5. **Task Integration**: Ensure all Celery tasks use the standardized job operations
6. **Backward Compatibility**: Maintain existing API contracts and result schemas

### Reasoning

I systematically explored the codebase to understand the migration requirements. I examined the job management infrastructure (`JobOperations`, `JobStatusManager`, `FileManagementService`), analyzed all four services to understand their current structure, reviewed the tasks module to see how Celery orchestrates operations, and checked the routes to understand the API layer. I also examined the Job model to verify compatibility and understand the current job creation patterns across the system.

## Mermaid Diagram

sequenceDiagram
    participant Route as API Route
    participant Task as Celery Task
    participant JobOps as JobOperations
    participant Service as Service Layer
    participant FileService as FileManagementService
    participant DB as Database

    Route->>Task: enqueue task with job_id and file_data
    Task->>JobOps: create_job_safely(job_id, task_type, input_data)
    JobOps->>DB: create job with transaction safety
    DB-->>JobOps: job created
    JobOps-->>Task: job instance

    Task->>JobOps: update_job_status_safely(job_id, PROCESSING)
    JobOps->>DB: update status with row lock
    
    Task->>Service: process_file_data(file_data, options)
    Service->>FileService: save_file(file_data)
    FileService-->>Service: file_path
    Service->>Service: perform processing
    Service->>FileService: save_file(result_data)
    FileService-->>Service: output_path
    Service-->>Task: processing result

    Task->>JobOps: execute_job_operation(job_id, update_progress)
    JobOps->>DB: update progress with row lock
    
    alt Success
        Task->>JobOps: update_job_status_safely(job_id, COMPLETED, result)
        JobOps->>DB: mark completed with result
    else Failure
        Task->>JobOps: update_job_status_safely(job_id, FAILED, error)
        JobOps->>DB: mark failed with error
    end

    Route->>DB: poll job status
    DB-->>Route: job status and result

## Proposed File Changes

### src\tasks\utils.py(MODIFY)

References: 

- src\utils\job_operations.py

Update the `ProgressReporter` class to use `JobOperations.execute_job_operation` instead of direct job object mutation. Replace the current `update` method implementation to call `JobOperations.execute_job_operation(self.job.job_id, lambda job: self._update_job_progress(job, progress_data))` where `_update_job_progress` is a new private method that safely updates the job's result with progress information. This ensures thread-safe progress updates with proper database locking.

Add import for `JobOperations` from `src.utils.job_operations` and remove the direct database operation code that currently mutates `self.job.result` without proper locking.

### src\services\ocr_service.py(MODIFY)

References: 

- src\utils\job_operations.py

Remove the `create_ocr_job` method (lines 400-417) as job creation will be handled centrally by `JobOperations.create_job_safely`. The method currently returns a stub job dict without database interaction, which is redundant with the new centralized approach.

Update the class docstring and any references to indicate that job management is now handled externally through the job operations system. Ensure the `process_ocr_data` and `get_ocr_preview` methods continue to work as pure processing functions that return structured results.

### src\services\conversion_service.py(MODIFY)

References: 

- src\utils\job_operations.py

Remove the `create_conversion_job` method (lines 489-505) as it returns a stub job dict without database interaction, which is now redundant with centralized job creation through `JobOperations.create_job_safely`.

Update the class docstring to reflect that job management is handled externally. Ensure the `convert_pdf_data` and `get_conversion_preview` methods remain as pure processing functions that work with file data and return structured results.

### src\services\compression_service.py(MODIFY)

References: 

- src\utils\job_operations.py
- src\utils\job_manager.py

Replace all `JobStatusManager` imports and usage with `JobOperations`. Update the `create_compression_job` method (lines 150-172) to use `JobOperations.create_job_safely` instead of `JobStatusManager.get_or_create_job`.

In the `process_compression_job` method (lines 173-234), replace `JobStatusManager.update_job_status` calls with `JobOperations.update_job_status_safely`. This includes the status updates to PROCESSING (line 187), COMPLETED (line 224), and FAILED (line 230).

Add import for `JobOperations` from `src.utils.job_operations` and remove the `JobStatusManager` import. Update any error handling to use the enhanced transaction safety provided by `JobOperations`.

### src\services\ai_service.py(MODIFY)

References: 

- src\utils\job_operations.py

Update the `create_ai_job` method (lines 609-656) to use `JobOperations.create_job_safely` for actual database job creation instead of just returning a stub dictionary. Replace the current implementation that only returns job metadata with a call to `JobOperations.create_job_safely(job_id, task_type, input_data)` where `input_data` includes the text, options, and metadata.

Ensure the method now creates an actual database job record and returns both success status and the created job information. Update the return structure to be consistent with other services while maintaining backward compatibility.

### src\tasks\tasks.py(MODIFY)

References: 

- src\utils\job_operations.py
- src\utils\job_manager.py
- src\tasks\utils.py(MODIFY)

Replace all instances of `JobStatusManager` with `JobOperations` throughout the file. This includes:

1. Update imports to use `from src.utils.job_operations import JobOperations` instead of `JobStatusManager`
2. Replace `JobStatusManager.get_or_create_job` calls with `JobOperations.create_job_safely`
3. Replace `JobStatusManager.update_job_status` calls with `JobOperations.update_job_status_safely`
4. Update error handling in the `handle_task_error` function to use `JobOperations.update_job_status_safely`

Ensure all task functions (compression, conversion, OCR, AI) use the standardized job operations for consistent transaction safety and error handling. Verify that progress reporting through `ProgressReporter` works correctly with the updated job operations.

### src\routes\compression_routes.py(MODIFY)

References: 

- src\utils\job_operations.py
- src\utils\job_manager.py

Replace the `JobStatusManager` import and usage with `JobOperations`. Update the error handling in the `compress_pdf` endpoint (lines 70-75) to use `JobOperations.update_job_status_safely` instead of `JobStatusManager.update_job_status`.

Ensure that job creation is handled by the Celery tasks rather than in the route handlers, maintaining the current pattern where routes enqueue tasks and tasks handle job lifecycle management. Update the import statement to use `from src.utils.job_operations import JobOperations`.

### docs\job_manager_documentation.md(MODIFY)

References: 

- src\utils\job_operations.py
- src\utils\job_manager.py
- src\tasks\utils.py(MODIFY)

Update the documentation to reflect the migration to `JobOperations` as the primary job management interface. Add a new section explaining the relationship between `JobOperations` (enhanced, transaction-safe) and `JobStatusManager` (legacy, lower-level).

Document the new standardized patterns for:
1. Job creation using `JobOperations.create_job_safely`
2. Status updates using `JobOperations.update_job_status_safely`
3. Progress reporting through the updated `ProgressReporter`
4. Integration with services and tasks

Include migration notes for developers and examples of the new patterns. Mark `JobStatusManager` methods as legacy but still supported for backward compatibility.

### docs\tasks_module.md(MODIFY)

References: 

- src\tasks\tasks.py(MODIFY)
- src\tasks\utils.py(MODIFY)
- src\utils\job_operations.py

Update the tasks module documentation to reflect the standardized use of `JobOperations` for all job lifecycle management. Document the updated patterns for:

1. Task structure using `JobOperations.create_job_safely` and `JobOperations.update_job_status_safely`
2. Progress reporting with the enhanced `ProgressReporter` that uses `JobOperations.execute_job_operation`
3. Error handling using centralized job operations
4. Integration between tasks, services, and file management

Include examples of the new standardized task patterns and explain how the migration maintains compatibility with existing functionality while improving transaction safety and consistency.

### tests\test_job_operations_migration.py(NEW)

References: 

- src\utils\job_operations.py
- src\tasks\tasks.py(MODIFY)
- src\tasks\utils.py(MODIFY)
- src\services\ocr_service.py(MODIFY)
- src\services\conversion_service.py(MODIFY)
- src\services\compression_service.py(MODIFY)
- src\services\ai_service.py(MODIFY)

Create comprehensive integration tests to verify the migration to `JobOperations` works correctly. Include tests for:

1. **Job Creation**: Test that `JobOperations.create_job_safely` works for all service types (OCR, conversion, compression, AI)
2. **Status Updates**: Verify that `JobOperations.update_job_status_safely` properly handles state transitions
3. **Progress Reporting**: Test the updated `ProgressReporter` with `JobOperations.execute_job_operation`
4. **Task Integration**: End-to-end tests for each task type ensuring proper job lifecycle management
5. **Error Handling**: Test error scenarios and ensure proper job status updates
6. **Backward Compatibility**: Verify that existing API contracts and result schemas are maintained

Include setup and teardown methods for test database state, mock file data, and Celery task testing. Use pytest fixtures for common test data and ensure tests can run independently.