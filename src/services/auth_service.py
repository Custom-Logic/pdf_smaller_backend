from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from flask import current_app
from flask_jwt_extended import create_access_token, create_refresh_token, decode_token
from jwt.exceptions import ExpiredSignatureError, InvalidTokenError
from sqlalchemy.exc import IntegrityError

from src.models.base import db
from src.models.user import User
from src.utils.auth_utils import UserValidator, EmailValidator, PasswordValidator


class AuthService:
    """Service class for handling user authentication operations"""
    
    @staticmethod
    def register_user(email: str, password: str, name: str) -> Dict[str, Any]:
        """
        Register a new user
        
        Args:
            email: User's email address
            password: User's password
            name: User's full name
            
        Returns:
            Dict containing registration result and user data or error details
        """
        try:
            # Validate input data
            validation_result = UserValidator.validate_user_data(email, password, name)
            
            if not validation_result['valid']:
                return {
                    'success': False,
                    'message': 'Validation failed',
                    'errors': {
                        'email': validation_result['email']['message'] if not validation_result['email']['valid'] else None,
                        'password': validation_result['password']['errors'] if not validation_result['password']['valid'] else None,
                        'name': validation_result['name']['message'] if not validation_result['name']['valid'] else None
                    }
                }
            
            # Normalize email
            normalized_email = EmailValidator.normalize_email(email)
            
            # Check if user already exists
            existing_user = User.query.filter_by(email=normalized_email).first()
            if existing_user:
                return {
                    'success': False,
                    'message': 'User with this email already exists',
                    'errors': {'email': 'Email address is already registered'}
                }
            
            # Create new user
            user = User(
                email=normalized_email,
                password=password,
                name=validation_result['name']['normalized_name']
            )
            
            # Save to database
            db.session.add(user)
            db.session.commit()
            
            # Generate tokens
            access_token = create_access_token(
                identity=user.id,
                expires_delta=timedelta(minutes=current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', 15))
            )
            refresh_token = create_refresh_token(
                identity=user.id,
                expires_delta=timedelta(days=current_app.config.get('JWT_REFRESH_TOKEN_EXPIRES', 7))
            )
            
            return {
                'success': True,
                'message': 'User registered successfully',
                'user': user.to_dict(),
                'tokens': {
                    'access_token': access_token,
                    'refresh_token': refresh_token
                }
            }
            
        except IntegrityError:
            db.session.rollback()
            return {
                'success': False,
                'message': 'User with this email already exists',
                'errors': {'email': 'Email address is already registered'}
            }
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Registration error: {str(e)}")
            return {
                'success': False,
                'message': 'Registration failed due to server error',
                'errors': {'general': 'An unexpected error occurred'}
            }
    
    @staticmethod
    def authenticate_user(email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user with email and password
        
        Args:
            email: User's email address
            password: User's password
            
        Returns:
            Dict containing authentication result and tokens or error details
        """
        try:
            # Validate email format
            email_validation = EmailValidator.validate_email(email)
            if not email_validation['valid']:
                return {
                    'success': False,
                    'message': 'Invalid email format',
                    'errors': {'email': email_validation['message']}
                }
            
            # Normalize email
            normalized_email = email_validation['normalized_email']
            
            # Find user by email
            user = User.query.filter_by(email=normalized_email).first()
            
            if not user:
                return {
                    'success': False,
                    'message': 'Invalid credentials',
                    'errors': {'general': 'Email or password is incorrect'}
                }
            
            # Check if user is active
            if not user.is_active:
                return {
                    'success': False,
                    'message': 'Account is deactivated',
                    'errors': {'general': 'Your account has been deactivated'}
                }
            
            # Verify password
            if not user.check_password(password):
                return {
                    'success': False,
                    'message': 'Invalid credentials',
                    'errors': {'general': 'Email or password is incorrect'}
                }
            
            # Generate tokens
            access_token = create_access_token(
                identity=user.id,
                expires_delta=timedelta(minutes=current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', 15))
            )
            refresh_token = create_refresh_token(
                identity=user.id,
                expires_delta=timedelta(days=current_app.config.get('JWT_REFRESH_TOKEN_EXPIRES', 7))
            )
            
            return {
                'success': True,
                'message': 'Authentication successful',
                'user': user.to_dict(),
                'tokens': {
                    'access_token': access_token,
                    'refresh_token': refresh_token
                }
            }
            
        except Exception as e:
            current_app.logger.error(f"Authentication error: {str(e)}")
            return {
                'success': False,
                'message': 'Authentication failed due to server error',
                'errors': {'general': 'An unexpected error occurred'}
            }
    
    @staticmethod
    def refresh_access_token(refresh_token: str) -> Dict[str, Any]:
        """
        Generate new access token using refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            Dict containing new access token or error details
        """
        try:
            # Decode refresh token to get user ID
            decoded_token = decode_token(refresh_token)
            user_id = decoded_token['sub']
            
            # Verify user still exists and is active
            user = User.query.get(user_id)
            if not user:
                return {
                    'success': False,
                    'message': 'User not found',
                    'errors': {'token': 'Invalid refresh token'}
                }
            
            if not user.is_active:
                return {
                    'success': False,
                    'message': 'Account is deactivated',
                    'errors': {'token': 'Account has been deactivated'}
                }
            
            # Generate new access token
            access_token = create_access_token(
                identity=user.id,
                expires_delta=timedelta(minutes=current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES', 15))
            )
            
            return {
                'success': True,
                'message': 'Token refreshed successfully',
                'tokens': {
                    'access_token': access_token
                }
            }
            
        except ExpiredSignatureError:
            return {
                'success': False,
                'message': 'Refresh token has expired',
                'errors': {'token': 'Please log in again'}
            }
        except InvalidTokenError:
            return {
                'success': False,
                'message': 'Invalid refresh token',
                'errors': {'token': 'Invalid token format'}
            }
        except Exception as e:
            current_app.logger.error(f"Token refresh error: {str(e)}")
            return {
                'success': False,
                'message': 'Token refresh failed due to server error',
                'errors': {'general': 'An unexpected error occurred'}
            }
    
    @staticmethod
    def get_user_by_id(user_id: int) -> Optional[User]:
        """
        Get user by ID
        
        Args:
            user_id: User's ID
            
        Returns:
            User object or None if not found
        """
        try:
            return User.query.get(user_id)
        except Exception as e:
            current_app.logger.error(f"Error fetching user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def get_user_profile(user_id: int) -> Dict[str, Any]:
        """
        Get user profile information
        
        Args:
            user_id: User's ID
            
        Returns:
            Dict containing user profile or error details
        """
        try:
            user = User.query.get(user_id)
            
            if not user:
                return {
                    'success': False,
                    'message': 'User not found',
                    'errors': {'user': 'User does not exist'}
                }
            
            if not user.is_active:
                return {
                    'success': False,
                    'message': 'Account is deactivated',
                    'errors': {'user': 'Account has been deactivated'}
                }
            
            return {
                'success': True,
                'message': 'Profile retrieved successfully',
                'user': user.to_dict()
            }
            
        except Exception as e:
            current_app.logger.error(f"Error fetching profile for user {user_id}: {str(e)}")
            return {
                'success': False,
                'message': 'Failed to retrieve profile',
                'errors': {'general': 'An unexpected error occurred'}
            }
    
    @staticmethod
    def update_user_profile(user_id: int, name: Optional[str] = None, email: Optional[str] = None) -> Dict[str, Any]:
        """
        Update user profile information
        
        Args:
            user_id: User's ID
            name: New name (optional)
            email: New email (optional)
            
        Returns:
            Dict containing update result
        """
        try:
            user = User.query.get(user_id)
            
            if not user:
                return {
                    'success': False,
                    'message': 'User not found',
                    'errors': {'user': 'User does not exist'}
                }
            
            if not user.is_active:
                return {
                    'success': False,
                    'message': 'Account is deactivated',
                    'errors': {'user': 'Account has been deactivated'}
                }
            
            # Update name if provided
            if name is not None:
                name_validation = UserValidator.validate_name(name)
                if not name_validation['valid']:
                    return {
                        'success': False,
                        'message': 'Invalid name',
                        'errors': {'name': name_validation['message']}
                    }
                user.name = name_validation['normalized_name']
            
            # Update email if provided
            if email is not None:
                email_validation = EmailValidator.validate_email(email)
                if not email_validation['valid']:
                    return {
                        'success': False,
                        'message': 'Invalid email',
                        'errors': {'email': email_validation['message']}
                    }
                
                normalized_email = email_validation['normalized_email']
                
                # Check if email is already taken by another user
                existing_user = User.query.filter_by(email=normalized_email).first()
                if existing_user and existing_user.id != user_id:
                    return {
                        'success': False,
                        'message': 'Email already in use',
                        'errors': {'email': 'This email is already registered to another account'}
                    }
                
                user.email = normalized_email
            
            # Save changes
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Profile updated successfully',
                'user': user.to_dict()
            }
            
        except IntegrityError:
            db.session.rollback()
            return {
                'success': False,
                'message': 'Email already in use',
                'errors': {'email': 'This email is already registered to another account'}
            }
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating profile for user {user_id}: {str(e)}")
            return {
                'success': False,
                'message': 'Failed to update profile',
                'errors': {'general': 'An unexpected error occurred'}
            }
    
    @staticmethod
    def change_password(user_id: int, current_password: str, new_password: str) -> Dict[str, Any]:
        """
        Change user password
        
        Args:
            user_id: User's ID
            current_password: Current password for verification
            new_password: New password
            
        Returns:
            Dict containing change result
        """
        try:
            user = User.query.get(user_id)
            
            if not user:
                return {
                    'success': False,
                    'message': 'User not found',
                    'errors': {'user': 'User does not exist'}
                }
            
            if not user.is_active:
                return {
                    'success': False,
                    'message': 'Account is deactivated',
                    'errors': {'user': 'Account has been deactivated'}
                }
            
            # Verify current password
            if not user.check_password(current_password):
                return {
                    'success': False,
                    'message': 'Current password is incorrect',
                    'errors': {'current_password': 'The current password you entered is incorrect'}
                }
            
            # Validate new password
            password_validation = PasswordValidator.validate_password_strength(new_password)
            if not password_validation['valid']:
                return {
                    'success': False,
                    'message': 'New password does not meet requirements',
                    'errors': {'new_password': password_validation['errors']}
                }
            
            # Update password
            user.set_password(new_password)
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Password changed successfully'
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error changing password for user {user_id}: {str(e)}")
            return {
                'success': False,
                'message': 'Failed to change password',
                'errors': {'general': 'An unexpected error occurred'}
            }
    
    @staticmethod
    def deactivate_user(user_id: int) -> Dict[str, Any]:
        """
        Deactivate user account
        
        Args:
            user_id: User's ID
            
        Returns:
            Dict containing deactivation result
        """
        try:
            user = User.query.get(user_id)
            
            if not user:
                return {
                    'success': False,
                    'message': 'User not found',
                    'errors': {'user': 'User does not exist'}
                }
            
            user.is_active = False
            db.session.commit()
            
            return {
                'success': True,
                'message': 'Account deactivated successfully'
            }
            
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deactivating user {user_id}: {str(e)}")
            return {
                'success': False,
                'message': 'Failed to deactivate account',
                'errors': {'general': 'An unexpected error occurred'}
            }