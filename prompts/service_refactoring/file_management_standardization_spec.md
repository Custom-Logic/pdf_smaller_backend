# File Management Standardization Specification

## Overview

This specification outlines the refactoring plan to standardize file handling across all services in the PDF processing backend. The goal is to replace direct file operations with the unified `FileManagementService`, deprecate the legacy `FileManagementService` class, and establish consistent patterns for file management throughout the application.

## Current State Analysis

### Existing Services and Their File Handling Patterns

#### 1. FileManagementService (Target Pattern)
**Location**: `src/services/file_management_service.py`
**Status**: ✅ Already implemented - serves as the target pattern

**Key Features**:
- Unified interface for all file operations
- Job-based file management with retention policies
- Comprehensive cleanup operations
- File download management
- Error handling and logging
- Configurable upload folders

**Core Methods**:
```python
# File Storage Operations
save_file(file_data: bytes, original_filename: str = None) -> Tuple[str, str]
get_file_path(file_id: str, extension: str = '.pdf') -> str
file_exists(file_path: str) -> bool
get_file_size(file_path: str) -> int
delete_file(file_path: str) -> bool

# Download Operations
get_job_download_response(job_id: str)
is_download_available(job_id: str) -> bool

# Cleanup Operations
cleanup_old_files(max_age_hours: int = None) -> Dict[str, Any]
cleanup_expired_jobs() -> Dict[str, Any]
cleanup_temp_files() -> Dict[str, Any]
```

#### 2. OCRService (Needs Refactoring)
**Location**: `src/services/ocr_service.py`
**Status**: ❌ Uses direct file operations

**Current Pattern**:
- Creates its own upload folder using `tempfile.mkdtemp()`
- Direct file operations with `_save_file_data()` method
- Manual file path management
- No integration with job-based cleanup

**Issues**:
- Inconsistent file storage location
- No centralized cleanup management
- Duplicate file handling logic

#### 3. ConversionService (Needs Refactoring)
**Location**: `src/services/conversion_service.py`
**Status**: ❌ Uses direct file operations

**Current Pattern**:
- Creates its own upload folder using `tempfile.mkdtemp()`
- Direct file operations with `_save_file_data()` method
- Manual temporary file management
- No integration with job-based cleanup

**Issues**:
- Inconsistent file storage location
- No centralized cleanup management
- Duplicate file handling logic

#### 4. CompressionService (Needs Refactoring)
**Location**: `src/services/compression_service.py`
**Status**: ❌ Uses mixed file operations

**Current Pattern**:
- Takes upload_folder as constructor parameter
- Creates persistent output files in `upload_folder/results/`
- Uses temporary directories for processing
- Manual file cleanup on errors

**Issues**:
- Inconsistent with other services
- Manual error cleanup
- No integration with job-based retention policies

#### 5. FileManagementService (Legacy - To Be Deprecated)
**Location**: `src/services/file_manager.py`
**Status**: ⚠️ Legacy service - to be deprecated

**Current Usage**:
- Simple file operations (save, get_path, cleanup)
- Used by legacy tests and some older code
- Functionality fully replaced by FileManagementService

## Target Architecture

### Standardized Service Pattern

All services should follow this pattern:

```python
class ServiceName:
    def __init__(self, file_service: FileManagementService = None):
        """Initialize service with file management dependency"""
        self.file_service = file_service or FileManagementService()
        # Other service-specific initialization
    
    def process_data(self, file_data: bytes, options: Dict[str, Any] = None, 
                    original_filename: str = None) -> Dict[str, Any]:
        """Main processing method using file_service for all file operations"""
        try:
            # Use file_service for file operations
            file_id, temp_path = self.file_service.save_file(file_data, original_filename)
            
            # Service-specific processing logic
            result = self._process_internal(temp_path, options)
            
            # Return standardized result format
            return {
                'success': True,
                'output_path': result['output_path'],
                'filename': result['filename'],
                'mime_type': result['mime_type'],
                'file_size': self.file_service.get_file_size(result['output_path']),
                'original_filename': original_filename,
                'original_size': len(file_data)
            }
            
        except Exception as e:
            logger.error(f"Processing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'original_filename': original_filename,
                'original_size': len(file_data)
            }
```

### Dependency Injection Pattern

Services should accept `FileManagementService` as a dependency:
- Constructor parameter with default instantiation
- Enables testing with mock file services
- Allows for different file service configurations
- Maintains backward compatibility

## Refactoring Tasks

### Phase 1: OCRService Refactoring

**Files to Modify**:
- `src/services/ocr_service.py`

**Changes Required**:
1. Add `file_service` parameter to constructor
2. Replace `self.upload_folder` with `self.file_service`
3. Replace `_save_file_data()` with `file_service.save_file()`
4. Remove manual file path construction
5. Update error handling to use file_service methods
6. Remove temporary directory creation logic

