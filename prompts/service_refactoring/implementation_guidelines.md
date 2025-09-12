# Implementation Guidelines and Migration Strategy

This document provides detailed guidelines for implementing the file management standardization refactoring and managing the migration process.

## Implementation Guidelines

### Code Standards

#### 1. Dependency Injection Pattern

**Standard Constructor Pattern**:
```python
class ServiceName:
    def __init__(self, file_service: Optional[FileManagementService] = None):
        """Initialize service with file management dependency
        
        Args:
            file_service: File management service instance. If None, creates default instance.
        """
        from src.services.file_management_service import FileManagementService
        self.file_service = file_service or FileManagementService()
        
        # Service-specific initialization
        self._initialize_service_specifics()
```

**Benefits**:
- Enables easy testing with mock services
- Allows for different file service configurations
- Maintains backward compatibility
- Follows SOLID principles (Dependency Inversion)

#### 2. Error Handling Standards

**Standard Error Handling Pattern**:

```python
def process_data(self, file_data: bytes, options: Dict[str, Any] = None,
                 original_filename: str = None) -> Dict[str, Any]:
    """Process data with standardized error handling"""
    temp_files = []  # Track temporary files for cleanup

    try:
        # Save input file
        file_id, temp_path = self.file_service.save_file(file_data, original_filename)
        temp_files.append(temp_path)

        # Process the file
        result = self._process_internal(temp_path, options)

        # Return standardized success response
        return {
            'success': True,
            'output_path': result['output_path'],
            'filename': result['filename'],
            'mime_type': result['mime_type'],
            'file_size': self.file_service._get_file_size(result['output_path']),
            'original_filename': original_filename,
            'original_size': len(file_data)
        }

    except Exception as e:
        logger.error(f"Processing failed for {original_filename}: {str(e)}")

        # Clean up temporary files
        for temp_file in temp_files:
            try:
                self.file_service.delete_file(temp_file)
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup {temp_file}: {cleanup_error}")

        # Return standardized error response
        return {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'original_filename': original_filename,
            'original_size': len(file_data)
        }
```

#### 3. Logging Standards

**Logging Configuration**:
```python
import logging

# Use module-level logger
logger = logging.getLogger(__name__)

# Standard logging patterns
class ServiceName:
    def process_data(self, file_data: bytes, original_filename: str = None):
        logger.info(f"Starting processing for {original_filename or 'unnamed file'} "
                   f"({len(file_data)} bytes)")
        
        try:
            # Processing logic
            result = self._process_internal()
            
            logger.info(f"Processing completed successfully for {original_filename}. "
                       f"Output: {result['filename']} ({result['file_size']} bytes)")
            
            return result
            
        except Exception as e:
            logger.error(f"Processing failed for {original_filename}: {str(e)}", 
                        exc_info=True)
            raise
```

**Logging Levels**:
- `DEBUG`: Detailed file operations, internal state
- `INFO`: Processing start/completion, file metadata
- `WARNING`: Non-fatal issues, fallback operations
- `ERROR`: Processing failures, file operation errors
- `CRITICAL`: Service initialization failures

#### 4. Testing Standards

**Unit Test Pattern**:
```python
import pytest
from unittest.mock import Mock, patch
from src.services.file_management_service import FileManagementService
from src.services.service_name import ServiceName

class TestServiceName:
    @pytest.fixture
    def mock_file_service(self):
        """Create mock file service for testing"""
        mock = Mock(spec=FileManagementService)
        mock.save_file.return_value = ('test-id', '/tmp/test-file.pdf')
        mock.get_file_size.return_value = 1024
        mock.file_exists.return_value = True
        return mock
    
    @pytest.fixture
    def service(self, mock_file_service):
        """Create service instance with mock file service"""
        return ServiceName(file_service=mock_file_service)
    
    def test_process_data_success(self, service, mock_file_service):
        """Test successful data processing"""
        test_data = b"test file content"
        filename = "test.pdf"
        
        result = service.process_data(test_data, original_filename=filename)
        
        # Verify file service interactions
        mock_file_service.save_file.assert_called_once_with(test_data, filename)
        
        # Verify result structure
        assert result['success'] is True
        assert result['original_filename'] == filename
        assert result['original_size'] == len(test_data)
    
    def test_process_data_error_handling(self, service, mock_file_service):
        """Test error handling and cleanup"""
        # Setup mock to raise exception
        mock_file_service.save_file.side_effect = Exception("File save failed")
        
        test_data = b"test file content"
        result = service.process_data(test_data)
        
        # Verify error response
        assert result['success'] is False
        assert 'error' in result
        assert result['original_size'] == len(test_data)
```

