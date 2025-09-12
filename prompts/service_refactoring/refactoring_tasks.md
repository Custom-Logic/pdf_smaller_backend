# Service Refactoring Tasks

This document provides detailed, actionable tasks for refactoring each service to use the standardized FileManagementService pattern.

## Phase 1: OCRService Refactoring

### Task 1.1: Update Constructor

**File**: `src/services/ocr_service.py`
**Lines**: ~42-47

**Current Code**:
```python
def __init__(self, upload_folder: Optional[str] = None):
    self.upload_folder = Path(upload_folder or tempfile.mkdtemp(prefix="ocr_"))
    self.upload_folder.mkdir(parents=True, exist_ok=True)
```

**Target Code**:
```python
def __init__(self, file_service: Optional[FileManagementService] = None):
    from src.services.file_management_service import FileManagementService
    self.file_service = file_service or FileManagementService()
```

**Additional Changes**:
- Add import: `from src.services.file_management_service import FileManagementService`
- Remove import: `import tempfile` (if no longer needed)
- Remove `self.upload_folder` references

### Task 1.2: Replace _save_file_data Method

**File**: `src/services/ocr_service.py`
**Method**: `_save_file_data` (find and replace)

**Current Pattern**:
```python
def _save_file_data(self, file_data: bytes, original_filename: Optional[str]) -> Path:
    # Manual file saving logic
    pass
```

**Target Pattern**:
```python
def _save_file_data(self, file_data: bytes, original_filename: Optional[str]) -> Path:
    """Save file data using file management service"""
    file_id, file_path = self.file_service.save_file(file_data, original_filename)
    return Path(file_path)
```

### Task 1.3: Update File Path References

**File**: `src/services/ocr_service.py`
**Locations**: Throughout the class

**Changes**:
- Replace `self.upload_folder` with `self.file_service`
- Use `self.file_service.get_file_path()` for path construction
- Use `self.file_service.file_exists()` for existence checks
- Use `self.file_service.get_file_size()` for size operations

### Task 1.4: Update Error Handling

**File**: `src/services/ocr_service.py`
**Method**: `process_ocr_data`

**Add cleanup in exception handling**:
```python
except Exception as exc:
    logger.exception("OCR failed")
    # Clean up any temporary files
    if 'temp_file' in locals() and temp_file:
        self.file_service.delete_file(str(temp_file))
    return {
        "success": False,
        "error": str(exc),
        "original_filename": original_filename,
        "original_size": len(file_data),
    }
```

## Phase 2: ConversionService Refactoring

### Task 2.1: Update Constructor

**File**: `src/services/conversion_service.py`
**Lines**: ~50-53

**Current Code**:
```python
def __init__(self, upload_folder: Optional[str] = None):
    self.upload_folder = Path(upload_folder or tempfile.mkdtemp(prefix="pdf_conv_"))
    self.upload_folder.mkdir(parents=True, exist_ok=True)
```

**Target Code**:
```python
def __init__(self, file_service: Optional[FileManagementService] = None):
    from src.services.file_management_service import FileManagementService
    self.file_service = file_service or FileManagementService()
```

### Task 2.2: Replace _save_file_data Method

**File**: `src/services/conversion_service.py`
**Method**: `_save_file_data` (find and replace)

**Target Pattern**:
```python
def _save_file_data(self, file_data: bytes, original_filename: Optional[str]) -> Path:
    """Save file data using file management service"""
    file_id, file_path = self.file_service.save_file(file_data, original_filename)
    return Path(file_path)
```

### Task 2.3: Update File Operations in Converters

**File**: `src/services/conversion_service.py`
**Methods**: `_convert_to_docx`, `_convert_to_txt`, `_convert_to_html`, etc.

**Changes**:
- Replace manual file path construction with `self.file_service.get_file_path()`
- Use `self.file_service.save_file()` for output files
- Replace file existence checks with `self.file_service.file_exists()`

### Task 2.4: Update Error Handling

**File**: `src/services/conversion_service.py`
**Method**: `convert_pdf_data`

**Add cleanup in exception handling**:
```python
except Exception as exc:
    logger.exception("Conversion failed")
    # Clean up any temporary files
    if 'temp_pdf' in locals() and temp_pdf:
        self.file_service.delete_file(str(temp_pdf))
    return {
        "success": False,
        "error": str(exc),
        "format": target_format,
        "original_filename": original_filename,
        "original_size": len(file_data),
    }
```

## Phase 3: CompressionService Refactoring

### Task 3.1: Update Constructor

**File**: `src/services/compression_service.py`
**Lines**: ~17-21

**Current Code**:
```python
def __init__(self, upload_folder):
    self.upload_folder = upload_folder
    Path(self.upload_folder).mkdir(parents=True, exist_ok=True)
```

