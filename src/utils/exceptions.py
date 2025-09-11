"""
Custom exception classes for the PDF compression service.

This module defines custom exceptions that provide structured error handling
throughout the application with consistent error codes and messages.
"""

import uuid
from typing import Dict, Any, Optional


class PDFCompressionError(Exception):
    """Base exception class for PDF compression service errors."""
    
    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.error_code = error_code or self.__class__.__name__.upper()
        self.details = details or {}
        self.status_code = status_code
        self.request_id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        return {
            'error': {
                'code': self.error_code,
                'message': self.message,
                'details': self.details
            },
            'request_id': self.request_id
        }


class ValidationError(PDFCompressionError):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: str = None, details: Dict[str, Any] = None):
        error_details = details or {}
        if field:
            error_details['field'] = field
        
        super().__init__(
            message=message,
            error_code='VALIDATION_ERROR',
            details=error_details,
            status_code=400
        )


class AuthenticationError(PDFCompressionError):
    """Raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication required", details: Dict[str, Any] = None):
        super().__init__(
            message=message,
            error_code='AUTHENTICATION_ERROR',
            details=details or {},
            status_code=401
        )


class AuthorizationError(PDFCompressionError):
    """Raised when user lacks permission for requested action."""
    
    def __init__(self, message: str = "Insufficient permissions", details: Dict[str, Any] = None):
        super().__init__(
            message=message,
            error_code='AUTHORIZATION_ERROR',
            details=details or {},
            status_code=403
        )


class ResourceNotFoundError(PDFCompressionError):
    """Raised when a requested resource is not found."""
    
    def __init__(self, resource_type: str, resource_id: str = None, details: Dict[str, Any] = None):
        message = f"{resource_type} not found"
        if resource_id:
            message += f" (ID: {resource_id})"
        
        error_details = details or {}
        error_details.update({
            'resource_type': resource_type,
            'resource_id': resource_id
        })
        
        super().__init__(
            message=message,
            error_code='RESOURCE_NOT_FOUND',
            details=error_details,
            status_code=404
        )


class RateLimitExceededError(PDFCompressionError):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, limit: int, window: str, retry_after: int = None, details: Dict[str, Any] = None):
        message = f"Rate limit exceeded: {limit} requests per {window}"
        
        error_details = details or {}
        error_details.update({
            'limit': limit,
            'window': window,
            'retry_after': retry_after
        })
        
        super().__init__(
            message=message,
            error_code='RATE_LIMIT_EXCEEDED',
            details=error_details,
            status_code=429
        )


class FileProcessingError(PDFCompressionError):
    """Raised when file processing fails."""
    
    def __init__(self, message: str, file_name: str = None, details: Dict[str, Any] = None):
        error_details = details or {}
        if file_name:
            error_details['file_name'] = file_name
        
        super().__init__(
            message=message,
            error_code='FILE_PROCESSING_ERROR',
            details=error_details,
            status_code=422
        )


class SubscriptionError(PDFCompressionError):
    """Raised when subscription-related operations fail."""
    
    def __init__(self, message: str, subscription_status: str = None, details: Dict[str, Any] = None):
        error_details = details or {}
        if subscription_status:
            error_details['subscription_status'] = subscription_status
        
        super().__init__(
            message=message,
            error_code='SUBSCRIPTION_ERROR',
            details=error_details,
            status_code=402
        )


class UsageLimitExceededError(PDFCompressionError):
    """Raised when user exceeds their usage limits."""
    
    def __init__(self, limit_type: str, current_usage: int, limit: int, details: Dict[str, Any] = None):
        message = f"{limit_type} limit exceeded: {current_usage}/{limit}"
        
        error_details = details or {}
        error_details.update({
            'limit_type': limit_type,
            'current_usage': current_usage,
            'limit': limit
        })
        
        super().__init__(
            message=message,
            error_code='USAGE_LIMIT_EXCEEDED',
            details=error_details,
            status_code=402
        )


class ExternalServiceError(PDFCompressionError):
    """Raised when external service integration fails."""
    
    def __init__(self, service_name: str, message: str = None, details: Dict[str, Any] = None):
        error_message = message or f"{service_name} service unavailable"
        
        error_details = details or {}
        error_details['service_name'] = service_name
        
        super().__init__(
            message=error_message,
            error_code='EXTERNAL_SERVICE_ERROR',
            details=error_details,
            status_code=503
        )


class ConfigurationError(PDFCompressionError):
    """Raised when application configuration is invalid."""
    
    def __init__(self, message: str, config_key: str = None, details: Dict[str, Any] = None):
        error_details = details or {}
        if config_key:
            error_details['config_key'] = config_key
        
        super().__init__(
            message=message,
            error_code='CONFIGURATION_ERROR',
            details=error_details,
            status_code=500
        )


class DatabaseError(PDFCompressionError):
    """Raised when database operations fail."""
    
    def __init__(self, message: str, operation: str = None, details: Dict[str, Any] = None):
        error_details = details or {}
        if operation:
            error_details['operation'] = operation
        
        super().__init__(
            message=message,
            error_code='DATABASE_ERROR',
            details=error_details,
            status_code=500
        )


class SecurityError(PDFCompressionError):
    """Raised when security violations are detected."""
    
    def __init__(self, message: str, violation_type: str = None, details: Dict[str, Any] = None):
        error_details = details or {}
        if violation_type:
            error_details['violation_type'] = violation_type
        
        super().__init__(
            message=message,
            error_code='SECURITY_ERROR',
            details=error_details,
            status_code=403
        )


class ExtractionError(PDFCompressionError):
    """Base exception class for AI extraction service errors."""
    
    def __init__(self, message: str, extraction_type: str = None, details: Dict[str, Any] = None):
        error_details = details or {}
        if extraction_type:
            error_details['extraction_type'] = extraction_type
        
        super().__init__(
            message=message,
            error_code='EXTRACTION_ERROR',
            details=error_details,
            status_code=422
        )


class ExtractionValidationError(ExtractionError):
    """Raised when extraction result validation fails."""
    
    def __init__(self, message: str, validation_field: str = None, details: Dict[str, Any] = None):
        error_details = details or {}
        if validation_field:
            error_details['validation_field'] = validation_field
        
        super().__init__(
            message=message,
            extraction_type='validation',
            details=error_details
        )
        self.error_code = 'EXTRACTION_VALIDATION_ERROR'


class ExportFormatError(PDFCompressionError):
    """Raised when export format is invalid or export fails."""
    
    def __init__(self, message: str, format_type: str = None, details: Dict[str, Any] = None):
        error_details = details or {}
        if format_type:
            error_details['format_type'] = format_type
        
        super().__init__(
            message=message,
            error_code='EXPORT_FORMAT_ERROR',
            details=error_details,
            status_code=422
        )