# Service Integration Fixes

**Priority:** 🟡 Medium  
**Estimated Effort:** 3-4 hours  
**Risk Level:** Medium  

## Overview

The codebase contains deprecated services and inconsistent usage patterns between old and new service implementations, creating maintenance overhead and potential bugs.

## Issues Identified

### 1. Deprecated FileManagementService Service

**Location:** `src/services/file_manager.py`

**Status:** Marked as DEPRECATED with warning

**Problem:**
```python
class FileManagementService:
    """
    DEPRECATED: This class is deprecated and will be removed in a future version.
    Use FileManagementService instead for all file operations.
    """
```

**Current Usage:**
- Still exists in codebase
- Documentation references still point to it
- Potential for confusion between old and new services

### 2. Mixed Service Usage Patterns

**Problem Areas:**

1. **File Management:**
   - Some code uses `FileManagementService` (deprecated)
   - Some code uses `FileManagementService` (current)
   - Inconsistent instantiation patterns

2. **Service Dependencies:**
   - Some services depend on deprecated services
   - Circular dependency risks
   - Inconsistent error handling between services

### 3. Legacy Service References

**Locations:**
- Documentation files
- Prompt files
- Comment references
- Import statements in archived code

**Found References:**
```bash
./prompts/_old/prompt_documenter.md:from src.services.file_manager import FileManagementService
./prompts/service_refactoring/refactoring_tasks.md:from src.services.file_manager import FileManagementService
./prompts/service_refactoring/implementation_guidelines.md:from src.services.file_manager import FileManagementService
```

## Solutions

### Solution 1: Complete FileManagementService Removal

**Action Plan:**
1. Verify no active code uses `FileManagementService`
2. Update all documentation references
3. Remove the deprecated service file
4. Clean up any remaining imports

**Implementation Steps:**

1. **Search for active usage:**
```bash
# Check for any remaining usage
grep -r "FileManagementService" src/ --exclude-dir=__pycache__
grep -r "file_manager" src/ --exclude-dir=__pycache__
```

2. **Update documentation:**
```bash
# Update all documentation files
find docs/ -name "*.md" -exec sed -i 's/FileManagementService/FileManagementService/g' {} +
find prompts/ -name "*.md" -exec sed -i 's/FileManagementService/FileManagementService/g' {} +
```

3. **Remove deprecated file:**
```bash
# After confirming no active usage
rm src/services/file_manager.py
```

### Solution 2: Standardize Service Instantiation

**Current Issues:**
```python
# Inconsistent patterns found:

# Pattern 1: Module-level (good)
file_management_service = FileManagementService()

# Pattern 2: Function-level with default config (okay)
def some_function():
    service = FileManagementService()

# Pattern 3: Function-level with custom config (good)
def some_function():
    service = FileManagementService(upload_folder='/custom/path')

# Pattern 4: Import inside function (bad)
def some_function():
    from src.services.file_management_service import FileManagementService
    service = FileManagementService()
```

**Standardized Approach:**

1. **Create Service Registry Pattern:**

Create `src/services/service_registry.py`:
```python
"""
Service Registry - Centralized service instantiation and configuration
"""
from typing import Dict, Any, Optional
from src.config import Config
from src.services.file_management_service import FileManagementService
from src.services.compression_service import CompressionService
from src.services.ai_service import AIService
# ... other services

class ServiceRegistry:
    """Centralized service management"""
    _instances: Dict[str, Any] = {}
    
    @classmethod
    def get_file_management_service(cls, upload_folder: str = None) -> FileManagementService:
        """Get FileManagementService instance"""
        key = f"file_management_{upload_folder or 'default'}"
        if key not in cls._instances:
            cls._instances[key] = FileManagementService(upload_folder)
        return cls._instances[key]
    
    @classmethod
    def get_compression_service(cls) -> CompressionService:
        """Get CompressionService instance"""
        if 'compression' not in cls._instances:
            cls._instances['compression'] = CompressionService()
        return cls._instances['compression']
    
    # ... other service getters
    
    @classmethod
    def clear_cache(cls):
        """Clear service cache (useful for testing)"""
        cls._instances.clear()
```

2. **Update Service Usage:**

```python
# In routes and tasks:
from src.services.service_registry import ServiceRegistry

# Instead of:
# file_service = FileManagementService()

# Use:
file_service = ServiceRegistry.get_file_management_service()
```

### Solution 3: Service Dependency Cleanup

**Action Plan:**
1. Map current service dependencies
2. Identify circular dependencies
3. Refactor to remove circular dependencies
4. Implement proper dependency injection

**Current Dependency Issues:**

```python
# Example of potential circular dependency:
# CompressionService uses FileManagementService
# FileManagementService might use other services
# Tasks use both services
```

