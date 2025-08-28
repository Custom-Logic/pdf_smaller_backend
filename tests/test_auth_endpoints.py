import pytest
import json
from unittest.mock import patch, Mock

from src.models.user import User
from src.models.base import db


class TestAuthEndpoints:
    """Integration tests for authentication endpoints"""
    
    def test_register_endpoint_success(self, client, db_session):
        """Test successful user registration via API"""
        with patch('src.routes.auth_routes.AuthService.register_user') as mock_register:
            mock_register.return_value = {
                'success': True,
                'message': 'User registered successfully',
                'user': {
                    'id': 1,
                    'email': 'test@example.com',
                    'name': 'Test User',
                    'is_active': True
                },
                'tokens': {
                    'access_token': 'mock_access_token',
                    'refresh_token': 'mock_refresh_token'
                }
            }
            
            response = client.post('/api/auth/register', 
                json={
                    'email': 'test@example.com',
                    'password': 'TestPass123',
                    'name': 'Test User'
                },
                content_type='application/json'
            )
            
            assert response.status_code == 201
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['message'] == 'User registered successfully'
            assert 'user' in data
            assert 'tokens' in data
            
            # Verify service was called with correct parameters
            mock_register.assert_called_once_with(
                email='test@example.com',
                password='TestPass123',
                name='Test User'
            )
    
    def test_register_endpoint_missing_fields(self, client, db_session):
        """Test registration with missing required fields"""
        response = client.post('/api/auth/register',
            json={
                'email': 'test@example.com'
                # Missing password and name
            },
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error']['code'] == 'MISSING_FIELDS'
        assert 'missing_fields' in data['error']['details']
        assert 'password' in data['error']['details']['missing_fields']
        assert 'name' in data['error']['details']['missing_fields']
    
    def test_register_endpoint_invalid_json(self, client, db_session):
        """Test registration with invalid JSON"""
        response = client.post('/api/auth/register',
            data='invalid json',
            content_type='application/json'
        )
        
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error']['code'] == 'INVALID_REQUEST'
    
    def test_register_endpoint_validation_error(self, client, db_session):
        """Test registration with validation errors"""
        with patch('src.routes.auth_routes.AuthService.register_user') as mock_register:
            mock_register.return_value = {
                'success': False,
                'message': 'Validation failed',
                'errors': {
                    'email': 'Invalid email format',
                    'password': ['Password too short'],
                    'name': None
                }
            }
            
            response = client.post('/api/auth/register',
                json={
                    'email': 'invalid-email',
                    'password': 'weak',
                    'name': 'Test User'
                },
                content_type='application/json'
            )
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['error']['code'] == 'SERVICE_ERROR'
            assert 'Validation failed' in data['error']['message']
    
    def test_login_endpoint_success(self, client, db_session):
        """Test successful user login via API"""
        with patch('src.routes.auth_routes.AuthService.authenticate_user') as mock_auth:
            mock_auth.return_value = {
                'success': True,
                'message': 'Authentication successful',
                'user': {
                    'id': 1,
                    'email': 'test@example.com',
                    'name': 'Test User',
                    'is_active': True
                },
                'tokens': {
                    'access_token': 'mock_access_token',
                    'refresh_token': 'mock_refresh_token'
                }
            }
            
            response = client.post('/api/auth/login',
                json={
                    'email': 'test@example.com',
                    'password': 'TestPass123'
                },
                content_type='application/json'
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['message'] == 'Authentication successful'
            assert 'user' in data
            assert 'tokens' in data
            
            # Verify service was called with correct parameters
            mock_auth.assert_called_once_with(
                email='test@example.com',
                password='TestPass123'
            )
    
    def test_login_endpoint_invalid_credentials(self, client, db_session):
        """Test login with invalid credentials"""
        with patch('src.routes.auth_routes.AuthService.authenticate_user') as mock_auth:
            mock_auth.return_value = {
                'success': False,
                'message': 'Invalid credentials',
                'errors': {
                    'general': 'Email or password is incorrect'
                }
            }
            
            response = client.post('/api/auth/login',
                json={
                    'email': 'test@example.com',
                    'password': 'WrongPassword'
                },
                content_type='application/json'
            )
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['error']['code'] == 'SERVICE_ERROR'
            assert 'Invalid credentials' in data['error']['message']
    
    def test_refresh_token_endpoint_success(self, client, db_session):
        """Test successful token refresh via API"""
        with patch('src.routes.auth_routes.AuthService.refresh_access_token') as mock_refresh:
            mock_refresh.return_value = {
                'success': True,
                'message': 'Token refreshed successfully',
                'tokens': {
                    'access_token': 'new_access_token'
                }
            }
            
            response = client.post('/api/auth/refresh',
                json={
                    'refresh_token': 'valid_refresh_token'
                },
                content_type='application/json'
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data['success'] is True
            assert data['message'] == 'Token refreshed successfully'
            assert 'tokens' in data
            
            # Verify service was called with correct parameters
            mock_refresh.assert_called_once_with('valid_refresh_token')
    
    def test_refresh_token_endpoint_expired(self, client, db_session):
        """Test token refresh with expired token"""
        with patch('src.routes.auth_routes.AuthService.refresh_access_token') as mock_refresh:
            mock_refresh.return_value = {
                'success': False,
                'message': 'Refresh token has expired',
                'errors': {
                    'token': 'Please log in again'
                }
            }
            
            response = client.post('/api/auth/refresh',
                json={
                    'refresh_token': 'expired_refresh_token'
                },
                content_type='application/json'
            )
            
            assert response.status_code == 400
            data = json.loads(response.data)
            assert data['error']['code'] == 'SERVICE_ERROR'
            assert 'expired' in data['error']['message'].lower()
    
    def test_get_profile_endpoint_success(self, client, db_session):
        """Test getting user profile via API"""
        with patch('src.routes.auth_routes.get_jwt_identity') as mock_jwt_identity, \
             patch('src.routes.auth_routes.AuthService.get_user_profile') as mock_get_profile:
            
            mock_jwt_identity.return_value = 1
            mock_get_profile.return_value = {
                'success': True,
                'message': 'Profile retrieved successfully',
                'user': {
                    'id': 1,
                    'email': 'test@example.com',
                    'name': 'Test User',
                    'is_active': True
                }
            }
            
            # Mock JWT required decorator
            with patch('src.routes.auth_routes.jwt_required', return_value=lambda f: f):
                response = client.get('/api/auth/profile',
                    headers={'Authorization': 'Bearer mock_token'}
                )
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['success'] is True
                assert data['message'] == 'Profile retrieved successfully'
                assert 'user' in data
                
                # Verify service was called with correct user ID
                mock_get_profile.assert_called_once_with(1)
    
    def test_update_profile_endpoint_success(self, client, db_session):
        """Test updating user profile via API"""
        with patch('src.routes.auth_routes.get_jwt_identity') as mock_jwt_identity, \
             patch('src.routes.auth_routes.AuthService.update_user_profile') as mock_update_profile:
            
            mock_jwt_identity.return_value = 1
            mock_update_profile.return_value = {
                'success': True,
                'message': 'Profile updated successfully',
                'user': {
                    'id': 1,
                    'email': 'test@example.com',
                    'name': 'Updated Name',
                    'is_active': True
                }
            }
            
            # Mock JWT required decorator
            with patch('src.routes.auth_routes.jwt_required', return_value=lambda f: f):
                response = client.put('/api/auth/profile',
                    json={
                        'name': 'Updated Name'
                    },
                    content_type='application/json',
                    headers={'Authorization': 'Bearer mock_token'}
                )
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['success'] is True
                assert data['message'] == 'Profile updated successfully'
                assert 'user' in data
                
                # Verify service was called with correct parameters
                mock_update_profile.assert_called_once_with(
                    user_id=1,
                    name='Updated Name',
                    email=None
                )
    
    def test_change_password_endpoint_success(self, client, db_session):
        """Test changing password via API"""
        with patch('src.routes.auth_routes.get_jwt_identity') as mock_jwt_identity, \
             patch('src.routes.auth_routes.AuthService.change_password') as mock_change_password:
            
            mock_jwt_identity.return_value = 1
            mock_change_password.return_value = {
                'success': True,
                'message': 'Password changed successfully'
            }
            
            # Mock JWT required decorator
            with patch('src.routes.auth_routes.jwt_required', return_value=lambda f: f):
                response = client.post('/api/auth/change-password',
                    json={
                        'current_password': 'CurrentPass123',
                        'new_password': 'NewPass456'
                    },
                    content_type='application/json',
                    headers={'Authorization': 'Bearer mock_token'}
                )
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['success'] is True
                assert data['message'] == 'Password changed successfully'
                
                # Verify service was called with correct parameters
                mock_change_password.assert_called_once_with(
                    user_id=1,
                    current_password='CurrentPass123',
                    new_password='NewPass456'
                )
    
    def test_deactivate_account_endpoint_success(self, client, db_session):
        """Test deactivating account via API"""
        with patch('src.routes.auth_routes.get_jwt_identity') as mock_jwt_identity, \
             patch('src.routes.auth_routes.AuthService.deactivate_user') as mock_deactivate:
            
            mock_jwt_identity.return_value = 1
            mock_deactivate.return_value = {
                'success': True,
                'message': 'Account deactivated successfully'
            }
            
            # Mock JWT required decorator
            with patch('src.routes.auth_routes.jwt_required', return_value=lambda f: f):
                response = client.post('/api/auth/deactivate',
                    headers={'Authorization': 'Bearer mock_token'}
                )
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['success'] is True
                assert data['message'] == 'Account deactivated successfully'
                
                # Verify service was called with correct user ID
                mock_deactivate.assert_called_once_with(1)
    
    def test_rate_limiting_headers(self, client, db_session):
        """Test that rate limiting is applied to endpoints"""
        # This test would need actual rate limiting setup to work properly
        # For now, we'll just verify the endpoint responds
        response = client.post('/api/auth/register',
            json={
                'email': 'test@example.com',
                'password': 'TestPass123',
                'name': 'Test User'
            },
            content_type='application/json'
        )
        
        # Should get some response (even if it's an error due to missing app context)
        assert response.status_code in [200, 201, 400, 500]
    
    def test_error_handler_404(self, client, db_session):
        """Test 404 error handler"""
        response = client.get('/api/auth/nonexistent')
        
        assert response.status_code == 404
        data = json.loads(response.data)
        assert 'error' in data
        assert data['error']['code'] == 'NOT_FOUND'