**Target Code**:
```python
def __init__(self, file_service: Optional[FileManagementService] = None):
    from src.services.file_management_service import FileManagementService
    self.file_service = file_service or FileManagementService()
```

### Task 3.2: Update process_file_data Method

**File**: `src/services/compression_service.py`
**Method**: `process_file_data`
**Lines**: ~24-70

**Current Pattern**:
```python
# Create output directory in upload folder (persistent)
output_dir = os.path.join(self.upload_folder, 'results')
Path(output_dir).mkdir(parents=True, exist_ok=True)

# Generate unique output filename
job_id = str(uuid.uuid4())
output_filename = f"compressed_{job_id}_{secure_filename(original_filename or 'file.pdf')}"
output_path = os.path.join(output_dir, output_filename)
```

**Target Pattern**:
```python
# Use file service for output file management
with tempfile.TemporaryDirectory() as temp_dir:
    # Save input file in temp directory
    input_path = os.path.join(temp_dir, secure_filename(original_filename or 'input.pdf'))
    with open(input_path, 'wb') as f:
        f.write(file_data)
    
    # Create temporary output file
    temp_output = os.path.join(temp_dir, 'compressed_output.pdf')
    
    # Compress to temporary location
    self.compress_pdf(input_path, temp_output, compression_level, image_quality)
    
    # Read compressed file and save through file service
    with open(temp_output, 'rb') as f:
        compressed_data = f.read()
    
    # Save final result through file service
    output_filename = f"compressed_{secure_filename(original_filename or 'file.pdf')}"
    file_id, output_path = self.file_service.save_file(compressed_data, output_filename)
```

### Task 3.3: Update Error Cleanup

**File**: `src/services/compression_service.py`
**Method**: `process_file_data`

**Replace manual cleanup**:
```python
except Exception as e:
    logger.error(f"Error processing file data: {str(e)}")
    # Clean up output file if created through file service
    if 'file_id' in locals():
        self.file_service.delete_file(output_path)
    raise
```

### Task 3.4: Update File Size Operations

**File**: `src/services/compression_service.py`

**Replace**:
```python
compressed_size = get_file_size(output_path)
```

**With**:

```python
compressed_size = self.file_service._get_file_size(output_path)
```

## Phase 4: FileManager Deprecation

### Task 4.1: Add Deprecation Warnings

**File**: `src/services/file_manager.py`
**Add to top of file**:
```python
import warnings
```

**Add to each method**:
```python
def save_file(self, file_data: bytes, original_filename: str = None) -> Tuple[str, str]:
    warnings.warn(
        "FileManager is deprecated. Use FileManagementService instead.",
        DeprecationWarning,
        stacklevel=2
    )
    # existing implementation
```

### Task 4.2: Update Import References

**Files to check**:
- `src/routes/`
- `src/services/`
- `tests/`

**Search for**:
```python
from src.services.file_manager import FileManager
```

**Replace with**:
```python
from src.services.file_management_service import FileManagementService
```

### Task 4.3: Update Variable Names

**Search and replace patterns**:
- `file_manager` → `file_service`
- `FileManager()` → `FileManagementService()`
- `.file_manager` → `.file_service`

## Phase 5: Test Updates

### Task 5.1: Update Service Tests

**Files**:
- `tests/test_ocr_service.py`
- `tests/test_conversion_service.py`
- `tests/test_compression_service.py`

**Pattern for test updates**:
```python
# Old pattern
def test_service():
    service = ServiceName(upload_folder="/tmp/test")

# New pattern
def test_service():
    mock_file_service = Mock(spec=FileManagementService)
    service = ServiceName(file_service=mock_file_service)
```

### Task 5.2: Update Integration Tests

**Files**: Any integration tests using services

**Ensure**:
- Services are initialized with proper file_service
- File operations are mocked appropriately
- Test data cleanup uses file_service methods

## Validation Checklist

After each phase, verify:

- [ ] All tests pass
- [ ] No direct file system operations outside FileManagementService
- [ ] Error handling includes proper cleanup
- [ ] Logging follows established patterns
- [ ] Performance benchmarks show no regression
- [ ] Memory usage remains stable
- [ ] File cleanup works correctly

## Rollback Procedures

If issues arise during refactoring:

1. **Immediate Rollback**: Revert to previous commit
2. **Partial Rollback**: Keep working changes, revert problematic ones
3. **Fix Forward**: Address issues in current implementation

**Rollback Commands**:
```bash
# Revert specific file
git checkout HEAD~1 -- src/services/service_name.py

# Revert entire commit
git revert <commit-hash>
```

---

**Document Version**: 1.0  
**Created**: 2025-01-11  
**Status**: Ready for Implementation  
**Dependencies**: file_management_standardization_spec.md