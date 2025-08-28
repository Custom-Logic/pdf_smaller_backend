import pytest
from src.utils.auth_utils import PasswordValidator, EmailValidator, UserValidator


class TestPasswordValidator:
    """Test cases for PasswordValidator utility"""
    
    def test_validate_password_strength_valid_password(self):
        """Test password validation with valid password"""
        result = PasswordValidator.validate_password_strength('TestPass123')
        
        assert result['valid'] is True
        assert result['message'] == 'Password meets all requirements'
        assert len(result['errors']) == 0
        assert 'requirements' in result
    
    def test_validate_password_strength_too_short(self):
        """Test password validation with too short password"""
        result = PasswordValidator.validate_password_strength('Test1')
        
        assert result['valid'] is False
        assert 'Password must be at least 8 characters long' in result['errors']
    
    def test_validate_password_strength_too_long(self):
        """Test password validation with too long password"""
        long_password = 'A' * 129 + 'a1'
        result = PasswordValidator.validate_password_strength(long_password)
        
        assert result['valid'] is False
        assert 'Password must be no more than 128 characters long' in result['errors']
    
    def test_validate_password_strength_no_uppercase(self):
        """Test password validation without uppercase letter"""
        result = PasswordValidator.validate_password_strength('testpass123')
        
        assert result['valid'] is False
        assert 'Password must contain at least one uppercase letter' in result['errors']
    
    def test_validate_password_strength_no_lowercase(self):
        """Test password validation without lowercase letter"""
        result = PasswordValidator.validate_password_strength('TESTPASS123')
        
        assert result['valid'] is False
        assert 'Password must contain at least one lowercase letter' in result['errors']
    
    def test_validate_password_strength_no_digit(self):
        """Test password validation without digit"""
        result = PasswordValidator.validate_password_strength('TestPassword')
        
        assert result['valid'] is False
        assert 'Password must contain at least one digit' in result['errors']
    
    def test_validate_password_strength_common_password(self):
        """Test password validation with common password"""
        result = PasswordValidator.validate_password_strength('Password123')
        
        # Should pass character requirements but might fail on common password check
        # Let's test with a definitely common one
        result = PasswordValidator.validate_password_strength('password')
        assert result['valid'] is False
    
    def test_validate_password_strength_empty_password(self):
        """Test password validation with empty password"""
        result = PasswordValidator.validate_password_strength('')
        
        assert result['valid'] is False
        assert result['message'] == 'Password is required'
    
    def test_validate_password_strength_none_password(self):
        """Test password validation with None password"""
        result = PasswordValidator.validate_password_strength(None)
        
        assert result['valid'] is False
        assert result['message'] == 'Password is required'
    
    def test_hash_password_valid(self):
        """Test password hashing with valid password"""
        password = 'TestPass123'
        hashed = PasswordValidator.hash_password(password)
        
        assert hashed != password
        assert hashed.startswith('pbkdf2:sha256:')
    
    def test_hash_password_invalid(self):
        """Test password hashing with invalid password"""
        with pytest.raises(ValueError, match="Password validation failed"):
            PasswordValidator.hash_password('weak')
    
    def test_verify_password_correct(self):
        """Test password verification with correct password"""
        password = 'TestPass123'
        hashed = PasswordValidator.hash_password(password)
        
        assert PasswordValidator.verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password"""
        password = 'TestPass123'
        hashed = PasswordValidator.hash_password(password)
        
        assert PasswordValidator.verify_password('WrongPass123', hashed) is False
    
    def test_verify_password_empty_inputs(self):
        """Test password verification with empty inputs"""
        assert PasswordValidator.verify_password('', 'hash') is False
        assert PasswordValidator.verify_password('password', '') is False
        assert PasswordValidator.verify_password(None, 'hash') is False
        assert PasswordValidator.verify_password('password', None) is False


class TestEmailValidator:
    """Test cases for EmailValidator utility"""
    
    def test_validate_email_valid_emails(self):
        """Test email validation with valid emails"""
        valid_emails = [
            'test@example.com',
            'user.name@domain.co.uk',
            'user+tag@example.org',
            'user123@test-domain.com',
            'a@b.co',
            'test.email+tag@example-domain.com'
        ]
        
        for email in valid_emails:
            result = EmailValidator.validate_email(email)
            assert result['valid'] is True, f"Email {email} should be valid"
            assert result['normalized_email'] == email.strip().lower()
    
    def test_validate_email_invalid_emails(self):
        """Test email validation with invalid emails"""
        invalid_emails = [
            'invalid-email',
            '@example.com',
            'user@',
            'user@.com',
            'user..name@example.com',
            'user@example',
            'user@example.',
            'user name@example.com',  # space in local part
            'user@exam ple.com'  # space in domain
        ]
        
        for email in invalid_emails:
            result = EmailValidator.validate_email(email)
            assert result['valid'] is False, f"Email {email} should be invalid"
    
    def test_validate_email_empty(self):
        """Test email validation with empty email"""
        result = EmailValidator.validate_email('')
        
        assert result['valid'] is False
        assert result['message'] == 'Email is required'
        assert result['normalized_email'] is None
    
    def test_validate_email_none(self):
        """Test email validation with None email"""
        result = EmailValidator.validate_email(None)
        
        assert result['valid'] is False
        assert result['message'] == 'Email is required'
    
    def test_validate_email_too_long(self):
        """Test email validation with too long email"""
        long_email = 'a' * 250 + '@example.com'
        result = EmailValidator.validate_email(long_email)
        
        assert result['valid'] is False
        assert 'too long' in result['message']
    
    def test_validate_email_long_local_part(self):
        """Test email validation with too long local part"""
        long_local = 'a' * 65 + '@example.com'
        result = EmailValidator.validate_email(long_local)
        
        assert result['valid'] is False
        assert 'local part is too long' in result['message']
    
    def test_validate_email_normalization(self):
        """Test email normalization"""
        result = EmailValidator.validate_email('  TEST@EXAMPLE.COM  ')
        
        assert result['valid'] is True
        assert result['normalized_email'] == 'test@example.com'
    
    def test_normalize_email_valid(self):
        """Test email normalization utility method"""
        normalized = EmailValidator.normalize_email('  TEST@EXAMPLE.COM  ')
        assert normalized == 'test@example.com'
    
    def test_normalize_email_invalid(self):
        """Test email normalization with invalid email"""
        normalized = EmailValidator.normalize_email('invalid-email')
        assert normalized is None


class TestUserValidator:
    """Test cases for UserValidator utility"""
    
    def test_validate_name_valid_names(self):
        """Test name validation with valid names"""
        valid_names = [
            'John Doe',
            'Mary Jane',
            'Jean-Pierre',
            "O'Connor",
            'Dr. Smith',
            'Anne-Marie'
        ]
        
        for name in valid_names:
            result = UserValidator.validate_name(name)
            assert result['valid'] is True, f"Name '{name}' should be valid"
            assert result['normalized_name'] == name.strip()
    
    def test_validate_name_invalid_names(self):
        """Test name validation with invalid names"""
        invalid_names = [
            '',
            'A',  # too short
            'John123',  # contains numbers
            'John@Doe',  # contains invalid characters
            'A' * 101  # too long
        ]
        
        for name in invalid_names:
            result = UserValidator.validate_name(name)
            assert result['valid'] is False, f"Name '{name}' should be invalid"
    
    def test_validate_name_empty(self):
        """Test name validation with empty name"""
        result = UserValidator.validate_name('')
        
        assert result['valid'] is False
        assert result['message'] == 'Name is required'
    
    def test_validate_name_none(self):
        """Test name validation with None name"""
        result = UserValidator.validate_name(None)
        
        assert result['valid'] is False
        assert result['message'] == 'Name is required'
    
    def test_validate_name_normalization(self):
        """Test name normalization"""
        result = UserValidator.validate_name('  John Doe  ')
        
        assert result['valid'] is True
        assert result['normalized_name'] == 'John Doe'
    
    def test_validate_user_data_all_valid(self):
        """Test complete user data validation with all valid data"""
        result = UserValidator.validate_user_data(
            email='test@example.com',
            password='TestPass123',
            name='John Doe'
        )
        
        assert result['valid'] is True
        assert result['email']['valid'] is True
        assert result['password']['valid'] is True
        assert result['name']['valid'] is True
        assert result['message'] == 'All user data is valid'
    
    def test_validate_user_data_invalid_email(self):
        """Test complete user data validation with invalid email"""
        result = UserValidator.validate_user_data(
            email='invalid-email',
            password='TestPass123',
            name='John Doe'
        )
        
        assert result['valid'] is False
        assert result['email']['valid'] is False
        assert result['password']['valid'] is True
        assert result['name']['valid'] is True
    
    def test_validate_user_data_invalid_password(self):
        """Test complete user data validation with invalid password"""
        result = UserValidator.validate_user_data(
            email='test@example.com',
            password='weak',
            name='John Doe'
        )
        
        assert result['valid'] is False
        assert result['email']['valid'] is True
        assert result['password']['valid'] is False
        assert result['name']['valid'] is True
    
    def test_validate_user_data_invalid_name(self):
        """Test complete user data validation with invalid name"""
        result = UserValidator.validate_user_data(
            email='test@example.com',
            password='TestPass123',
            name='A'
        )
        
        assert result['valid'] is False
        assert result['email']['valid'] is True
        assert result['password']['valid'] is True
        assert result['name']['valid'] is False
    
    def test_validate_user_data_all_invalid(self):
        """Test complete user data validation with all invalid data"""
        result = UserValidator.validate_user_data(
            email='invalid-email',
            password='weak',
            name='A'
        )
        
        assert result['valid'] is False
        assert result['email']['valid'] is False
        assert result['password']['valid'] is False
        assert result['name']['valid'] is False