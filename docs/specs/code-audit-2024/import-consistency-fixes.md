# Import Consistency Fixes

## Problem Analysis

### Issue Description
The codebase still contains inconsistent import patterns that reduce maintainability, make dependencies unclear, and can lead to circular import issues. These were identified in the previous audit but not yet addressed.

### Current Import Inconsistencies

#### 1. Mixed Import Styles

```python
# Inconsistent patterns across files:

# File A: Explicit imports (GOOD)
from src.services.compression_service import CompressionService
from src.models.job import Job, JobStatus

# File B: Relative imports (INCONSISTENT)
from ..models.job import Job
from .compression_service import CompressionService

# File C: Mixed patterns (BAD)
from src.services import *  # Wildcard import
from src.models.job import Job  # Explicit import
import src.utils.file_utils as file_utils  # Module import
```

#### 2. Service Import Patterns

```python
# Anti-pattern 1: Inconsistent service instantiation
# Some files:
from src.services import CompressionService
compression_service = CompressionService()

# Other files:
from src.services.compression_service import CompressionService
service = CompressionService()

# Still other files:
import src.services
service = src.services.CompressionService()
```

#### 3. Lazy Import Inconsistencies

```python
# Some services use lazy imports for heavy dependencies
def get_ai_service():
    from src.services.ai_service import AIService
    return AIService()

# While others import at module level
from src.services.ai_service import AIService  # Always loaded
```

### Affected Files

Files with import inconsistencies:

- `src/routes/compression_routes.py` - Mixed import patterns
- `src/routes/pdf_suite.py` - Service instantiation inconsistencies
- `src/tasks/tasks.py` - Lazy vs direct imports
- `src/services/*.py` - Inter-service dependencies
- `src/utils/*.py` - Utility import patterns

## Solution Design

### 1. Standardized Import Hierarchy

#### Import Order Standard

```python
# Standard import order for all files:

# 1. Standard library imports
import os
import logging
from typing import Dict, List, Optional
from contextlib import contextmanager

# 2. Third-party imports  
from flask import Blueprint, request, jsonify
from celery import Celery
from sqlalchemy.exc import SQLAlchemyError

# 3. Local application imports (absolute paths)
from src.models.job import Job, JobStatus
from src.services.compression_service import CompressionService
from src.utils.exceptions import ValidationError
from src.utils.response_helpers import success_response, error_response

# 4. Configuration and constants
from src.config.config import Config
```

#### Absolute Import Policy

```python
# ALWAYS use absolute imports for clarity:

# ✅ CORRECT
from src.services.compression_service import CompressionService
from src.models.job import Job
from src.utils.file_utils import validate_file

# ❌ AVOID relative imports
from ..services.compression_service import CompressionService
from .file_utils import validate_file

# ❌ AVOID wildcard imports
from src.services import *
from src.utils import *
```

### 2. Service Import Standardization

#### Service Dependency Injection Pattern

```python
# src/utils/service_locator.py
from typing import Dict, Type, Any, Optional
from src.services.compression_service import CompressionService
from src.services.ai_service import AIService
from src.services.file_management_service import FileManagementService
from src.services.ocr_service import OCRService
from src.services.conversion_service import ConversionService
from src.services.invoice_extraction_service import InvoiceExtractionService
from src.services.bank_statement_extraction_service import BankStatementExtractionService
from src.services.export_service import ExportService

class ServiceLocator:
    """
    Centralized service locator for dependency injection.
    Ensures consistent service instantiation across the application.
    """
    
    _instances: Dict[Type, Any] = {}
    _service_classes = {
        'compression': CompressionService,
        'ai': AIService,
        'file_management': FileManagementService,
        'ocr': OCRService,
        'conversion': ConversionService,
        'invoice_extraction': InvoiceExtractionService,
        'bank_statement_extraction': BankStatementExtractionService,
        'export': ExportService,
    }
    
    @classmethod
    def get_service(cls, service_name: str) -> Any:
        """
        Get a service instance by name.
        Uses singleton pattern to ensure consistent instances.
        """
        service_class = cls._service_classes.get(service_name)
        if not service_class:
            raise ValueError(f"Unknown service: {service_name}")
            
        if service_class not in cls._instances:
            cls._instances[service_class] = service_class()
            
        return cls._instances[service_class]
    
    @classmethod
    def get_compression_service(cls) -> CompressionService:
        return cls.get_service('compression')
        
    @classmethod
    def get_ai_service(cls) -> AIService:
        return cls.get_service('ai')
        
    @classmethod
    def get_file_management_service(cls) -> FileManagementService:
        return cls.get_service('file_management')
    
    # ... add getters for all services
    
    @classmethod
    def clear_instances(cls):
        """Clear all service instances. Useful for testing."""
        cls._instances.clear()
```

#### Standard Service Usage Pattern

