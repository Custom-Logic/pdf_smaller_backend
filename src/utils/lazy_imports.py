"""Lazy Import Utility - Standardized lazy import utility for heavy dependencies.

Provides lazy loading capabilities for heavy dependencies to improve startup time
and reduce memory footprint when dependencies aren't always needed.
"""
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class LazyImporter:
    """
    Standardized lazy import utility for heavy dependencies.
    
    This class provides a centralized way to lazy load modules that are:
    - Heavy dependencies that aren't always needed
    - Optional dependencies
    - Dependencies that require initialization
    """
    
    _cached_modules: Dict[str, Any] = {}
    
    @classmethod
    def get_module(cls, module_path: str, description: str = "") -> Any:
        """
        Lazy import a module with caching.
        
        Args:
            module_path: Full module import path (e.g., 'openai', 'pytesseract')
            description: Human-readable description for logging
            
        Returns:
            The imported module
            
        Raises:
            ImportError: If the module cannot be imported
        """
        if module_path not in cls._cached_modules:
            try:
                logger.info(f"Lazy loading {description or module_path}")
                
                # Handle different import patterns
                if '.' in module_path:
                    # For submodule imports like 'package.submodule'
                    parts = module_path.split('.')
                    module = __import__(module_path, fromlist=[parts[-1]])
                else:
                    # For top-level module imports
                    module = __import__(module_path)
                    
                cls._cached_modules[module_path] = module
                logger.debug(f"Successfully cached module: {module_path}")
                
            except ImportError as e:
                logger.error(f"Failed to lazy load {module_path}: {e}")
                raise ImportError(f"Could not import {module_path}: {e}") from e
                
        return cls._cached_modules[module_path]
    
    @classmethod
    def get_ai_models(cls):
        """Lazy load AI model dependencies."""
        return cls.get_module('openai', 'OpenAI client library')
    
    @classmethod
    def get_ocr_engine(cls):
        """Lazy load OCR engine dependencies."""
        return cls.get_module('pytesseract', 'Tesseract OCR engine')
    
    @classmethod
    def get_pdf_processing(cls):
        """Lazy load PDF processing dependencies."""
        return cls.get_module('PyPDF2', 'PDF processing library')
    
    @classmethod
    def get_image_processing(cls):
        """Lazy load image processing dependencies."""
        return cls.get_module('PIL', 'Python Imaging Library (Pillow)')
    
    @classmethod
    def get_requests(cls):
        """Lazy load HTTP client dependencies."""
        return cls.get_module('requests', 'HTTP library for Python')
    
    @classmethod
    def get_numpy(cls):
        """Lazy load NumPy for numerical operations."""
        return cls.get_module('numpy', 'NumPy numerical computing library')
    
    @classmethod
    def get_pandas(cls):
        """Lazy load Pandas for data manipulation."""
        return cls.get_module('pandas', 'Pandas data analysis library')
    
    @classmethod
    def get_cv2(cls):
        """Lazy load OpenCV for computer vision."""
        return cls.get_module('cv2', 'OpenCV computer vision library')
    
    @classmethod
    def clear_cache(cls):
        """Clear all cached modules. Useful for testing."""
        logger.info("Clearing lazy import cache")
        cls._cached_modules.clear()
    
    @classmethod
    def is_cached(cls, module_path: str) -> bool:
        """Check if a module is already cached."""
        return module_path in cls._cached_modules
    
    @classmethod
    def get_cached_modules(cls) -> list:
        """Get list of all cached module paths."""
        return list(cls._cached_modules.keys())
    
    @classmethod
    def get_cache_size(cls) -> int:
        """Get the number of cached modules."""
        return len(cls._cached_modules)


# Convenience functions for common lazy imports
def lazy_import_openai():
    """Convenience function to lazy import OpenAI."""
    return LazyImporter.get_ai_models()


def lazy_import_pytesseract():
    """Convenience function to lazy import Tesseract OCR."""
    return LazyImporter.get_ocr_engine()


def lazy_import_pypdf2():
    """Convenience function to lazy import PyPDF2."""
    return LazyImporter.get_pdf_processing()


def lazy_import_pil():
    """Convenience function to lazy import PIL/Pillow."""
    return LazyImporter.get_image_processing()