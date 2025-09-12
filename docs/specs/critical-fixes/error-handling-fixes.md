# Error Handling Standardization Fixes

**Priority:** 🟡 Medium  
**Estimated Effort:** 4-5 hours  
**Risk Level:** Medium-High  

## Overview

The codebase has inconsistent error handling patterns across different modules, leading to unpredictable error responses, logging inconsistencies, and maintenance difficulties.

## Issues Identified

### 1. Inconsistent Task Error Handling

**Location:** `src/tasks/tasks.py`

**Problem:** Multiple error handling approaches in the same file:

```python
# Pattern 1: New centralized error handling (good)
def handle_task_error(task_instance, exc, job_id, job=None):
    """Centralized error handling for all tasks."""
    # Sophisticated error categorization and retry logic

# Pattern 2: Old manual error handling (inconsistent)
@celery_app.task(bind=True, max_retries=3, name='tasks.compress_task')
def compress_task(self, job_id: str, ...):
    try:
        # ... task logic ...
    except (DBAPIError, OperationalError, IntegrityError) as db_e:
        # Manual retry logic - duplicated
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (self.request.retries + 1))
    except (EnvironmentError, TimeoutError) as env_e:
        # Different retry logic - inconsistent
        if isinstance(env_e, EnvironmentError):
            raise Ignore()
    except Exception as e:
        # Generic handling - inconsistent
        raise
```

**Issues:**
- Some tasks use new `handle_task_error()` function
- Some tasks use old manual error handling
- Inconsistent retry strategies
- Different error logging approaches
- Mixed exception types and handling

### 2. Route Error Response Inconsistencies

**Locations:** 
- `src/routes/compression_routes.py`
- `src/routes/pdf_suite.py`

**Problem:** Different error response formats:

```python
# Pattern 1: Using error_response helper (good)
return error_response(message='No file provided', error_code='NO_FILE', status_code=400)

# Pattern 2: Direct jsonify (inconsistent)
return jsonify({
    'error': 'Failed to create bulk compression job',
    'error_code': 'SYSTEM_ERROR'
}), 500

# Pattern 3: Missing error codes
return error_response(message='Invalid file', errors={'file': [validation_error]}, status_code=400)
```

### 3. Database Error Handling Inconsistencies

**Problem:** Database operations have different error handling:

```python
# Pattern 1: Try-catch with rollback
try:
    job.mark_as_completed(result)
    db.session.commit()
except (DBAPIError, OperationalError, IntegrityError) as db_err:
    db.session.rollback()
    logger.error(f"Database error: {db_err}")

# Pattern 2: Try-catch without rollback
try:
    job.status = JobStatus.FAILED.value
    db.session.commit()
except (DBAPIError, OperationalError, IntegrityError) as db_err:
    logger.error(f"Failed to update job status: {db_err}")

# Pattern 3: No error handling
job.mark_as_completed(result)
db.session.commit()
```

### 4. Exception Type Usage Inconsistencies

**Problem:** Different modules use different exception hierarchies:

```python
# In utils/exceptions.py - comprehensive hierarchy
class PDFCompressionError(Exception): ...
class ValidationError(PDFCompressionError): ...
class ExtractionError(PDFCompressionError): ...

# In tasks - uses different exceptions
from src.exceptions.extraction_exceptions import ExtractionError
from src.exceptions.export_exceptions import ExportError

# In services - mixed usage
raise EnvironmentError("Ghostscript not available")
raise Exception("Compression failed")
raise RuntimeError("Missing libraries")
```

## Solutions

### Solution 1: Standardize Task Error Handling

**Action Plan:** All tasks should use the centralized `handle_task_error()` function

**Implementation:**

1. **Update all task functions to use centralized error handling:**

```python
@celery_app.task(bind=True, max_retries=3, name='tasks.compress_task')
def compress_task(self, job_id: str, file_data: bytes, compression_settings: Dict[str, Any],
                  original_filename: str = None) -> Dict[str, Any]:
    job = None
    try:
        # ... existing task logic ...
        return result
    except Exception as exc:
        handle_task_error(self, exc, job_id, job)
```

2. **Remove all manual error handling from tasks:**
   - Remove duplicate try-catch blocks
   - Remove manual retry logic
   - Remove manual job status updates in error cases

