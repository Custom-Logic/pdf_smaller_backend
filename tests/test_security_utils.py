"""Unit tests for security utilities"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, request
from datetime import datetime, timedelta
from src.utils.security_utils import (
    validate_file,
    validate_origin,
    validate_request_headers,
    get_client_ip,
    track_suspicious_activity,
    is_rate_limited,
    sanitize_request_data,
    check_file_reputation,
    generate_security_token,
    validate_csrf_token,
    log_security_event,
    get_security_headers,
    THREAT_TRACKING
)


class TestFileValidation:
    """Test file validation functions"""
    
    def setup_method(self):
        """Reset threat tracking before each test"""
        THREAT_TRACKING['suspicious_ips'].clear()
        THREAT_TRACKING['blocked_ips'].clear()
        THREAT_TRACKING['malicious_files'].clear()
    
    def test_validate_file_no_file(self):
        """Test validation with no file"""
        result = validate_file(None)
        assert result == 'No file selected'
        
        mock_file = Mock()
        mock_file.filename = ''
        result = validate_file(mock_file)
        assert result == 'No file selected'
    
    def test_validate_file_invalid_extension(self):
        """Test validation with invalid file extension"""
        mock_file = Mock()
        mock_file.filename = 'document.txt'
        
        result = validate_file(mock_file)
        assert 'Invalid file type' in result
    
    def test_validate_file_too_large(self):
        """Test validation with oversized file"""
        mock_file = Mock()
        mock_file.filename = 'document.pdf'
        mock_file.seek = Mock()
        mock_file.tell = Mock(return_value=101 * 1024 * 1024)  # 101MB
        
        result = validate_file(mock_file)
        assert 'File too large' in result
    
    def test_validate_file_empty(self):
        """Test validation with empty file"""
        mock_file = Mock()
        mock_file.filename = 'document.pdf'
        mock_file.seek = Mock()
        mock_file.tell = Mock(return_value=0)
        
        result = validate_file(mock_file)
        assert 'File is empty' in result
    
    @patch('src.utils.security_utils.validate_file_content')
    def test_validate_file_content_validation_failure(self, mock_validate):
        """Test file validation when content validation fails"""
        mock_file = Mock()
        mock_file.filename = 'document.pdf'
        mock_file.seek = Mock()
        mock_file.tell = Mock(return_value=1024)
        mock_file.read = Mock(return_value=b'fake pdf content')
        
        mock_validate.return_value = {
            'valid': False,
            'errors': ['Invalid PDF structure']
        }
        
        result = validate_file(mock_file)
        assert 'File validation failed' in result
        assert 'Invalid PDF structure' in result
    
    @patch('src.utils.security_utils.validate_file_content')
    def test_validate_file_with_warnings(self, mock_validate):
        """Test file validation with security warnings"""
        mock_file = Mock()
        mock_file.filename = 'document.pdf'
        mock_file.seek = Mock()
        mock_file.tell = Mock(return_value=1024)
        mock_file.read = Mock(return_value=b'%PDF-1.4 content')
        
        mock_validate.return_value = {
            'valid': True,
            'errors': [],
            'warnings': ['PDF contains JavaScript']
        }
        
        with patch('src.utils.security_utils.get_client_ip', return_value='127.0.0.1'):
            result = validate_file(mock_file)
            assert result is None  # Should pass despite warnings
            
            # Check that suspicious activity was tracked
            assert '127.0.0.1' in THREAT_TRACKING['suspicious_ips']
    
    def test_validate_file_malicious_hash(self):
        """Test file validation with known malicious hash"""
        mock_file = Mock()
        mock_file.filename = 'document.pdf'
        mock_file.seek = Mock()
        mock_file.tell = Mock(return_value=1024)
        mock_file.read = Mock(return_value=b'malicious content')
        
        # Add hash to malicious files
        import hashlib
        file_hash = hashlib.sha256(b'malicious content').hexdigest()
        THREAT_TRACKING['malicious_files'].add(file_hash)
        
        with patch('src.utils.security_utils.validate_file_content') as mock_validate:
            mock_validate.return_value = {'valid': True, 'errors': [], 'warnings': []}
            
            result = validate_file(mock_file)
            assert 'File blocked due to security concerns' in result


class TestOriginValidation:
    """Test origin validation"""
    
    def setup_method(self):
        """Set up Flask app for testing"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        THREAT_TRACKING['suspicious_ips'].clear()
    
    def test_validate_origin_allowed(self):
        """Test validation with allowed origin"""
        with self.app.test_request_context(headers={'Origin': 'https://example.com'}):
            result = validate_origin(['https://example.com', 'https://test.com'])
            assert result is None
    
    def test_validate_origin_not_allowed(self):
        """Test validation with disallowed origin"""
        with self.app.test_request_context(headers={'Origin': 'https://malicious.com'}):
            with patch('src.utils.security_utils.get_client_ip', return_value='127.0.0.1'):
                result = validate_origin(['https://example.com'])
                assert result == 'Origin not allowed'
                
                # Check that suspicious activity was tracked
                assert '127.0.0.1' in THREAT_TRACKING['suspicious_ips']
    
    def test_validate_origin_no_origin_header(self):
        """Test validation with no origin header"""
        with self.app.test_request_context():
            result = validate_origin(['https://example.com'])
            assert result is None