**Solution - Dependency Injection:**

```python
# In CompressionService:
class CompressionService:
    def __init__(self, file_service: FileManagementService = None):
        self.file_service = file_service or ServiceRegistry.get_file_management_service()
    
    def process_file_data(self, ...):
        # Use self.file_service instead of creating new instance
        pass
```

## Implementation Plan

### Phase 1: Audit and Documentation (1 hour)
1. Complete audit of FileManagementService usage
2. Document current service dependencies
3. Identify all files that need updates
4. Create migration checklist

### Phase 2: Create Service Registry (1 hour)
1. Implement `ServiceRegistry` class
2. Add methods for all major services
3. Include configuration handling
4. Add tests for service registry

### Phase 3: Update Service Usage (1.5 hours)
1. Update all modules to use ServiceRegistry
2. Remove direct service instantiation
3. Update imports throughout codebase
4. Fix any circular dependency issues

### Phase 4: Remove Deprecated Code (30 minutes)
1. Remove `file_manager.py`
2. Clean up documentation references
3. Update any remaining comments
4. Remove from imports

## Testing Requirements

### Unit Tests
```python
# Test service registry
def test_service_registry_singleton_behavior():
    service1 = ServiceRegistry.get_file_management_service()
    service2 = ServiceRegistry.get_file_management_service()
    assert service1 is service2

def test_service_registry_different_configs():
    service1 = ServiceRegistry.get_file_management_service('/path1')
    service2 = ServiceRegistry.get_file_management_service('/path2')
    assert service1 is not service2

def test_service_registry_clear_cache():
    service1 = ServiceRegistry.get_file_management_service()
    ServiceRegistry.clear_cache()
    service2 = ServiceRegistry.get_file_management_service()
    assert service1 is not service2
```

### Integration Tests
- Test that all routes still work with new service pattern
- Test that all tasks still work
- Verify no performance degradation
- Test service instantiation under load

### Migration Tests
```python
def test_no_FileManagementService_references():
    """Ensure no code references deprecated FileManagementService"""
    # Scan codebase for any remaining references
    import ast
    import os
    
    for root, dirs, files in os.walk('src/'):
        for file in files:
            if file.endswith('.py'):
                with open(os.path.join(root, file)) as f:
                    content = f.read()
                    assert 'FileManagementService' not in content
                    assert 'file_manager' not in content
```

## Benefits

### Code Quality
- Eliminates deprecated code
- Consistent service usage patterns
- Better dependency management
- Cleaner architecture

### Maintainability
- Single source of truth for service instances
- Easier to modify service configurations
- Better testability with service registry
- Reduced coupling between modules

### Performance
- Service instance reuse
- Reduced memory footprint
- Faster service access
- Better resource management

## Risk Assessment

**Medium Risk Factors:**
- Changes affect core service instantiation
- Potential for introducing new bugs during migration
- Service registry adds new complexity

**Mitigation Strategies:**
- Implement service registry with extensive tests
- Migrate modules one at a time
- Keep backward compatibility during transition
- Comprehensive integration testing

## Rollback Plan

**If Issues Arise:**
1. **Partial Rollback** - revert specific modules
2. **Full Rollback** - restore all original service patterns
3. **Emergency Rollback** - restore deprecated FileManagementService temporarily

**Rollback Commands:**
```bash
# Restore deprecated service
git checkout HEAD~1 -- src/services/file_manager.py

# Revert service registry changes
git checkout HEAD~1 -- src/services/service_registry.py

# Revert specific modules
git checkout HEAD~1 -- src/routes/
git checkout HEAD~1 -- src/tasks/
```

## Success Criteria

- ✅ No deprecated FileManagementService references in active code
- ✅ All services use consistent instantiation patterns
- ✅ Service registry works correctly
- ✅ All tests pass
- ✅ No performance regression
- ✅ Documentation is updated
- ✅ No circular dependencies

## File Changes Summary

**New Files:**
- `src/services/service_registry.py`
- `tests/test_service_registry.py`

**Modified Files:**
- All files that instantiate services
- `src/routes/*.py`
- `src/tasks/tasks.py`
- `src/services/*.py` (for dependency injection)

**Removed Files:**
- `src/services/file_manager.py`

**Documentation Updates:**
- `docs/service_documentation.md`
- `prompts/*.md`
- Any other files referencing FileManagementService

## Dependencies

- Should be done after import consistency fixes
- May affect error handling standardization
- Coordinates with code duplication fixes

## Future Considerations

### Service Registry Enhancements
- Add configuration validation
- Implement service health checks
- Add metrics collection
- Support for service lifecycle management

### Additional Services
- Add other services to registry as needed
- Consider dependency injection framework
- Implement service discovery patterns
