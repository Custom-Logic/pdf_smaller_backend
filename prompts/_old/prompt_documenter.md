# File Management Service Documentation Refactoring Prompt

## Overview
This prompt provides instructions for refactoring documentation across the codebase to reflect the new `FileManagementService` that combines the functionality of `FileManager` and `CleanupService`.

## Context
A new `FileManagementService` has been created at `src/services/file_management_service.py` that:
- Combines file storage/retrieval functionality from `FileManager`
- Integrates cleanup and retention policies from `CleanupService`
- Adds file download capabilities for job routes
- Maintains backward compatibility with existing services
- Provides comprehensive file management in a single service

## Files Created/Modified
- **NEW**: `src/services/file_management_service.py` - Combined service implementation
- **NEW**: `tests/test_file_management_service.py` - Comprehensive unit tests
- **UPDATED**: `src/services/__init__.py` - Added FileManagementService to exports
- **UPDATED**: `src/services/README.MD` - Updated with FileManagementService documentation
- **UPDATED**: `src/utils/scheduler.py` - Updated to use FileManagementService

## Documentation Refactoring Tasks

### 1. API Documentation Updates
**Priority: High**

#### Files to Update:
- `docs/api/` - All API documentation files
- `docs/endpoints/` - Endpoint documentation
- Any OpenAPI/Swagger specifications

#### Required Changes:
- Update file upload/download endpoint documentation
- Reference `FileManagementService` instead of separate `FileManager`/`CleanupService`
- Update cleanup operation documentation
- Add new combined service capabilities to API docs

### 2. Architecture Documentation
**Priority: High**

#### Files to Update:
- `docs/architecture/` - System architecture documents
- `docs/services/` - Service layer documentation
- Any system design documents

#### Required Changes:
- Update service architecture diagrams
- Document the new unified file management approach
- Update service interaction diagrams
- Reflect the consolidation of file operations

### 3. Developer Documentation
**Priority: Medium**

#### Files to Update:
- `docs/development/` - Developer guides
- `docs/setup/` - Setup and configuration guides
- `README.md` files in relevant directories

#### Required Changes:
- Update service usage examples
- Modify integration guides
- Update configuration documentation
- Revise troubleshooting guides

### 4. Deployment Documentation
**Priority: Medium**

#### Files to Update:
- `docs/deployment/` - Deployment guides
- `docs/configuration/` - Configuration documentation
- Docker and environment setup files

#### Required Changes:
- Update service configuration examples
- Modify environment variable documentation
- Update deployment scripts if they reference old services
- Revise monitoring and logging configurations

### 5. User Documentation
**Priority: Low**

#### Files to Update:
- `docs/user/` - User guides
- `docs/features/` - Feature documentation
- Any user-facing documentation

#### Required Changes:
- Update file management feature descriptions
- Modify cleanup policy explanations
- Update any user-visible service references

## Specific Documentation Patterns to Update

### Replace References
Look for and update these patterns:

```markdown
# OLD PATTERNS:
- "FileManager and CleanupService"
- "file_manager.py and cleanup_service.py"
- "separate file management services"
- References to individual FileManager/CleanupService imports

# NEW PATTERNS:
- "FileManagementService"
- "file_management_service.py"
- "unified file management service"
- References to FileManagementService import
```

### Update Code Examples
Replace code examples that show:

```python
# OLD:
from src.services.file_manager import FileManager
from src.services.cleanup_service import CleanupService

file_manager = FileManager()
cleanup_service = CleanupService()

# NEW:
from src.services.file_management_service import FileManagementService

file_service = FileManagementService()
```

### Update Configuration Examples
Modify configuration documentation to reflect:
- Single service configuration
- Combined retention policies
- Unified file management settings

## Implementation Guidelines

### 1. Backward Compatibility Notes
- Document that `FileManager` and `CleanupService` are still available
- Explain migration path for existing code
- Provide compatibility examples

### 2. New Features to Document
- Combined file operations
- Enhanced cleanup capabilities
- Integrated download functionality
- Unified service status and monitoring

### 3. Performance Improvements
- Document reduced service overhead
- Explain improved file operation efficiency
- Highlight unified cleanup scheduling

## Validation Checklist

After refactoring documentation:

- [ ] All references to separate FileManager/CleanupService are updated
- [ ] Code examples use FileManagementService
- [ ] API documentation reflects new service structure
- [ ] Architecture diagrams show unified service
- [ ] Configuration examples are updated
- [ ] Deployment guides reference correct service
- [ ] User documentation is consistent
- [ ] Links between documents are updated
- [ ] Search functionality works with new terms
- [ ] Documentation builds without errors

## Files That May Need Updates

### High Priority:
```
docs/api/
docs/services/
docs/architecture/
README.md (root)
src/services/README.MD (already updated)
```

### Medium Priority:
```
docs/development/
docs/deployment/
docs/configuration/
docs/troubleshooting/
```

### Low Priority:
```
docs/user/
docs/features/
docs/changelog/
```

## Search Patterns for Finding Files

Use these search patterns to find files that need updates:

```bash
# Find files mentioning FileManager or CleanupService
grep -r "FileManager\|CleanupService" docs/
grep -r "file_manager\|cleanup_service" docs/

# Find files with old import patterns
grep -r "from.*file_manager\|from.*cleanup_service" docs/

# Find configuration references
grep -r "upload_folder\|cleanup.*config" docs/
```

## Success Criteria

1. **Consistency**: All documentation consistently references FileManagementService
2. **Accuracy**: Code examples and configurations are correct
3. **Completeness**: No broken links or missing references
4. **Clarity**: New unified approach is clearly explained
5. **Migration**: Clear migration path from old to new service

## Notes for Implementation

- Maintain backward compatibility documentation
- Preserve existing functionality descriptions
- Add new capabilities without removing old feature docs
- Update timestamps and version information
- Consider adding migration examples
- Test all code examples in documentation

## Post-Refactoring Tasks

1. Update any automated documentation generation
2. Refresh search indexes
3. Update internal wikis or knowledge bases
4. Notify team members of documentation changes
5. Update any external documentation references

This refactoring should result in consistent, accurate documentation that reflects the new unified file management architecture while maintaining clarity for developers and users.