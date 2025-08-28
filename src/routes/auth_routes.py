from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from functools import wraps
import logging

from src.services.auth_service import AuthService
from src.utils.rate_limiter import auth_rate_limit
from src.utils.validation import validate_request_payload
from src.utils.security_utils import validate_request_headers, log_security_event, sanitize_request_data

logger = logging.getLogger(__name__)

# Create authentication blueprint
auth_bp = Blueprint('auth', __name__)

@auth_bp.before_request
def before_request():
    """Security checks before processing auth requests"""
    # Validate request headers for security threats
    header_validation = validate_request_headers()
    if not header_validation['valid']:
        log_security_event('blocked_auth_request', {
            'reason': 'header_validation_failed',
            'warnings': header_validation['warnings']
        }, 'WARNING')
        return jsonify({
            'error': {
                'code': 'REQUEST_BLOCKED',
                'message': 'Request blocked due to security concerns'
            }
        }), 403
    
    # Sanitize request data if JSON
    if request.is_json:
        try:
            data = request.get_json()
            if data:
                sanitized_data = sanitize_request_data(data)
                # Store sanitized data for use in endpoints
                request._sanitized_json = sanitized_data
        except Exception as e:
            logger.warning(f"Failed to sanitize request data: {str(e)}")


def validate_json_request(required_fields=None):
    """Decorator to validate JSON request data"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({
                    'error': {
                        'code': 'INVALID_REQUEST',
                        'message': 'Request must be JSON',
                        'details': {'content_type': 'application/json required'}
                    }
                }), 400
            
            data = request.get_json()
            if not data:
                return jsonify({
                    'error': {
                        'code': 'INVALID_REQUEST',
                        'message': 'Request body cannot be empty',
                        'details': {'body': 'JSON data required'}
                    }
                }), 400
            
            if required_fields:
                missing_fields = []
                for field in required_fields:
                    if field not in data or not data[field]:
                        missing_fields.append(field)
                
                if missing_fields:
                    return jsonify({
                        'error': {
                            'code': 'MISSING_FIELDS',
                            'message': 'Required fields are missing',
                            'details': {'missing_fields': missing_fields}
                        }
                    }), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def handle_service_response(service_result, success_status=200):
    """Helper function to handle service response and convert to API response"""
    if service_result['success']:
        response_data = {
            'success': True,
            'message': service_result['message']
        }
        
        # Add additional data if present
        if 'user' in service_result:
            response_data['user'] = service_result['user']
        if 'tokens' in service_result:
            response_data['tokens'] = service_result['tokens']
        
        return jsonify(response_data), success_status
    else:
        error_response = {
            'error': {
                'code': 'SERVICE_ERROR',
                'message': service_result['message'],
                'details': service_result.get('errors', {})
            }
        }
        
        # Determine appropriate HTTP status code based on error type
        status_code = 400  # Default to bad request
        
        if 'not found' in service_result['message'].lower():
            status_code = 404
        elif 'deactivated' in service_result['message'].lower():
            status_code = 403
        elif 'already exists' in service_result['message'].lower():
            status_code = 409
        elif 'server error' in service_result['message'].lower():
            status_code = 500
        
        return jsonify(error_response), status_code


@auth_bp.route('/register', methods=['POST'])
@auth_rate_limit
@validate_request_payload(required_fields=['email', 'password', 'name'])
def register():
    """
    User registration endpoint
    
    Expected JSON payload:
    {
        "email": "user@example.com",
        "password": "SecurePass123",
        "name": "John Doe"
    }
    """
    try:
        data = request.get_json()
        
        result = AuthService.register_user(
            email=data['email'],
            password=data['password'],
            name=data['name']
        )
        
        return handle_service_response(result, success_status=201)
        
    except Exception as e:
        logger.error(f"Registration endpoint error: {str(e)}")
        return jsonify({
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'Registration failed due to server error',
                'details': {'general': 'An unexpected error occurred'}
            }
        }), 500


@auth_bp.route('/login', methods=['POST'])
@auth_rate_limit
@validate_request_payload(required_fields=['email', 'password'])
def login():
    """
    User login endpoint
    
    Expected JSON payload:
    {
        "email": "user@example.com",
        "password": "SecurePass123"
    }
    """
    try:
        data = request.get_json()
        
        result = AuthService.authenticate_user(
            email=data['email'],
            password=data['password']
        )
        
        return handle_service_response(result)
        
    except Exception as e:
        logger.error(f"Login endpoint error: {str(e)}")
        return jsonify({
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'Login failed due to server error',
                'details': {'general': 'An unexpected error occurred'}
            }
        }), 500


@auth_bp.route('/refresh', methods=['POST'])
@limiter.limit("20 per minute")  # More lenient for token refresh
@validate_json_request(required_fields=['refresh_token'])
def refresh_token():
    """
    Token refresh endpoint
    
    Expected JSON payload:
    {
        "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."
    }
    """
    try:
        data = request.get_json()
        
        result = AuthService.refresh_access_token(data['refresh_token'])
        
        return handle_service_response(result)
        
    except Exception as e:
        logger.error(f"Token refresh endpoint error: {str(e)}")
        return jsonify({
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'Token refresh failed due to server error',
                'details': {'general': 'An unexpected error occurred'}
            }
        }), 500


@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """
    Get user profile endpoint (requires authentication)
    
    Headers:
    Authorization: Bearer <access_token>
    """
    try:
        user_id = get_jwt_identity()
        
        result = AuthService.get_user_profile(user_id)
        
        return handle_service_response(result)
        
    except Exception as e:
        logger.error(f"Get profile endpoint error: {str(e)}")
        return jsonify({
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'Failed to retrieve profile',
                'details': {'general': 'An unexpected error occurred'}
            }
        }), 500


@auth_bp.route('/profile', methods=['PUT'])
@jwt_required()
@validate_json_request()
def update_profile():
    """
    Update user profile endpoint (requires authentication)
    
    Headers:
    Authorization: Bearer <access_token>
    
    Expected JSON payload (all fields optional):
    {
        "name": "New Name",
        "email": "new@example.com"
    }
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        result = AuthService.update_user_profile(
            user_id=user_id,
            name=data.get('name'),
            email=data.get('email')
        )
        
        return handle_service_response(result)
        
    except Exception as e:
        logger.error(f"Update profile endpoint error: {str(e)}")
        return jsonify({
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'Failed to update profile',
                'details': {'general': 'An unexpected error occurred'}
            }
        }), 500


