"""Enhanced security utilities for file validation and threat detection"""
import os
import hashlib
import time
import logging
from flask import request, g
from typing import Dict, Any, List, Optional, Set
from datetime import datetime, timedelta
from .validation import validate_file_content, sanitize_input

logger = logging.getLogger(__name__)

# Global threat tracking
THREAT_TRACKING = {
    'suspicious_ips': {},
    'blocked_ips': set(),
    'malicious_files': set()
}


def validate_file(file) -> Optional[str]:
    """Enhanced file validation with security scanning"""
    if not file or file.filename == '':
        return 'No file selected'
    
    # Basic filename validation
    allowed_extensions = {'pdf'}
    if '.' not in file.filename or \
       file.filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
        return 'Invalid file type. Only PDF files are allowed.'
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_length = file.tell()
    file.seek(0)  # Reset file pointer
    
    if file_length > 100 * 1024 * 1024:  # 100MB
        return 'File too large. Maximum size is 100MB.'
    
    if file_length == 0:
        return 'File is empty'
    
    # Read file content for security scanning
    try:
        file_data = file.read()
        file.seek(0)  # Reset file pointer
        
        # Perform comprehensive content validation
        validation_result = validate_file_content(file_data, file.filename)
        
        if not validation_result['valid']:
            logger.warning(f"File validation failed: {validation_result['errors']}")
            return f"File validation failed: {'; '.join(validation_result['errors'])}"
        
        # Log warnings but don't block
        if validation_result['warnings']:
            logger.warning(f"File security warnings for {file.filename}: {validation_result['warnings']}")
            track_suspicious_activity('suspicious_file', {
                'filename': file.filename,
                'warnings': validation_result['warnings'],
                'ip': get_client_ip()
            })
        
        # Check file hash against known malicious files
        file_hash = hashlib.sha256(file_data).hexdigest()
        if file_hash in THREAT_TRACKING['malicious_files']:
            logger.error(f"Blocked known malicious file: {file_hash}")
            return 'File blocked due to security concerns'
        
    except Exception as e:
        logger.error(f"File security scan error: {str(e)}")
        return 'File validation failed due to security scan error'
    
    return None


def validate_origin(allowed_origins: List[str]) -> Optional[str]:
    """Enhanced origin validation with security logging"""
    origin = request.headers.get('Origin')
    referer = request.headers.get('Referer')
    
    if origin and origin not in allowed_origins:
        track_suspicious_activity('invalid_origin', {
            'origin': origin,
            'referer': referer,
            'ip': get_client_ip()
        })
        return 'Origin not allowed'
    
    return None


def validate_request_headers() -> Dict[str, Any]:
    """Validate and analyze request headers for security threats"""
    result = {
        'valid': True,
        'warnings': [],
        'suspicious': False
    }
    
    headers = dict(request.headers)
    client_ip = get_client_ip()
    
    # Check for missing or suspicious User-Agent
    user_agent = headers.get('User-Agent', '')
    if not user_agent:
        result['warnings'].append('Missing User-Agent header')
        result['suspicious'] = True
    elif len(user_agent) > 500:
        result['warnings'].append('Unusually long User-Agent header')
        result['suspicious'] = True
    
    # Check for suspicious headers
    suspicious_headers = [
        'X-Forwarded-For',
        'X-Real-IP',
        'X-Originating-IP',
        'X-Remote-IP'
    ]
    
    for header in suspicious_headers:
        if header in headers:
            result['warnings'].append(f'Proxy header detected: {header}')
    
    # Check for automated tools
    automated_patterns = ['curl', 'wget', 'python', 'java', 'bot', 'crawler']
    for pattern in automated_patterns:
        if pattern.lower() in user_agent.lower():
            result['warnings'].append(f'Automated tool detected: {pattern}')
            result['suspicious'] = True
    
    # Rate limiting check
    if is_rate_limited(client_ip):
        result['valid'] = False
        result['warnings'].append('Rate limit exceeded')
    
    # Check if IP is blocked
    if client_ip in THREAT_TRACKING['blocked_ips']:
        result['valid'] = False
        result['warnings'].append('IP address is blocked')
    
    if result['suspicious'] or not result['valid']:
        track_suspicious_activity('suspicious_headers', {
            'ip': client_ip,
            'user_agent': user_agent,
            'warnings': result['warnings']
        })
    
    return result


