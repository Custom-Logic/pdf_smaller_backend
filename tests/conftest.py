import pytest
import tempfile
import os
from src.main import create_app
from src.models.base import db
from src.config import Config


class TestConfig(Config):
    """Test configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = 'test-secret-key'
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    """Create application for testing"""
    app = create_app(TestConfig)
    
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client"""
    return app.test_client()


@pytest.fixture
def db_session(app):
    """Create database session for testing"""
    with app.app_context():
        yield db.session


@pytest.fixture
def test_user(app):
    """Create a test user"""
    from src.models import User
    with app.app_context():
        user = User(
            email='test@example.com',
            password='TestPassword123',
            name='Test User'
        )
        db.session.add(user)
        db.session.commit()
        yield user


@pytest.fixture
def test_plan(app):
    """Create a test plan"""
    from src.models import Plan
    from decimal import Decimal
    with app.app_context():
        plan = Plan(
            name='test_plan',
            display_name='Test Plan',
            description='A test subscription plan',
            price_monthly=Decimal('9.99'),
            price_yearly=Decimal('99.99'),
            daily_compression_limit=100,
            max_file_size_mb=25,
            bulk_processing=True,
            priority_processing=False,
            api_access=True
        )
        db.session.add(plan)
        db.session.commit()
        yield plan


@pytest.fixture
def auth_headers(app, test_user):
    """Create authentication headers with JWT token"""
    from flask_jwt_extended import create_access_token
    with app.app_context():
        access_token = create_access_token(identity=str(test_user.id))
        return {'Authorization': f'Bearer {access_token}'}