"""
Integration tests for the comprehensive logging system.

Tests structured logging, sensitive data filtering, performance monitoring,
and specialized logging functions.
"""

import pytest
import logging
import json
import tempfile
import os
import time
from unittest.mock import patch, MagicMock
from io import StringIO

from src.utils.logging_utils import (
    setup_logging, SensitiveDataFilter, StructuredFormatter,
    log_request_info, log_error_with_context, log_security_event,
    log_performance_metric, log_business_event, log_api_call,
    log_health_check, log_audit_event, performance_monitor,
    setup_specialized_loggers, get_log_stats, sanitize_for_logging
)


class TestSensitiveDataFilter:
    """Test sensitive data filtering functionality."""
    
    def test_password_filtering(self):
        """Test password filtering in log messages."""
        filter_instance = SensitiveDataFilter()
        
        test_cases = [
            ('password=secret123', 'password=***MASKED***'),
            ('{"password": "secret123"}', '{"password": "***MASKED***"}'),
            ('password: secret123', 'password: ***MASKED***'),
            ("password='secret123'", "password='***MASKED***'"),
        ]
        
        for original, expected in test_cases:
            result = filter_instance._sanitize_message(original)
            assert '***MASKED***' in result
            assert 'secret123' not in result
    
    def test_token_filtering(self):
        """Test token filtering in log messages."""
        filter_instance = SensitiveDataFilter()
        
        test_cases = [
            ('token=abc123xyz', 'token=***MASKED***'),
            ('access_token: bearer_token_123', 'access_token: ***MASKED***'),
            ('Authorization: Bearer jwt.token.here', 'Authorization: ***MASKED***'),
        ]
        
        for original, expected in test_cases:
            result = filter_instance._sanitize_message(original)
            assert '***MASKED***' in result
            assert 'abc123xyz' not in result
            assert 'bearer_token_123' not in result
            assert 'jwt.token.here' not in result
    
    def test_email_partial_masking(self):
        """Test email partial masking."""
        filter_instance = SensitiveDataFilter()
        
        original = "User email: user@example.com"
        result = filter_instance._sanitize_message(original)
        
        # Should partially mask email
        assert 'us***@example.com' in result
        assert 'user@example.com' not in result
    
    def test_credit_card_masking(self):
        """Test credit card number masking."""
        filter_instance = SensitiveDataFilter()
        
        original = "Card number: 1234-5678-9012-3456"
        result = filter_instance._sanitize_message(original)
        
        # Should mask all but last 4 digits
        assert '****-****-****-3456' in result
        assert '1234-5678-9012' not in result
    
    def test_log_record_filtering(self):
        """Test filtering of actual log records."""
        filter_instance = SensitiveDataFilter()
        
        # Create a log record with sensitive data
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='User login with password=secret123',
            args=(),
            exc_info=None
        )
        
        # Apply filter
        filter_instance.filter(record)
        
        # Check that sensitive data was masked
        assert '***MASKED***' in record.msg
        assert 'secret123' not in record.msg


