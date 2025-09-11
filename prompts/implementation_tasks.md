# Implementation Tasks - Invoice and Bank Statement Extraction Features

## Task Execution Protocol

This document provides a sequential, task-based implementation plan for the invoice and bank statement extraction features. Each task must be completed in order and marked as complete before proceeding to the next.

**Task Completion Marking:**
- [ ] Incomplete task
- [x] Completed task

**Dependencies:** Tasks are numbered and must be completed sequentially unless otherwise noted.

## Phase 1: Core Infrastructure Tasks

### Task 1: Extend Job Model and Enums
**File:** `src/models/job.py`
**Dependencies:** None
**Estimated Time:** 15 minutes

- [ ] Add new TaskType enum values:
  - `AI_INVOICE_EXTRACTION = "ai_invoice_extraction"`
  - `AI_BANK_STATEMENT_EXTRACTION = "ai_bank_statement_extraction"`
- [ ] Test that existing job creation still works
- [ ] Verify enum serialization in job.to_dict() method

**Completion Criteria:**
- New task types are available in TaskType enum
- Existing functionality remains unaffected
- Job model can create jobs with new task types

### Task 2: Add Custom Exceptions
**File:** `src/utils/exceptions.py`
**Dependencies:** Task 1
**Estimated Time:** 10 minutes

- [ ] Add `ExtractionError` base exception class
- [ ] Add `ExtractionValidationError` subclass
- [ ] Add `ExportFormatError` exception class
- [ ] Follow existing exception patterns in the file
- [ ] Add proper docstrings

**Completion Criteria:**
- New exceptions are properly defined
- Exceptions follow existing code patterns
- Import statements work correctly

### Task 3: Update Configuration
**File:** `src/config/config.py`
**Dependencies:** Task 2
**Estimated Time:** 10 minutes

- [ ] Add extraction feature configuration variables:
  - `INVOICE_EXTRACTION_ENABLED`
  - `BANK_STATEMENT_EXTRACTION_ENABLED`
  - `EXTRACTION_MAX_FILE_SIZE`
  - `EXTRACTION_TIMEOUT`
- [ ] Add default values following existing patterns
- [ ] Update `.env.example` with new variables

**Completion Criteria:**
- Configuration variables are accessible
- Default values are reasonable
- Environment example is updated

## Phase 2: Service Implementation Tasks

### Task 4: Create Invoice Extraction Service
**File:** `src/services/invoice_extraction_service.py` (NEW)
**Dependencies:** Task 3
**Estimated Time:** 2 hours

- [ ] Create `InvoiceExtractionService` class following existing service patterns
- [ ] Implement `__init__` method with AI service and file manager initialization
- [ ] Implement `extract_invoice_data` method with proper error handling
- [ ] Implement `_prepare_extraction_prompt` method with comprehensive prompts
- [ ] Implement `_validate_extraction_result` method with data validation
- [ ] Implement `_export_to_format` method supporting JSON, CSV, Excel
- [ ] Add comprehensive logging following existing patterns
- [ ] Add proper docstrings and type hints

**Completion Criteria:**
- Service class follows existing patterns from `ai_service.py`
- All methods have proper error handling
- Logging is implemented consistently
- Service can be imported and instantiated

### Task 5: Create Bank Statement Extraction Service
**File:** `src/services/bank_statement_extraction_service.py` (NEW)
**Dependencies:** Task 4
**Estimated Time:** 2 hours

- [ ] Create `BankStatementExtractionService` class following invoice service patterns
- [ ] Implement `__init__` method with required dependencies
- [ ] Implement `extract_statement_data` method with proper error handling
- [ ] Implement `_prepare_extraction_prompt` method for bank statements
- [ ] Implement `_validate_extraction_result` method with balance validation
- [ ] Implement `_categorize_transactions` method using AI
- [ ] Implement `_export_to_format` method supporting all formats
- [ ] Add comprehensive logging and error handling
- [ ] Add proper docstrings and type hints

**Completion Criteria:**
- Service class is consistent with invoice extraction service
- Transaction categorization works properly
- Balance validation is implemented
- Service integrates with existing AI service

### Task 6: Create Export Utility Service
**File:** `src/services/export_service.py` (NEW)
**Dependencies:** Task 5
**Estimated Time:** 1.5 hours

- [ ] Create `ExportService` class for handling data exports
- [ ] Implement CSV export functionality
- [ ] Implement Excel export functionality using openpyxl
- [ ] Implement JSON export with proper formatting
- [ ] Add file naming conventions with job IDs
- [ ] Integrate with file manager for secure file storage
- [ ] Add proper error handling for export failures
- [ ] Add logging for export operations

**Completion Criteria:**
- All export formats work correctly
- Files are saved securely using file manager
- Export errors are handled gracefully
- Service can be used by both extraction services

## Phase 3: Celery Task Implementation

### Task 7: Implement Invoice Extraction Task
**File:** `src/tasks/tasks.py` (UPDATE)
**Dependencies:** Task 6
**Estimated Time:** 45 minutes