3. **Enhance centralized error handler:**

```python
def handle_task_error(task_instance, exc, job_id, job=None):
    """Enhanced centralized error handling for all tasks."""
    from flask import current_app
    
    # Enhanced error categorization
    error_tier = categorize_error(exc)
    
    # Standardized job status update with rollback
    update_job_status_safely(job_id, JobStatus.FAILED, str(exc), job)
    
    # Consistent retry logic based on error tier
    if should_retry(error_tier, exc, task_instance.request.retries):
        countdown = calculate_retry_delay(error_tier, task_instance.request.retries)
        logger.warning(f"Retrying job {job_id} ({error_tier} error, attempt {task_instance.request.retries + 1}): {exc}")
        raise task_instance.retry(countdown=countdown, exc=exc)
    
    # Final error logging and handling
    logger.error(f"Task failed permanently for job {job_id}: {exc}")
    raise exc
```

### Solution 2: Standardize Route Error Responses

**Action Plan:** All routes should use consistent error response format

**Implementation:**

1. **Enhance `error_response` helper:**

```python
# In src/utils/response_helpers.py
def error_response(
    message: str, 
    error_code: str = None, 
    details: Dict[str, Any] = None,
    errors: Dict[str, List[str]] = None,  # For validation errors
    status_code: int = 400,
    request_id: str = None
) -> Tuple[Dict[str, Any], int]:
    """Standardized error response format"""
    response = {
        'success': False,
        'error': {
            'code': error_code or 'GENERIC_ERROR',
            'message': message,
            'details': details or {}
        },
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'request_id': request_id or generate_request_id()
    }
    
    # Add validation errors if present
    if errors:
        response['error']['validation_errors'] = errors
    
    return jsonify(response), status_code
```

2. **Update all routes to use standardized responses:**

```python
# Replace all instances like:
# return jsonify({'error': '...', 'error_code': '...'}), 500

# With:
return error_response(
    message="Failed to create bulk compression job",
    error_code="SYSTEM_ERROR",
    status_code=500
)
```

### Solution 3: Standardize Database Error Handling

**Action Plan:** Create database operation helpers with consistent error handling

**Implementation:**

1. **Create database operation helpers:**

Create `src/utils/database_helpers.py`:
```python
from typing import Callable, Any, Optional
from sqlalchemy.exc import DBAPIError, OperationalError, IntegrityError
from src.models.base import db
import logging

logger = logging.getLogger(__name__)

def safe_db_operation(operation: Callable, rollback_on_error: bool = True, 
                     max_retries: int = 3) -> Optional[Any]:
    """Safely execute database operation with consistent error handling"""
    for attempt in range(max_retries + 1):
        try:
            result = operation()
            db.session.commit()
            return result
        except (DBAPIError, OperationalError, IntegrityError) as db_err:
            if rollback_on_error:
                db.session.rollback()
            
            if attempt < max_retries:
                logger.warning(f"Database operation failed (attempt {attempt + 1}), retrying: {db_err}")
                continue
            else:
                logger.error(f"Database operation failed permanently: {db_err}")
                raise
        except Exception as e:
            if rollback_on_error:
                db.session.rollback()
            logger.error(f"Unexpected error in database operation: {e}")
            raise

def update_job_status_safely(job_id: str, status: JobStatus, error_msg: str = None, job: Job = None):
    """Safely update job status with consistent error handling"""
    def update_operation():
        target_job = job or Job.query.filter_by(job_id=job_id).first()
        if target_job:
            if status == JobStatus.FAILED:
                target_job.mark_as_failed(error_msg)
            elif status == JobStatus.COMPLETED:
                target_job.mark_as_completed()
            # Add other status updates as needed
        return target_job
    
    return safe_db_operation(update_operation)
```

2. **Update all database operations to use helpers:**

```python
# Replace scattered database operations like:
# try:
#     job.mark_as_completed(result)
#     db.session.commit()
# except ...

# With:
from src.utils.database_helpers import safe_db_operation

safe_db_operation(lambda: job.mark_as_completed(result))
```

### Solution 4: Standardize Exception Types

**Action Plan:** Consolidate exception hierarchies and standardize usage

**Implementation:**

1. **Audit and consolidate exception files:**
   - Move all exceptions to `src/utils/exceptions.py`
   - Remove duplicate exception files
   - Create clear exception hierarchy

