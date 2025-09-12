# Import Consistency Fixes

**Priority:** 🟡 Medium  
**Estimated Effort:** 2-3 hours  
**Risk Level:** Low  

## Overview

The codebase has inconsistent import patterns, mixing lazy imports (inside functions) with standard top-level imports, and using problematic wildcard imports.

## Issues Identified

### 1. Lazy Imports in Route Functions

**Locations:**
- `src/routes/compression_routes.py`
- `src/routes/pdf_suite.py`

**Problem:**
```python
# Current problematic pattern
@compression_bp.route('/compress', methods=['POST'])
def compress_pdf():
    try:
        # ... file processing ...
        try:
            from src.tasks.tasks import compress_task  # ❌ Lazy import
            compress_task.delay(job_id, file_data, compression_settings, file.filename)
        except Exception as task_error:
            # ...
```

**Issues:**
- Makes dependency analysis difficult
- Inconsistent with standard Python practices
- Could hide import errors until runtime
- Makes code harder to understand and maintain

### 2. Wildcard Import in Tasks

**Location:** `src/tasks/tasks.py`

**Problem:**
```python
from .app_context import *   # ❌ Wildcard import
```

**Issues:**
- Unknown what symbols are being imported
- Potential namespace pollution
- Makes code analysis tools less effective
- Violates PEP 8 guidelines

### 3. Inconsistent Service Instantiation

**Locations:**
- `src/routes/pdf_suite.py` - services instantiated at module level
- `src/routes/compression_routes.py` - no service instantiation
- Various task functions - services instantiated inside functions

**Problem:**
```python
# In pdf_suite.py - module level (good)
conversion_service = ConversionService()
ocr_service = OCRService()

# In tasks.py - module level (good)
compression_service = CompressionService()

# But then in pdf_suite.py - function level (inconsistent)
def extract_invoice():
    from src.services.file_management_service import FileManagementService
    file_service = FileManagementService()  # ❌ Inconsistent
```

## Solutions

### Solution 1: Standardize Task Imports

**Approach:** Move all task imports to the top of route files

**Implementation:**

1. **Update `src/routes/compression_routes.py`:**
```python
# Add to top-level imports
from src.tasks.tasks import compress_task, bulk_compress_task

# Remove from function:
@compression_bp.route('/compress', methods=['POST'])
def compress_pdf():
    try:
        # ... file processing ...
        # Remove this:
        # try:
        #     from src.tasks.tasks import compress_task
        
        # Just use directly:
        compress_task.delay(job_id, file_data, compression_settings, file.filename)
    except Exception as task_error:
        # Handle task errors
```

2. **Update `src/routes/pdf_suite.py`:**
```python
# Add to top-level imports
from src.tasks.tasks import (
    convert_pdf_task,
    conversion_preview_task,
    ocr_process_task,
    ocr_preview_task,
    ai_summarize_task,
    ai_translate_task,
    extract_text_task,
    extract_invoice_task,
    extract_bank_statement_task
)

# Remove all lazy imports from functions
```

### Solution 2: Fix Wildcard Import

**Approach:** Replace wildcard import with explicit imports

**Investigation Needed:**
1. Examine `src/tasks/app_context.py` to see what it exports
2. Identify what symbols are actually used in `tasks.py`
3. Replace wildcard with explicit imports

**Implementation:**
```python
# Replace this:
# from .app_context import *

# With explicit imports (example):
from .app_context import (
    setup_task_context,
    cleanup_task_context,
    task_signal_handler
)
```

### Solution 3: Standardize Service Instantiation

**Approach:** Consistent service instantiation patterns

**Recommended Pattern:**
- **Module-level instantiation** for stateless services
- **Function-level instantiation** only when configuration varies
- **Dependency injection** for services that need specific configs

**Implementation:**

