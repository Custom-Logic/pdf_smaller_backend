"""Integration tests for security middleware and logging"""
import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, jsonify, g
from src.utils.security_middleware import (
    SecurityMiddleware,
    create_security_middleware,
    require_https,
    log_sensitive_action
)
from src.utils.cors_config import SecureCORS, configure_secure_cors
from src.utils.security_utils import THREAT_TRACKING


class TestSecurityMiddleware:
    """Test security middleware functionality"""
    
    def setup_method(self):
        """Set up test Flask app with security middleware"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.config['ALLOWED_ORIGINS'] = ['https://example.com', 'https://test.com']
        
        # Clear threat tracking
        THREAT_TRACKING['suspicious_ips'].clear()
        THREAT_TRACKING['blocked_ips'].clear()
        
        # Initialize security middleware
        self.security_middleware = create_security_middleware(self.app)
        
        # Create test endpoints
        @self.app.route('/test')
        def test_endpoint():
            return jsonify({'status': 'success'})
        
        @self.app.route('/sensitive')
        @require_https
        def sensitive_endpoint():
            return jsonify({'data': 'sensitive'})
        
        @self.app.route('/logged-action')
        @log_sensitive_action('test_action', {'detail': 'test'})
        def logged_action():
            return jsonify({'action': 'completed'})
        
        self.client = self.app.test_client()
    
    def test_middleware_initialization(self):
        """Test middleware is properly initialized"""
        assert self.security_middleware.app == self.app
        assert len(self.security_middleware.allowed_origins) > 0
        assert len(self.security_middleware.suspicious_patterns) > 0
    
    def test_request_id_generation(self):
        """Test request ID is generated and added to headers"""
        response = self.client.get('/test')
        
        assert response.status_code == 200
        assert 'X-Request-ID' in response.headers
        assert len(response.headers['X-Request-ID']) == 8
    
    def test_security_headers_added(self):
        """Test security headers are added to responses"""
        response = self.client.get('/test')
        
        expected_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options',
            'X-XSS-Protection',
            'Strict-Transport-Security',
            'Content-Security-Policy',
            'Referrer-Policy'
        ]
        
        for header in expected_headers:
            assert header in response.headers
    
    def test_blocked_ip_handling(self):
        """Test blocked IP addresses are rejected"""
        # Add IP to blocked list
        THREAT_TRACKING['blocked_ips'].add('192.168.1.100')
        
        with patch('src.utils.security_middleware.get_client_ip', return_value='192.168.1.100'):
            response = self.client.get('/test')
            
            assert response.status_code == 403
            data = response.get_json()
            assert data['error']['code'] == 'REQUEST_BLOCKED'
    
    def test_suspicious_user_agent_tracking(self):
        """Test suspicious user agents are tracked"""
        headers = {'User-Agent': 'sqlmap/1.0'}
        
        with patch('src.utils.security_middleware.get_client_ip', return_value='127.0.0.1'):
            response = self.client.get('/test', headers=headers)
            
            # Should still allow request but track as suspicious
            assert response.status_code == 200
            assert '127.0.0.1' in THREAT_TRACKING['suspicious_ips']
    
    def test_blocked_user_agent_rejection(self):
        """Test blocked user agents are rejected"""
        # Add user agent to blocked list
        self.security_middleware.blocked_user_agents.add('sqlmap/1.0')
        
        headers = {'User-Agent': 'sqlmap/1.0'}
        
        response = self.client.get('/test', headers=headers)
        
        assert response.status_code == 403
        data = response.get_json()
        assert data['error']['code'] == 'REQUEST_BLOCKED'
    
    def test_oversized_request_rejection(self):
        """Test oversized requests are rejected"""
        # Set very small max content length for testing
        self.app.config['MAX_CONTENT_LENGTH'] = 100
        
        large_data = 'x' * 200
        
        response = self.client.post('/test', data=large_data)
        
        # Flask itself might reject this before our middleware
        # but our middleware should also handle it
        assert response.status_code in [403, 413]
    
    def test_suspicious_path_detection(self):
        """Test suspicious path patterns are detected"""
        suspicious_paths = [
            '/admin',
            '/wp-admin',
            '/phpmyadmin',
            '/test/../etc/passwd',
            '/config.php'
        ]
        
        with patch('src.utils.security_middleware.get_client_ip', return_value='127.0.0.1'):
            for path in suspicious_paths:
                response = self.client.get(path)
                # Should track as suspicious even if 404
                assert '127.0.0.1' in THREAT_TRACKING['suspicious_ips']
    
    def test_suspicious_query_parameters(self):
        """Test suspicious query parameters are detected"""
        suspicious_queries = [
            '?id=1 UNION SELECT * FROM users',
            '?search=<script>alert("xss")</script>',
            '?callback=eval(document.cookie)',
            '?file=../../../etc/passwd'
        ]
        
        with patch('src.utils.security_middleware.get_client_ip', return_value='127.0.0.1'):
            for query in suspicious_queries:
                response = self.client.get(f'/test{query}')
                # Should track as suspicious
                assert '127.0.0.1' in THREAT_TRACKING['suspicious_ips']
    
    def test_404_pattern_tracking(self):
        """Test 404 patterns are tracked for potential scanning"""
        with patch('src.utils.security_middleware.get_client_ip', return_value='127.0.0.1'):
            # Generate multiple 404s
            for i in range(5):
                response = self.client.get(f'/nonexistent{i}')
                assert response.status_code == 404
            
            # Should track 404 patterns
            assert '127.0.0.1' in THREAT_TRACKING['suspicious_ips']
            activities = THREAT_TRACKING['suspicious_ips']['127.0.0.1']
            assert any(activity['type'] == '404_pattern' for activity in activities)
    
    @patch('src.utils.security_middleware.logger')
    def test_request_logging(self, mock_logger):
        """Test request logging functionality"""
        response = self.client.get('/test')
        
        assert response.status_code == 200
        
        # Check that logging was called
        assert mock_logger.info.called
        
        # Check log content
        log_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any('Request started:' in call for call in log_calls)
        assert any('Request completed successfully:' in call for call in log_calls)
    
    def test_https_requirement_decorator(self):
        """Test HTTPS requirement decorator"""
        # Test without HTTPS (should fail)
        response = self.client.get('/sensitive')
        assert response.status_code == 400
        
        data = response.get_json()
        assert data['error']['code'] == 'HTTPS_REQUIRED'
    
    @patch('src.utils.security_middleware.log_security_event')
    def test_sensitive_action_logging(self, mock_log):
        """Test sensitive action logging decorator"""
        response = self.client.get('/logged-action')
        
        assert response.status_code == 200
        
        # Check that security events were logged
        assert mock_log.called
        
        # Should log both start and success
        call_args = [call[0] for call in mock_log.call_args_list]
        assert any('sensitive_action_start' in args for args in call_args)
        assert any('sensitive_action_success' in args for args in call_args)


class TestSecureCORS:
    """Test secure CORS configuration"""
    
    def setup_method(self):
        """Set up test Flask app with secure CORS"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.config['ALLOWED_ORIGINS'] = ['https://example.com', 'https://test.com']
        
        # Initialize secure CORS
        self.cors = configure_secure_cors(self.app)
        
        # Create test endpoint
        @self.app.route('/api/test')
        def test_endpoint():
            return jsonify({'status': 'success'})
        
        self.client = self.app.test_client()
    
    def test_cors_initialization(self):
        """Test CORS is properly initialized"""
        assert self.cors.app == self.app
        assert self.cors.cors is not None
    
    def test_allowed_origin_request(self):
        """Test request from allowed origin"""
        headers = {'Origin': 'https://example.com'}
        
        response = self.client.get('/api/test', headers=headers)
        
        assert response.status_code == 200
        assert 'Access-Control-Allow-Origin' in response.headers
    
    def test_disallowed_origin_request(self):
        """Test request from disallowed origin"""
        headers = {'Origin': 'https://malicious.com'}
        
        response = self.client.get('/api/test', headers=headers)
        
        # Should be blocked by our custom validation
        assert response.status_code == 403
    
    def test_preflight_request_allowed_origin(self):
        """Test preflight request from allowed origin"""
        headers = {
            'Origin': 'https://example.com',
            'Access-Control-Request-Method': 'POST',
            'Access-Control-Request-Headers': 'Content-Type'
        }
        
        response = self.client.options('/api/test', headers=headers)
        
        assert response.status_code == 200
        assert 'Access-Control-Allow-Methods' in response.headers
    
    def test_preflight_request_disallowed_origin(self):
        """Test preflight request from disallowed origin"""
        headers = {
            'Origin': 'https://malicious.com',
            'Access-Control-Request-Method': 'POST'
        }
        
        response = self.client.options('/api/test', headers=headers)
        
        assert response.status_code == 403
    
    def test_invalid_origin_format(self):
        """Test invalid origin formats are rejected"""
        invalid_origins = [
            'javascript:alert(1)',
            'data:text/html,<script>alert(1)</script>',
            'file:///etc/passwd',
            'ftp://example.com',
            'not-a-url'
        ]
        
        for origin in invalid_origins:
            headers = {'Origin': origin}
            response = self.client.get('/api/test', headers=headers)
            assert response.status_code == 403
    
    def test_localhost_blocked_in_production(self):
        """Test localhost is blocked in production mode"""
        # Disable testing mode to simulate production
        self.app.config['TESTING'] = False
        self.app.debug = False
        
        headers = {'Origin': 'http://localhost:3000'}
        
        response = self.client.get('/api/test', headers=headers)
        
        assert response.status_code == 403
    
    def test_dynamic_origin_management(self):
        """Test dynamic addition and removal of allowed origins"""
        new_origin = 'https://newdomain.com'
        
        # Add new origin
        self.cors.add_allowed_origin(new_origin)
        
        assert new_origin in self.app.config['ALLOWED_ORIGINS']
        
        # Test request from new origin
        headers = {'Origin': new_origin}
        response = self.client.get('/api/test', headers=headers)
        assert response.status_code == 200
        
        # Remove origin
        self.cors.remove_allowed_origin(new_origin)
        
        assert new_origin not in self.app.config['ALLOWED_ORIGINS']