**Integration Test Pattern**:
```python
import tempfile
import pytest
from pathlib import Path
from src.services.file_management_service import FileManagementService
from src.services.service_name import ServiceName

class TestServiceNameIntegration:
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def file_service(self, temp_dir):
        """Create real file service for integration testing"""
        return FileManagementService(upload_folder=temp_dir)
    
    @pytest.fixture
    def service(self, file_service):
        """Create service with real file service"""
        return ServiceName(file_service=file_service)
    
    def test_end_to_end_processing(self, service, temp_dir):
        """Test complete processing workflow"""
        # Load test file
        test_file_path = Path(__file__).parent / "fixtures" / "test.pdf"
        with open(test_file_path, 'rb') as f:
            test_data = f.read()
        
        # Process the file
        result = service.process_data(test_data, original_filename="test.pdf")
        
        # Verify processing success
        assert result['success'] is True
        
        # Verify output file exists
        output_path = Path(result['output_path'])
        assert output_path.exists()
        assert output_path.stat().st_size > 0
```

### Performance Guidelines

#### 1. Memory Management

```python
def process_large_file(self, file_data: bytes) -> Dict[str, Any]:
    """Process large files with memory-efficient patterns"""
    # Avoid keeping large data in memory
    file_id, temp_path = self.file_service.save_file(file_data)
    
    # Clear reference to large data early
    del file_data
    
    try:
        # Process from disk rather than memory
        result = self._process_from_disk(temp_path)
        return result
    finally:
        # Always cleanup temporary files
        self.file_service.delete_file(temp_path)
```

#### 2. File I/O Optimization

```python
def process_with_streaming(self, file_data: bytes) -> Dict[str, Any]:
    """Use streaming for large file operations"""
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        # Write in chunks for large files
        chunk_size = 8192
        for i in range(0, len(file_data), chunk_size):
            temp_file.write(file_data[i:i + chunk_size])
        
        temp_path = temp_file.name
    
    try:
        # Process the file
        result = self._process_file(temp_path)
        return result
    finally:
        # Cleanup
        os.unlink(temp_path)
```

## Migration Strategy

### Pre-Migration Checklist

- [ ] All existing tests pass
- [ ] Performance baseline established
- [ ] Backup of current codebase created
- [ ] Development environment prepared
- [ ] Team notified of migration timeline

### Migration Phases

#### Phase 1: OCRService (Low Risk)

**Timeline**: 1-2 days
**Risk Level**: Low
**Dependencies**: None

**Steps**:
1. Create feature branch: `feature/ocr-service-refactor`
2. Update OCRService constructor
3. Replace file operations with file_service calls
4. Update error handling
5. Run tests and fix issues
6. Performance validation
7. Code review and merge

**Validation Criteria**:
- All OCR tests pass
- Performance within 5% of baseline
- No memory leaks detected
- Error handling works correctly

#### Phase 2: ConversionService (Medium Risk)

**Timeline**: 2-3 days
**Risk Level**: Medium
**Dependencies**: Phase 1 complete

**Steps**:
1. Create feature branch: `feature/conversion-service-refactor`
2. Update ConversionService constructor
3. Replace file operations with file_service calls
4. Update all converter methods
5. Update error handling
6. Run comprehensive tests
7. Performance validation
8. Code review and merge

**Validation Criteria**:
- All conversion tests pass
- All output formats work correctly
- Performance within 5% of baseline
- Memory usage stable
- Error handling works correctly

#### Phase 3: CompressionService (High Risk)

**Timeline**: 3-4 days
**Risk Level**: High
**Dependencies**: Phases 1-2 complete

**Steps**:
1. Create feature branch: `feature/compression-service-refactor`
2. Update CompressionService constructor
3. Refactor file handling in process_file_data
4. Update Ghostscript integration
5. Update error handling and cleanup
6. Run extensive tests with various file sizes
7. Performance validation with large files
8. Code review and merge

