from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from src.models.base import BaseModel, db
import re


class User(BaseModel):
    """User model for authentication and user management"""
    __tablename__ = 'users'
    
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # Relationships
    subscription = db.relationship('Subscription', backref='user', uselist=False, lazy='select')
    compression_jobs = db.relationship('CompressionJob', backref='user', lazy='dynamic')
    
    def __init__(self, email, password, name):
        """Initialize user with hashed password"""
        self.email = email.lower().strip()
        self.name = name.strip()
        self.is_active = True  # Set default value explicitly
        self.set_password(password)
    
    def set_password(self, password):
        """Hash and set the user's password"""
        if not self._validate_password(password):
            raise ValueError("Password does not meet security requirements")
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        """Check if provided password matches the stored hash"""
        return check_password_hash(self.password_hash, password)
    
    @staticmethod
    def _validate_password(password):
        """Validate password meets security requirements"""
        if not password or len(password) < 8:
            return False
        
        # Check for at least one uppercase, one lowercase, and one digit
        if not re.search(r'[A-Z]', password):
            return False
        if not re.search(r'[a-z]', password):
            return False
        if not re.search(r'\d', password):
            return False
        
        return True
    
    @staticmethod
    def validate_email(email):
        """Validate email format"""
        if not email:
            return False
        
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(email_pattern, email.strip()) is not None
    
    def to_dict(self, include_sensitive=False):
        """Convert user to dictionary representation"""
        user_dict = {
            'id': self.id,
            'email': self.email,
            'name': self.name,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_sensitive:
            user_dict['password_hash'] = self.password_hash
        
        return user_dict
    
    def __repr__(self):
        return f'<User {self.email}>'