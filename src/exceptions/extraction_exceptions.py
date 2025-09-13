"""Exceptions for extraction operations."""


class ExtractionError(Exception):
    """Base exception for extraction operations.
    
    Raised when there are issues during text or data extraction
    from documents that might be recoverable with retry.
    """
    pass


class ExtractionValidationError(Exception):
    """Exception for extraction validation failures.
    
    Raised when extracted data fails validation checks.
    This is typically a non-retryable error as it indicates
    issues with the source document or extraction logic.
    """
    pass