- [ ] Add `extract_invoice_task` function following existing task patterns
- [ ] Implement proper job status updates (PENDING → PROCESSING → COMPLETED/FAILED)
- [ ] Add retry logic with exponential backoff
- [ ] Integrate with `InvoiceExtractionService`
- [ ] Add comprehensive error handling and logging
- [ ] Follow existing task patterns from `compress_task`
- [ ] Add proper cleanup on task failure

**Completion Criteria:**
- Task follows existing Celery patterns
- Job status updates work correctly
- Retry logic is implemented
- Error handling is comprehensive

### Task 8: Implement Bank Statement Extraction Task
**File:** `src/tasks/tasks.py` (UPDATE)
**Dependencies:** Task 7
**Estimated Time:** 45 minutes

- [ ] Add `extract_bank_statement_task` function following invoice task patterns
- [ ] Implement proper job status updates
- [ ] Add retry logic with exponential backoff
- [ ] Integrate with `BankStatementExtractionService`
- [ ] Add comprehensive error handling and logging
- [ ] Add proper cleanup on task failure
- [ ] Ensure task isolation and resource management

**Completion Criteria:**
- Task is consistent with invoice extraction task
- Job lifecycle is properly managed
- Resource cleanup works correctly
- Task can handle failures gracefully

## Phase 4: API Route Implementation

### Task 9: Add Invoice Extraction Routes
**File:** `src/routes/pdf_suite.py` (UPDATE)
**Dependencies:** Task 8
**Estimated Time:** 1 hour

- [ ] Add `extract_invoice` route following existing route patterns
- [ ] Implement file validation using `get_file_and_validate` helper
- [ ] Add parameter validation for extraction options
- [ ] Implement job creation and task enqueueing
- [ ] Add `get_invoice_capabilities` route
- [ ] Use existing response helpers for consistent responses
- [ ] Add proper error handling following existing patterns
- [ ] Add comprehensive logging

**Completion Criteria:**
- Routes follow existing patterns from pdf_suite.py
- File validation works correctly
- Job creation and task enqueueing work
- Response formats are consistent

### Task 10: Add Bank Statement Extraction Routes
**File:** `src/routes/pdf_suite.py` (UPDATE)
**Dependencies:** Task 9
**Estimated Time:** 1 hour

- [ ] Add `extract_bank_statement` route following invoice route patterns
- [ ] Implement file validation and parameter validation
- [ ] Implement job creation and task enqueueing
- [ ] Add `get_bank_statement_capabilities` route
- [ ] Use consistent response helpers and error handling
- [ ] Add proper logging and monitoring
- [ ] Ensure route security and validation

**Completion Criteria:**
- Routes are consistent with invoice extraction routes
- All validation works correctly
- Job workflow is properly implemented
- API responses are standardized

### Task 11: Update Route Registration
**File:** `src/main/main.py` (UPDATE)
**Dependencies:** Task 10
**Estimated Time:** 5 minutes

- [ ] Verify pdf_suite blueprint is properly registered
- [ ] Test that new routes are accessible
- [ ] Verify route URL patterns are correct
- [ ] Check for any route conflicts

**Completion Criteria:**
- New routes are accessible via API
- No route conflicts exist
- Blueprint registration works correctly

## Phase 5: Testing Implementation

### Task 12: Create Unit Tests for Services
**Files:** `tests/test_invoice_extraction_service.py`, `tests/test_bank_statement_extraction_service.py` (NEW)
**Dependencies:** Task 11
**Estimated Time:** 2 hours

- [ ] Create unit tests for `InvoiceExtractionService`
- [ ] Create unit tests for `BankStatementExtractionService`
- [ ] Create unit tests for `ExportService`
- [ ] Mock AI service responses for testing
- [ ] Test error handling and edge cases
- [ ] Follow existing test patterns from other service tests
- [ ] Add test fixtures for sample data

**Completion Criteria:**
- All service methods are tested
- Mock responses work correctly
- Error cases are covered
- Tests follow existing patterns

### Task 13: Create Integration Tests for Routes
**Files:** `tests/test_extraction_routes.py` (NEW)
**Dependencies:** Task 12
**Estimated Time:** 1.5 hours

- [ ] Create integration tests for invoice extraction endpoints
- [ ] Create integration tests for bank statement extraction endpoints
- [ ] Test file upload and validation
- [ ] Test job creation and status tracking
- [ ] Test error responses and edge cases
- [ ] Use existing test client patterns
- [ ] Add test fixtures for PDF files

**Completion Criteria:**
- End-to-end workflows are tested
- File upload testing works
- Job lifecycle testing is complete
- Error scenarios are covered

### Task 14: Create Celery Task Tests
**File:** `tests/test_extraction_tasks.py` (NEW)
**Dependencies:** Task 13
**Estimated Time:** 1 hour

- [ ] Create tests for `extract_invoice_task`
- [ ] Create tests for `extract_bank_statement_task`
- [ ] Test task retry logic
- [ ] Test job status updates
- [ ] Test error handling and cleanup
- [ ] Follow existing task test patterns
- [ ] Mock external dependencies

