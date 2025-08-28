import re
from werkzeug.security import generate_password_hash, check_password_hash
from typing import Optional, Dict, Any


class PasswordValidator:
    """Utility class for password validation and security"""
    
    MIN_LENGTH = 8
    MAX_LENGTH = 128
    
    @staticmethod
    def validate_password_strength(password: str) -> Dict[str, Any]:
        """
        Validate password strength and return detailed feedback
        
        Args:
            password: The password to validate
            
        Returns:
            Dict containing validation result and feedback
        """
        if not password:
            return {
                'valid': False,
                'message': 'Password is required',
                'requirements': PasswordValidator._get_requirements()
            }
        
        errors = []
        
        # Length check
        if len(password) < PasswordValidator.MIN_LENGTH:
            errors.append(f'Password must be at least {PasswordValidator.MIN_LENGTH} characters long')
        
        if len(password) > PasswordValidator.MAX_LENGTH:
            errors.append(f'Password must be no more than {PasswordValidator.MAX_LENGTH} characters long')
        
        # Character requirements
        if not re.search(r'[A-Z]', password):
            errors.append('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', password):
            errors.append('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', password):
            errors.append('Password must contain at least one digit')
        
        # Optional: Special character requirement (commented out for basic implementation)
        # if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        #     errors.append('Password must contain at least one special character')
        
        # Check for common weak patterns
        if password.lower() in ['password', '12345678', 'qwerty123', 'admin123']:
            errors.append('Password is too common and easily guessable')
        
        is_valid = len(errors) == 0
        
        return {
            'valid': is_valid,
            'message': 'Password meets all requirements' if is_valid else 'Password does not meet requirements',
            'errors': errors,
            'requirements': PasswordValidator._get_requirements()
        }
    
    @staticmethod
    def _get_requirements() -> list:
        """Get list of password requirements"""
        return [
            f'At least {PasswordValidator.MIN_LENGTH} characters long',
            'At least one uppercase letter (A-Z)',
            'At least one lowercase letter (a-z)',
            'At least one digit (0-9)',
            'No common or easily guessable passwords'
        ]
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using secure methods
        
        Args:
            password: Plain text password to hash
            
        Returns:
            Hashed password string
            
        Raises:
            ValueError: If password doesn't meet requirements
        """
        validation = PasswordValidator.validate_password_strength(password)
        if not validation['valid']:
            raise ValueError(f"Password validation failed: {', '.join(validation['errors'])}")
        
        return generate_password_hash(password, method='pbkdf2:sha256')
    
    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash
        
        Args:
            password: Plain text password to verify
            password_hash: Stored password hash
            
        Returns:
            True if password matches, False otherwise
        """
        if not password or not password_hash:
            return False
        
        return check_password_hash(password_hash, password)


class EmailValidator:
    """Utility class for email validation"""
    
    # RFC 5322 compliant email regex (simplified)
    EMAIL_PATTERN = re.compile(
        r'^[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&\'*+/=?^_`{|}~-]+)*@'
        r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'
        r'(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$'
    )
    
    @staticmethod
    def validate_email(email: str) -> Dict[str, Any]:
        """
        Validate email format and return detailed feedback
        
        Args:
            email: Email address to validate
            
        Returns:
            Dict containing validation result and feedback
        """
        if not email:
            return {
                'valid': False,
                'message': 'Email is required',
                'normalized_email': None
            }
        
        # Normalize email (strip whitespace, convert to lowercase)
        normalized_email = email.strip().lower()
        
        # Basic length check
        if len(normalized_email) > 254:  # RFC 5321 limit
            return {
                'valid': False,
                'message': 'Email address is too long',
                'normalized_email': normalized_email
            }
        
        # Pattern validation
        if not EmailValidator.EMAIL_PATTERN.match(normalized_email):
            return {
                'valid': False,
                'message': 'Invalid email format',
                'normalized_email': normalized_email
            }
        
        # Check for valid domain part
        local_part, domain_part = normalized_email.rsplit('@', 1)
        
        if len(local_part) > 64:  # RFC 5321 limit for local part
            return {
                'valid': False,
                'message': 'Email local part is too long',
                'normalized_email': normalized_email
            }
        
        if not domain_part or '.' not in domain_part:
            return {
                'valid': False,
                'message': 'Invalid email domain',
                'normalized_email': normalized_email
            }
        
        return {
            'valid': True,
            'message': 'Valid email address',
            'normalized_email': normalized_email
        }
    
    @staticmethod
    def normalize_email(email: str) -> Optional[str]:
        """
        Normalize email address (strip whitespace, convert to lowercase)
        
        Args:
            email: Email address to normalize
            
        Returns:
            Normalized email or None if invalid
        """
        validation = EmailValidator.validate_email(email)
        return validation['normalized_email'] if validation['valid'] else None


class UserValidator:
    """Utility class for user data validation"""
    
    @staticmethod
    def validate_name(name: str) -> Dict[str, Any]:
        """
        Validate user name
        
        Args:
            name: User name to validate
            
        Returns:
            Dict containing validation result and feedback
        """
        if not name:
            return {
                'valid': False,
                'message': 'Name is required',
                'normalized_name': None
            }
        
        # Normalize name (strip whitespace)
        normalized_name = name.strip()
        
        if len(normalized_name) < 2:
            return {
                'valid': False,
                'message': 'Name must be at least 2 characters long',
                'normalized_name': normalized_name
            }
        
        if len(normalized_name) > 100:
            return {
                'valid': False,
                'message': 'Name must be no more than 100 characters long',
                'normalized_name': normalized_name
            }
        
        # Check for valid characters (letters, spaces, hyphens, apostrophes)
        if not re.match(r"^[a-zA-Z\s\-'\.]+$", normalized_name):
            return {
                'valid': False,
                'message': 'Name contains invalid characters',
                'normalized_name': normalized_name
            }
        
        return {
            'valid': True,
            'message': 'Valid name',
            'normalized_name': normalized_name
        }
    
    @staticmethod
    def validate_user_data(email: str, password: str, name: str) -> Dict[str, Any]:
        """
        Validate complete user registration data
        
        Args:
            email: User email
            password: User password
            name: User name
            
        Returns:
            Dict containing validation results for all fields
        """
        email_validation = EmailValidator.validate_email(email)
        password_validation = PasswordValidator.validate_password_strength(password)
        name_validation = UserValidator.validate_name(name)
        
        all_valid = (
            email_validation['valid'] and 
            password_validation['valid'] and 
            name_validation['valid']
        )
        
        return {
            'valid': all_valid,
            'email': email_validation,
            'password': password_validation,
            'name': name_validation,
            'message': 'All user data is valid' if all_valid else 'User data validation failed'
        }