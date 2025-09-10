"""CORS configuration and security utilities"""
from flask_cors import CORS
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class SecureCORS:
    """Secure CORS configuration with enhanced security features"""
    
    def __init__(self, app=None):
        self.app = app
        self.cors = None
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize secure CORS with Flask app"""
        self.app = app
        
        # Get allowed origins from config
        allowed_origins = ["https://wwww.pdfsmaller.site", 'https://pdfsmaller.site']
        
        # Configure CORS with security-focused settings
        cors_config = {
            'origins': allowed_origins,
            'methods': ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
            'allow_headers': [
                'Content-Type',
                'Authorization',
                'X-Requested-With',
                'X-Request-ID'
            ],
            'expose_headers': [
                'X-Request-ID',
                'X-RateLimit-Limit',
                'X-RateLimit-Remaining',
                'X-RateLimit-Reset'
            ],
            'supports_credentials': True,
            'max_age': 86400,  # 24 hours
            'send_wildcard': False,  # Never send wildcard for security
            'vary_header': True
        }
        
        # Initialize CORS
        self.cors = CORS(app, **cors_config)
        
        # Add custom CORS validation
        app.before_request(self.validate_cors_request)
        
        logger.info(f"Secure CORS initialized with origins: {allowed_origins}")
    
    def validate_cors_request(self):
        """Additional CORS validation beyond Flask-CORS"""
        from flask import request, jsonify
        
        origin = request.headers.get('Origin')
        
        if origin:
            allowed_origins = ["https://wwww.pdfsmaller.site", 'https://pdfsmaller.site']
            
            # Check if origin is allowed
            if origin not in allowed_origins:
                logger.warning(f"CORS violation: Origin {origin} not in allowed list {allowed_origins}")
                
                # For preflight requests, return proper CORS error
                if request.method == 'OPTIONS':
                    return jsonify({
                        'error': {
                            'code': 'CORS_ERROR',
                            'message': 'Origin not allowed'
                        }
                    }), 403
            
            # Validate that origin matches expected format
            if not self.is_valid_origin_format(origin):
                logger.warning(f"CORS violation: Invalid origin format {origin}")
                return jsonify({
                    'error': {
                        'code': 'CORS_ERROR',
                        'message': 'Invalid origin format'
                    }
                }), 403
    
    def is_valid_origin_format(self, origin: str) -> bool:
        """Validate origin format"""
        import re
        
        # Basic URL format validation
        url_pattern = r'^https?://[a-zA-Z0-9.-]+(?:\:[0-9]+)?$'
        
        if not re.match(url_pattern, origin):
            return False
        
        # Additional security checks
        origin_lower = origin.lower()
        
        # Block suspicious origins
        suspicious_patterns = [
            'localhost',
            '127.0.0.1',
            '0.0.0.0',
            'file://',
            'data:',
            'javascript:',
            'vbscript:'
        ]
        
        # Allow localhost only in development
        if not self.app.config.get('TESTING') and not self.app.debug:
            for pattern in suspicious_patterns:
                if pattern in origin_lower:
                    return False
        
        return True
    
    def add_allowed_origin(self, origin: str):
        """Dynamically add an allowed origin"""
        if self.is_valid_origin_format(origin):
            allowed_origins = self.app.config.get('ALLOWED_ORIGINS', [])
            if origin not in allowed_origins:
                allowed_origins.append(origin)
                self.app.config['ALLOWED_ORIGINS'] = allowed_origins
                logger.info(f"Added allowed origin: {origin}")
        else:
            logger.warning(f"Rejected invalid origin format: {origin}")
    
    def remove_allowed_origin(self, origin: str):
        """Dynamically remove an allowed origin"""
        allowed_origins = self.app.config.get('ALLOWED_ORIGINS', [])
        if origin in allowed_origins:
            allowed_origins.remove(origin)
            self.app.config['ALLOWED_ORIGINS'] = allowed_origins
            logger.info(f"Removed allowed origin: {origin}")


def configure_secure_cors(app, allowed_origins: List[str] = None) -> SecureCORS:
    """Configure secure CORS for Flask app"""
    if allowed_origins:
        app.config['ALLOWED_ORIGINS'] = allowed_origins
    
    return SecureCORS(app)


def get_cors_headers(origin: str = None) -> Dict[str, str]:
    """Get CORS headers for manual responses"""
    headers = {
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization, X-Requested-With, X-Request-ID',
        'Access-Control-Expose-Headers': 'X-Request-ID, X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset',
        'Access-Control-Max-Age': '86400',
        'Vary': 'Origin'
    }
    
    if origin:
        headers['Access-Control-Allow-Origin'] = origin
        headers['Access-Control-Allow-Credentials'] = 'true'
    
    return headers