class TestStructuredFormatter:
    """Test structured JSON logging formatter."""
    
    def test_basic_formatting(self):
        """Test basic log record formatting."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='/path/to/file.py',
            lineno=42,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.funcName = 'test_function'
        record.module = 'test_module'
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data['level'] == 'INFO'
        assert log_data['logger'] == 'test_logger'
        assert log_data['message'] == 'Test message'
        assert log_data['module'] == 'test_module'
        assert log_data['function'] == 'test_function'
        assert log_data['line'] == 42
        assert 'timestamp' in log_data
    
    def test_custom_fields(self):
        """Test formatting with custom fields."""
        formatter = StructuredFormatter()
        
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='',
            lineno=0,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        # Add custom fields
        record.user_id = 123
        record.request_id = 'req-456'
        record.custom_field = 'custom_value'
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert log_data['user_id'] == 123
        assert log_data['request_id'] == 'req-456'
        assert log_data['custom_field'] == 'custom_value'
    
    def test_exception_formatting(self):
        """Test formatting with exception information."""
        formatter = StructuredFormatter()
        
        try:
            raise ValueError("Test exception")
        except ValueError:
            record = logging.LogRecord(
                name='test_logger',
                level=logging.ERROR,
                pathname='',
                lineno=0,
                msg='Error occurred',
                args=(),
                exc_info=True
            )
        
        result = formatter.format(record)
        log_data = json.loads(result)
        
        assert 'exception' in log_data
        assert 'ValueError' in log_data['exception']
        assert 'Test exception' in log_data['exception']


class TestLoggingSetup:
    """Test logging setup and configuration."""
    
    def test_basic_setup(self):
        """Test basic logging setup."""
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            setup_logging(log_level='DEBUG')
            
            # Verify logger configuration
            mock_logger.setLevel.assert_called()
            mock_logger.addHandler.assert_called()
    
    def test_file_logging_setup(self):
        """Test file logging setup."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_path = temp_file.name
        
        try:
            setup_logging(log_level='INFO', log_file=temp_path)
            
            # Test that we can log to the file
            logger = logging.getLogger('test')
            logger.info('Test message')
            
            # Verify file was created and contains log
            assert os.path.exists(temp_path)
            
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_structured_logging_setup(self):
        """Test structured logging setup."""
        with patch('logging.getLogger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            setup_logging(log_level='INFO', structured=True)
            
            # Verify structured formatter is used
            mock_logger.addHandler.assert_called()


class TestSpecializedLogging:
    """Test specialized logging functions."""
    
    def test_log_business_event(self):
        """Test business event logging."""
        with patch('src.utils.logging_utils.get_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            log_business_event(
                event_type='user_registration',
                user_id=123,
                details={'plan': 'premium'}
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            
            assert call_args[0][0] == "Business event"
            assert 'event_type' in call_args[1]['extra']
            assert call_args[1]['extra']['event_type'] == 'user_registration'
            assert call_args[1]['extra']['user_id'] == 123
    
    def test_log_api_call(self):
        """Test API call logging."""
        with patch('src.utils.logging_utils.get_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            log_api_call(
                method='POST',
                endpoint='/api/compress',
                user_id=123,
                status_code=200,
                duration=1.5,
                request_size=1024,
                response_size=512
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            
            assert call_args[0][0] == "API call"
            extra = call_args[1]['extra']
            assert extra['method'] == 'POST'
            assert extra['endpoint'] == '/api/compress'
            assert extra['status_code'] == 200
            assert extra['duration_seconds'] == 1.5
    
    def test_log_health_check(self):
        """Test health check logging."""
        with patch('src.utils.logging_utils.get_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            # Test healthy status
            log_health_check(
                service='database',
                status='healthy',
                details={'response_time': 0.1}
            )
            
            mock_logger.log.assert_called_once()
            call_args = mock_logger.log.call_args
            
            assert call_args[0][0] == logging.INFO  # Log level
            assert call_args[0][1] == "Health check"
            assert call_args[1]['extra']['service'] == 'database'
            assert call_args[1]['extra']['status'] == 'healthy'
    
    def test_log_audit_event(self):
        """Test audit event logging."""
        with patch('src.utils.logging_utils.get_logger') as mock_get_logger:
            mock_logger = MagicMock()
            mock_get_logger.return_value = mock_logger
            
            log_audit_event(
                action='delete',
                user_id=123,
                resource_type='file',
                resource_id='file-456',
                details={'reason': 'user_request'}
            )
            
            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args
            
            assert call_args[0][0] == "Audit event"
            extra = call_args[1]['extra']
            assert extra['action'] == 'delete'
            assert extra['user_id'] == 123
            assert extra['resource_type'] == 'file'
            assert extra['resource_id'] == 'file-456'


class TestPerformanceMonitoring:
    """Test performance monitoring functionality."""
    
    def test_performance_monitor_decorator_success(self):
        """Test performance monitor decorator with successful function."""
        with patch('src.utils.logging_utils.log_performance_metric') as mock_log:
            
            @performance_monitor('test_operation')
            def test_function():
                time.sleep(0.1)  # Simulate work
                return 'success'
            
            result = test_function()
            
            assert result == 'success'
            mock_log.assert_called_once()
            
            call_args = mock_log.call_args
            assert call_args[1]['operation'] == 'test_operation'
            assert call_args[1]['duration'] >= 0.1
            assert call_args[1]['details']['status'] == 'success'
    
    def test_performance_monitor_decorator_error(self):
        """Test performance monitor decorator with function that raises exception."""
        with patch('src.utils.logging_utils.log_performance_metric') as mock_log:
            
            @performance_monitor('test_operation')
            def test_function():
                raise ValueError("Test error")
            
            with pytest.raises(ValueError):
                test_function()
            
            mock_log.assert_called_once()
            
            call_args = mock_log.call_args
            assert call_args[1]['operation'] == 'test_operation'
            assert call_args[1]['details']['status'] == 'error'
            assert call_args[1]['details']['error_type'] == 'ValueError'
            assert call_args[1]['details']['error_message'] == 'Test error'
    
    def test_performance_monitor_default_name(self):
        """Test performance monitor with default operation name."""
        with patch('src.utils.logging_utils.log_performance_metric') as mock_log:
            
            @performance_monitor()
            def test_function():
                return 'success'
            
            test_function()
            
            call_args = mock_log.call_args
            # Should use module.function_name format
            assert 'test_function' in call_args[1]['operation']


class TestDataSanitization:
    """Test data sanitization functionality."""
    
    def test_sanitize_dict_with_sensitive_keys(self):
        """Test sanitizing dictionary with sensitive keys."""
        data = {
            'username': 'testuser',
            'password': 'secret123',
            'token': 'abc123xyz',
            'api_key': 'key123',
            'normal_field': 'normal_value'
        }
        
        sanitized = sanitize_for_logging(data)
        
        assert sanitized['username'] == 'testuser'
        assert sanitized['password'] == '***MASKED***'
        assert sanitized['token'] == '***MASKED***'
        assert sanitized['api_key'] == '***MASKED***'
        assert sanitized['normal_field'] == 'normal_value'
    
    def test_sanitize_nested_dict(self):
        """Test sanitizing nested dictionary."""
        data = {
            'user': {
                'name': 'testuser',
                'password': 'secret123'
            },
            'config': {
                'api_key': 'key123',
                'timeout': 30
            }
        }
        
        sanitized = sanitize_for_logging(data)
        
        assert sanitized['user']['name'] == 'testuser'
        assert sanitized['user']['password'] == '***MASKED***'
        assert sanitized['config']['api_key'] == '***MASKED***'
        assert sanitized['config']['timeout'] == 30
    
    def test_sanitize_list(self):
        """Test sanitizing list with mixed data."""
        data = [
            'normal_string',
            {'password': 'secret123'},
            ['nested', {'token': 'abc123'}]
        ]
        
        sanitized = sanitize_for_logging(data)
        
        assert sanitized[0] == 'normal_string'
        assert sanitized[1]['password'] == '***MASKED***'
        assert sanitized[2][1]['token'] == '***MASKED***'
    
    def test_sanitize_string_with_sensitive_data(self):
        """Test sanitizing string with sensitive patterns."""
        data = "Login attempt with password=secret123 and token=abc123xyz"
        
        sanitized = sanitize_for_logging(data)
        
        assert 'secret123' not in sanitized
        assert 'abc123xyz' not in sanitized
        assert '***MASKED***' in sanitized


class TestLoggingStats:
    """Test logging statistics functionality."""
    
    def test_get_log_stats(self):
        """Test getting logging statistics."""
        # Set up a simple logger configuration
        logger = logging.getLogger('test_stats')
        handler = logging.StreamHandler()
        logger.addHandler(handler)
        
        stats = get_log_stats()
        
        assert 'root_level' in stats
        assert 'handlers_count' in stats
        assert 'handlers' in stats
        assert isinstance(stats['handlers'], list)
        
        if stats['handlers']:
            handler_info = stats['handlers'][0]
            assert 'type' in handler_info
            assert 'level' in handler_info


class TestIntegrationScenarios:
    """Test real-world integration scenarios."""
    
    def test_complete_logging_workflow(self):
        """Test complete logging workflow with all components."""
        # Set up logging with structured format and file output
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.log') as temp_file:
            temp_path = temp_file.name
        
        try:
            setup_logging(log_level='INFO', log_file=temp_path, structured=True)
            setup_specialized_loggers()
            
            # Log various types of events
            log_business_event('test_event', user_id=123)
            log_api_call('GET', '/api/test', status_code=200, duration=0.5)
            log_health_check('test_service', 'healthy')
            log_audit_event('test_action', user_id=123, resource_type='test')
            
            # Verify logs were written
            assert os.path.exists(temp_path)
            
            with open(temp_path, 'r') as f:
                log_content = f.read()
                assert len(log_content) > 0
                
                # Should contain structured JSON logs
                lines = log_content.strip().split('\n')
                for line in lines:
                    if line.strip():
                        log_data = json.loads(line)
                        assert 'timestamp' in log_data
                        assert 'level' in log_data
                        assert 'message' in log_data
        
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_sensitive_data_end_to_end(self):
        """Test sensitive data filtering in end-to-end scenario."""
        # Capture log output
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        
        # Set up logging with sensitive data filter
        logger = logging.getLogger('test_sensitive')
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)
        
        # Add sensitive data filter
        sensitive_filter = SensitiveDataFilter()
        handler.addFilter(sensitive_filter)
        
        # Log message with sensitive data
        logger.info("User login: username=testuser password=secret123 token=abc123xyz")
        
        # Check that sensitive data was filtered
        log_output = log_stream.getvalue()
        assert 'secret123' not in log_output
        assert 'abc123xyz' not in log_output
        assert '***MASKED***' in log_output
        assert 'testuser' in log_output  # Non-sensitive data should remain