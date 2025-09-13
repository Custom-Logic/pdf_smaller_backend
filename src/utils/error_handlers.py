"""
Centralized error handling system for the PDF compression service.

This module provides error handlers, response formatting, and request ID tracking
for consistent error handling throughout the application.
"""

import logging
import traceback
import uuid
from datetime import datetime
from typing import Dict, Any, Tuple
from flask import Flask, request, jsonify, g
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from src.utils.exceptions import (
    PDFCompressionError, ValidationError, AuthenticationError, 
    AuthorizationError, ResourceNotFoundError, RateLimitExceededError,
    FileProcessingError, SubscriptionError, UsageLimitExceededError,
    ExternalServiceError, ConfigurationError, DatabaseError, SecurityError
)
from src.utils.logging_utils import log_error_with_context

logger = logging.getLogger(__name__)


def generate_request_id() -> str:
    """Generate a unique request ID for tracking."""
    return str(uuid.uuid4())


def get_request_id() -> str:
    """Get the current request ID from Flask's g object."""
    if not hasattr(g, 'request_id'):
        g.request_id = generate_request_id()
    return g.request_id


def format_error_response(
    error_code: str,
    message: str,
    details: Dict[str, Any] = None,
    status_code: int = 500,
    request_id: str = None
) -> Tuple[Dict[str, Any], int]:
    """
    Format a consistent error response.
    
    Args:
        error_code: Error code identifier
        message: Human-readable error message
        details: Additional error details
        status_code: HTTP status code
        request_id: Request ID for tracking
    
    Returns:
        Tuple of (response_dict, status_code)
    """
    response = {
        'error': {
            'code': error_code,
            'message': message,
            'details': details or {}
        },
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'request_id': request_id or get_request_id()
    }
    
    return response, status_code