```python
# Standard pattern for using services in routes and tasks:

from src.utils.service_locator import ServiceLocator

def compress_pdf_task(job_id: str, file_path: str):
    """Standard service usage pattern."""
    # Get services through service locator
    compression_service = ServiceLocator.get_compression_service()
    file_service = ServiceLocator.get_file_management_service()
    
    # Use services
    result = compression_service.compress_pdf(file_path)
    file_service.cleanup_temp_files(job_id)
    
    return result
```

### 3. Lazy Import Standardization

#### Heavy Dependency Lazy Loading

```python
# src/utils/lazy_imports.py
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)

class LazyImporter:
    """
    Standardized lazy import utility for heavy dependencies.
    """
    
    _cached_modules: Dict[str, Any] = {}
    
    @classmethod
    def get_module(cls, module_path: str, description: str = "") -> Any:
        """
        Lazy import a module with caching.
        
        Args:
            module_path: Full module import path
            description: Human-readable description for logging
        """
        if module_path not in cls._cached_modules:
            try:
                logger.info(f"Lazy loading {description or module_path}")
                module = __import__(module_path, fromlist=[''])
                cls._cached_modules[module_path] = module
            except ImportError as e:
                logger.error(f"Failed to lazy load {module_path}: {e}")
                raise
                
        return cls._cached_modules[module_path]
    
    @classmethod
    def get_ai_models(cls):
        """Lazy load AI model dependencies."""
        return cls.get_module('openai', 'OpenAI client')
    
    @classmethod
    def get_ocr_engine(cls):
        """Lazy load OCR engine dependencies."""
        return cls.get_module('pytesseract', 'Tesseract OCR engine')
    
    @classmethod
    def get_pdf_processing(cls):
        """Lazy load PDF processing dependencies."""
        return cls.get_module('PyPDF2', 'PDF processing library')
```

#### When to Use Lazy Imports

```python
# Use lazy imports for:
# 1. Heavy dependencies that aren't always needed
# 2. Optional dependencies
# 3. Dependencies that require initialization

# Example: AI service with lazy loading
class AIService:
    def __init__(self):
        self._openai_client = None
        
    def _get_openai_client(self):
        """Lazy load OpenAI client only when needed."""
        if self._openai_client is None:
            openai = LazyImporter.get_ai_models()
            self._openai_client = openai.OpenAI()
        return self._openai_client
    
    def summarize_text(self, text: str) -> str:
        client = self._get_openai_client()
        # ... use client
```

## Implementation Plan

### Phase 1: Standards and Tools (Week 1)

1. **Create import standards documentation**
   - Document import order and style guide
   - Create examples for common patterns
   - Add to development guidelines

2. **Implement service locator**
   - Create `src/utils/service_locator.py`
   - Create `src/utils/lazy_imports.py`
   - Write comprehensive tests

3. **Set up automated linting**
   - Configure `isort` for import sorting
   - Configure `flake8` for import validation
   - Add to CI/CD pipeline

### Phase 2: Core Files (Week 2)

4. **Update route files**
   - `src/routes/compression_routes.py`
   - `src/routes/pdf_suite.py`
   - `src/routes/jobs_routes.py`
   - Standardize service usage patterns

5. **Update task files**
   - `src/tasks/tasks.py`
   - `src/tasks/utils.py`
   - Implement lazy loading for heavy dependencies

### Phase 3: Service Files (Week 3)

6. **Update service files**
   - All files in `src/services/`
   - Standardize inter-service dependencies
   - Implement lazy loading where appropriate

7. **Update utility files**
   - All files in `src/utils/`
   - Ensure consistent import patterns

### Phase 4: Validation (Week 4)

8. **Testing and validation**
   - Run import linting on entire codebase
   - Test service locator under load
   - Verify no circular import issues

## Example Transformations

### Before: Route File with Inconsistent Imports

```python
# src/routes/compression_routes.py (BEFORE)
import os
from flask import Blueprint, request, jsonify, current_app
from src.services import *  # Wildcard import
from ..models.job import Job  # Relative import
import src.utils.file_utils as file_utils  # Module import
from celery import Celery
from src.utils.response_helpers import success_response

compression_bp = Blueprint('compression', __name__)

@compression_bp.route('/compress', methods=['POST'])
def compress_pdf():
    # Direct service instantiation
    compression_service = CompressionService()
    file_service = FileManagementService()
    
    # ... rest of implementation
```

### After: Route File with Consistent Imports

```python
# src/routes/compression_routes.py (AFTER)
import os
from typing import Dict, Any

from flask import Blueprint, request, jsonify, current_app
from celery import Celery

from src.models.job import Job
from src.utils.service_locator import ServiceLocator
from src.utils.file_utils import validate_uploaded_file
from src.utils.response_helpers import success_response, error_response
from src.utils.exceptions import ValidationError

compression_bp = Blueprint('compression', __name__)

@compression_bp.route('/compress', methods=['POST'])
def compress_pdf():
    # Service locator usage
    compression_service = ServiceLocator.get_compression_service()
    file_service = ServiceLocator.get_file_management_service()
    
    # ... rest of implementation
```