def get_client_ip() -> str:
    """Get the real client IP address"""
    # Check for forwarded headers (in order of preference)
    forwarded_headers = [
        'X-Forwarded-For',
        'X-Real-IP',
        'X-Forwarded',
        'X-Cluster-Client-IP'
    ]
    
    for header in forwarded_headers:
        if header in request.headers:
            # Take the first IP if there are multiple
            ip = request.headers[header].split(',')[0].strip()
            if ip:
                return ip
    
    return request.remote_addr or 'unknown'


def track_suspicious_activity(activity_type: str, details: Dict[str, Any]) -> None:
    """Track suspicious activities for security monitoring"""
    timestamp = datetime.utcnow()
    client_ip = details.get('ip', get_client_ip())
    
    # Log the activity
    logger.warning(f"Suspicious activity detected - Type: {activity_type}, IP: {client_ip}, Details: {details}")
    
    # Track IP-based suspicious activity
    if client_ip not in THREAT_TRACKING['suspicious_ips']:
        THREAT_TRACKING['suspicious_ips'][client_ip] = []
    
    THREAT_TRACKING['suspicious_ips'][client_ip].append({
        'type': activity_type,
        'timestamp': timestamp,
        'details': details
    })
    
    # Auto-block IPs with too many suspicious activities
    recent_activities = [
        activity for activity in THREAT_TRACKING['suspicious_ips'][client_ip]
        if activity['timestamp'] > timestamp - timedelta(hours=1)
    ]
    
    if len(recent_activities) >= 10:  # 10 suspicious activities in 1 hour
        THREAT_TRACKING['blocked_ips'].add(client_ip)
        logger.error(f"Auto-blocked IP due to suspicious activity: {client_ip}")


def is_rate_limited(client_ip: str, max_requests: int = 100, window_minutes: int = 60) -> bool:
    """Simple rate limiting check"""
    # This is a basic implementation - in production, use Redis or similar
    current_time = datetime.utcnow()
    window_start = current_time - timedelta(minutes=window_minutes)
    
    if client_ip in THREAT_TRACKING['suspicious_ips']:
        recent_requests = [
            activity for activity in THREAT_TRACKING['suspicious_ips'][client_ip]
            if activity['timestamp'] > window_start
        ]
        return len(recent_requests) > max_requests
    
    return False


def sanitize_request_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize all request data to prevent injection attacks"""
    sanitized = {}
    
    for key, value in data.items():
        # Sanitize key
        clean_key = sanitize_input(key, max_length=100)
        
        # Sanitize value based on type
        if isinstance(value, str):
            clean_value = sanitize_input(value)
        elif isinstance(value, dict):
            clean_value = sanitize_request_data(value)  # Recursive sanitization
        elif isinstance(value, list):
            clean_value = [sanitize_input(str(item)) if isinstance(item, str) else item for item in value]
        else:
            clean_value = value
        
        sanitized[clean_key] = clean_value
    
    return sanitized


def check_file_reputation(file_hash: str) -> Dict[str, Any]:
    """Check file reputation against known threat databases"""
    result = {
        'safe': True,
        'reputation': 'unknown',
        'threats': []
    }
    
    # Check against local blacklist
    if file_hash in THREAT_TRACKING['malicious_files']:
        result['safe'] = False
        result['reputation'] = 'malicious'
        result['threats'].append('Known malicious file')
    
    # In a production environment, you might integrate with:
    # - VirusTotal API
    # - Local antivirus scanning
    # - Custom threat intelligence feeds
    
    return result


def generate_security_token() -> str:
    """Generate a secure token for CSRF protection"""
    import secrets
    return secrets.token_urlsafe(32)


def validate_csrf_token(token: str, expected_token: str) -> bool:
    """Validate CSRF token"""
    if not token or not expected_token:
        return False
    
    # Use constant-time comparison to prevent timing attacks
    import hmac
    return hmac.compare_digest(token, expected_token)


def log_security_event(event_type: str, details: Dict[str, Any], severity: str = 'INFO') -> None:
    """Log security events with structured format"""
    security_log = {
        'timestamp': datetime.utcnow().isoformat(),
        'event_type': event_type,
        'severity': severity,
        'client_ip': get_client_ip(),
        'user_agent': request.headers.get('User-Agent', ''),
        'endpoint': request.endpoint,
        'method': request.method,
        'details': details
    }
    
    if severity == 'ERROR':
        logger.error(f"Security Event: {security_log}")
    elif severity == 'WARNING':
        logger.warning(f"Security Event: {security_log}")
    else:
        logger.info(f"Security Event: {security_log}")


def get_security_headers() -> Dict[str, str]:
    """Get security headers to add to responses"""
    return {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'Content-Security-Policy': "default-src 'self'",
        'Referrer-Policy': 'strict-origin-when-cross-origin'
    }