class TestHeaderValidation:
    """Test request header validation"""
    
    def setup_method(self):
        """Set up Flask app for testing"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        THREAT_TRACKING['suspicious_ips'].clear()
        THREAT_TRACKING['blocked_ips'].clear()
    
    def test_validate_request_headers_normal(self):
        """Test validation with normal headers"""
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        with self.app.test_request_context(headers=headers):
            with patch('src.utils.security_utils.get_client_ip', return_value='127.0.0.1'):
                result = validate_request_headers()
                assert result['valid'] is True
                assert result['suspicious'] is False
    
    def test_validate_request_headers_missing_user_agent(self):
        """Test validation with missing user agent"""
        with self.app.test_request_context():
            with patch('src.utils.security_utils.get_client_ip', return_value='127.0.0.1'):
                result = validate_request_headers()
                assert result['suspicious'] is True
                assert 'Missing User-Agent header' in result['warnings']
    
    def test_validate_request_headers_suspicious_user_agent(self):
        """Test validation with suspicious user agent"""
        headers = {'User-Agent': 'curl/7.68.0'}
        
        with self.app.test_request_context(headers=headers):
            with patch('src.utils.security_utils.get_client_ip', return_value='127.0.0.1'):
                result = validate_request_headers()
                assert result['suspicious'] is True
                assert any('curl' in warning for warning in result['warnings'])
    
    def test_validate_request_headers_blocked_ip(self):
        """Test validation with blocked IP"""
        THREAT_TRACKING['blocked_ips'].add('192.168.1.100')
        
        with self.app.test_request_context():
            with patch('src.utils.security_utils.get_client_ip', return_value='192.168.1.100'):
                result = validate_request_headers()
                assert result['valid'] is False
                assert 'IP address is blocked' in result['warnings']


class TestClientIP:
    """Test client IP detection"""
    
    def setup_method(self):
        """Set up Flask app for testing"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
    
    def test_get_client_ip_direct(self):
        """Test getting client IP from direct connection"""
        with self.app.test_request_context(environ_base={'REMOTE_ADDR': '192.168.1.1'}):
            ip = get_client_ip()
            assert ip == '192.168.1.1'
    
    def test_get_client_ip_forwarded(self):
        """Test getting client IP from forwarded headers"""
        headers = {'X-Forwarded-For': '203.0.113.1, 192.168.1.1'}
        
        with self.app.test_request_context(headers=headers):
            ip = get_client_ip()
            assert ip == '203.0.113.1'  # Should get the first IP
    
    def test_get_client_ip_real_ip(self):
        """Test getting client IP from X-Real-IP header"""
        headers = {'X-Real-IP': '203.0.113.2'}
        
        with self.app.test_request_context(headers=headers):
            ip = get_client_ip()
            assert ip == '203.0.113.2'
    
    def test_get_client_ip_unknown(self):
        """Test getting client IP when none available"""
        with self.app.test_request_context():
            with patch('flask.request') as mock_request:
                mock_request.headers = {}
                mock_request.remote_addr = None
                ip = get_client_ip()
                assert ip == 'unknown'


class TestSuspiciousActivityTracking:
    """Test suspicious activity tracking"""
    
    def setup_method(self):
        """Reset threat tracking"""
        THREAT_TRACKING['suspicious_ips'].clear()
        THREAT_TRACKING['blocked_ips'].clear()
    
    def test_track_suspicious_activity(self):
        """Test tracking suspicious activity"""
        details = {'ip': '192.168.1.1', 'reason': 'test'}
        
        track_suspicious_activity('test_activity', details)
        
        assert '192.168.1.1' in THREAT_TRACKING['suspicious_ips']
        activities = THREAT_TRACKING['suspicious_ips']['192.168.1.1']
        assert len(activities) == 1
        assert activities[0]['type'] == 'test_activity'
    
    def test_auto_block_after_threshold(self):
        """Test automatic IP blocking after threshold"""
        ip = '192.168.1.2'
        
        # Generate 10 suspicious activities
        for i in range(10):
            track_suspicious_activity('test_activity', {'ip': ip})
        
        assert ip in THREAT_TRACKING['blocked_ips']
    
    def test_rate_limiting(self):
        """Test rate limiting functionality"""
        ip = '192.168.1.3'
        
        # Add some activities
        for i in range(5):
            track_suspicious_activity('request', {'ip': ip})
        
        # Should not be rate limited yet
        assert is_rate_limited(ip, max_requests=10) is False
        
        # Add more activities
        for i in range(10):
            track_suspicious_activity('request', {'ip': ip})
        
        # Should now be rate limited
        assert is_rate_limited(ip, max_requests=10) is True


