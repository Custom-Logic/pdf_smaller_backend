"""Request validation utilities"""
from flask import Request
from typing import Dict, Any, List, Optional, Union
import logging
import re
import os
import magic
from functools import wraps

logger = logging.getLogger(__name__)


def validate_json_request(request: Request) -> bool:
    """Validate that request contains valid JSON data"""
    try:
        if not request.is_json:
            return False
        
        data = request.get_json()
        return data is not None
        
    except Exception as e:
        logger.warning(f"JSON validation failed: {str(e)}")
        return False


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> bool:
    """Validate that all required fields are present in data"""
    if not isinstance(data, dict):
        return False
    
    for field in required_fields:
        if field not in data or data[field] is None:
            return False
    
    return True


def validate_email(email: str) -> bool:
    """Validate email format"""
    import re
    
    if not email or not isinstance(email, str):
        return False
    
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(email_pattern, email.strip()) is not None


def validate_password_strength(password: str) -> Dict[str, Any]:
    """Validate password strength and return detailed feedback"""
    import re
    
    if not password or not isinstance(password, str):
        return {
            'valid': False,
            'errors': ['Password is required']
        }
    
    errors = []
    
    # Check length
    if len(password) < 8:
        errors.append('Password must be at least 8 characters long')
    
    # Check for uppercase letter
    if not re.search(r'[A-Z]', password):
        errors.append('Password must contain at least one uppercase letter')
    
    # Check for lowercase letter
    if not re.search(r'[a-z]', password):
        errors.append('Password must contain at least one lowercase letter')
    
    # Check for digit
    if not re.search(r'\d', password):
        errors.append('Password must contain at least one digit')
    
    return {
        'valid': len(errors) == 0,
        'errors': errors
    }


def validate_file_size(file_size: int, max_size_mb: int) -> bool:
    """Validate file size against maximum allowed size"""
    if file_size <= 0:
        return False
    
    max_size_bytes = max_size_mb * 1024 * 1024
    return file_size <= max_size_bytes


