I have created the following plan after thorough exploration and analysis of the codebase. Follow the below plan verbatim. Trust the files and references. Do not re-verify what's written in the plan. Explore only when absolutely necessary. First implement all the proposed file changes and then I'll review all the changes together at the end.

### Observations

I've analyzed the current state of exception handling in `tasks.py` and found significant inconsistencies across different task categories. The codebase has a well-designed custom exception hierarchy in `src/utils/exceptions.py` and comprehensive error handlers in `src/utils/error_handlers.py`, but tasks don't consistently use them. Current patterns range from basic `except Exception` blocks to sophisticated three-tier handling. The documentation in `docs/tasks_module.md` already defines the target three-tier pattern, but implementation is inconsistent. Some tasks import from non-existent `src/exceptions/` modules, indicating missing exception files that need to be created or imports that need to be corrected.

### Approach

The standardization will implement a consistent three-tier exception handling pattern across all Celery tasks in `tasks.py`. This involves: (1) creating missing exception modules, (2) implementing standardized exception handling utilities, (3) refactoring each task category to use the three-tier pattern, and (4) creating comprehensive specification documentation. The approach prioritizes backward compatibility while establishing consistent retry logic, error reporting, and job state management.

### Reasoning

I examined the current `tasks.py` file structure and found 1083 lines with multiple task categories (compression, conversion, OCR, AI, extraction, maintenance). I analyzed existing exception handling patterns, reviewed the custom exception hierarchy in `src/utils/exceptions.py`, studied the error handlers in `src/utils/error_handlers.py`, and examined the three-tier pattern documentation in `docs/tasks_module.md`. I also identified missing exception modules that are imported but don't exist, and reviewed test files to understand the current exception handling contract.

## Proposed File Changes

### docs\specs\exception_handling_standardization_spec.md(NEW)

References: 

- prompts\service_refactoring\file_management_standardization_spec.md
- docs\tasks_module.md(MODIFY)
- src\tasks\tasks.py(MODIFY)

Create a comprehensive specification document following the established format from `e:/projects/pdf_smaller_backend/prompts/service_refactoring/file_management_standardization_spec.md`. Include:

**Overview**: Define the goal of standardizing three-tier exception handling across all Celery tasks in `e:/projects/pdf_smaller_backend/src/tasks/tasks.py`.

**Current State Analysis**: Document the inconsistent exception handling patterns found across task categories:
- Compression tasks: Mix of database-specific and generic exception handling
- Conversion tasks: Context-safe error updates with specific exception types
- OCR tasks: Basic exception handling with generic retry logic
- AI tasks: Minimal exception handling with local variable checks
- Extraction tasks: Some use of custom exceptions but inconsistent patterns
- Maintenance tasks: Basic exception handling

**Target Architecture**: Define the standardized three-tier pattern:
- Tier 1: Context-safe error updates with job state management
- Tier 2: Intelligent retry logic based on exception type
- Tier 3: Final error handling with cleanup and logging

**Exception Classification Matrix**: Map exception types to retry strategies based on the documented matrix in `e:/projects/pdf_smaller_backend/docs/tasks_module.md`.

**Implementation Phases**: Break down the refactoring into manageable phases by task category.

**Migration Strategy**: Ensure backward compatibility and provide rollback plans.

**Success Metrics**: Define validation criteria for the standardization.

### src\exceptions(NEW)

References: 

- src\tasks\tasks.py(MODIFY)

Create the missing exceptions directory that is referenced in `e:/projects/pdf_smaller_backend/src/tasks/tasks.py` imports but doesn't exist.

### src\exceptions\__init__.py(NEW)

Create an empty `__init__.py` file to make the exceptions directory a Python package.

### src\exceptions\extraction_exceptions.py(NEW)

References: 

- src\utils\exceptions.py(MODIFY)
- src\tasks\tasks.py(MODIFY)

Create the extraction exceptions module that is imported in `e:/projects/pdf_smaller_backend/src/tasks/tasks.py` but doesn't exist. Import and re-export the `ExtractionError` and `ExtractionValidationError` classes from `e:/projects/pdf_smaller_backend/src/utils/exceptions.py` to maintain compatibility with existing imports. This file serves as a bridge until the import statements in tasks.py can be updated to use the correct path.

### src\exceptions\export_exceptions.py(NEW)

References: 

- src\utils\exceptions.py(MODIFY)
- src\tasks\tasks.py(MODIFY)

Create the export exceptions module that is imported in `e:/projects/pdf_smaller_backend/src/tasks/tasks.py` but doesn't exist. Import and re-export the `ExportError` class from `e:/projects/pdf_smaller_backend/src/utils/exceptions.py` and create a new `FormatError` exception class that inherits from `ExportError`. This maintains compatibility with existing imports while providing the missing `FormatError` exception.

### src\utils\exceptions.py(MODIFY)

References: 

- docs\tasks_module.md(MODIFY)

Add missing exception classes that are referenced in the documentation but not yet implemented:

