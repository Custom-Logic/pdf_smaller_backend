# Code Duplication Fixes

**Priority:** 🔴 Critical  
**Estimated Effort:** 4-6 hours  
**Risk Level:** Medium  

## Overview

Multiple functions and logic blocks are duplicated across different modules, violating the DRY (Don't Repeat Yourself) principle and creating maintenance overhead.

## Issues Identified

### 1. `_cleanup_job_files` Function Duplication

**Locations:**
- `src/tasks/tasks.py` (line ~687)
- `src/services/file_management_service.py` (line ~485)
- `src/services/cleanup_service.py` (exists)

**Problem:**
- Same function exists in 3 different places
- Different return types (int vs float)
- Slightly different implementations
- Maintenance nightmare when logic needs to change

**Current Signatures:**
```python
# In tasks.py
def _cleanup_job_files(job: Job) -> int:
    """Clean up files associated with a job – identical behaviour."""

# In file_management_service.py  
def _cleanup_job_files(job: Job) -> float:
    """Clean up files associated with a job"""
```

**Impact:**
- High maintenance overhead
- Potential for inconsistent behavior
- Code bloat

### 2. File Validation Logic

**Locations:**
- `src/routes/pdf_suite.py` - `get_file_and_validate()` function
- `src/routes/compression_routes.py` - inline validation logic
- `src/utils/security_utils.py` - `validate_file()` function

**Problem:**
- File validation scattered across multiple locations
- Different validation criteria in different places
- Inconsistent error messages

### 3. Job Status Update Logic

**Locations:**
- Multiple task functions in `src/tasks/tasks.py`
- Individual service methods

**Problem:**
- Repeated try-catch blocks for database updates
- Inconsistent error handling for DB failures
- Code duplication in status transitions

## Solutions

### Solution 1: Consolidate `_cleanup_job_files`

**Action Plan:**
1. **Keep** the implementation in `FileManagementService` as the canonical version
2. **Remove** duplicates from `tasks.py` and `cleanup_service.py`
3. **Update** all references to use `FileManagementService._cleanup_job_files`
4. **Standardize** return type to `float` (MB freed)

**Implementation Steps:**

1. Update imports in `tasks.py`:
```python
# Add import
from src.services.file_management_service import FileManagementService

# Remove the duplicated function
# Update calls to:
file_management_service = FileManagementService()
space_freed = file_management_service._cleanup_job_files(job)
```

2. Remove function from `cleanup_service.py` if it exists
3. Update all test files to reference the single implementation

### Solution 2: Centralize File Validation

**Action Plan:**
1. Enhance `src/utils/security_utils.validate_file()` to be comprehensive
2. Remove inline validation from routes
3. Standardize `get_file_and_validate()` to use central validation

**Implementation Steps:**

1. Enhance `validate_file()` in `security_utils.py`:
```python
def validate_file(file, feature_type: str = 'general', max_size_mb: int = None) -> Optional[str]:
    """Comprehensive file validation for all features"""
    # Consolidate all validation logic here
```

2. Update `pdf_suite.py` to use enhanced validation:
```python
# Replace get_file_and_validate with standardized approach
from src.utils.security_utils import validate_file

def get_file_and_validate(feature_type, max_size_mb=None):
    if 'file' not in request.files:
        return None, error_response(message="No file provided", status_code=400)
    
    file = request.files['file']
    validation_error = validate_file(file, feature_type, max_size_mb)
    if validation_error:
        return None, error_response(message=validation_error, status_code=400)
    
    return file, None
```

### Solution 3: Create Job Status Update Helper

**Action Plan:**
1. Create `JobStatusManager` utility class
2. Centralize all job status update logic
3. Include consistent error handling and retry logic

**Implementation Steps:**

1. Create `src/utils/job_status_manager.py`:
```python
class JobStatusManager:
    @staticmethod
    def safe_update_status(job_id: str, status: JobStatus, result: Dict = None, error: str = None):
        """Safely update job status with consistent error handling"""
        # Centralized update logic with retry and error handling
```

2. Update all task functions to use the manager:
```python
from src.utils.job_status_manager import JobStatusManager

# Replace scattered status updates with:
JobStatusManager.safe_update_status(job_id, JobStatus.COMPLETED, result=result)
```

## Testing Requirements

### Unit Tests
- Test consolidated `_cleanup_job_files` function
- Test enhanced file validation logic
- Test `JobStatusManager` error handling

### Integration Tests
- Verify all routes still work with centralized validation
- Verify task status updates work correctly
- Test cleanup functionality across all services

### Regression Tests
- Run full test suite to ensure no functionality broken
- Verify file upload/processing still works
- Test job lifecycle management

## Risk Assessment

**Medium Risk Factors:**
- Changes affect core file handling logic
- Database update patterns are modified
- Multiple modules are touched

**Mitigation Strategies:**
- Implement changes incrementally
- Maintain backward compatibility during transition
- Comprehensive testing at each step
- Keep original functions temporarily with deprecation warnings

## Rollback Plan

**If Issues Arise:**
1. Revert to original duplicated functions
2. Restore original import statements
3. Run regression tests to verify functionality
4. Investigate root cause before re-attempting

**Rollback Commands:**
```bash
git checkout HEAD~1 -- src/tasks/tasks.py
git checkout HEAD~1 -- src/utils/security_utils.py
git checkout HEAD~1 -- src/routes/pdf_suite.py
```

## Success Criteria

- ✅ No duplicate `_cleanup_job_files` functions
- ✅ All file validation goes through single function
- ✅ Job status updates use centralized manager
- ✅ All existing tests pass
- ✅ No regression in functionality
- ✅ Code coverage maintained or improved

## Dependencies

- Must coordinate with service integration fixes
- Affects error handling standardization
- May impact performance (should improve)

## Implementation Order

1. Create centralized utilities first
2. Update task functions to use utilities
3. Update route handlers
4. Remove duplicate code
5. Update tests
6. Verify everything works
