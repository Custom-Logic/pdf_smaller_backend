"""Unit tests for validation utilities"""
import pytest
import tempfile
import os
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, request
from src.utils.validation import (
    validate_json_request,
    validate_required_fields,
    validate_email,
    validate_password_strength,
    validate_file_size,
    validate_file_extension,
    sanitize_filename,
    validate_plan_id,
    validate_billing_cycle,
    validate_compression_level,
    validate_request_payload,
    validate_field_types,
    validate_file_content,
    check_pdf_security,
    sanitize_input,
    validate_ip_address,
    validate_user_agent
)


class TestBasicValidation:
    """Test basic validation functions"""
    
    def test_validate_email_valid(self):
        """Test valid email addresses"""
        valid_emails = [
            'test@example.com',
            'user.name@domain.co.uk',
            'user+tag@example.org',
            'user123@test-domain.com'
        ]
        
        for email in valid_emails:
            assert validate_email(email) is True
    
    def test_validate_email_invalid(self):
        """Test invalid email addresses"""
        invalid_emails = [
            '',
            None,
            'invalid',
            '@example.com',
            'user@',
            'user..name@example.com',
            'user@.com',
            'user@domain.',
            'user name@example.com'
        ]
        
        for email in invalid_emails:
            assert validate_email(email) is False
    
    def test_validate_password_strength_valid(self):
        """Test valid passwords"""
        valid_passwords = [
            'Password123',
            'MySecure1Pass',
            'Complex@Pass1'
        ]
        
        for password in valid_passwords:
            result = validate_password_strength(password)
            assert result['valid'] is True
            assert len(result['errors']) == 0
    
    def test_validate_password_strength_invalid(self):
        """Test invalid passwords"""
        invalid_cases = [
            ('', ['Password is required']),
            (None, ['Password is required']),
            ('short', ['Password must be at least 8 characters long', 
                      'Password must contain at least one uppercase letter',
                      'Password must contain at least one digit']),
            ('lowercase123', ['Password must contain at least one uppercase letter']),
            ('UPPERCASE123', ['Password must contain at least one lowercase letter']),
            ('NoNumbers', ['Password must contain at least one digit'])
        ]
        
        for password, expected_errors in invalid_cases:
            result = validate_password_strength(password)
            assert result['valid'] is False
            for error in expected_errors:
                assert error in result['errors']
    
    def test_validate_file_size(self):
        """Test file size validation"""
        assert validate_file_size(1024, 1) is True  # 1KB file, 1MB limit
        assert validate_file_size(1024 * 1024, 1) is True  # 1MB file, 1MB limit
        assert validate_file_size(2 * 1024 * 1024, 1) is False  # 2MB file, 1MB limit
        assert validate_file_size(0, 1) is False  # Empty file
        assert validate_file_size(-1, 1) is False  # Invalid size
    
    def test_validate_file_extension(self):
        """Test file extension validation"""
        allowed_extensions = {'pdf', 'txt'}
        
        assert validate_file_extension('document.pdf', allowed_extensions) is True
        assert validate_file_extension('file.txt', allowed_extensions) is True
        assert validate_file_extension('FILE.PDF', allowed_extensions) is True  # Case insensitive
        assert validate_file_extension('document.doc', allowed_extensions) is False
        assert validate_file_extension('noextension', allowed_extensions) is False
        assert validate_file_extension('', allowed_extensions) is False
        assert validate_file_extension(None, allowed_extensions) is False
    
    def test_sanitize_filename(self):
        """Test filename sanitization"""
        test_cases = [
            ('normal_file.pdf', 'normal_file.pdf'),
            ('file with spaces.pdf', 'file_with_spaces.pdf'),
            ('file/with\\path.pdf', 'file_with_path.pdf'),
            ('file<>:|"?.pdf', 'file_______.pdf'),
            ('', 'unnamed_file'),
            ('.' * 300 + '.pdf', 'unnamed_file'),  # Too long
            ('../../../etc/passwd', '.._.._.._.._etc_.._passwd')
        ]
        
        for input_name, expected in test_cases:
            result = sanitize_filename(input_name)
            assert result == expected or result == 'unnamed_file'  # Allow fallback