**Before**:
```python
def __init__(self, upload_folder: Optional[str] = None):
    self.upload_folder = Path(upload_folder or tempfile.mkdtemp(prefix="ocr_"))
    self.upload_folder.mkdir(parents=True, exist_ok=True)
```

**After**:
```python
def __init__(self, file_service: FileManagementService = None):
    self.file_service = file_service or FileManagementService()
```

### Phase 2: ConversionService Refactoring

**Files to Modify**:
- `src/services/conversion_service.py`

**Changes Required**:
1. Add `file_service` parameter to constructor
2. Replace `self.upload_folder` with `self.file_service`
3. Replace `_save_file_data()` with `file_service.save_file()`
4. Remove manual file path construction
5. Update error handling to use file_service methods
6. Remove temporary directory creation logic

### Phase 3: CompressionService Refactoring

**Files to Modify**:
- `src/services/compression_service.py`

**Changes Required**:
1. Replace `upload_folder` parameter with `file_service` parameter
2. Use `file_service.save_file()` for output file management
3. Remove manual output directory creation
4. Replace manual cleanup with `file_service.delete_file()`
5. Update file size operations to use `file_service.get_file_size()`

**Before**:
```python
def __init__(self, upload_folder):
    self.upload_folder = upload_folder
    Path(self.upload_folder).mkdir(parents=True, exist_ok=True)
```

**After**:
```python
def __init__(self, file_service: FileManagementService = None):
    self.file_service = file_service or FileManagementService()
```

### Phase 4: FileManagementService Deprecation

**Files to Update**:
- `src/services/file_manager.py` - Add deprecation warnings
- All files importing FileManagementService - Update to use FileManagementService
- Test files - Update or mark as legacy

**Deprecation Strategy**:
1. Add deprecation warnings to all FileManagementService methods
2. Update documentation to point to FileManagementService
3. Create migration guide for existing code
4. Schedule removal for future version

## Implementation Guidelines

### Error Handling Standards

```python
try:
    # File operations using file_service
    result = self.file_service.some_operation()
except Exception as e:
    logger.error(f"Operation failed: {str(e)}")
    # Clean up any partial results
    if 'temp_file' in locals():
        self.file_service.delete_file(temp_file)
    raise
```

### Logging Standards

```python
import logging
logger = logging.getLogger(__name__)

# Log file operations
logger.info(f"Processing file: {original_filename}")
logger.debug(f"File saved to: {file_path}")
logger.error(f"File operation failed: {str(e)}")
```

### Testing Standards

```python
# Use dependency injection for testing
def test_service_with_mock_file_service():
    mock_file_service = Mock(spec=FileManagementService)
    service = ServiceName(file_service=mock_file_service)
    
    # Test service behavior
    result = service.process_data(test_data)
    
    # Verify file service interactions
    mock_file_service.save_file.assert_called_once()
```

## Migration Strategy

### Backward Compatibility

1. **Constructor Compatibility**: New constructors should maintain backward compatibility where possible
2. **Gradual Migration**: Services can be updated incrementally
3. **Legacy Support**: FileManagementService remains available with deprecation warnings
4. **Test Updates**: Update tests to use new patterns while maintaining coverage

### Rollout Plan

1. **Phase 1**: Update OCRService (lowest risk)
2. **Phase 2**: Update ConversionService 
3. **Phase 3**: Update CompressionService (highest complexity)
4. **Phase 4**: Deprecate FileManagementService and update remaining references
5. **Phase 5**: Update all tests and documentation

### Validation Criteria

- [ ] All services use FileManagementService for file operations
- [ ] No direct file system operations outside of FileManagementService
- [ ] Consistent error handling across all services
- [ ] All tests pass with new implementations
- [ ] Performance benchmarks show no regression
- [ ] Memory usage remains stable
- [ ] File cleanup works correctly across all services

## Benefits of Standardization

1. **Consistency**: Uniform file handling across all services
2. **Maintainability**: Single point of file management logic
3. **Testing**: Easier to mock and test file operations
4. **Cleanup**: Centralized file cleanup and retention policies
5. **Monitoring**: Better visibility into file operations
6. **Security**: Consistent security practices for file handling
7. **Performance**: Optimized file operations in one place

## Risk Mitigation

1. **Incremental Changes**: Update one service at a time
2. **Comprehensive Testing**: Maintain test coverage throughout refactoring
3. **Rollback Plan**: Keep original implementations until validation complete
4. **Performance Monitoring**: Track performance metrics during migration
5. **Documentation**: Update all documentation to reflect changes

## Success Metrics

- Code duplication reduced by eliminating redundant file handling
- Test coverage maintained or improved
- Performance benchmarks show no regression
- All file operations go through FileManagementService
- Legacy FileManagementService usage eliminated
- Documentation updated and accurate

---

**Document Version**: 1.0  
**Created**: 2025-01-11  
**Status**: Draft  
**Next Review**: After Phase 1 completion