@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
@limiter.limit("5 per minute")  # Stricter rate limiting for password changes
@validate_json_request(required_fields=['current_password', 'new_password'])
def change_password():
    """
    Change password endpoint (requires authentication)
    
    Headers:
    Authorization: Bearer <access_token>
    
    Expected JSON payload:
    {
        "current_password": "CurrentPass123",
        "new_password": "NewPass456"
    }
    """
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        result = AuthService.change_password(
            user_id=user_id,
            current_password=data['current_password'],
            new_password=data['new_password']
        )
        
        return handle_service_response(result)
        
    except Exception as e:
        logger.error(f"Change password endpoint error: {str(e)}")
        return jsonify({
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'Failed to change password',
                'details': {'general': 'An unexpected error occurred'}
            }
        }), 500


@auth_bp.route('/deactivate', methods=['POST'])
@jwt_required()
@limiter.limit("2 per minute")  # Very strict rate limiting for account deactivation
def deactivate_account():
    """
    Deactivate user account endpoint (requires authentication)
    
    Headers:
    Authorization: Bearer <access_token>
    """
    try:
        user_id = get_jwt_identity()
        
        result = AuthService.deactivate_user(user_id)
        
        return handle_service_response(result)
        
    except Exception as e:
        logger.error(f"Deactivate account endpoint error: {str(e)}")
        return jsonify({
            'error': {
                'code': 'INTERNAL_ERROR',
                'message': 'Failed to deactivate account',
                'details': {'general': 'An unexpected error occurred'}
            }
        }), 500


# Error handlers for the auth blueprint
@auth_bp.errorhandler(400)
def bad_request(error):
    """Handle bad request errors"""
    return jsonify({
        'error': {
            'code': 'BAD_REQUEST',
            'message': 'Bad request',
            'details': {'description': str(error)}
        }
    }), 400


@auth_bp.errorhandler(401)
def unauthorized(error):
    """Handle unauthorized errors"""
    return jsonify({
        'error': {
            'code': 'UNAUTHORIZED',
            'message': 'Authentication required',
            'details': {'description': 'Valid access token required'}
        }
    }), 401


@auth_bp.errorhandler(403)
def forbidden(error):
    """Handle forbidden errors"""
    return jsonify({
        'error': {
            'code': 'FORBIDDEN',
            'message': 'Access forbidden',
            'details': {'description': str(error)}
        }
    }), 403


@auth_bp.errorhandler(404)
def not_found(error):
    """Handle not found errors"""
    return jsonify({
        'error': {
            'code': 'NOT_FOUND',
            'message': 'Resource not found',
            'details': {'description': str(error)}
        }
    }), 404


@auth_bp.errorhandler(429)
def rate_limit_exceeded(error):
    """Handle rate limit exceeded errors"""
    return jsonify({
        'error': {
            'code': 'RATE_LIMIT_EXCEEDED',
            'message': 'Rate limit exceeded',
            'details': {
                'description': 'Too many requests. Please try again later.',
                'retry_after': error.retry_after if hasattr(error, 'retry_after') else None
            }
        }
    }), 429


@auth_bp.errorhandler(500)
def internal_server_error(error):
    """Handle internal server errors"""
    logger.error(f"Internal server error in auth blueprint: {str(error)}")
    return jsonify({
        'error': {
            'code': 'INTERNAL_SERVER_ERROR',
            'message': 'Internal server error',
            'details': {'description': 'An unexpected error occurred'}
        }
    }), 500