"""
Tests for configuration management
"""
import os
import tempfile
import pytest
from datetime import timedelta

from src.config.config import (
    BaseConfig, DevelopmentConfig, TestingConfig, ProductionConfig,
    get_config, validate_current_config, ConfigValidationError,
    config_by_name
)


class TestBaseConfig:
    """Test base configuration class"""
    
    def test_default_values(self):
        """Test that default configuration values are set correctly"""
        config = BaseConfig()
        
        assert config.MAX_CONTENT_LENGTH == 100 * 1024 * 1024
        assert config.SQLALCHEMY_TRACK_MODIFICATIONS is False
        assert config.JWT_ALGORITHM == 'HS256'
        assert config.DEFAULT_COMPRESSION_LEVEL == 'medium'
        assert 'pdf' in config.ALLOWED_EXTENSIONS
        assert config.RATE_LIMIT_STRATEGY == 'fixed-window'
        
    def test_environment_variable_override(self, monkeypatch):
        """Test that environment variables override defaults"""
        monkeypatch.setenv('MAX_CONTENT_LENGTH', '50000000')  # 50MB
        monkeypatch.setenv('JWT_ACCESS_TOKEN_MINUTES', '30')
        monkeypatch.setenv('LOG_LEVEL', 'DEBUG')
        
        config = BaseConfig()
        
        assert config.MAX_CONTENT_LENGTH == 50000000
        assert config.JWT_ACCESS_TOKEN_EXPIRES == timedelta(minutes=30)
        assert config.LOG_LEVEL == 'DEBUG'
    
    def test_subscription_plans_structure(self):
        """Test that subscription plans are properly structured"""
        config = BaseConfig()
        
        assert 'free' in config.SUBSCRIPTION_PLANS
        assert 'premium' in config.SUBSCRIPTION_PLANS
        assert 'pro' in config.SUBSCRIPTION_PLANS
        
        for plan_name, plan_config in config.SUBSCRIPTION_PLANS.items():
            assert 'name' in plan_config
            assert 'price' in plan_config
            assert 'compressions_per_day' in plan_config
            assert 'max_file_size' in plan_config
            assert 'bulk_processing' in plan_config
            assert 'priority_processing' in plan_config
    
    def test_rate_limits_structure(self):
        """Test that rate limits are properly structured"""
        config = BaseConfig()
        
        assert 'free' in config.RATE_LIMITS
        assert 'premium' in config.RATE_LIMITS
        assert 'pro' in config.RATE_LIMITS
        
        for tier, limits in config.RATE_LIMITS.items():
            assert 'compression' in limits
            assert 'api' in limits
            assert 'auth' in limits
    
    def test_compression_levels(self):
        """Test compression levels configuration"""
        config = BaseConfig()
        
        expected_levels = ['low', 'medium', 'high', 'maximum']
        assert all(level in config.COMPRESSION_LEVELS for level in expected_levels)
        assert config.DEFAULT_COMPRESSION_LEVEL in config.COMPRESSION_LEVELS


