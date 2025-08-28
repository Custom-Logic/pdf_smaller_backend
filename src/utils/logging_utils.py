"""
Comprehensive logging utilities with structured logging, security event tracking,
and sensitive information filtering.
"""
import logging
import logging.handlers
import os
import json
import re
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from functools import wraps


# Sensitive data patterns to filter from logs
SENSITIVE_PATTERNS = [
    r'Bearer\s+([A-Za-z0-9\._-]+)',  # JWT Bearer tokens - must come first
    r'authorization["\']?\s*[:]\s*Bearer\s+([A-Za-z0-9\._-]+)',  # Authorization: Bearer pattern
    r'password["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
    r'token["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
    r'secret["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
    r'key["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
    r'api_key["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
    r'access_token["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
    r'refresh_token["\']?\s*[:=]\s*["\']?([^"\'}\s,]+)',
    # Credit card patterns
    r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
    # Email patterns (partial masking)
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
    # Phone number patterns
    r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
]


class SensitiveDataFilter(logging.Filter):
    """Filter to remove or mask sensitive information from log records."""
    
    def __init__(self):
        super().__init__()
        self.patterns = [re.compile(pattern, re.IGNORECASE) for pattern in SENSITIVE_PATTERNS]
    
    def filter(self, record):
        """Filter sensitive data from log record."""
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            record.msg = self._sanitize_message(record.msg)
        
        if hasattr(record, 'args') and record.args:
            record.args = tuple(
                self._sanitize_message(str(arg)) if isinstance(arg, str) else arg
                for arg in record.args
            )
        
        return True
    
    def _sanitize_message(self, message: str) -> str:
        """Sanitize a message by masking sensitive information."""
        sanitized = message
        
        for pattern in self.patterns:
            pattern_str = pattern.pattern.lower()
            
            if any(keyword in pattern_str for keyword in ['password', 'token', 'secret', 'key', 'authorization', 'bearer']):
                # Completely mask authentication-related data
                def mask_auth_data(match):
                    full_match = match.group()
                    if 'bearer' in pattern_str:
                        # For Bearer tokens, replace the entire token part
                        return "Bearer ***MASKED***"
                    elif '=' in full_match:
                        key_part = full_match.split('=')[0]
                        return f"{key_part}=***MASKED***"
                    elif ':' in full_match:
                        key_part = full_match.split(':')[0]
                        return f"{key_part}: ***MASKED***"
                    else:
                        return "***MASKED***"
                
                sanitized = pattern.sub(mask_auth_data, sanitized)
                
            elif '@' in pattern.pattern and '[A-Za-z0-9._%+-]+@' in pattern.pattern:
                # Partially mask email addresses
                def mask_email(match):
                    email = match.group()
                    if '@' in email:
                        local, domain = email.split('@', 1)
                        masked_local = local[:2] + '***' if len(local) > 2 else '***'
                        return f"{masked_local}@{domain}"
                    return email
                
                sanitized = pattern.sub(mask_email, sanitized)
                
            elif r'\d{4}[-\s]?\d{4}' in pattern.pattern:
                # Mask credit card numbers
                sanitized = pattern.sub(lambda m: f"****-****-****-{m.group()[-4:]}", sanitized)
            else:
                # Generic masking for other sensitive data
                sanitized = pattern.sub("***MASKED***", sanitized)
        
        return sanitized


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging."""
    
    def format(self, record):
        """Format log record as structured JSON."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception information if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add custom fields from record
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 
                          'filename', 'module', 'lineno', 'funcName', 'created', 
                          'msecs', 'relativeCreated', 'thread', 'threadName', 
                          'processName', 'process', 'exc_info', 'exc_text', 'stack_info']:
                log_entry[key] = value
        
        return json.dumps(log_entry, default=str)