def register_error_handlers(app: Flask) -> None:
    """
    Register all error handlers with the Flask application.
    
    Args:
        app: Flask application instance
    """
    
    @app.before_request
    def before_request():
        """Set up request ID tracking before each request."""
        g.request_id = generate_request_id()
        g.start_time = datetime.utcnow()
    
    @app.errorhandler(PDFCompressionError)
    def handle_pdf_compression_error(error: PDFCompressionError):
        """Handle custom PDF compression errors."""
        log_error_with_context(error, {
            'request_id': get_request_id(),
            'path': request.path,
            'method': request.method,
            'user_agent': request.headers.get('User-Agent'),
            'client_ip': request.remote_addr
        })
        
        response_data = error.to_dict()
        response_data['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        response_data['request_id'] = get_request_id()
        
        return jsonify(response_data), error.status_code
    
    @app.errorhandler(ValidationError)
    def handle_validation_error(error: ValidationError):
        """Handle validation errors with detailed field information."""
        return handle_pdf_compression_error(error)
    
    @app.errorhandler(AuthenticationError)
    def handle_authentication_error(error: AuthenticationError):
        """Handle authentication errors."""
        return handle_pdf_compression_error(error)
    
    @app.errorhandler(AuthorizationError)
    def handle_authorization_error(error: AuthorizationError):
        """Handle authorization errors."""
        return handle_pdf_compression_error(error)
    
    @app.errorhandler(ResourceNotFoundError)
    def handle_not_found_error(error: ResourceNotFoundError):
        """Handle resource not found errors."""
        return handle_pdf_compression_error(error)
    
    @app.errorhandler(RateLimitExceededError)
    def handle_rate_limit_error(error: RateLimitExceededError):
        """Handle rate limit exceeded errors with retry headers."""
        response_data, status_code = handle_pdf_compression_error(error)
        response = jsonify(response_data[0])
        
        # Add rate limit headers
        if 'retry_after' in error.details:
            response.headers['Retry-After'] = str(error.details['retry_after'])
        
        return response, status_code
    
    @app.errorhandler(FileProcessingError)
    def handle_file_processing_error(error: FileProcessingError):
        """Handle file processing errors."""
        return handle_pdf_compression_error(error)
    
    @app.errorhandler(SubscriptionError)
    def handle_subscription_error(error: SubscriptionError):
        """Handle subscription-related errors."""
        return handle_pdf_compression_error(error)
    
    @app.errorhandler(UsageLimitExceededError)
    def handle_usage_limit_error(error: UsageLimitExceededError):
        """Handle usage limit exceeded errors."""
        return handle_pdf_compression_error(error)
    
    @app.errorhandler(ExternalServiceError)
    def handle_external_service_error(error: ExternalServiceError):
        """Handle external service errors."""
        return handle_pdf_compression_error(error)
    
    @app.errorhandler(SecurityError)
    def handle_security_error(error: SecurityError):
        """Handle security violations."""
        # Log security errors with high priority
        logger.critical(f"Security violation detected: {error.message}", extra={
            'request_id': get_request_id(),
            'violation_type': error.details.get('violation_type'),
            'client_ip': request.remote_addr,
            'path': request.path,
            'method': request.method
        })
        
        return handle_pdf_compression_error(error)
    
    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error: SQLAlchemyError):
        """Handle SQLAlchemy database errors."""
        db_error = DatabaseError(
            message="Database operation failed",
            operation=getattr(error, 'statement', 'unknown'),
            details={'original_error': str(error)}
        )
        
        return handle_pdf_compression_error(db_error)
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(error: HTTPException):
        """Handle standard HTTP exceptions."""
        error_code = f"HTTP_{error.code}"
        
        # Map common HTTP errors to more descriptive codes
        error_code_mapping = {
            400: 'BAD_REQUEST',
            401: 'UNAUTHORIZED',
            403: 'FORBIDDEN',
            404: 'NOT_FOUND',
            405: 'METHOD_NOT_ALLOWED',
            413: 'PAYLOAD_TOO_LARGE',
            415: 'UNSUPPORTED_MEDIA_TYPE',
            429: 'TOO_MANY_REQUESTS',
            500: 'INTERNAL_SERVER_ERROR',
            502: 'BAD_GATEWAY',
            503: 'SERVICE_UNAVAILABLE',
            504: 'GATEWAY_TIMEOUT'
        }
        
        error_code = error_code_mapping.get(error.code, error_code)
        
        response, status_code = format_error_response(
            error_code=error_code,
            message=error.description or f"HTTP {error.code} error",
            status_code=error.code
        )
        
        # Log HTTP errors
        log_error_with_context(error, {
            'request_id': get_request_id(),
            'path': request.path,
            'method': request.method,
            'status_code': error.code
        })
        
        return jsonify(response), status_code
    
    @app.errorhandler(Exception)
    def handle_unexpected_error(error: Exception):
        """Handle unexpected errors with sanitized messages."""
        # Log the full error details for debugging
        log_error_with_context(error, {
            'request_id': get_request_id(),
            'path': request.path,
            'method': request.method,
            'traceback': traceback.format_exc()
        })
        
        # Return sanitized error message to client
        response, status_code = format_error_response(
            error_code='INTERNAL_SERVER_ERROR',
            message='An unexpected error occurred. Please try again later.',
            details={'type': type(error).__name__},
            status_code=500
        )
        
        return jsonify(response), status_code
    
    @app.teardown_request
    def log_request_completion(exception):
        """Log request completion and any exceptions."""
        if hasattr(g, 'start_time'):
            duration = (datetime.utcnow() - g.start_time).total_seconds()
            
            log_data = {
                'request_id': get_request_id(),
                'method': request.method,
                'path': request.path,
                'duration_seconds': duration,
                'client_ip': request.remote_addr
            }
            
            if exception:
                log_data['exception'] = str(exception)
                logger.error(f"Request failed: {log_data}")
            else:
                logger.info(f"Request completed: {log_data}")


def create_error_response(
    error_code: str,
    message: str,
    details: Dict[str, Any] = None,
    status_code: int = 500
) -> Tuple[Dict[str, Any], int]:
    """
    Create a standardized error response.
    
    This is a convenience function for creating error responses
    without raising exceptions.
    
    Args:
        error_code: Error code identifier
        message: Human-readable error message
        details: Additional error details
        status_code: HTTP status code
    
    Returns:
        Tuple of (response_dict, status_code)
    """
    return format_error_response(error_code, message, details, status_code)


def validate_and_raise(condition: bool, error_class: type, message: str, **kwargs):
    """
    Validate a condition and raise an exception if it fails.
    
    Args:
        condition: Condition to validate
        error_class: Exception class to raise
        message: Error message
        **kwargs: Additional arguments for the exception
    """
    if not condition:
        raise error_class(message, **kwargs)


def safe_execute(func, *args, error_message: str = None, **kwargs):
    """
    Safely execute a function and convert exceptions to PDFCompressionError.
    
    Args:
        func: Function to execute
        *args: Function arguments
        error_message: Custom error message
        **kwargs: Function keyword arguments
    
    Returns:
        Function result
    
    Raises:
        PDFCompressionError: If function execution fails
    """
    try:
        return func(*args, **kwargs)
    except PDFCompressionError:
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        message = error_message or f"Operation failed: {str(e)}"
        raise PDFCompressionError(
            message=message,
            details={'original_error': str(e), 'error_type': type(e).__name__}
        )