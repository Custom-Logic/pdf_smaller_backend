import pytest
from src.models.user import User
from src.models.base import db


class TestUserModel:
    """Test cases for User model"""
    
    def test_user_creation(self, db_session):
        """Test basic user creation"""
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        
        assert user.email == 'test@example.com'
        assert user.name == 'Test User'
        assert user.is_active is True
        assert user.password_hash is not None
        assert user.password_hash != 'TestPass123'  # Should be hashed
    
    def test_user_email_normalization(self, db_session):
        """Test email normalization during user creation"""
        user = User(
            email='  TEST@EXAMPLE.COM  ',
            password='TestPass123',
            name='Test User'
        )
        
        assert user.email == 'test@example.com'
    
    def test_user_name_normalization(self, db_session):
        """Test name normalization during user creation"""
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='  Test User  '
        )
        
        assert user.name == 'Test User'
    
    def test_password_hashing(self, db_session):
        """Test password hashing functionality"""
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        
        # Password should be hashed
        assert user.password_hash != 'TestPass123'
        assert user.password_hash.startswith('pbkdf2:sha256:')
        
        # Should be able to verify correct password
        assert user.check_password('TestPass123') is True
        assert user.check_password('WrongPassword') is False
    
    def test_password_validation_weak_password(self, db_session):
        """Test password validation rejects weak passwords"""
        with pytest.raises(ValueError, match="Password does not meet security requirements"):
            User(
                email='test@example.com',
                password='weak',
                name='Test User'
            )
    
    def test_password_validation_no_uppercase(self, db_session):
        """Test password validation requires uppercase"""
        with pytest.raises(ValueError, match="Password does not meet security requirements"):
            User(
                email='test@example.com',
                password='testpass123',
                name='Test User'
            )
    
    def test_password_validation_no_lowercase(self, db_session):
        """Test password validation requires lowercase"""
        with pytest.raises(ValueError, match="Password does not meet security requirements"):
            User(
                email='test@example.com',
                password='TESTPASS123',
                name='Test User'
            )
    
    def test_password_validation_no_digit(self, db_session):
        """Test password validation requires digit"""
        with pytest.raises(ValueError, match="Password does not meet security requirements"):
            User(
                email='test@example.com',
                password='TestPassword',
                name='Test User'
            )
    
    def test_set_password(self, db_session):
        """Test set_password method"""
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        
        original_hash = user.password_hash
        
        # Change password
        user.set_password('NewPass456')
        
        # Hash should be different
        assert user.password_hash != original_hash
        
        # Should verify with new password
        assert user.check_password('NewPass456') is True
        assert user.check_password('TestPass123') is False
    
    def test_email_validation_valid_emails(self, db_session):
        """Test email validation accepts valid emails"""
        valid_emails = [
            'test@example.com',
            'user.name@domain.co.uk',
            'user+tag@example.org',
            'user123@test-domain.com'
        ]
        
        for email in valid_emails:
            assert User.validate_email(email) is True
    
    def test_email_validation_invalid_emails(self, db_session):
        """Test email validation rejects invalid emails"""
        invalid_emails = [
            '',
            'invalid-email',
            '@example.com',
            'user@',
            'user@.com',
            'user..name@example.com',
            'user@example',
            None
        ]
        
        for email in invalid_emails:
            assert User.validate_email(email) is False
    
    def test_to_dict_basic(self, db_session):
        """Test to_dict method basic functionality"""
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        
        user_dict = user.to_dict()
        
        assert user_dict['email'] == 'test@example.com'
        assert user_dict['name'] == 'Test User'
        assert user_dict['is_active'] is True
        assert 'password_hash' not in user_dict
        assert 'id' in user_dict
        assert 'created_at' in user_dict
        assert 'updated_at' in user_dict
    
    def test_to_dict_include_sensitive(self, db_session):
        """Test to_dict method with sensitive data"""
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        
        user_dict = user.to_dict(include_sensitive=True)
        
        assert 'password_hash' in user_dict
        assert user_dict['password_hash'] is not None
    
    def test_user_repr(self, db_session):
        """Test user string representation"""
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        
        assert repr(user) == '<User test@example.com>'
    
    def test_user_database_persistence(self, db_session):
        """Test user can be saved to and loaded from database"""
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        
        # Save to database
        db_session.add(user)
        db_session.commit()
        
        # Retrieve from database
        retrieved_user = User.query.filter_by(email='test@example.com').first()
        
        assert retrieved_user is not None
        assert retrieved_user.email == 'test@example.com'
        assert retrieved_user.name == 'Test User'
        assert retrieved_user.check_password('TestPass123') is True
    
    def test_user_unique_email_constraint(self, db_session):
        """Test that email uniqueness is enforced"""
        user1 = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User 1'
        )
        
        user2 = User(
            email='test@example.com',
            password='TestPass456',
            name='Test User 2'
        )
        
        db_session.add(user1)
        db_session.commit()
        
        # Adding second user with same email should fail
        db_session.add(user2)
        
        with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
            db_session.commit()