def setup_logging(log_level: str = 'INFO', log_file: str = None, structured: bool = False) -> None:
    """
    Set up comprehensive application logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional log file path
        structured: Whether to use structured JSON logging
    """
    # Convert string level to logging constant
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    # Create formatter
    if structured:
        formatter = StructuredFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Create sensitive data filter
    sensitive_filter = SensitiveDataFilter()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(sensitive_filter)
    root_logger.addHandler(console_handler)
    
    # File handler (if log_file is specified)
    if log_file:
        try:
            # Ensure log directory exists
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, exist_ok=True)
            
            # Create rotating file handler
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5
            )
            file_handler.setLevel(numeric_level)
            file_handler.setFormatter(formatter)
            file_handler.addFilter(sensitive_filter)
            root_logger.addHandler(file_handler)
            
        except (OSError, IOError) as e:
            # If file logging fails, log to console
            logging.warning(f"Could not set up file logging: {str(e)}")
    
    # Set specific logger levels
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    logging.info(f"Logging configured with level: {log_level}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_request_info(request, user_id: int = None) -> None:
    """
    Log request information for debugging and monitoring.
    
    Args:
        request: Flask request object
        user_id: Optional user ID for the request
    """
    logger = get_logger('request_logger')
    
    log_data = {
        'method': request.method,
        'path': request.path,
        'remote_addr': request.remote_addr,
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'content_length': request.content_length or 0
    }
    
    if user_id:
        log_data['user_id'] = user_id
    
    logger.info(f"Request: {log_data}")


def log_error_with_context(error: Exception, context: dict = None) -> None:
    """
    Log an error with additional context information.
    
    Args:
        error: Exception to log
        context: Optional context dictionary
    """
    logger = get_logger('error_logger')
    
    error_info = {
        'error_type': type(error).__name__,
        'error_message': str(error),
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if context:
        error_info['context'] = context
    
    logger.error(f"Error occurred: {error_info}", exc_info=True)


def log_security_event(event_type: str, details: dict = None, user_id: int = None) -> None:
    """
    Log security-related events for monitoring and alerting.
    
    Args:
        event_type: Type of security event
        details: Optional event details
        user_id: Optional user ID associated with the event
    """
    logger = get_logger('security_logger')
    
    event_info = {
        'event_type': event_type,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if user_id:
        event_info['user_id'] = user_id
    
    if details:
        event_info['details'] = details
    
    logger.warning(f"Security event: {event_info}")


def log_performance_metric(operation: str, duration: float, details: dict = None) -> None:
    """
    Log performance metrics for monitoring.
    
    Args:
        operation: Name of the operation
        duration: Duration in seconds
        details: Optional additional details
    """
    logger = get_logger('performance_logger')
    
    metric_info = {
        'operation': operation,
        'duration_seconds': round(duration, 3),
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if details:
        metric_info['details'] = details
    
    logger.info(f"Performance metric: {metric_info}")


def log_business_event(event_type: str, user_id: Optional[int] = None, 
                      details: Optional[Dict[str, Any]] = None) -> None:
    """
    Log business events for analytics and monitoring.
    
    Args:
        event_type: Type of business event (e.g., 'user_registration', 'file_compressed')
        user_id: Optional user ID associated with the event
        details: Optional event details
    """
    logger = get_logger('business_logger')
    
    event_info = {
        'event_type': event_type,
        'timestamp': datetime.utcnow().isoformat(),
        'user_id': user_id
    }
    
    if details:
        event_info.update(details)
    
    logger.info("Business event", extra=event_info)


def log_api_call(method: str, endpoint: str, user_id: Optional[int] = None,
                status_code: Optional[int] = None, duration: Optional[float] = None,
                request_size: Optional[int] = None, response_size: Optional[int] = None) -> None:
    """
    Log API call information for monitoring and analytics.
    
    Args:
        method: HTTP method
        endpoint: API endpoint
        user_id: Optional user ID
        status_code: HTTP status code
        duration: Request duration in seconds
        request_size: Request size in bytes
        response_size: Response size in bytes
    """
    logger = get_logger('api_logger')
    
    api_info = {
        'method': method,
        'endpoint': endpoint,
        'user_id': user_id,
        'status_code': status_code,
        'duration_seconds': round(duration, 3) if duration else None,
        'request_size_bytes': request_size,
        'response_size_bytes': response_size,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    # Remove None values
    api_info = {k: v for k, v in api_info.items() if v is not None}
    
    logger.info("API call", extra=api_info)


def log_health_check(service: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
    """
    Log health check results for monitoring.
    
    Args:
        service: Name of the service being checked
        status: Health status ('healthy', 'unhealthy', 'degraded')
        details: Optional health check details
    """
    logger = get_logger('health_logger')
    
    health_info = {
        'service': service,
        'status': status,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if details:
        health_info['details'] = details
    
    log_level = logging.INFO if status == 'healthy' else logging.WARNING
    logger.log(log_level, "Health check", extra=health_info)


def log_audit_event(action: str, user_id: Optional[int] = None, resource_type: Optional[str] = None,
                   resource_id: Optional[str] = None, details: Optional[Dict[str, Any]] = None) -> None:
    """
    Log audit events for compliance and security monitoring.
    
    Args:
        action: Action performed (e.g., 'create', 'update', 'delete', 'access')
        user_id: Optional user ID who performed the action
        resource_type: Optional type of resource affected
        resource_id: Optional ID of the resource affected
        details: Optional additional audit details
    """
    logger = get_logger('audit_logger')
    
    audit_info = {
        'action': action,
        'user_id': user_id,
        'resource_type': resource_type,
        'resource_id': resource_id,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if details:
        audit_info['details'] = details
    
    logger.info("Audit event", extra=audit_info)


def performance_monitor(operation_name: str = None):
    """
    Decorator to automatically log performance metrics for functions.
    
    Args:
        operation_name: Optional custom operation name (defaults to function name)
    
    Returns:
        Decorated function
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            operation = operation_name or f"{func.__module__}.{func.__name__}"
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                log_performance_metric(
                    operation=operation,
                    duration=duration,
                    details={'status': 'success'}
                )
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                log_performance_metric(
                    operation=operation,
                    duration=duration,
                    details={
                        'status': 'error',
                        'error_type': type(e).__name__,
                        'error_message': str(e)
                    }
                )
                
                raise
        
        return wrapper
    return decorator


def setup_specialized_loggers() -> None:
    """
    Set up specialized loggers for different types of events.
    """
    # Security logger - higher level, separate file
    security_logger = logging.getLogger('security_logger')
    security_logger.setLevel(logging.WARNING)
    
    # Performance logger - for metrics
    performance_logger = logging.getLogger('performance_logger')
    performance_logger.setLevel(logging.INFO)
    
    # Business logger - for business events
    business_logger = logging.getLogger('business_logger')
    business_logger.setLevel(logging.INFO)
    
    # API logger - for API call tracking
    api_logger = logging.getLogger('api_logger')
    api_logger.setLevel(logging.INFO)
    
    # Health logger - for health checks
    health_logger = logging.getLogger('health_logger')
    health_logger.setLevel(logging.INFO)
    
    # Audit logger - for compliance
    audit_logger = logging.getLogger('audit_logger')
    audit_logger.setLevel(logging.INFO)


def get_log_stats() -> Dict[str, Any]:
    """
    Get logging statistics for monitoring.
    
    Returns:
        Dictionary with logging statistics
    """
    root_logger = logging.getLogger()
    
    stats = {
        'root_level': root_logger.level,
        'handlers_count': len(root_logger.handlers),
        'handlers': []
    }
    
    for handler in root_logger.handlers:
        handler_info = {
            'type': type(handler).__name__,
            'level': handler.level,
            'formatter': type(handler.formatter).__name__ if handler.formatter else None
        }
        
        if hasattr(handler, 'baseFilename'):
            handler_info['file'] = handler.baseFilename
        
        stats['handlers'].append(handler_info)
    
    return stats


def sanitize_for_logging(data: Any) -> Any:
    """
    Sanitize data for safe logging by removing sensitive information.
    
    Args:
        data: Data to sanitize (can be dict, list, string, etc.)
    
    Returns:
        Sanitized data
    """
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            if any(sensitive in key.lower() for sensitive in ['password', 'token', 'secret', 'key']):
                sanitized[key] = '***MASKED***'
            else:
                sanitized[key] = sanitize_for_logging(value)
        return sanitized
    
    elif isinstance(data, list):
        return [sanitize_for_logging(item) for item in data]
    
    elif isinstance(data, str):
        # Apply sensitive data filter
        filter_instance = SensitiveDataFilter()
        return filter_instance._sanitize_message(data)
    
    else:
        return data