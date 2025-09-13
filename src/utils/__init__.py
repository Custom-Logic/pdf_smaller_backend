from src.utils.file_utils import secure_filename, cleanup_old_files, validate_file_type
from src.utils.logging_utils import setup_logging
from src.utils.scheduler import start_background_scheduler, stop_background_scheduler

# Alias for backward compatibility
validate_file = validate_file_type

# Import validation functions only when needed to avoid magic dependency issues
def get_validation_functions():
    """Import validation functions on demand."""
    try:
        import importlib
        validation_module = importlib.import_module('.validation', package='utils')
        return validation_module
    except ImportError:
        return None

__all__ = [
    'secure_filename', 'cleanup_old_files', 'validate_file', 'validate_file_type', 
    'setup_logging', 'start_background_scheduler', 'stop_background_scheduler',
    'get_validation_functions'
]