class TestSecurityIntegration:
    """Integration tests for complete security system"""
    
    def setup_method(self):
        """Set up complete security environment"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.config['ALLOWED_ORIGINS'] = ['https://example.com']
        
        # Initialize security middleware (CORS now handled in routes only)
        self.security_middleware = create_security_middleware(self.app)
        
        # Create test endpoints
        @self.app.route('/api/public')
        def public_endpoint():
            return jsonify({'data': 'public'})
        
        @self.app.route('/api/sensitive')
        @require_https
        @log_sensitive_action('access_sensitive_data')
        def sensitive_endpoint():
            return jsonify({'data': 'sensitive'})
        
        self.client = self.app.test_client()
    
    def test_complete_security_flow(self):
        """Test complete security flow with all components"""
        headers = {
            'Origin': 'https://example.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        response = self.client.get('/api/public', headers=headers)
        
        # Should succeed with all security headers
        assert response.status_code == 200
        
        # Check security headers
        security_headers = [
            'X-Content-Type-Options',
            'X-Frame-Options',
            'X-Request-ID'
        ]
        
        for header in security_headers:
            assert header in response.headers
        
        # Check CORS headers
        assert 'Access-Control-Allow-Origin' in response.headers
    
    def test_blocked_request_flow(self):
        """Test complete flow for blocked requests"""
        # Use suspicious user agent and disallowed origin
        headers = {
            'Origin': 'https://malicious.com',
            'User-Agent': 'sqlmap/1.0'
        }
        
        response = self.client.get('/api/public', headers=headers)
        
        # Should be blocked
        assert response.status_code == 403
        
        data = response.get_json()
        assert 'error' in data
        assert data['error']['code'] in ['REQUEST_BLOCKED', 'CORS_ERROR']
    
    @patch('src.utils.security_middleware.logger')
    def test_security_logging_integration(self, mock_logger):
        """Test security logging across all components"""
        headers = {
            'Origin': 'https://example.com',
            'User-Agent': 'Mozilla/5.0'
        }
        
        response = self.client.get('/api/public', headers=headers)
        
        assert response.status_code == 200
        
        # Verify logging occurred
        assert mock_logger.info.called
        
        # Check for request logging
        log_calls = [str(call) for call in mock_logger.info.call_args_list]
        assert any('Request started:' in call for call in log_calls)
        assert any('Request completed successfully:' in call for call in log_calls)


if __name__ == '__main__':
    pytest.main([__file__])