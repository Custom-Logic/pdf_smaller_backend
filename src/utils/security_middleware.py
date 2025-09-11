"""Security middleware for request logging and threat detection"""
import logging
import time
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from flask import request, g, current_app, jsonify
from functools import wraps
from .security_utils import (
    get_client_ip, 
    validate_request_headers, 
    track_suspicious_activity,
    log_security_event,
    get_security_headers,
    THREAT_TRACKING
)

logger = logging.getLogger(__name__)


class SecurityMiddleware:
    """Comprehensive security middleware for Flask applications"""
    
    def __init__(self, app=None):
        self.app = app
        self.suspicious_patterns = []
        self.blocked_user_agents = set()
        self.allowed_origins = []
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize security middleware with Flask app"""
        self.app = app
        
        # Load configuration
        self.allowed_origins = ['https://pdfsmaller.site', 'https://www.pdfsmaller.site']
        self.load_security_config()
        
        # Register middleware hooks
        app.before_request(self.before_request)
        app.after_request(self.after_request)
        app.teardown_request(self.teardown_request)
        
        # Register error handlers
        self.register_error_handlers()
    
    def load_security_config(self):
        """Load security configuration"""
        # Suspicious user agent patterns
        self.suspicious_patterns = [
            r'(sqlmap|nikto|nmap|masscan|zap|burp)',
            r'(python-requests|curl|wget|httpie)',
            r'(bot|crawler|spider|scraper)',
            r'(scan|test|hack|exploit|inject)'
        ]
        
        # Blocked user agents (exact matches)
        self.blocked_user_agents = {
            'sqlmap/1.0',
            'nikto',
            'nmap',
            'masscan',
            'zaproxy'
        }
    
    def before_request(self):
        """Security checks before processing each request"""
        # Record request start time
        g.request_start_time = time.time()
        g.request_id = self.generate_request_id()
        
        # Get client information
        client_ip = get_client_ip()
        user_agent = request.headers.get('User-Agent', '')
        
        # Store client info in g for later use
        g.client_ip = client_ip
        g.user_agent = user_agent
        
        # Check if IP is blocked
        if client_ip in THREAT_TRACKING['blocked_ips']:
            self.log_blocked_request('blocked_ip', {'ip': client_ip})
            return self.create_blocked_response('IP address is blocked')
        
        # Validate request headers
        header_validation = validate_request_headers()
        if not header_validation['valid']:
            self.log_blocked_request('invalid_headers', {
                'ip': client_ip,
                'warnings': header_validation['warnings']
            })
            return self.create_blocked_response('Request blocked due to security policy')
        
        # Check for suspicious user agents
        if self.is_suspicious_user_agent(user_agent):
            track_suspicious_activity('suspicious_user_agent', {
                'ip': client_ip,
                'user_agent': user_agent
            })
        
        # Check for blocked user agents
        if user_agent.lower() in [ua.lower() for ua in self.blocked_user_agents]:
            self.log_blocked_request('blocked_user_agent', {
                'ip': client_ip,
                'user_agent': user_agent
            })
            return self.create_blocked_response('User agent not allowed')
        
        # Validate request size
        if request.content_length and request.content_length > current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024):
            self.log_blocked_request('oversized_request', {
                'ip': client_ip,
                'content_length': request.content_length
            })
            return self.create_blocked_response('Request too large')
        
        # Check for suspicious request patterns
        if self.has_suspicious_patterns():
            track_suspicious_activity('suspicious_request_pattern', {
                'ip': client_ip,
                'path': request.path,
                'method': request.method,
                'args': dict(request.args)
            })
        
        # Log request details
        self.log_request_start()
    
    def after_request(self, response):
        """Security processing after request completion"""
        # Add security headers
        security_headers = get_security_headers()
        for header, value in security_headers.items():
            response.headers[header] = value
        
        # Add request ID header
        if hasattr(g, 'request_id'):
            response.headers['X-Request-ID'] = g.request_id
        
        # Log response details
        self.log_request_completion(response)
        
        # Check for suspicious response patterns
        if response.status_code >= 400:
            self.check_error_patterns(response)
        
        # Add CORS headers
        origin = request.headers.get('Origin')
        if origin in self.allowed_origins:
            response.headers['Access-Control-Allow-Origin'] = origin
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS, PUT, DELETE'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
            response.headers['Access-Control-Allow-Credentials'] = 'true'
        else:
            logger.error(f"CORS HEADER FOR ORIGIN NOT SET: {origin}")
        # Add request ID header
        if hasattr(g, 'request_id'):
            response.headers['X-Request-ID'] = g.request_id
        
        return response

    
    
    def teardown_request(self, exception):
        """Cleanup after request processing"""
        if exception:
            self.log_request_exception(exception)
    
    def generate_request_id(self) -> str:
        """Generate unique request ID"""
        import uuid
        return str(uuid.uuid4())[:8]
    
    def is_suspicious_user_agent(self, user_agent: str) -> bool:
        """Check if user agent matches suspicious patterns"""
        import re
        
        if not user_agent:
            return True
        
        user_agent_lower = user_agent.lower()
        
        for pattern in self.suspicious_patterns:
            if re.search(pattern, user_agent_lower, re.IGNORECASE):
                return True
        
        return False
    
    def has_suspicious_patterns(self) -> bool:
        """Check for suspicious patterns in request"""
        # Check URL path for suspicious patterns
        suspicious_path_patterns = [
            'admin', 'wp-admin', 'phpmyadmin', 'config',
            'backup', 'test', 'debug', 'console',
            '../', '..\\', '%2e%2e', 'etc/passwd',
            'boot.ini', 'web.config'
        ]
        
        path_lower = request.path.lower()
        for pattern in suspicious_path_patterns:
            if pattern in path_lower:
                return True
        
        # Check query parameters for injection attempts
        for key, value in request.args.items():
            value_lower = str(value).lower()
            if any(pattern in value_lower for pattern in [
                'select', 'union', 'insert', 'delete', 'drop',
                'script', 'javascript:', 'vbscript:', 'onload',
                'onerror', 'eval(', 'alert(', 'document.cookie'
            ]):
                return True
        
        return False
    
    def create_blocked_response(self, message: str):
        """Create standardized blocked request response"""
        return jsonify({
            'error': {
                'code': 'REQUEST_BLOCKED',
                'message': message,
                'request_id': getattr(g, 'request_id', 'unknown')
            }
        }), 403
    
    def log_blocked_request(self, reason: str, details: Dict[str, Any]):
        """Log blocked request with details"""
        log_security_event('blocked_request', {
            'reason': reason,
            'details': details,
            'request_id': getattr(g, 'request_id', 'unknown')
        }, 'WARNING')
    
    def log_request_start(self):
        """Log request start details"""
        log_data = {
            'request_id': g.request_id,
            'method': request.method,
            'path': request.path,
            'client_ip': g.client_ip,
            'user_agent': g.user_agent,
            'content_length': request.content_length,
            'referrer': request.headers.get('Referer', ''),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Request started: {json.dumps(log_data)}")
    
    def log_request_completion(self, response):
        """Log request completion details"""
        request_duration = time.time() - getattr(g, 'request_start_time', time.time())
        
        log_data = {
            'request_id': getattr(g, 'request_id', 'unknown'),
            'status_code': response.status_code,
            'response_size': len(response.get_data()),
            'duration_ms': round(request_duration * 1000, 2),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Log level based on status code
        if response.status_code >= 500:
            logger.error(f"Request completed with error: {json.dumps(log_data)}")
        elif response.status_code >= 400:
            logger.warning(f"Request completed with client error: {json.dumps(log_data)}")
        else:
            logger.info(f"Request completed successfully: {json.dumps(log_data)}")
    
    def log_request_exception(self, exception):
        """Log request exception details"""
        log_data = {
            'request_id': getattr(g, 'request_id', 'unknown'),
            'exception_type': type(exception).__name__,
            'exception_message': str(exception),
            'client_ip': getattr(g, 'client_ip', 'unknown'),
            'path': request.path,
            'method': request.method,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        logger.error(f"Request exception: {json.dumps(log_data)}")
        
        # Track as suspicious activity
        track_suspicious_activity('request_exception', log_data)
    
    def check_error_patterns(self, response):
        """Check for suspicious error patterns"""
        # Track repeated 404s from same IP
        if response.status_code == 404:
            self.track_404_pattern()
        
        # Track authentication failures
        elif response.status_code == 401:
            self.track_auth_failure()
        
        # Track rate limit violations
        elif response.status_code == 429:
            self.track_rate_limit_violation()
    
    def track_404_pattern(self):
        """Track 404 patterns for potential scanning"""
        client_ip = getattr(g, 'client_ip', 'unknown')
        
        # Count 404s in the last hour
        current_time = datetime.utcnow()
        hour_ago = current_time - timedelta(hours=1)
        
        if client_ip in THREAT_TRACKING['suspicious_ips']:
            recent_404s = [
                activity for activity in THREAT_TRACKING['suspicious_ips'][client_ip]
                if (activity['type'] == '404_pattern' and 
                    activity['timestamp'] > hour_ago)
            ]
            
            if len(recent_404s) >= 10:  # 10 404s in an hour
                track_suspicious_activity('potential_scanning', {
                    'ip': client_ip,
                    'path': request.path,
                    'recent_404_count': len(recent_404s)
                })
        
        track_suspicious_activity('404_pattern', {
            'ip': client_ip,
            'path': request.path
        })
    

    
    def track_rate_limit_violation(self):
        """Track rate limit violations"""
        track_suspicious_activity('rate_limit_violation', {
            'ip': getattr(g, 'client_ip', 'unknown'),
            'path': request.path,
            'user_agent': getattr(g, 'user_agent', '')
        })
    
    def register_error_handlers(self):
        """Register security-focused error handlers"""
        @self.app.errorhandler(403)
        def handle_forbidden(error):
            log_security_event('access_denied', {
                'path': request.path,
                'method': request.method,
                'client_ip': getattr(g, 'client_ip', 'unknown')
            }, 'WARNING')
            
            return jsonify({
                'error': {
                    'code': 'ACCESS_DENIED',
                    'message': 'Access denied',
                    'request_id': getattr(g, 'request_id', 'unknown')
                }
            }), 403
        
        @self.app.errorhandler(404)
        def handle_not_found(error):
            # Don't log every 404 as it's normal, but track patterns
            return jsonify({
                'error': {
                    'code': 'NOT_FOUND',
                    'message': 'Resource not found',
                    'request_id': getattr(g, 'request_id', 'unknown')
                }
            }), 404
        
        @self.app.errorhandler(500)
        def handle_internal_error(error):
            log_security_event('internal_error', {
                'path': request.path,
                'method': request.method,
                'client_ip': getattr(g, 'client_ip', 'unknown'),
                'error': str(error)
            }, 'ERROR')
            
            return jsonify({
                'error': {
                    'code': 'INTERNAL_ERROR',
                    'message': 'Internal server error',
                    'request_id': getattr(g, 'request_id', 'unknown')
                }
            }), 500


def create_security_middleware(app=None) -> SecurityMiddleware:
    """Factory function to create security middleware"""
    return SecurityMiddleware(app)


def require_https(f):
    """Decorator to require HTTPS for sensitive endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_secure and not current_app.config.get('TESTING'):
            return jsonify({
                'error': {
                    'code': 'HTTPS_REQUIRED',
                    'message': 'HTTPS is required for this endpoint'
                }
            }), 400
        return f(*args, **kwargs)
    return decorated_function


def log_sensitive_action(action: str, details: Dict[str, Any] = None):
    """Decorator to log sensitive actions"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Log before action
            log_security_event('sensitive_action_start', {
                'action': action,
                'details': details or {},
                'function': f.__name__
            }, 'INFO')
            
            try:
                result = f(*args, **kwargs)
                
                # Log successful completion
                log_security_event('sensitive_action_success', {
                    'action': action,
                    'function': f.__name__
                }, 'INFO')
                
                return result
                
            except Exception as e:
                # Log failure
                log_security_event('sensitive_action_failure', {
                    'action': action,
                    'function': f.__name__,
                    'error': str(e)
                }, 'ERROR')
                raise
        
        return decorated_function
    return decorator