1. **Update `src/routes/pdf_suite.py`:**
```python
# At module level (consistent with existing pattern)
from src.services.file_management_service import FileManagementService

# Add to other module-level service instantiations
file_management_service = FileManagementService()

# Remove from functions:
def extract_invoice():
    # Remove this:
    # from src.services.file_management_service import FileManagementService
    # file_service = FileManagementService()
    
    # Use module-level instance:
    file_path = file_management_service.save_file(file, job_id)
```

2. **Document the pattern** in a service instantiation guide

## Implementation Plan

### Phase 1: Task Import Standardization (1 hour)
1. Update `compression_routes.py` imports
2. Update `pdf_suite.py` imports
3. Remove lazy imports from all route functions
4. Test that all routes still work

### Phase 2: Wildcard Import Fix (30 minutes)
1. Analyze `app_context.py` exports
2. Identify used symbols in `tasks.py`
3. Replace wildcard with explicit imports
4. Test that tasks still work

### Phase 3: Service Instantiation (1 hour)
1. Move `FileManagementService` to module level in `pdf_suite.py`
2. Update function calls to use module-level instance
3. Review other services for similar issues
4. Test all affected routes

### Phase 4: Documentation (30 minutes)
1. Update code style guide
2. Document import patterns
3. Document service instantiation patterns

## Testing Requirements

### Unit Tests
- Verify all route handlers still work
- Verify all task functions still work
- Test service instantiation

### Integration Tests
- Test full request cycles through routes
- Test task enqueueing and execution
- Verify no circular import issues

### Import Testing
```bash
# Test that modules can be imported without errors
python -c "from src.routes.compression_routes import compression_bp"
python -c "from src.routes.pdf_suite import pdf_suite_bp"
python -c "from src.tasks.tasks import compress_task"
```

## Benefits

### Code Quality
- Cleaner, more readable code
- Easier dependency analysis
- Better IDE support and code completion
- Consistent patterns across codebase

### Maintainability
- Easier to understand what dependencies exist
- Simpler to refactor imports when needed
- Better error messages for import issues
- Easier onboarding for new developers

### Performance
- Slightly better performance (no runtime imports)
- Faster startup time (all imports resolved at module load)
- Better caching of imported modules

## Risk Assessment

**Low Risk Factors:**
- Changes are mostly cosmetic
- No functional logic changes
- Easy to rollback

**Potential Issues:**
- Circular import dependencies (unlikely but possible)
- Changed import timing could reveal hidden bugs

## Rollback Plan

**Quick Rollback:**
```bash
# Revert specific files
git checkout HEAD~1 -- src/routes/compression_routes.py
git checkout HEAD~1 -- src/routes/pdf_suite.py
git checkout HEAD~1 -- src/tasks/tasks.py
```

**Verification:**
```bash
# Test that everything still works
python -m pytest tests/test_compression_routes.py
python -m pytest tests/test_pdf_suite.py
```

## Success Criteria

- ✅ No lazy imports in route functions
- ✅ No wildcard imports
- ✅ Consistent service instantiation patterns
- ✅ All tests pass
- ✅ No import errors
- ✅ Code is more readable and maintainable

## File Changes Summary

**Modified Files:**
- `src/routes/compression_routes.py` - Add top-level task imports
- `src/routes/pdf_suite.py` - Add top-level task imports, fix service instantiation
- `src/tasks/tasks.py` - Replace wildcard import with explicit imports

**New Files:**
- `docs/development_guide.md` (section on import patterns)

**Test Files to Update:**
- Any tests that rely on the current import patterns
- Integration tests for route handling

## Code Style Guidelines (to be documented)

### Import Order
1. Standard library imports
2. Third-party library imports
3. Local application imports
4. Relative imports (minimal use)

### Import Patterns
- ✅ Top-level imports for all dependencies
- ✅ Explicit imports (no wildcards)
- ✅ Module-level service instantiation for stateless services
- ❌ Lazy imports inside functions (except for circular import resolution)
- ❌ Wildcard imports
- ❌ Function-level service instantiation (unless configuration varies)