def validate_file_extension(filename: str, allowed_extensions: set) -> bool:
    """Validate file extension against allowed extensions"""
    if not filename or not isinstance(filename, str):
        return False
    
    if '.' not in filename:
        return False
    
    extension = filename.rsplit('.', 1)[1].lower()
    return extension in allowed_extensions


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and other issues"""
    import re
    import os
    
    if not filename:
        return 'unnamed_file'
    
    # Get just the filename, no path
    filename = os.path.basename(filename)
    
    # Remove or replace dangerous characters
    filename = re.sub(r'[^\w\-_\.]', '_', filename)
    
    # Ensure it's not empty after sanitization
    if not filename or filename == '.':
        return 'unnamed_file'
    
    # Limit length
    if len(filename) > 255:
        name, ext = os.path.splitext(filename)
        filename = name[:250] + ext
    
    return filename


def validate_plan_id(plan_id: Any) -> bool:
    """Validate plan ID is a positive integer"""
    try:
        plan_id = int(plan_id)
        return plan_id > 0
    except (ValueError, TypeError):
        return False


def validate_billing_cycle(billing_cycle: str) -> bool:
    """Validate billing cycle value"""
    if not billing_cycle or not isinstance(billing_cycle, str):
        return False
    
    return billing_cycle.lower() in ['monthly', 'yearly']


def validate_compression_level(level: str) -> bool:
    """Validate compression level value"""
    if not level or not isinstance(level, str):
        return False
    
    valid_levels = ['low', 'medium', 'high', 'maximum']
    return level.lower() in valid_levels


def validate_request_payload(required_fields: List[str] = None, 
                           optional_fields: List[str] = None,
                           max_payload_size: int = 1024 * 1024):  # 1MB default
    """
    Decorator for comprehensive request payload validation
    
    Args:
        required_fields: List of required field names
        optional_fields: List of optional field names
        max_payload_size: Maximum payload size in bytes
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            from flask import request, jsonify
            
            # Check content length
            if request.content_length and request.content_length > max_payload_size:
                return jsonify({
                    'error': {
                        'code': 'PAYLOAD_TOO_LARGE',
                        'message': f'Request payload too large. Maximum size: {max_payload_size} bytes'
                    }
                }), 413
            
            # Validate JSON for JSON requests
            if request.is_json:
                try:
                    data = request.get_json()
                    if data is None:
                        return jsonify({
                            'error': {
                                'code': 'INVALID_JSON',
                                'message': 'Invalid JSON payload'
                            }
                        }), 400
                    
                    # Validate required fields
                    if required_fields:
                        missing_fields = [field for field in required_fields if field not in data]
                        if missing_fields:
                            return jsonify({
                                'error': {
                                    'code': 'MISSING_REQUIRED_FIELDS',
                                    'message': f'Missing required fields: {", ".join(missing_fields)}'
                                }
                            }), 400
                    
                    # Validate field types and values
                    validation_errors = validate_field_types(data, required_fields or [], optional_fields or [])
                    if validation_errors:
                        return jsonify({
                            'error': {
                                'code': 'VALIDATION_ERROR',
                                'message': 'Field validation failed',
                                'details': validation_errors
                            }
                        }), 400
                        
                except Exception as e:
                    logger.error(f"Request validation error: {str(e)}")
                    return jsonify({
                        'error': {
                            'code': 'VALIDATION_ERROR',
                            'message': 'Request validation failed'
                        }
                    }), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def validate_field_types(data: Dict[str, Any], required_fields: List[str], optional_fields: List[str]) -> List[Dict[str, str]]:
    """Validate field types and values"""
    errors = []
    
    # Define field type expectations
    field_validators = {
        'email': lambda x: validate_email(x),
        'password': lambda x: validate_password_strength(x)['valid'],
        'name': lambda x: isinstance(x, str) and 1 <= len(x.strip()) <= 100,
        'plan_id': lambda x: validate_plan_id(x),
        'billing_cycle': lambda x: validate_billing_cycle(x),
        'compression_level': lambda x: validate_compression_level(x),
        'file_count': lambda x: isinstance(x, int) and x > 0,
        'settings': lambda x: isinstance(x, dict)
    }
    
    all_fields = required_fields + optional_fields
    
    for field in all_fields:
        if field in data:
            value = data[field]
            
            # Check for null/empty values in required fields
            if field in required_fields and (value is None or value == ''):
                errors.append({
                    'field': field,
                    'message': f'{field} is required and cannot be empty'
                })
                continue
            
            # Apply specific field validation
            if field in field_validators:
                if not field_validators[field](value):
                    errors.append({
                        'field': field,
                        'message': f'Invalid {field} format or value'
                    })
            
            # Generic string length validation
            elif isinstance(value, str):
                if len(value) > 1000:  # Prevent extremely long strings
                    errors.append({
                        'field': field,
                        'message': f'{field} is too long (maximum 1000 characters)'
                    })
    
    return errors


def validate_file_content(file_data: bytes, filename: str) -> Dict[str, Any]:
    """
    Comprehensive file content validation and security scanning
    
    Args:
        file_data: File content as bytes
        filename: Original filename
        
    Returns:
        Dict with validation results
    """
    result = {
        'valid': True,
        'errors': [],
        'warnings': [],
        'file_type': None,
        'size': len(file_data)
    }
    
    try:
        # Check file size
        if len(file_data) == 0:
            result['valid'] = False
            result['errors'].append('File is empty')
            return result
        
        if len(file_data) > 100 * 1024 * 1024:  # 100MB
            result['valid'] = False
            result['errors'].append('File too large (maximum 100MB)')
            return result
        
        # Detect actual file type using magic numbers
        try:
            import magic
            file_type = magic.from_buffer(file_data, mime=True)
            result['file_type'] = file_type
            
            # Validate PDF files
            if file_type != 'application/pdf':
                result['valid'] = False
                result['errors'].append(f'Invalid file type: {file_type}. Only PDF files are allowed.')
                return result
                
        except ImportError:
            # Fallback to basic header check if python-magic is not available
            logger.warning("python-magic not available, using basic file validation")
            if not file_data.startswith(b'%PDF-'):
                result['valid'] = False
                result['errors'].append('File does not appear to be a valid PDF')
                return result
        
        # Check for malicious content patterns
        malicious_patterns = [
            b'<script',
            b'javascript:',
            b'vbscript:',
            b'onload=',
            b'onerror=',
            b'eval(',
            b'document.cookie',
            b'window.location'
        ]
        
        file_data_lower = file_data.lower()
        for pattern in malicious_patterns:
            if pattern in file_data_lower:
                result['warnings'].append(f'Potentially suspicious content detected: {pattern.decode("utf-8", errors="ignore")}')
        
        # PDF-specific security checks
        pdf_security_issues = check_pdf_security(file_data)
        if pdf_security_issues:
            result['warnings'].extend(pdf_security_issues)
        
        # Check for embedded files or suspicious structures
        if b'/EmbeddedFile' in file_data or b'/Launch' in file_data:
            result['warnings'].append('PDF contains embedded files or launch actions')
        
        if b'/JavaScript' in file_data or b'/JS' in file_data:
            result['warnings'].append('PDF contains JavaScript code')
            
    except Exception as e:
        logger.error(f"File validation error: {str(e)}")
        result['valid'] = False
        result['errors'].append('File validation failed due to internal error')
    
    return result