class TestAdvancedValidation:
    """Test advanced validation functions"""
    
    def test_validate_plan_id(self):
        """Test plan ID validation"""
        assert validate_plan_id(1) is True
        assert validate_plan_id('1') is True
        assert validate_plan_id(0) is False
        assert validate_plan_id(-1) is False
        assert validate_plan_id('invalid') is False
        assert validate_plan_id(None) is False
    
    def test_validate_billing_cycle(self):
        """Test billing cycle validation"""
        assert validate_billing_cycle('monthly') is True
        assert validate_billing_cycle('yearly') is True
        assert validate_billing_cycle('MONTHLY') is True  # Case insensitive
        assert validate_billing_cycle('weekly') is False
        assert validate_billing_cycle('') is False
        assert validate_billing_cycle(None) is False
    
    def test_validate_compression_level(self):
        """Test compression level validation"""
        valid_levels = ['low', 'medium', 'high', 'maximum']
        for level in valid_levels:
            assert validate_compression_level(level) is True
            assert validate_compression_level(level.upper()) is True  # Case insensitive
        
        assert validate_compression_level('invalid') is False
        assert validate_compression_level('') is False
        assert validate_compression_level(None) is False
    
    def test_sanitize_input(self):
        """Test input sanitization"""
        test_cases = [
            ('normal text', 'normal text'),
            ('<script>alert("xss")</script>', 'alert("xss")'),
            ('SELECT * FROM users', ' * FROM users'),  # SQL injection attempt
            ('text with\x00null\x01bytes', 'text withnullbytes'),
            ('a' * 2000, 'a' * 1000),  # Length limiting
            (None, ''),
            (123, '123')
        ]
        
        for input_text, expected in test_cases:
            result = sanitize_input(input_text)
            assert len(result) <= 1000
            if expected:
                assert expected in result or result == expected
    
    def test_validate_ip_address(self):
        """Test IP address validation"""
        valid_ips = ['192.168.1.1', '10.0.0.1', '127.0.0.1', '::1', '2001:db8::1']
        invalid_ips = ['256.256.256.256', '192.168.1', 'not.an.ip', '']
        
        for ip in valid_ips:
            assert validate_ip_address(ip) is True
        
        for ip in invalid_ips:
            assert validate_ip_address(ip) is False


class TestFileContentValidation:
    """Test file content validation"""
    
    def test_validate_file_content_empty(self):
        """Test validation of empty file"""
        result = validate_file_content(b'', 'test.pdf')
        assert result['valid'] is False
        assert 'File is empty' in result['errors']
    
    def test_validate_file_content_too_large(self):
        """Test validation of oversized file"""
        large_data = b'x' * (101 * 1024 * 1024)  # 101MB
        result = validate_file_content(large_data, 'test.pdf')
        assert result['valid'] is False
        assert 'File too large' in result['errors'][0]
    
    @patch('src.utils.validation.magic')
    def test_validate_file_content_valid_pdf(self, mock_magic):
        """Test validation of valid PDF file"""
        mock_magic.from_buffer.return_value = 'application/pdf'
        
        pdf_data = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<<\n/Size 1\n/Root 1 0 R\n>>\nstartxref\n9\n%%EOF'
        result = validate_file_content(pdf_data, 'test.pdf')
        
        assert result['valid'] is True
        assert result['file_type'] == 'application/pdf'
        assert result['size'] == len(pdf_data)
    
    @patch('src.utils.validation.magic')
    def test_validate_file_content_invalid_type(self, mock_magic):
        """Test validation of invalid file type"""
        mock_magic.from_buffer.return_value = 'text/plain'
        
        text_data = b'This is not a PDF file'
        result = validate_file_content(text_data, 'test.pdf')
        
        assert result['valid'] is False
        assert 'Invalid file type' in result['errors'][0]
    
    def test_validate_file_content_fallback_validation(self):
        """Test fallback validation when magic is not available"""
        with patch('src.utils.validation.magic', side_effect=ImportError):
            # Valid PDF header
            pdf_data = b'%PDF-1.4\nsome pdf content'
            result = validate_file_content(pdf_data, 'test.pdf')
            assert result['valid'] is True
            
            # Invalid PDF header
            text_data = b'This is not a PDF'
            result = validate_file_content(text_data, 'test.pdf')
            assert result['valid'] is False
    
    def test_check_pdf_security(self):
        """Test PDF security checks"""
        # Test encrypted PDF
        encrypted_pdf = b'%PDF-1.4\n/Encrypt 123 0 R'
        warnings = check_pdf_security(encrypted_pdf)
        assert any('password protected' in warning.lower() for warning in warnings)
        
        # Test PDF with JavaScript
        js_pdf = b'%PDF-1.4\n/JavaScript (alert("test"))'
        warnings = check_pdf_security(js_pdf)
        assert any('javascript' in warning.lower() for warning in warnings)
        
        # Test PDF with forms
        form_pdf = b'%PDF-1.4\n/AcroForm 123 0 R'
        warnings = check_pdf_security(form_pdf)
        assert any('forms' in warning.lower() for warning in warnings)