class TestConfigValidation:
    """Test configuration validation"""
    
    def test_validate_config_success(self, monkeypatch):
        """Test successful configuration validation"""
        # Set up valid configuration
        monkeypatch.setenv('SECRET_KEY', 'a' * 32)  # 32 character key
        monkeypatch.setenv('JWT_SECRET_KEY', 'b' * 32)
        monkeypatch.setenv('DATABASE_URL', 'sqlite:///test.db')
        
        with tempfile.TemporaryDirectory() as temp_dir:
            monkeypatch.setenv('UPLOAD_FOLDER', os.path.join(temp_dir, 'uploads'))
            
            config = BaseConfig()
            errors = config.validate_config()
            
            assert len(errors) == 0
    
    def test_validate_config_missing_secret_key(self, monkeypatch):
        """Test validation fails with missing secret key"""
        monkeypatch.setenv('SECRET_KEY', '')
        
        config = BaseConfig()
        errors = config.validate_config()
        
        assert any('SECRET_KEY must be set' in error for error in errors)
    
    def test_validate_config_short_secret_key(self, monkeypatch):
        """Test validation fails with short secret key"""
        monkeypatch.setenv('SECRET_KEY', 'short')
        
        config = BaseConfig()
        errors = config.validate_config()
        
        assert any('at least 32 characters' in error for error in errors)
    
    def test_validate_config_invalid_compression_level(self, monkeypatch):
        """Test validation fails with invalid compression level"""
        monkeypatch.setenv('DEFAULT_COMPRESSION_LEVEL', 'invalid')
        
        config = BaseConfig()
        errors = config.validate_config()
        
        assert any('DEFAULT_COMPRESSION_LEVEL must be one of' in error for error in errors)
    
    def test_validate_config_invalid_log_level(self, monkeypatch):
        """Test validation fails with invalid log level"""
        monkeypatch.setenv('LOG_LEVEL', 'INVALID')
        
        config = BaseConfig()
        errors = config.validate_config()
        
        assert any('LOG_LEVEL must be one of' in error for error in errors)
    
    def test_get_config_summary(self):
        """Test configuration summary generation"""
        config = BaseConfig()
        summary = config.get_config_summary()
        
        expected_keys = [
            'database_type', 'upload_folder', 'max_file_size',
            'compression_levels', 'default_compression', 'jwt_access_expires',
            'jwt_refresh_expires', 'log_level', 'rate_limit_default',
            'allowed_origins', 'subscription_plans', 'health_check_enabled',
            'metrics_enabled'
        ]
        
        for key in expected_keys:
            assert key in summary
        
        # Ensure sensitive data is not included
        assert 'SECRET_KEY' not in str(summary)
        assert 'JWT_SECRET_KEY' not in str(summary)
        assert 'STRIPE_SECRET_KEY' not in str(summary)


class TestEnvironmentConfigs:
    """Test environment-specific configurations"""
    
    def test_development_config(self):
        """Test development configuration"""
        config = DevelopmentConfig()
        
        assert config.DEBUG is True
        assert config.TESTING is False
        assert config.LOG_LEVEL == 'DEBUG'
        assert 'sqlite' in config.SQLALCHEMY_DATABASE_URI
        assert 'localhost' in str(config.ALLOWED_ORIGINS)
    
    def test_testing_config(self):
        """Test testing configuration"""
        config = TestingConfig()
        
        assert config.DEBUG is True
        assert config.TESTING is True
        assert config.SQLALCHEMY_DATABASE_URI == 'sqlite:///:memory:'
        assert config.WTF_CSRF_ENABLED is False
        assert config.CELERY_TASK_ALWAYS_EAGER is True
        assert 'test' in config.STRIPE_SECRET_KEY
    
    def test_production_config(self):
        """Test production configuration"""
        config = ProductionConfig()
        
        assert config.DEBUG is False
        assert config.TESTING is False
        assert config.LOG_LEVEL == 'WARNING'
        assert 'postgresql' in config.SQLALCHEMY_DATABASE_URI
        assert len(config.SECURITY_HEADERS) > 0
    
    def test_production_config_validation(self, monkeypatch):
        """Test production-specific validation"""
        # Set up production environment
        monkeypatch.setenv('SECRET_KEY', 'a' * 32)
        monkeypatch.setenv('JWT_SECRET_KEY', 'b' * 32)
        
        config = ProductionConfig()
        errors = config.validate_config()
        
        # Should have errors for SQLite and test Stripe key
        assert any('PostgreSQL' in error for error in errors)
        assert any('STRIPE_SECRET_KEY' in error for error in errors)