class TestDataSanitization:
    """Test data sanitization functions"""
    
    def test_sanitize_request_data_simple(self):
        """Test sanitizing simple request data"""
        data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'message': '<script>alert("xss")</script>'
        }
        
        sanitized = sanitize_request_data(data)
        
        assert sanitized['name'] == 'John Doe'
        assert sanitized['email'] == 'john@example.com'
        assert '<script>' not in sanitized['message']
    
    def test_sanitize_request_data_nested(self):
        """Test sanitizing nested request data"""
        data = {
            'user': {
                'name': '<script>alert("xss")</script>',
                'preferences': {
                    'theme': 'dark'
                }
            },
            'tags': ['<script>', 'normal tag']
        }
        
        sanitized = sanitize_request_data(data)
        
        assert '<script>' not in sanitized['user']['name']
        assert sanitized['user']['preferences']['theme'] == 'dark'
        assert '<script>' not in sanitized['tags'][0]
        assert sanitized['tags'][1] == 'normal tag'


class TestSecurityTokens:
    """Test security token functions"""
    
    def test_generate_security_token(self):
        """Test security token generation"""
        token1 = generate_security_token()
        token2 = generate_security_token()
        
        assert len(token1) > 20  # Should be reasonably long
        assert token1 != token2  # Should be unique
        assert isinstance(token1, str)
    
    def test_validate_csrf_token_valid(self):
        """Test CSRF token validation with valid tokens"""
        token = generate_security_token()
        assert validate_csrf_token(token, token) is True
    
    def test_validate_csrf_token_invalid(self):
        """Test CSRF token validation with invalid tokens"""
        token1 = generate_security_token()
        token2 = generate_security_token()
        
        assert validate_csrf_token(token1, token2) is False
        assert validate_csrf_token('', token1) is False
        assert validate_csrf_token(token1, '') is False
        assert validate_csrf_token(None, token1) is False


class TestFileReputation:
    """Test file reputation checking"""
    
    def setup_method(self):
        """Reset malicious files tracking"""
        THREAT_TRACKING['malicious_files'].clear()
    
    def test_check_file_reputation_safe(self):
        """Test checking reputation of safe file"""
        result = check_file_reputation('safe_hash_123')
        
        assert result['safe'] is True
        assert result['reputation'] == 'unknown'
        assert len(result['threats']) == 0
    
    def test_check_file_reputation_malicious(self):
        """Test checking reputation of malicious file"""
        malicious_hash = 'malicious_hash_456'
        THREAT_TRACKING['malicious_files'].add(malicious_hash)
        
        result = check_file_reputation(malicious_hash)
        
        assert result['safe'] is False
        assert result['reputation'] == 'malicious'
        assert 'Known malicious file' in result['threats']


class TestSecurityHeaders:
    """Test security headers"""
    
    def test_get_security_headers(self):
        """Test getting security headers"""
        headers = get_security_headers()
        
        expected_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options',
            'X-XSS-Protection',
            'Strict-Transport-Security',
            'Content-Security-Policy',
            'Referrer-Policy'
        ]
        
        for header in expected_headers:
            assert header in headers
            assert headers[header]  # Should have a value


class TestSecurityLogging:
    """Test security event logging"""
    
    def setup_method(self):
        """Set up Flask app for testing"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
    
    @patch('src.utils.security_utils.logger')
    def test_log_security_event(self, mock_logger):
        """Test security event logging"""
        with self.app.test_request_context():
            with patch('src.utils.security_utils.get_client_ip', return_value='127.0.0.1'):
                log_security_event('test_event', {'key': 'value'}, 'WARNING')
                
                mock_logger.warning.assert_called_once()
                call_args = mock_logger.warning.call_args[0][0]
                assert 'test_event' in call_args
                assert '127.0.0.1' in call_args


if __name__ == '__main__':
    pytest.main([__file__])