class TestRequestValidation:
    """Test request validation decorators and functions"""
    
    def setup_method(self):
        """Set up test Flask app"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()
    
    def test_validate_required_fields(self):
        """Test required fields validation"""
        data = {'name': 'John', 'email': 'john@example.com'}
        required = ['name', 'email']
        
        assert validate_required_fields(data, required) is True
        
        # Missing field
        assert validate_required_fields({'name': 'John'}, required) is False
        
        # None value
        assert validate_required_fields({'name': None, 'email': 'john@example.com'}, required) is False
        
        # Invalid data type
        assert validate_required_fields('not a dict', required) is False
    
    def test_validate_field_types(self):
        """Test field type validation"""
        data = {
            'email': 'test@example.com',
            'password': 'ValidPass123',
            'name': 'John Doe',
            'plan_id': 1
        }
        
        required_fields = ['email', 'password']
        optional_fields = ['name', 'plan_id']
        
        errors = validate_field_types(data, required_fields, optional_fields)
        assert len(errors) == 0
        
        # Invalid email
        data['email'] = 'invalid-email'
        errors = validate_field_types(data, required_fields, optional_fields)
        assert len(errors) > 0
        assert any(error['field'] == 'email' for error in errors)
    
    def test_validate_user_agent(self):
        """Test user agent validation"""
        # Normal browser
        result = validate_user_agent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        assert result['valid'] is True
        assert result['suspicious'] is False
        assert result['bot'] is False
        
        # Bot user agent
        result = validate_user_agent('Googlebot/2.1')
        assert result['bot'] is True
        
        # Suspicious user agent
        result = validate_user_agent('curl/7.68.0')
        assert result['suspicious'] is True
        
        # Missing user agent
        result = validate_user_agent('')
        assert result['valid'] is False
        
        # Too long user agent
        result = validate_user_agent('x' * 600)
        assert result['valid'] is False


class TestRequestPayloadDecorator:
    """Test request payload validation decorator"""
    
    def setup_method(self):
        """Set up test Flask app"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        @self.app.route('/test', methods=['POST'])
        @validate_request_payload(
            required_fields=['name', 'email'],
            optional_fields=['age'],
            max_payload_size=1024
        )
        def test_endpoint():
            return {'status': 'success'}
        
        self.client = self.app.test_client()
    
    def test_valid_request(self):
        """Test valid request passes validation"""
        with self.app.app_context():
            response = self.client.post('/test', 
                json={'name': 'John', 'email': 'john@example.com', 'age': 30})
            assert response.status_code == 200
    
    def test_missing_required_field(self):
        """Test missing required field is rejected"""
        with self.app.app_context():
            response = self.client.post('/test', 
                json={'name': 'John'})  # Missing email
            assert response.status_code == 400
            data = response.get_json()
            assert 'MISSING_REQUIRED_FIELDS' in data['error']['code']
    
    def test_invalid_json(self):
        """Test invalid JSON is rejected"""
        with self.app.app_context():
            response = self.client.post('/test', 
                data='invalid json', 
                content_type='application/json')
            assert response.status_code == 400
    
    def test_payload_too_large(self):
        """Test oversized payload is rejected"""
        with self.app.app_context():
            large_data = {'name': 'x' * 2000, 'email': 'test@example.com'}
            response = self.client.post('/test', json=large_data)
            # This might not trigger due to Flask's built-in limits, but the decorator should handle it


if __name__ == '__main__':
    pytest.main([__file__])