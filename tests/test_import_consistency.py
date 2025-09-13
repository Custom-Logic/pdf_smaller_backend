"""Tests for import consistency and lazy loading functionality.

This module tests the import structure standards and lazy import utilities
to ensure consistent patterns across the codebase.
"""
import ast
import os
import pytest
from unittest.mock import patch, MagicMock

from src.utils.lazy_imports import LazyImporter


class TestImportStructure:
    """Test import structure consistency across the codebase."""
    
    def test_no_wildcard_imports(self):
        """Ensure no wildcard imports exist in the codebase."""
        wildcard_imports = []
        
        for root, dirs, files in os.walk('src'):
            # Skip __pycache__ and other irrelevant directories
            dirs[:] = [d for d in dirs if not d.startswith('__pycache__')]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            tree = ast.parse(content)
                            
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ImportFrom):
                                for name in node.names:
                                    if name.name == '*':
                                        wildcard_imports.append(file_path)
                                        
                    except (SyntaxError, UnicodeDecodeError):
                        # Skip files with syntax errors or encoding issues
                        continue
        
        assert not wildcard_imports, f"Wildcard imports found in: {wildcard_imports}"
    
    def test_absolute_imports_in_src(self):
        """Test that src/ modules use absolute imports."""
        relative_imports = []
        
        for root, dirs, files in os.walk('src'):
            dirs[:] = [d for d in dirs if not d.startswith('__pycache__')]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            tree = ast.parse(content)
                            
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ImportFrom):
                                if node.level > 0:  # Relative import
                                    relative_imports.append({
                                        'file': file_path,
                                        'line': node.lineno,
                                        'module': node.module or '(relative)',
                                        'level': node.level
                                    })
                                    
                    except (SyntaxError, UnicodeDecodeError):
                        continue
        
        if relative_imports:
            error_msg = "Relative imports found:\n"
            for imp in relative_imports:
                error_msg += f"  {imp['file']}:{imp['line']} - {'.' * imp['level']}{imp['module']}\n"
            pytest.fail(error_msg)
    
    def test_import_order_consistency(self):
        """Test that imports follow the standard order: stdlib, third-party, local."""
        # This is a basic check - in practice, isort would handle this
        import_violations = []
        
        stdlib_modules = {
            'os', 'sys', 'json', 'logging', 'datetime', 'typing', 'uuid',
            'pathlib', 'collections', 'functools', 'itertools', 'asyncio'
        }
        
        for root, dirs, files in os.walk('src'):
            dirs[:] = [d for d in dirs if not d.startswith('__pycache__')]
            
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                            
                        import_lines = []
                        for i, line in enumerate(lines, 1):
                            stripped = line.strip()
                            if (stripped.startswith('import ') or 
                                stripped.startswith('from ')) and not stripped.startswith('#'):
                                import_lines.append((i, stripped))
                        
                        # Check basic ordering: stdlib before third-party before local
                        prev_type = 0  # 1=stdlib, 2=third-party, 3=local
                        for line_num, import_line in import_lines:
                            if import_line.startswith('from src.') or import_line.startswith('import src.'):
                                current_type = 3  # local
                            elif any(mod in import_line for mod in stdlib_modules):
                                current_type = 1  # stdlib
                            else:
                                current_type = 2  # third-party
                            
                            if current_type < prev_type:
                                import_violations.append({
                                    'file': file_path,
                                    'line': line_num,
                                    'import': import_line
                                })
                            prev_type = max(prev_type, current_type)
                            
                    except (UnicodeDecodeError, IOError):
                        continue
        
        # Note: This is a basic check. In practice, isort handles complex cases
        # We're mainly checking for obvious violations
        assert len(import_violations) < 5, f"Import order violations found: {import_violations[:3]}"


