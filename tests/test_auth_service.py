import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from src.services.auth_service import AuthService
from src.models.user import User
from src.models.base import db


class TestAuthService:
    """Test cases for AuthService"""
    
    def test_register_user_success(self, db_session):
        """Test successful user registration"""
        result = AuthService.register_user(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        
        assert result['success'] is True
        assert result['message'] == 'User registered successfully'
        assert 'user' in result
        assert 'tokens' in result
        assert result['user']['email'] == 'test@example.com'
        assert result['user']['name'] == 'Test User'
        assert 'access_token' in result['tokens']
        assert 'refresh_token' in result['tokens']
    
    def test_register_user_invalid_email(self, db_session):
        """Test user registration with invalid email"""
        result = AuthService.register_user(
            email='invalid-email',
            password='TestPass123',
            name='Test User'
        )
        
        assert result['success'] is False
        assert 'Validation failed' in result['message']
        assert 'errors' in result
        assert result['errors']['email'] is not None
    
    def test_register_user_weak_password(self, db_session):
        """Test user registration with weak password"""
        result = AuthService.register_user(
            email='test@example.com',
            password='weak',
            name='Test User'
        )
        
        assert result['success'] is False
        assert 'Validation failed' in result['message']
        assert 'errors' in result
        assert result['errors']['password'] is not None
    
    def test_register_user_invalid_name(self, db_session):
        """Test user registration with invalid name"""
        result = AuthService.register_user(
            email='test@example.com',
            password='TestPass123',
            name='A'  # Too short
        )
        
        assert result['success'] is False
        assert 'Validation failed' in result['message']
        assert 'errors' in result
        assert result['errors']['name'] is not None
    
    def test_register_user_duplicate_email(self, db_session):
        """Test user registration with duplicate email"""
        # Create first user
        user1 = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User 1'
        )
        db_session.add(user1)
        db_session.commit()
        
        # Try to create second user with same email
        result = AuthService.register_user(
            email='test@example.com',
            password='TestPass456',
            name='Test User 2'
        )
        
        assert result['success'] is False
        assert 'already exists' in result['message']
        assert 'errors' in result
        assert result['errors']['email'] is not None
    
    def test_authenticate_user_success(self, db_session):
        """Test successful user authentication"""
        # Create user first
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        db_session.add(user)
        db_session.commit()
        
        # Authenticate
        result = AuthService.authenticate_user(
            email='test@example.com',
            password='TestPass123'
        )
        
        assert result['success'] is True
        assert result['message'] == 'Authentication successful'
        assert 'user' in result
        assert 'tokens' in result
        assert result['user']['email'] == 'test@example.com'
        assert 'access_token' in result['tokens']
        assert 'refresh_token' in result['tokens']
    
    def test_authenticate_user_invalid_email(self, db_session):
        """Test authentication with invalid email format"""
        result = AuthService.authenticate_user(
            email='invalid-email',
            password='TestPass123'
        )
        
        assert result['success'] is False
        assert 'Invalid email format' in result['message']
        assert 'errors' in result
        assert result['errors']['email'] is not None
    
    def test_authenticate_user_not_found(self, db_session):
        """Test authentication with non-existent user"""
        result = AuthService.authenticate_user(
            email='nonexistent@example.com',
            password='TestPass123'
        )
        
        assert result['success'] is False
        assert 'Invalid credentials' in result['message']
        assert 'errors' in result
        assert result['errors']['general'] is not None
    
    def test_authenticate_user_wrong_password(self, db_session):
        """Test authentication with wrong password"""
        # Create user first
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        db_session.add(user)
        db_session.commit()
        
        # Try wrong password
        result = AuthService.authenticate_user(
            email='test@example.com',
            password='WrongPassword'
        )
        
        assert result['success'] is False
        assert 'Invalid credentials' in result['message']
        assert 'errors' in result
        assert result['errors']['general'] is not None
    
    def test_authenticate_user_inactive(self, db_session):
        """Test authentication with inactive user"""
        # Create inactive user
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        user.is_active = False
        db_session.add(user)
        db_session.commit()
        
        # Try to authenticate
        result = AuthService.authenticate_user(
            email='test@example.com',
            password='TestPass123'
        )
        
        assert result['success'] is False
        assert 'Account is deactivated' in result['message']
        assert 'errors' in result
        assert result['errors']['general'] is not None
    
    def test_get_user_by_id_success(self, db_session):
        """Test getting user by ID"""
        # Create user
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        db_session.add(user)
        db_session.commit()
        
        # Get user by ID
        retrieved_user = AuthService.get_user_by_id(user.id)
        
        assert retrieved_user is not None
        assert retrieved_user.email == 'test@example.com'
        assert retrieved_user.name == 'Test User'
    
    def test_get_user_by_id_not_found(self, db_session):
        """Test getting non-existent user by ID"""
        retrieved_user = AuthService.get_user_by_id(999)
        assert retrieved_user is None
    
    def test_get_user_profile_success(self, db_session):
        """Test getting user profile"""
        # Create user
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        db_session.add(user)
        db_session.commit()
        
        # Get profile
        result = AuthService.get_user_profile(user.id)
        
        assert result['success'] is True
        assert result['message'] == 'Profile retrieved successfully'
        assert 'user' in result
        assert result['user']['email'] == 'test@example.com'
        assert result['user']['name'] == 'Test User'
    
    def test_get_user_profile_not_found(self, db_session):
        """Test getting profile for non-existent user"""
        result = AuthService.get_user_profile(999)
        
        assert result['success'] is False
        assert 'User not found' in result['message']
        assert 'errors' in result
        assert result['errors']['user'] is not None
    
    def test_get_user_profile_inactive(self, db_session):
        """Test getting profile for inactive user"""
        # Create inactive user
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        user.is_active = False
        db_session.add(user)
        db_session.commit()
        
        # Try to get profile
        result = AuthService.get_user_profile(user.id)
        
        assert result['success'] is False
        assert 'Account is deactivated' in result['message']
        assert 'errors' in result
        assert result['errors']['user'] is not None
    
    def test_update_user_profile_name(self, db_session):
        """Test updating user profile name"""
        # Create user
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        db_session.add(user)
        db_session.commit()
        
        # Update name
        result = AuthService.update_user_profile(user.id, name='Updated Name')
        
        assert result['success'] is True
        assert result['message'] == 'Profile updated successfully'
        assert result['user']['name'] == 'Updated Name'
        assert result['user']['email'] == 'test@example.com'  # Should remain unchanged
    
    def test_update_user_profile_email(self, db_session):
        """Test updating user profile email"""
        # Create user
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        db_session.add(user)
        db_session.commit()
        
        # Update email
        result = AuthService.update_user_profile(user.id, email='updated@example.com')
        
        assert result['success'] is True
        assert result['message'] == 'Profile updated successfully'
        assert result['user']['email'] == 'updated@example.com'
        assert result['user']['name'] == 'Test User'  # Should remain unchanged
    
    def test_update_user_profile_invalid_name(self, db_session):
        """Test updating user profile with invalid name"""
        # Create user
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        db_session.add(user)
        db_session.commit()
        
        # Try to update with invalid name
        result = AuthService.update_user_profile(user.id, name='A')  # Too short
        
        assert result['success'] is False
        assert 'Invalid name' in result['message']
        assert 'errors' in result
        assert result['errors']['name'] is not None
    
    def test_update_user_profile_duplicate_email(self, db_session):
        """Test updating user profile with duplicate email"""
        # Create two users
        user1 = User(
            email='user1@example.com',
            password='TestPass123',
            name='User 1'
        )
        user2 = User(
            email='user2@example.com',
            password='TestPass123',
            name='User 2'
        )
        db_session.add(user1)
        db_session.add(user2)
        db_session.commit()
        
        # Try to update user2's email to user1's email
        result = AuthService.update_user_profile(user2.id, email='user1@example.com')
        
        assert result['success'] is False
        assert 'Email already in use' in result['message']
        assert 'errors' in result
        assert result['errors']['email'] is not None
    
    def test_change_password_success(self, db_session):
        """Test successful password change"""
        # Create user
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        db_session.add(user)
        db_session.commit()
        
        # Change password
        result = AuthService.change_password(
            user.id,
            current_password='TestPass123',
            new_password='NewPass456'
        )
        
        assert result['success'] is True
        assert result['message'] == 'Password changed successfully'
        
        # Verify new password works
        assert user.check_password('NewPass456') is True
        assert user.check_password('TestPass123') is False
    
    def test_change_password_wrong_current(self, db_session):
        """Test password change with wrong current password"""
        # Create user
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        db_session.add(user)
        db_session.commit()
        
        # Try to change with wrong current password
        result = AuthService.change_password(
            user.id,
            current_password='WrongPassword',
            new_password='NewPass456'
        )
        
        assert result['success'] is False
        assert 'Current password is incorrect' in result['message']
        assert 'errors' in result
        assert result['errors']['current_password'] is not None
    
    def test_change_password_weak_new(self, db_session):
        """Test password change with weak new password"""
        # Create user
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        db_session.add(user)
        db_session.commit()
        
        # Try to change to weak password
        result = AuthService.change_password(
            user.id,
            current_password='TestPass123',
            new_password='weak'
        )
        
        assert result['success'] is False
        assert 'does not meet requirements' in result['message']
        assert 'errors' in result
        assert result['errors']['new_password'] is not None
    
    def test_deactivate_user_success(self, db_session):
        """Test successful user deactivation"""
        # Create user
        user = User(
            email='test@example.com',
            password='TestPass123',
            name='Test User'
        )
        db_session.add(user)
        db_session.commit()
        
        # Deactivate user
        result = AuthService.deactivate_user(user.id)
        
        assert result['success'] is True
        assert result['message'] == 'Account deactivated successfully'
        
        # Verify user is deactivated
        assert user.is_active is False
    
    def test_deactivate_user_not_found(self, db_session):
        """Test deactivating non-existent user"""
        result = AuthService.deactivate_user(999)
        
        assert result['success'] is False
        assert 'User not found' in result['message']
        assert 'errors' in result
        assert result['errors']['user'] is not None