class TestConfigFactory:
    """Test configuration factory functions"""
    
    def test_get_config_by_name(self):
        """Test getting configuration by name"""
        dev_config = get_config('development')
        test_config = get_config('testing')
        prod_config = get_config('production')
        
        assert dev_config == DevelopmentConfig
        assert test_config == TestingConfig
        assert prod_config == ProductionConfig
    
    def test_get_config_default(self, monkeypatch):
        """Test getting default configuration"""
        monkeypatch.setenv('FLASK_ENV', 'development')
        config = get_config()
        assert config == DevelopmentConfig
        
        monkeypatch.setenv('FLASK_ENV', 'production')
        config = get_config()
        assert config == ProductionConfig
    
    def test_get_config_invalid_name(self):
        """Test getting configuration with invalid name"""
        with pytest.raises(ConfigValidationError):
            get_config('invalid_config')
    
    def test_config_by_name_mapping(self):
        """Test configuration name mapping"""
        assert 'development' in config_by_name
        assert 'testing' in config_by_name
        assert 'production' in config_by_name
        assert 'default' in config_by_name
        
        assert config_by_name['development'] == DevelopmentConfig
        assert config_by_name['testing'] == TestingConfig
        assert config_by_name['production'] == ProductionConfig
        assert config_by_name['default'] == DevelopmentConfig


class TestConfigValidationFunction:
    """Test configuration validation function"""
    
    def test_validate_current_config_success(self, monkeypatch):
        """Test successful current configuration validation"""
        monkeypatch.setenv('FLASK_ENV', 'testing')
        monkeypatch.setenv('SECRET_KEY', 'a' * 32)
        monkeypatch.setenv('JWT_SECRET_KEY', 'b' * 32)
        
        # Should not raise exception
        validate_current_config()
    
    def test_validate_current_config_failure(self, monkeypatch):
        """Test failed current configuration validation"""
        monkeypatch.setenv('FLASK_ENV', 'development')
        monkeypatch.setenv('SECRET_KEY', 'short')  # Too short
        
        with pytest.raises(ConfigValidationError) as exc_info:
            validate_current_config()
        
        assert 'Configuration validation failed' in str(exc_info.value)
        assert 'at least 32 characters' in str(exc_info.value)


class TestConfigIntegration:
    """Test configuration integration scenarios"""
    
    def test_celery_task_routes(self):
        """Test Celery task routing configuration"""
        config = BaseConfig()
        
        assert 'src.tasks.compression_tasks.process_bulk_compression' in config.CELERY_TASK_ROUTES
        assert 'src.tasks.cleanup_tasks.cleanup_expired_files' in config.CELERY_TASK_ROUTES
        
        compression_route = config.CELERY_TASK_ROUTES['src.tasks.compression_tasks.process_bulk_compression']
        cleanup_route = config.CELERY_TASK_ROUTES['src.tasks.cleanup_tasks.cleanup_expired_files']
        
        assert compression_route['queue'] == 'compression'
        assert cleanup_route['queue'] == 'cleanup'
    
    def test_security_headers_configuration(self):
        """Test security headers configuration"""
        base_config = BaseConfig()
        dev_config = DevelopmentConfig()
        prod_config = ProductionConfig()
        
        # Base config should have security headers
        assert len(base_config.SECURITY_HEADERS) > 0
        
        # Development should have no security headers (relaxed)
        assert len(dev_config.SECURITY_HEADERS) == 0
        
        # Production should have comprehensive security headers
        assert len(prod_config.SECURITY_HEADERS) > 0
        assert 'X-Content-Type-Options' in prod_config.SECURITY_HEADERS
        assert 'Strict-Transport-Security' in prod_config.SECURITY_HEADERS
    
    def test_database_engine_options(self):
        """Test database engine options configuration"""
        config = BaseConfig()
        
        engine_options = config.SQLALCHEMY_ENGINE_OPTIONS
        
        assert 'pool_pre_ping' in engine_options
        assert 'pool_recycle' in engine_options
        assert 'pool_timeout' in engine_options
        assert 'max_overflow' in engine_options
        
        assert engine_options['pool_pre_ping'] is True
        assert isinstance(engine_options['pool_recycle'], int)
        assert isinstance(engine_options['pool_timeout'], int)
        assert isinstance(engine_options['max_overflow'], int)