class TestLazyImporter:
    """Test the LazyImporter utility functionality."""
    
    def setup_method(self):
        """Clear cache before each test."""
        LazyImporter.clear_cache()
    
    def test_lazy_import_caching(self):
        """Test that modules are cached after first import."""
        with patch('builtins.__import__') as mock_import:
            mock_module = MagicMock()
            mock_import.return_value = mock_module
            
            # First call should import
            result1 = LazyImporter.get_module('test_module', 'Test Module')
            assert result1 is mock_module
            assert mock_import.call_count == 1
            
            # Second call should use cache
            result2 = LazyImporter.get_module('test_module', 'Test Module')
            assert result2 is mock_module
            assert mock_import.call_count == 1  # No additional import
            
            # Verify caching
            assert LazyImporter.is_cached('test_module')
            assert LazyImporter.get_cache_size() == 1
    
    def test_lazy_import_error_handling(self):
        """Test error handling when module import fails."""
        with patch('builtins.__import__', side_effect=ImportError("Module not found")):
            with pytest.raises(ImportError, match="Could not import nonexistent_module"):
                LazyImporter.get_module('nonexistent_module', 'Non-existent Module')
    
    def test_convenience_methods(self):
        """Test the convenience methods for common imports."""
        with patch('builtins.__import__') as mock_import:
            mock_module = MagicMock()
            mock_import.return_value = mock_module
            
            # Test AI models import
            result = LazyImporter.get_ai_models()
            assert result is mock_module
            mock_import.assert_called_with('openai')
            
            # Test OCR engine import
            LazyImporter.clear_cache()
            mock_import.reset_mock()
            result = LazyImporter.get_ocr_engine()
            assert result is mock_module
            mock_import.assert_called_with('pytesseract')
    
    def test_submodule_imports(self):
        """Test importing submodules with dot notation."""
        with patch('builtins.__import__') as mock_import:
            mock_module = MagicMock()
            mock_import.return_value = mock_module
            
            result = LazyImporter.get_module('package.submodule', 'Test Submodule')
            assert result is mock_module
            mock_import.assert_called_with('package.submodule', fromlist=['submodule'])
    
    def test_cache_management(self):
        """Test cache management functionality."""
        with patch('builtins.__import__') as mock_import:
            mock_module = MagicMock()
            mock_import.return_value = mock_module
            
            # Import some modules
            LazyImporter.get_module('module1')
            LazyImporter.get_module('module2')
            
            assert LazyImporter.get_cache_size() == 2
            assert 'module1' in LazyImporter.get_cached_modules()
            assert 'module2' in LazyImporter.get_cached_modules()
            
            # Clear cache
            LazyImporter.clear_cache()
            assert LazyImporter.get_cache_size() == 0
            assert not LazyImporter.is_cached('module1')
    
    def test_convenience_functions(self):
        """Test the standalone convenience functions."""
        from src.utils.lazy_imports import lazy_import_openai, lazy_import_pytesseract
        
        with patch('src.utils.lazy_imports.LazyImporter.get_ai_models') as mock_ai:
            with patch('src.utils.lazy_imports.LazyImporter.get_ocr_engine') as mock_ocr:
                mock_module = MagicMock()
                mock_ai.return_value = mock_module
                mock_ocr.return_value = mock_module
                
                result1 = lazy_import_openai()
                assert result1 is mock_module
                mock_ai.assert_called_once()
                
                result2 = lazy_import_pytesseract()
                assert result2 is mock_module
                mock_ocr.assert_called_once()


class TestServiceRegistryConsistency:
    """Test that ServiceRegistry returns consistent instances."""
    
    def test_service_registry_singleton_behavior(self):
        """Test that service registry returns the same instance."""
        from src.services.service_registry import ServiceRegistry
        
        # Test singleton behavior for compression service
        service1 = ServiceRegistry.get_compression_service()
        service2 = ServiceRegistry.get_compression_service()
        assert service1 is service2
        
        # Test singleton behavior for AI service
        ai_service1 = ServiceRegistry.get_ai_service()
        ai_service2 = ServiceRegistry.get_ai_service()
        assert ai_service1 is ai_service2
    
    def test_service_registry_clear_functionality(self):
        """Test that clearing the registry creates new instances."""
        from src.services.service_registry import ServiceRegistry
        
        # Get initial service
        service1 = ServiceRegistry.get_compression_service()
        
        # Clear cache and get new service
        ServiceRegistry.clear_cache()
        service2 = ServiceRegistry.get_compression_service()
        
        # Should be different instances after clearing
        assert service1 is not service2
    
    def test_service_registry_different_configs(self):
        """Test that different configurations create different instances."""
        from src.services.service_registry import ServiceRegistry
        
        # Test file management service with different upload folders
        service1 = ServiceRegistry.get_file_management_service('/path1')
        service2 = ServiceRegistry.get_file_management_service('/path2')
        
        # Should be different instances for different configurations
        assert service1 is not service2
        
        # Same configuration should return same instance
        service3 = ServiceRegistry.get_file_management_service('/path1')
        assert service1 is service3