- `UnsupportedFormatError`: For file format validation failures
- `ServiceUnavailableError`: For external service connectivity issues
- `OutOfMemoryError`: For memory-related processing failures

Each exception should inherit from `PDFCompressionError` and follow the established pattern with appropriate error codes and status codes. These exceptions are needed to implement the retry matrix documented in `e:/projects/pdf_smaller_backend/docs/tasks_module.md`.

### src\tasks\exception_handler.py(NEW)

References: 

- docs\tasks_module.md(MODIFY)
- src\utils\exceptions.py(MODIFY)
- src\models\job.py

Create a new utility module for standardized task exception handling. Implement:

**TaskExceptionHandler class**: A context manager and decorator that implements the three-tier exception handling pattern. Include methods for:
- Context-safe job status updates
- Exception classification and retry decision logic
- Standardized error logging and progress reporting
- Cleanup operations for failed tasks

**Exception classification functions**: Implement the retry matrix logic from `e:/projects/pdf_smaller_backend/docs/tasks_module.md` to determine which exceptions should trigger retries.

**Standardized error update functions**: Provide consistent job state management that handles database errors gracefully.

This utility will be used by all tasks to ensure consistent exception handling behavior.

### src\tasks\tasks.py(MODIFY)

References: 

- src\tasks\exception_handler.py(NEW)
- src\utils\exceptions.py(MODIFY)
- docs\tasks_module.md(MODIFY)

Implement standardized three-tier exception handling across all task categories:

**Phase 1 - Import Updates**: Update imports to use the new `TaskExceptionHandler` from `e:/projects/pdf_smaller_backend/src/tasks/exception_handler.py` and ensure all custom exceptions are properly imported.

**Phase 2 - Compression Tasks**: Refactor `compress_task` and `bulk_compress_task` to use the standardized exception handling pattern, replacing the current manual try/catch blocks with the three-tier approach.

**Phase 3 - Conversion Tasks**: Update `convert_pdf_task` and `convert_pdf_preview_task` to use consistent exception handling, removing the manual context management and replacing with standardized patterns.

**Phase 4 - OCR Tasks**: Refactor `ocr_process_task` and `ocr_preview_task` to implement proper exception classification and retry logic instead of the current generic exception handling.

**Phase 5 - AI Tasks**: Update `ai_summarize_task`, `ai_translate_task`, and `extract_text_task` to use standardized exception handling and remove the manual local variable checks.

**Phase 6 - Extraction Tasks**: Enhance `extract_invoice_task` and `extract_bank_statement_task` to use consistent three-tier handling while preserving the existing custom exception handling for `ExtractionError` and `ExtractionValidationError`.

**Phase 7 - Maintenance Tasks**: Update `cleanup_expired_jobs` and `get_task_status` to use standardized error handling patterns.

Each phase should maintain backward compatibility and preserve existing functionality while implementing consistent patterns.

### tests\test_task_exception_handling.py(NEW)

References: 

- src\tasks\exception_handler.py(NEW)
- src\tasks\tasks.py(MODIFY)
- docs\tasks_module.md(MODIFY)

Create comprehensive tests for the new standardized exception handling:

**Test TaskExceptionHandler**: Verify the three-tier pattern implementation, exception classification logic, and retry decision making.

**Test Exception Classification**: Validate that the retry matrix from `e:/projects/pdf_smaller_backend/docs/tasks_module.md` is correctly implemented.

**Test Job State Management**: Ensure context-safe job status updates work correctly even when database errors occur.

**Test Integration**: Verify that tasks using the new exception handling maintain backward compatibility and produce expected results.

**Test Error Scenarios**: Cover database errors, service unavailability, validation failures, and other exception types to ensure proper handling.

Use mocking to simulate various error conditions and verify that the appropriate retry logic and error reporting occurs.

### tests\test_error_handling.py(MODIFY)

References: 

- src\utils\exceptions.py(MODIFY)

Update existing error handling tests to include the new exception classes added to `e:/projects/pdf_smaller_backend/src/utils/exceptions.py`. Add test cases for:
- `UnsupportedFormatError`
- `ServiceUnavailableError` 
- `OutOfMemoryError`

Ensure these tests follow the same pattern as existing exception tests and verify proper error codes, status codes, and message formatting.

### docs\tasks_module.md(MODIFY)

References: 

- src\tasks\exception_handler.py(NEW)
- src\tasks\tasks.py(MODIFY)

Update the tasks module documentation to reflect the implemented standardization:

**Update Error Handling Section**: Document the new `TaskExceptionHandler` utility and how it implements the three-tier pattern.

**Update Exception Matrix**: Ensure the retry matrix table includes all implemented exception types and their retry strategies.

**Add Usage Examples**: Provide code examples showing how tasks now use the standardized exception handling.

**Update Development Guidelines**: Revise the guidelines for adding new tasks to reference the standardized exception handling patterns.

Ensure the documentation accurately reflects the implemented changes and provides clear guidance for future development.