**Validation Criteria**:
- All compression tests pass
- Large file handling works correctly
- Compression ratios maintained
- Performance within 10% of baseline
- Memory usage stable under load
- Error handling and cleanup work correctly

#### Phase 4: FileManager Deprecation (Low Risk)

**Timeline**: 1-2 days
**Risk Level**: Low
**Dependencies**: Phases 1-3 complete

**Steps**:
1. Add deprecation warnings to FileManager
2. Update remaining imports
3. Update variable names
4. Update documentation
5. Run full test suite
6. Code review and merge

**Validation Criteria**:
- No FileManager usage in production code
- All tests pass
- Deprecation warnings appear correctly
- Documentation updated

#### Phase 5: Test and Documentation Updates (Low Risk)

**Timeline**: 2-3 days
**Risk Level**: Low
**Dependencies**: Phases 1-4 complete

**Steps**:
1. Update all service tests
2. Update integration tests
3. Update API documentation
4. Update README files
5. Run full test suite
6. Performance regression testing
7. Final code review

### Rollback Strategy

#### Immediate Rollback (< 1 hour)

```bash
# Revert to last known good state
git revert <commit-hash>
git push origin main

# Or reset to previous commit (if safe)
git reset --hard <previous-commit>
git push --force-with-lease origin main
```

#### Selective Rollback (1-2 hours)

```bash
# Revert specific files
git checkout <previous-commit> -- src/services/service_name.py
git commit -m "Rollback service_name.py to previous version"
git push origin main
```

#### Partial Rollback (2-4 hours)

1. Identify problematic changes
2. Create hotfix branch
3. Revert specific changes
4. Test thoroughly
5. Deploy hotfix

### Risk Mitigation

#### 1. Automated Testing

```bash
# Pre-migration test script
#!/bin/bash
set -e

echo "Running pre-migration tests..."
pytest tests/ -v --cov=src/services/

echo "Running performance benchmarks..."
python scripts/performance_benchmark.py

echo "Running memory leak detection..."
python scripts/memory_test.py

echo "All pre-migration checks passed!"
```

#### 2. Monitoring and Alerts

```python
# Add monitoring to services
import time
import psutil
from src.utils.monitoring import track_performance

class ServiceName:
    @track_performance
    def process_data(self, file_data: bytes) -> Dict[str, Any]:
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss
        
        try:
            result = self._process_internal(file_data)
            
            # Log performance metrics
            duration = time.time() - start_time
            memory_used = psutil.Process().memory_info().rss - start_memory
            
            logger.info(f"Processing completed in {duration:.2f}s, "
                       f"memory used: {memory_used / 1024 / 1024:.2f}MB")
            
            return result
            
        except Exception as e:
            logger.error(f"Processing failed after {time.time() - start_time:.2f}s")
            raise
```

#### 3. Gradual Deployment

```python
# Feature flag for gradual rollout
from src.config import Config

class ServiceName:
    def __init__(self, file_service: Optional[FileManagementService] = None):
        if Config.USE_NEW_FILE_MANAGEMENT:
            self.file_service = file_service or FileManagementService()
        else:
            # Fallback to old implementation
            from src.services.file_manager import FileManager
            self.file_manager = FileManager()
```

### Success Metrics

#### Technical Metrics

- **Code Quality**:
  - Cyclomatic complexity reduced
  - Code duplication eliminated
  - Test coverage maintained or improved

- **Performance**:
  - Response times within 5% of baseline
  - Memory usage stable
  - No performance regressions

- **Reliability**:
  - Error rates unchanged or improved
  - File cleanup success rate 100%
  - No data loss incidents

#### Business Metrics

- **Maintainability**:
  - Reduced time to implement new features
  - Faster bug resolution
  - Easier onboarding for new developers

- **Operational**:
  - Reduced support tickets
  - Improved system monitoring
  - Better error diagnostics

### Post-Migration Tasks

1. **Performance Monitoring**: Monitor for 2 weeks post-deployment
2. **Documentation Updates**: Update all technical documentation
3. **Team Training**: Conduct training sessions on new patterns
4. **Legacy Cleanup**: Schedule removal of deprecated code
5. **Lessons Learned**: Document migration experience

---

**Document Version**: 1.0  
**Created**: 2025-01-11  
**Status**: Ready for Implementation  
**Next Review**: After Phase 1 completion