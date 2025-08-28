"""
Unit tests for the error handling system.

Tests custom exceptions, error handlers, and response formatting.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from flask import Flask, g
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError
from sqlalchemy.exc import SQLAlchemyError

from src.utils.exceptions import (
    PDFCompressionError, ValidationError, AuthenticationError,
    AuthorizationError, ResourceNotFoundError, RateLimitExceededError,
    FileProcessingError, SubscriptionError, UsageLimitExceededError,
    ExternalServiceError, ConfigurationError, DatabaseError, SecurityError
)
from src.utils.error_handlers import (
    generate_request_id, get_request_id, format_error_response,
    register_error_handlers, create_error_response, validate_and_raise,
    safe_execute
)


class TestCustomExceptions:
    """Test custom exception classes."""
    
    def test_pdf_compression_error_base(self):
        """Test base PDFCompressionError class."""
        error = PDFCompressionError(
            message="Test error",
            error_code="TEST_ERROR",
            details={'key': 'value'},
            status_code=400
        )
        
        assert error.message == "Test error"
        assert error.error_code == "TEST_ERROR"
        assert error.details == {'key': 'value'}
        assert error.status_code == 400
        assert error.request_id is not None
        
        error_dict = error.to_dict()
        assert error_dict['error']['code'] == "TEST_ERROR"
        assert error_dict['error']['message'] == "Test error"
        assert error_dict['error']['details'] == {'key': 'value'}
        assert error_dict['request_id'] == error.request_id
    
    def test_validation_error(self):
        """Test ValidationError class."""
        error = ValidationError(
            message="Invalid field",
            field="email",
            details={'pattern': 'email'}
        )
        
        assert error.error_code == "VALIDATION_ERROR"
        assert error.status_code == 400
        assert error.details['field'] == "email"
        assert error.details['pattern'] == "email"
    
    def test_authentication_error(self):
        """Test AuthenticationError class."""
        error = AuthenticationError("Invalid credentials")
        
        assert error.error_code == "AUTHENTICATION_ERROR"
        assert error.status_code == 401
        assert error.message == "Invalid credentials"
    
    def test_authorization_error(self):
        """Test AuthorizationError class."""
        error = AuthorizationError("Access denied")
        
        assert error.error_code == "AUTHORIZATION_ERROR"
        assert error.status_code == 403
        assert error.message == "Access denied"
    
    def test_resource_not_found_error(self):
        """Test ResourceNotFoundError class."""
        error = ResourceNotFoundError("User", "123")
        
        assert error.error_code == "RESOURCE_NOT_FOUND"
        assert error.status_code == 404
        assert "User not found" in error.message
        assert error.details['resource_type'] == "User"
        assert error.details['resource_id'] == "123"
    
    def test_rate_limit_exceeded_error(self):
        """Test RateLimitExceededError class."""
        error = RateLimitExceededError(100, "hour", retry_after=3600)
        
        assert error.error_code == "RATE_LIMIT_EXCEEDED"
        assert error.status_code == 429
        assert "100 requests per hour" in error.message
        assert error.details['limit'] == 100
        assert error.details['window'] == "hour"
        assert error.details['retry_after'] == 3600
    
    def test_file_processing_error(self):
        """Test FileProcessingError class."""
        error = FileProcessingError("Compression failed", "test.pdf")
        
        assert error.error_code == "FILE_PROCESSING_ERROR"
        assert error.status_code == 422
        assert error.message == "Compression failed"
        assert error.details['file_name'] == "test.pdf"
    
    def test_subscription_error(self):
        """Test SubscriptionError class."""
        error = SubscriptionError("Payment failed", "expired")
        
        assert error.error_code == "SUBSCRIPTION_ERROR"
        assert error.status_code == 402
        assert error.message == "Payment failed"
        assert error.details['subscription_status'] == "expired"
    
    def test_usage_limit_exceeded_error(self):
        """Test UsageLimitExceededError class."""
        error = UsageLimitExceededError("daily_compressions", 15, 10)
        
        assert error.error_code == "USAGE_LIMIT_EXCEEDED"
        assert error.status_code == 402
        assert "daily_compressions limit exceeded: 15/10" in error.message
        assert error.details['limit_type'] == "daily_compressions"
        assert error.details['current_usage'] == 15
        assert error.details['limit'] == 10
    
    def test_external_service_error(self):
        """Test ExternalServiceError class."""
        error = ExternalServiceError("Stripe", "Connection timeout")
        
        assert error.error_code == "EXTERNAL_SERVICE_ERROR"
        assert error.status_code == 503
        assert error.message == "Connection timeout"
        assert error.details['service_name'] == "Stripe"
    
    def test_configuration_error(self):
        """Test ConfigurationError class."""
        error = ConfigurationError("Missing API key", "STRIPE_SECRET_KEY")
        
        assert error.error_code == "CONFIGURATION_ERROR"
        assert error.status_code == 500
        assert error.message == "Missing API key"
        assert error.details['config_key'] == "STRIPE_SECRET_KEY"
    
    def test_database_error(self):
        """Test DatabaseError class."""
        error = DatabaseError("Connection failed", "SELECT")
        
        assert error.error_code == "DATABASE_ERROR"
        assert error.status_code == 500
        assert error.message == "Connection failed"
        assert error.details['operation'] == "SELECT"
    
    def test_security_error(self):
        """Test SecurityError class."""
        error = SecurityError("Malicious file detected", "malware")
        
        assert error.error_code == "SECURITY_ERROR"
        assert error.status_code == 403
        assert error.message == "Malicious file detected"
        assert error.details['violation_type'] == "malware"


class TestErrorHandlers:
    """Test error handler functions."""
    
    def test_generate_request_id(self):
        """Test request ID generation."""
        request_id = generate_request_id()
        
        assert isinstance(request_id, str)
        assert len(request_id) == 36  # UUID4 length
        assert request_id != generate_request_id()  # Should be unique
    
    def test_get_request_id_with_existing(self):
        """Test getting request ID when one exists."""
        app = Flask(__name__)
        
        with app.app_context():
            with app.test_request_context():
                # Set a request ID
                g.request_id = "test-request-id"
                
                request_id = get_request_id()
                assert request_id == "test-request-id"
    
    def test_get_request_id_without_existing(self):
        """Test getting request ID when none exists."""
        app = Flask(__name__)
        
        with app.app_context():
            with app.test_request_context():
                request_id = get_request_id()
                
                assert isinstance(request_id, str)
                assert len(request_id) == 36
                assert hasattr(g, 'request_id')
                assert g.request_id == request_id
    
    def test_format_error_response(self):
        """Test error response formatting."""
        response, status_code = format_error_response(
            error_code="TEST_ERROR",
            message="Test message",
            details={'key': 'value'},
            status_code=400,
            request_id="test-id"
        )
        
        assert status_code == 400
        assert response['error']['code'] == "TEST_ERROR"
        assert response['error']['message'] == "Test message"
        assert response['error']['details'] == {'key': 'value'}
        assert response['request_id'] == "test-id"
        assert 'timestamp' in response
    
    def test_create_error_response(self):
        """Test convenience function for creating error responses."""
        response, status_code = create_error_response(
            error_code="CUSTOM_ERROR",
            message="Custom message",
            status_code=422
        )
        
        assert status_code == 422
        assert response['error']['code'] == "CUSTOM_ERROR"
        assert response['error']['message'] == "Custom message"
    
    def test_validate_and_raise_success(self):
        """Test validate_and_raise with successful condition."""
        # Should not raise an exception
        validate_and_raise(True, ValidationError, "Should not raise")
    
    def test_validate_and_raise_failure(self):
        """Test validate_and_raise with failing condition."""
        with pytest.raises(ValidationError) as exc_info:
            validate_and_raise(False, ValidationError, "Should raise", field="test")
        
        assert exc_info.value.message == "Should raise"
        assert exc_info.value.details['field'] == "test"
    
    def test_safe_execute_success(self):
        """Test safe_execute with successful function."""
        def test_func(x, y):
            return x + y
        
        result = safe_execute(test_func, 2, 3)
        assert result == 5
    
    def test_safe_execute_with_pdf_compression_error(self):
        """Test safe_execute re-raises PDFCompressionError."""
        def test_func():
            raise ValidationError("Test error")
        
        with pytest.raises(ValidationError):
            safe_execute(test_func)
    
    def test_safe_execute_with_generic_error(self):
        """Test safe_execute converts generic errors."""
        def test_func():
            raise ValueError("Generic error")
        
        with pytest.raises(PDFCompressionError) as exc_info:
            safe_execute(test_func, error_message="Custom error message")
        
        assert exc_info.value.message == "Custom error message"
        assert exc_info.value.details['original_error'] == "Generic error"
        assert exc_info.value.details['error_type'] == "ValueError"


class TestErrorHandlerIntegration:
    """Test error handler integration with Flask app."""
    
    @pytest.fixture
    def app(self):
        """Create a test Flask app with error handlers."""
        app = Flask(__name__)
        app.config['TESTING'] = True
        register_error_handlers(app)
        
        # Add test routes that raise different errors
        @app.route('/validation-error')
        def validation_error():
            raise ValidationError("Invalid input", field="email")
        
        @app.route('/auth-error')
        def auth_error():
            raise AuthenticationError("Not authenticated")
        
        @app.route('/not-found-error')
        def not_found_error():
            raise ResourceNotFoundError("User", "123")
        
        @app.route('/rate-limit-error')
        def rate_limit_error():
            raise RateLimitExceededError(100, "hour", retry_after=3600)
        
        @app.route('/security-error')
        def security_error():
            raise SecurityError("Malicious content", "malware")
        
        @app.route('/database-error')
        def database_error():
            raise SQLAlchemyError("Database connection failed")
        
        @app.route('/http-error')
        def http_error():
            raise BadRequest("Bad request")
        
        @app.route('/generic-error')
        def generic_error():
            raise ValueError("Generic error")
        
        return app
    
    def test_validation_error_handler(self, app):
        """Test validation error handler."""
        with app.test_client() as client:
            response = client.get('/validation-error')
            
            assert response.status_code == 400
            data = json.loads(response.data)
            
            assert data['error']['code'] == "VALIDATION_ERROR"
            assert data['error']['message'] == "Invalid input"
            assert data['error']['details']['field'] == "email"
            assert 'request_id' in data
            assert 'timestamp' in data
    
    def test_authentication_error_handler(self, app):
        """Test authentication error handler."""
        with app.test_client() as client:
            response = client.get('/auth-error')
            
            assert response.status_code == 401
            data = json.loads(response.data)
            
            assert data['error']['code'] == "AUTHENTICATION_ERROR"
            assert data['error']['message'] == "Not authenticated"
    
    def test_not_found_error_handler(self, app):
        """Test resource not found error handler."""
        with app.test_client() as client:
            response = client.get('/not-found-error')
            
            assert response.status_code == 404
            data = json.loads(response.data)
            
            assert data['error']['code'] == "RESOURCE_NOT_FOUND"
            assert "User not found" in data['error']['message']
    
    def test_rate_limit_error_handler(self, app):
        """Test rate limit error handler with retry headers."""
        with app.test_client() as client:
            response = client.get('/rate-limit-error')
            
            assert response.status_code == 429
            assert 'Retry-After' in response.headers
            assert response.headers['Retry-After'] == '3600'
            
            data = json.loads(response.data)
            assert data['error']['code'] == "RATE_LIMIT_EXCEEDED"
    
    @patch('src.utils.error_handlers.logger')
    def test_security_error_handler_logging(self, mock_logger, app):
        """Test security error handler logs critical events."""
        with app.test_client() as client:
            response = client.get('/security-error')
            
            assert response.status_code == 403
            data = json.loads(response.data)
            
            assert data['error']['code'] == "SECURITY_ERROR"
            mock_logger.critical.assert_called_once()
    
    def test_database_error_handler(self, app):
        """Test database error handler."""
        with app.test_client() as client:
            response = client.get('/database-error')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            
            assert data['error']['code'] == "DATABASE_ERROR"
            assert data['error']['message'] == "Database operation failed"
    
    def test_http_error_handler(self, app):
        """Test HTTP error handler."""
        with app.test_client() as client:
            response = client.get('/http-error')
            
            assert response.status_code == 400
            data = json.loads(response.data)
            
            assert data['error']['code'] == "BAD_REQUEST"
    
    @patch('src.utils.error_handlers.log_error_with_context')
    def test_generic_error_handler(self, mock_log_error, app):
        """Test generic error handler."""
        with app.test_client() as client:
            response = client.get('/generic-error')
            
            assert response.status_code == 500
            data = json.loads(response.data)
            
            assert data['error']['code'] == "INTERNAL_SERVER_ERROR"
            assert data['error']['message'] == "An unexpected error occurred. Please try again later."
            assert data['error']['details']['type'] == "ValueError"
            
            # Verify error was logged
            mock_log_error.assert_called_once()
    
    def test_request_id_tracking(self, app):
        """Test request ID is tracked throughout request lifecycle."""
        with app.test_client() as client:
            response = client.get('/validation-error')
            
            data = json.loads(response.data)
            request_id = data['request_id']
            
            assert isinstance(request_id, str)
            assert len(request_id) == 36  # UUID4 length
    
    @patch('src.utils.error_handlers.logger')
    def test_request_completion_logging(self, mock_logger, app):
        """Test request completion is logged."""
        @app.route('/success')
        def success():
            return {'status': 'ok'}
        
        with app.test_client() as client:
            response = client.get('/success')
            
            assert response.status_code == 200
            # Verify request completion was logged
            mock_logger.info.assert_called()