def check_pdf_security(file_data: bytes) -> List[str]:
    """Check PDF for security issues"""
    warnings = []
    
    try:
        # Check for password protection
        if b'/Encrypt' in file_data:
            warnings.append('PDF is password protected or encrypted')
        
        # Check for forms
        if b'/AcroForm' in file_data or b'/XFA' in file_data:
            warnings.append('PDF contains interactive forms')
        
        # Check for annotations
        if b'/Annot' in file_data:
            warnings.append('PDF contains annotations')
        
        # Check for suspicious actions
        suspicious_actions = [b'/URI', b'/Launch', b'/SubmitForm', b'/ImportData']
        for action in suspicious_actions:
            if action in file_data:
                warnings.append(f'PDF contains potentially unsafe action: {action.decode("utf-8", errors="ignore")}')
        
    except Exception as e:
        logger.error(f"PDF security check error: {str(e)}")
        warnings.append('Could not complete security scan')
    
    return warnings


def sanitize_input(value: Any, max_length: int = 1000) -> str:
    """
    Sanitize input value to prevent injection attacks
    
    Args:
        value: Input value to sanitize
        max_length: Maximum allowed length
        
    Returns:
        Sanitized string value
    """
    if value is None:
        return ''
    
    # Convert to string
    str_value = str(value)
    
    # Limit length
    if len(str_value) > max_length:
        str_value = str_value[:max_length]
    
    # Remove null bytes and control characters
    str_value = ''.join(char for char in str_value if ord(char) >= 32 or char in '\t\n\r')
    
    # Basic HTML/script tag removal
    str_value = re.sub(r'<[^>]*>', '', str_value)
    
    # Remove SQL injection patterns
    sql_patterns = [
        r'(\b(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER|EXEC|UNION)\b)',
        r'(--|#|/\*|\*/)',
        r'(\bOR\b.*=.*\bOR\b)',
        r'(\bAND\b.*=.*\bAND\b)'
    ]
    
    for pattern in sql_patterns:
        str_value = re.sub(pattern, '', str_value, flags=re.IGNORECASE)
    
    return str_value.strip()


def validate_ip_address(ip: str) -> bool:
    """Validate IP address format"""
    import ipaddress
    
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def validate_user_agent(user_agent: str) -> Dict[str, Any]:
    """Validate and analyze user agent string"""
    result = {
        'valid': True,
        'suspicious': False,
        'bot': False,
        'warnings': []
    }
    
    if not user_agent or len(user_agent) > 500:
        result['valid'] = False
        result['warnings'].append('Invalid or missing user agent')
        return result
    
    # Check for suspicious patterns
    suspicious_patterns = [
        r'(curl|wget|python|java|perl|ruby)',
        r'(bot|crawler|spider|scraper)',
        r'(scan|test|hack|exploit)'
    ]
    
    user_agent_lower = user_agent.lower()
    
    for pattern in suspicious_patterns:
        if re.search(pattern, user_agent_lower):
            if 'bot' in pattern or 'crawler' in pattern or 'spider' in pattern:
                result['bot'] = True
            else:
                result['suspicious'] = True
            result['warnings'].append(f'Suspicious user agent pattern: {pattern}')
    
    return result