### Before: Service with Inconsistent Dependencies

```python
# src/services/ai_service.py (BEFORE)
import openai  # Heavy import at module level
from src.services import ExportService  # Wildcard source
from ..models.job import Job  # Relative import
import src.config.config as config  # Module import

class AIService:
    def __init__(self):
        self.openai_client = openai.OpenAI()
        self.export_service = ExportService()  # Direct instantiation
```

### After: Service with Consistent Dependencies

```python
# src/services/ai_service.py (AFTER)
from typing import Dict, Any, Optional

from src.models.job import Job
from src.utils.lazy_imports import LazyImporter
from src.utils.service_locator import ServiceLocator
from src.config.config import Config
from src.utils.exceptions import AIServiceError

class AIService:
    def __init__(self):
        self._openai_client = None
    
    def _get_openai_client(self):
        """Lazy load OpenAI client."""
        if self._openai_client is None:
            openai = LazyImporter.get_ai_models()
            self._openai_client = openai.OpenAI(api_key=Config.OPENAI_API_KEY)
        return self._openai_client
    
    def get_export_service(self):
        """Get export service through service locator."""
        return ServiceLocator.get_service('export')
```

## Automated Tooling

### isort Configuration

```ini
# pyproject.toml
[tool.isort]
profile = "black"
line_length = 100
multi_line_output = 3
include_trailing_comma = true
force_grid_wrap = 0
use_parentheses = true
ensure_newline_before_comments = true

# Import sections
sections = ["FUTURE", "STDLIB", "THIRDPARTY", "FIRSTPARTY", "LOCALFOLDER"]
known_first_party = ["src"]
known_third_party = ["flask", "celery", "sqlalchemy", "openai"]

# Force single line imports for better readability
force_single_line = false
single_line_exclusions = ["typing"]
```

### flake8 Configuration

```ini
# setup.cfg
[flake8]
max-line-length = 100
ignore = E203, W503
exclude = 
    .git,
    __pycache__,
    .pytest_cache,
    .env,
    venv,
    migrations

# Import-specific rules
select = E,W,F,I
per-file-ignores =
    __init__.py:F401  # Allow unused imports in __init__.py files
```

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/PyCQA/isort
    rev: 5.12.0
    hooks:
      - id: isort
        args: ["--profile", "black"]
        
  - repo: https://github.com/PyCQA/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: ["--config", "setup.cfg"]
```

## Testing Strategy

### Import Structure Tests

```python
def test_no_wildcard_imports():
    """Ensure no wildcard imports exist in the codebase."""
    import ast
    import os
    
    for root, dirs, files in os.walk('src'):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r') as f:
                    try:
                        tree = ast.parse(f.read())
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ImportFrom):
                                for name in node.names:
                                    assert name.name != '*', \
                                        f"Wildcard import found in {file_path}"
                    except SyntaxError:
                        pass  # Skip files with syntax errors

def test_service_locator_consistency():
    """Test that service locator returns consistent instances."""
    from src.utils.service_locator import ServiceLocator
    
    # Test singleton behavior
    service1 = ServiceLocator.get_compression_service()
    service2 = ServiceLocator.get_compression_service()
    assert service1 is service2
    
    # Test clear functionality
    ServiceLocator.clear_instances()
    service3 = ServiceLocator.get_compression_service()
    assert service3 is not service1
```

### Lazy Import Tests

```python
def test_lazy_imports_cache():
    """Test that lazy imports are properly cached."""
    from src.utils.lazy_imports import LazyImporter
    
    # Clear cache
    LazyImporter._cached_modules.clear()
    
    # First import should cache
    module1 = LazyImporter.get_module('json', 'JSON module')
    assert 'json' in LazyImporter._cached_modules
    
    # Second import should use cache
    module2 = LazyImporter.get_module('json', 'JSON module')
    assert module1 is module2
```

## Success Criteria

- ✅ All imports follow absolute path convention
- ✅ No wildcard imports in production code
- ✅ Consistent service instantiation via service locator
- ✅ Heavy dependencies use lazy loading
- ✅ Import order consistent across all files
- ✅ Automated linting passes on entire codebase
- ✅ No circular import dependencies
- ✅ Service locator provides singleton instances

## Risk Mitigation

### Rollback Plan
- Keep backup of import patterns before changes
- Implement changes file-by-file for easy rollback
- Test each file change in isolation

### Testing Strategy
- Run full test suite after each file update
- Test lazy loading under various conditions
- Verify service locator doesn't create memory leaks

### Performance Impact
- Monitor import time changes
- Verify lazy loading reduces startup time
- Test service locator overhead