2. **Update services to use standard exceptions:**

```python
# Replace service-specific exceptions like:
# raise EnvironmentError("Ghostscript not available")
# raise Exception("Compression failed")
# raise RuntimeError("Missing libraries")

# With standardized exceptions:
from src.utils.exceptions import (
    ConfigurationError,
    FileProcessingError,
    ExternalServiceError
)

# In compression service:
if not ghostscript_available:
    raise ConfigurationError(
        message="Ghostscript not available",
        config_key="ghostscript",
        details={"required_for": "PDF compression"}
    )

# In conversion service:
if compression_failed:
    raise FileProcessingError(
        message="PDF compression failed",
        file_name=original_filename,
        details={"compression_level": compression_level}
    )
```

## Implementation Plan

### Phase 1: Database Helpers (1.5 hours)
1. Create `database_helpers.py`
2. Implement safe database operations
3. Add comprehensive tests
4. Update critical database operations

### Phase 2: Enhanced Error Response (1 hour)
1. Enhance `error_response` helper
2. Update all route error responses
3. Test response consistency
4. Update API documentation

### Phase 3: Task Error Standardization (2 hours)
1. Enhance centralized error handler
2. Update all task functions
3. Remove manual error handling
4. Test task error scenarios

### Phase 4: Exception Consolidation (1.5 hours)
1. Consolidate exception files
2. Update all service exception usage
3. Update imports throughout codebase
4. Test exception hierarchy

## Testing Requirements

### Error Handling Tests
```python
def test_task_error_handling():
    """Test that all tasks use centralized error handling"""
    # Simulate various error conditions
    # Verify consistent retry behavior
    # Check error logging format

def test_route_error_responses():
    """Test that all routes return consistent error format"""
    # Test validation errors
    # Test system errors
    # Verify response structure

def test_database_error_handling():
    """Test database operation error handling"""
    # Simulate database connection issues
    # Test rollback behavior
    # Verify retry logic

def test_exception_hierarchy():
    """Test exception inheritance and usage"""
    # Test exception creation
    # Verify exception details
    # Test error response conversion
```

### Integration Tests
- Test complete request cycles with errors
- Test task failure and recovery
- Test database failure scenarios
- Verify error logging consistency

## Benefits

### Consistency
- Uniform error handling across all modules
- Consistent error response formats
- Standardized retry strategies
- Predictable error logging

### Maintainability
- Centralized error handling logic
- Easier to update error handling globally
- Better error debugging and monitoring
- Reduced code duplication

### Reliability
- More robust database operations
- Better error recovery mechanisms
- Consistent retry behavior
- Improved error reporting

## Risk Assessment

**Medium-High Risk Factors:**
- Changes affect core error handling throughout application
- Database operation changes could introduce new issues
- Error response format changes could break client expectations

**Mitigation Strategies:**
- Implement changes incrementally
- Maintain backward compatibility for error responses
- Extensive testing of error scenarios
- Monitor error rates after deployment

## Rollback Plan

**Staged Rollback:**
1. Revert task error handling changes
2. Revert route error response changes
3. Revert database helper changes
4. Revert exception consolidation

**Emergency Rollback:**
```bash
# Quick rollback of critical files
git checkout HEAD~1 -- src/tasks/tasks.py
git checkout HEAD~1 -- src/routes/
git checkout HEAD~1 -- src/utils/response_helpers.py
```

## Success Criteria

- ✅ All tasks use centralized error handling
- ✅ All routes return consistent error format
- ✅ All database operations use safe helpers
- ✅ Exception hierarchy is consolidated
- ✅ Error logging is consistent
- ✅ All tests pass
- ✅ No increase in error rates

## Monitoring & Metrics

**Error Metrics to Track:**
- Task failure rates by error type
- Database operation failure rates
- Route error response consistency
- Error recovery success rates

**Logging Improvements:**
- Structured error logging
- Error correlation IDs
- Error categorization tags
- Performance impact metrics

## Documentation Updates

**Required Documentation:**
- Error handling guide for developers
- Exception usage guidelines
- Database operation best practices
- Error monitoring and debugging guide

**API Documentation:**
- Updated error response formats
- Error code reference
- Client error handling examples
