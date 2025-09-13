"""Exceptions for export operations."""


class ExportError(Exception):
    """Base exception for export operations.
    
    Raised when there are issues during file export or format
    conversion that might be recoverable with retry.
    """
    pass


class FormatError(Exception):
    """Exception for format-related errors.
    
    Raised when there are issues with file formats, unsupported
    formats, or format conversion failures.
    """
    pass