**Completion Criteria:**
- Task execution is tested
- Retry logic works correctly
- Job status updates are verified
- Error handling is tested

## Phase 6: Documentation and Configuration

### Task 15: Update API Documentation
**File:** `docs/api_documentation.md` (UPDATE)
**Dependencies:** Task 14
**Estimated Time:** 45 minutes

- [ ] Add invoice extraction endpoint documentation
- [ ] Add bank statement extraction endpoint documentation
- [ ] Add capability endpoint documentation
- [ ] Include request/response examples
- [ ] Add error response documentation
- [ ] Follow existing documentation patterns
- [ ] Update table of contents

**Completion Criteria:**
- New endpoints are fully documented
- Examples are accurate and helpful
- Documentation follows existing format
- All response codes are documented

### Task 16: Update Service Documentation
**File:** `docs/service_documentation.md` (UPDATE)
**Dependencies:** Task 15
**Estimated Time:** 30 minutes

- [ ] Document `InvoiceExtractionService`
- [ ] Document `BankStatementExtractionService`
- [ ] Document `ExportService`
- [ ] Add service integration examples
- [ ] Document configuration requirements
- [ ] Follow existing service documentation patterns

**Completion Criteria:**
- New services are documented
- Integration examples are provided
- Configuration is documented
- Documentation is consistent

### Task 17: Update Architecture Guide
**File:** `docs/architecture_guide.md` (UPDATE)
**Dependencies:** Task 16
**Estimated Time:** 30 minutes

- [ ] Add extraction features to architecture overview
- [ ] Update service layer documentation
- [ ] Add new task types to job processing flow
- [ ] Update component interaction diagrams
- [ ] Document new dependencies

**Completion Criteria:**
- Architecture documentation is current
- New components are properly integrated
- Flow diagrams are updated
- Dependencies are documented

### Task 18: Update README and Deployment Docs
**Files:** `README.md`, `docs/deployment_guide.md` (UPDATE)
**Dependencies:** Task 17
**Estimated Time:** 20 minutes

- [ ] Add feature descriptions to README
- [ ] Update feature list and capabilities
- [ ] Add deployment considerations for extraction features
- [ ] Update environment variable documentation
- [ ] Add resource requirements information

**Completion Criteria:**
- README reflects new features
- Deployment guide is updated
- Resource requirements are documented
- Environment setup is complete

## Phase 7: Final Integration and Validation

### Task 19: End-to-End Testing
**Dependencies:** Task 18
**Estimated Time:** 1 hour

- [ ] Test complete invoice extraction workflow
- [ ] Test complete bank statement extraction workflow
- [ ] Test job status polling and downloads
- [ ] Test error scenarios and recovery
- [ ] Test file cleanup and resource management
- [ ] Verify all export formats work correctly
- [ ] Test concurrent job processing

**Completion Criteria:**
- All workflows work end-to-end
- Error handling is robust
- Resource management works correctly
- Performance is acceptable

### Task 20: Performance and Security Review
**Dependencies:** Task 19
**Estimated Time:** 30 minutes

- [ ] Review file upload security
- [ ] Review data validation and sanitization
- [ ] Check for potential memory leaks
- [ ] Verify proper error message sanitization
- [ ] Review logging for sensitive data exposure
- [ ] Test with large files and edge cases

**Completion Criteria:**
- Security review is complete
- Performance is acceptable
- No sensitive data is logged
- Edge cases are handled

## Post-Implementation Tasks

### Task 21: Move Documentation to Production Location
**Dependencies:** Task 20
**Estimated Time:** 10 minutes

- [ ] Move `invoice_bankstatement_features_refactored.md` to `docs/ai_features/`
- [ ] Update internal documentation references
- [ ] Clean up prompts folder
- [ ] Update documentation index

**Completion Criteria:**
- Documentation is in correct location
- References are updated
- Folder structure is clean

### Task 22: Deployment Readiness Checklist
**Dependencies:** Task 21
**Estimated Time:** 15 minutes

- [ ] Verify all environment variables are documented
- [ ] Check database migrations if needed
- [ ] Verify Celery worker configuration
- [ ] Test with production-like data
- [ ] Verify monitoring and logging setup
- [ ] Check resource requirements and scaling

**Completion Criteria:**
- Deployment checklist is complete
- All requirements are documented
- System is ready for production

## Summary

**Total Estimated Time:** 16-20 hours
**Critical Path:** Tasks 1-11 (core functionality)
**Testing Phase:** Tasks 12-14
**Documentation Phase:** Tasks 15-18
**Validation Phase:** Tasks 19-22

**Key Dependencies:**
- OpenRouter AI API access
- Celery worker configuration
- File storage and cleanup
- Database for job tracking

**Risk Mitigation:**
- Each task has clear completion criteria
- Tasks are small and manageable
- Testing is integrated throughout
- Documentation is updated incrementally

**Success Metrics:**
- All tasks marked as complete [x]
- End-to-end workflows functional
- Documentation updated and accurate
- Tests passing with good coverage
- Performance within acceptable limits