# Environment Configuration Guide

This guide provides detailed information about configuring environment variables for the PDF Smaller backend application across different deployment environments.

## Table of Contents

1. [Configuration Overview](#configuration-overview)
2. [Environment Variables Reference](#environment-variables-reference)
3. [Environment-Specific Configurations](#environment-specific-configurations)
4. [Security Considerations](#security-considerations)
5. [Validation and Testing](#validation-and-testing)

## Configuration Overview

The PDF Smaller backend uses environment variables for configuration management, allowing different settings for development, testing, and production environments without code changes.

### Configuration Hierarchy

1. **Environment Variables** (highest priority)
2. **`.env` files** (environment-specific)
3. **Default values** (in configuration classes)

### Environment Selection

The application automatically selects the configuration based on the `FLASK_ENV` environment variable:

```bash
export FLASK_ENV=development  # Uses DevelopmentConfig
export FLASK_ENV=testing      # Uses TestingConfig  
export FLASK_ENV=production   # Uses ProductionConfig
```

## Environment Variables Reference

### Core Application Settings

| Variable | Type | Default | Description | Required |
|----------|------|---------|-------------|----------|
| `FLASK_ENV` | string | `development` | Environment mode (development/testing/production) | No |
| `SECRET_KEY` | string | Auto-generated | Flask secret key for sessions and CSRF protection | Yes |
| `DEBUG` | boolean | `false` | Enable debug mode (never use in production) | No |
| `HOST` | string | `0.0.0.0` | Host to bind the application to | No |
| `PORT` | integer | `5000` | Port to run the application on | No |

**Example:**
```bash
FLASK_ENV=production
SECRET_KEY=your-super-secure-64-character-secret-key-here
DEBUG=false
HOST=0.0.0.0
PORT=5000
```

### Database Configuration

| Variable | Type | Default | Description | Required |
|----------|------|---------|-------------|----------|
| `DATABASE_URL` | string | `sqlite:///pdf_smaller.db` | Database connection URL | Yes |
| `DB_POOL_SIZE` | integer | `10` | Database connection pool size | No |
| `DB_MAX_OVERFLOW` | integer | `20` | Maximum connection pool overflow | No |
| `DB_POOL_RECYCLE` | integer | `3600` | Connection recycle time (seconds) | No |
| `DB_POOL_TIMEOUT` | integer | `30` | Connection timeout (seconds) | No |
| `DB_POOL_PRE_PING` | boolean | `true` | Enable connection health checks | No |

**Examples:**

*SQLite (Development):*
```bash
DATABASE_URL=sqlite:///pdf_smaller_dev.db
```

*PostgreSQL (Production):*
```bash
DATABASE_URL=postgresql://username:password@localhost:5432/pdf_smaller_prod
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_POOL_RECYCLE=3600
```

### JWT Authentication

| Variable | Type | Default | Description | Required |
|----------|------|---------|-------------|----------|
| `JWT_SECRET_KEY` | string | Same as `SECRET_KEY` | JWT token signing key | Yes |
| `JWT_ACCESS_TOKEN_MINUTES` | integer | `15` | Access token expiration (minutes) | No |
| `JWT_REFRESH_TOKEN_DAYS` | integer | `7` | Refresh token expiration (days) | No |
| `JWT_ALGORITHM` | string | `HS256` | JWT signing algorithm | No |

**Example:**
```bash
JWT_SECRET_KEY=your-jwt-specific-secret-key-different-from-main-secret
JWT_ACCESS_TOKEN_MINUTES=60
JWT_REFRESH_TOKEN_DAYS=30
JWT_ALGORITHM=HS256
```

### File Storage and Processing

| Variable | Type | Default | Description | Required |
|----------|------|---------|-------------|----------|
| `UPLOAD_FOLDER` | string | `/tmp/pdf_uploads` | Directory for uploaded files | No |
| `MAX_FILE_SIZE` | integer | `52428800` | Maximum file size in bytes (50MB) | No |
| `MAX_CONTENT_LENGTH` | integer | `52428800` | Maximum request size in bytes | No |
| `MAX_FILE_AGE_HOURS` | integer | `1` | How long to keep files (hours) | No |
| `DEFAULT_COMPRESSION_LEVEL` | string | `medium` | Default PDF compression level | No |
| `CLEANUP_ENABLED` | boolean | `true` | Enable automatic file cleanup | No |

**Example:**
```bash
UPLOAD_FOLDER=/var/app/uploads
MAX_FILE_SIZE=104857600  # 100MB
MAX_CONTENT_LENGTH=104857600
MAX_FILE_AGE_HOURS=2
DEFAULT_COMPRESSION_LEVEL=medium
CLEANUP_ENABLED=true
```

### Redis and Caching

| Variable | Type | Default | Description | Required |
|----------|------|---------|-------------|----------|
| `REDIS_URL` | string | `redis://localhost:6379/0` | Redis connection URL | Yes |
| `CACHE_TYPE` | string | `redis` | Cache backend type | No |
| `CACHE_REDIS_URL` | string | Same as `REDIS_URL` | Redis URL for caching | No |
| `CACHE_DEFAULT_TIMEOUT` | integer | `300` | Default cache timeout (seconds) | No |

**Example:**
```bash
REDIS_URL=redis://localhost:6379/0
CACHE_TYPE=redis
CACHE_REDIS_URL=redis://localhost:6379/1
CACHE_DEFAULT_TIMEOUT=600
```

### Celery Background Processing

| Variable | Type | Default | Description | Required |
|----------|------|---------|-------------|----------|
| `CELERY_BROKER_URL` | string | `redis://localhost:6379/0` | Celery message broker URL | Yes |
| `CELERY_RESULT_BACKEND` | string | Same as broker | Celery result backend URL | No |
| `CELERY_TIMEZONE` | string | `UTC` | Celery timezone | No |
| `CELERY_WORKER_CONCURRENCY` | integer | `2` | Number of worker processes | No |
| `CELERY_WORKER_LOG_LEVEL` | string | `INFO` | Worker log level | No |
| `CELERY_TASK_SOFT_TIME_LIMIT` | integer | `300` | Soft task time limit (seconds) | No |
| `CELERY_TASK_TIME_LIMIT` | integer | `600` | Hard task time limit (seconds) | No |

**Example:**
```bash
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TIMEZONE=UTC
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_LOG_LEVEL=INFO
CELERY_TASK_SOFT_TIME_LIMIT=300
CELERY_TASK_TIME_LIMIT=600
```

### Security and CORS

| Variable | Type | Default | Description | Required |
|----------|------|---------|-------------|----------|
| `ALLOWED_ORIGINS` | string | `*` | Comma-separated list of allowed CORS origins | No |
| `SECURITY_HEADERS_ENABLED` | boolean | `false` | Enable security headers | No |
| `RATE_LIMIT_ENABLED` | boolean | `true` | Enable rate limiting | No |
| `RATE_LIMIT_STORAGE_URL` | string | Same as `REDIS_URL` | Redis URL for rate limiting | No |
| `RATE_LIMIT_DEFAULT` | string | `100 per hour` | Default rate limit | No |

**Example:**
```bash
ALLOWED_ORIGINS=https://pdfsmaller.site,https://www.pdfsmaller.site
SECURITY_HEADERS_ENABLED=true
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STORAGE_URL=redis://localhost:6379/1
RATE_LIMIT_DEFAULT=1000 per hour
```

### Stripe Payment Processing

| Variable | Type | Default | Description | Required |
|----------|------|---------|-------------|----------|
| `STRIPE_PUBLISHABLE_KEY` | string | None | Stripe publishable key | Yes* |
| `STRIPE_SECRET_KEY` | string | None | Stripe secret key | Yes* |
| `STRIPE_WEBHOOK_SECRET` | string | None | Stripe webhook endpoint secret | Yes* |
| `STRIPE_API_VERSION` | string | `2023-10-16` | Stripe API version | No |

*Required for subscription functionality

**Example:**
```bash
# Test keys (development)
STRIPE_PUBLISHABLE_KEY=pk_test_your_test_publishable_key
STRIPE_SECRET_KEY=sk_test_your_test_secret_key
STRIPE_WEBHOOK_SECRET=whsec_test_your_webhook_secret

# Live keys (production)
STRIPE_PUBLISHABLE_KEY=pk_live_your_live_publishable_key
STRIPE_SECRET_KEY=sk_live_your_live_secret_key
STRIPE_WEBHOOK_SECRET=whsec_your_live_webhook_secret
```

### Logging Configuration

| Variable | Type | Default | Description | Required |
|----------|------|---------|-------------|----------|
| `LOG_LEVEL` | string | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR/CRITICAL) | No |
| `LOG_FILE` | string | `app.log` | Log file path | No |
| `LOG_FORMAT` | string | Standard | Log message format | No |
| `LOG_MAX_BYTES` | integer | `10485760` | Maximum log file size (10MB) | No |
| `LOG_BACKUP_COUNT` | integer | `5` | Number of log file backups | No |

**Example:**
```bash
LOG_LEVEL=WARNING
LOG_FILE=/var/log/pdfsmaller/app.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5
```

### Email Configuration (Optional)

| Variable | Type | Default | Description | Required |
|----------|------|---------|-------------|----------|
| `MAIL_SERVER` | string | None | SMTP server hostname | No |
| `MAIL_PORT` | integer | `587` | SMTP server port | No |
| `MAIL_USE_TLS` | boolean | `true` | Use TLS for email | No |
| `MAIL_USE_SSL` | boolean | `false` | Use SSL for email | No |
| `MAIL_USERNAME` | string | None | SMTP username | No |
| `MAIL_PASSWORD` | string | None | SMTP password | No |
| `MAIL_DEFAULT_SENDER` | string | None | Default sender email | No |

**Example:**
```bash
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@pdfsmaller.site
```

### Monitoring and Health Checks

| Variable | Type | Default | Description | Required |
|----------|------|---------|-------------|----------|
| `HEALTH_CHECK_ENABLED` | boolean | `true` | Enable health check endpoints | No |
| `METRICS_ENABLED` | boolean | `false` | Enable metrics collection | No |
| `SENTRY_DSN` | string | None | Sentry error tracking DSN | No |

**Example:**
```bash
HEALTH_CHECK_ENABLED=true
METRICS_ENABLED=true
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

## Environment-Specific Configurations

### Development Environment

Create `.env.development`:
```bash
# Application
FLASK_ENV=development
SECRET_KEY=dev-secret-key-change-in-production
JWT_SECRET_KEY=dev-jwt-secret-key-change-in-production
DEBUG=true
HOST=0.0.0.0
PORT=5000

# Database
DATABASE_URL=sqlite:///pdf_smaller_dev.db

# File Storage
UPLOAD_FOLDER=./uploads/dev
MAX_FILE_SIZE=52428800  # 50MB
MAX_FILE_AGE_HOURS=24

# Redis & Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_WORKER_CONCURRENCY=2

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:8080

# Security (Relaxed for development)
SECURITY_HEADERS_ENABLED=false
RATE_LIMIT_ENABLED=true

# Logging
LOG_LEVEL=DEBUG
LOG_FILE=app.log

# Stripe (Test Keys)
STRIPE_PUBLISHABLE_KEY=pk_test_your_test_key
STRIPE_SECRET_KEY=sk_test_your_test_key
STRIPE_WEBHOOK_SECRET=whsec_test_your_webhook_secret

# Email (Optional - use MailHog for testing)
MAIL_SERVER=localhost
MAIL_PORT=1025
MAIL_USE_TLS=false

# Monitoring
HEALTH_CHECK_ENABLED=true
METRICS_ENABLED=false
```

### Testing Environment

Create `.env.testing`:
```bash
# Application
FLASK_ENV=testing
SECRET_KEY=test-secret-key-for-testing-only
JWT_SECRET_KEY=test-jwt-secret-key-for-testing-only
DEBUG=true
TESTING=true

# Database (In-memory SQLite)
DATABASE_URL=sqlite:///:memory:

# File Storage
UPLOAD_FOLDER=./uploads/test
MAX_FILE_SIZE=10485760  # 10MB for faster tests
MAX_FILE_AGE_HOURS=1

# Redis & Celery (Use different DB)
REDIS_URL=redis://localhost:6379/15
CELERY_BROKER_URL=redis://localhost:6379/15
CELERY_RESULT_BACKEND=redis://localhost:6379/15
CELERY_TASK_ALWAYS_EAGER=true  # Synchronous execution for tests

# Security (Disabled for testing)
SECURITY_HEADERS_ENABLED=false
RATE_LIMIT_ENABLED=false
WTF_CSRF_ENABLED=false

# Logging
LOG_LEVEL=DEBUG
LOG_FILE=test.log

# Stripe (Test Keys)
STRIPE_PUBLISHABLE_KEY=pk_test_your_test_key
STRIPE_SECRET_KEY=sk_test_your_test_key
STRIPE_WEBHOOK_SECRET=whsec_test_your_webhook_secret

# JWT (Shorter expiration for testing)
JWT_ACCESS_TOKEN_MINUTES=5
JWT_REFRESH_TOKEN_DAYS=1

# Monitoring
HEALTH_CHECK_ENABLED=true
METRICS_ENABLED=false
```

### Production Environment

Create `.env.production`:
```bash
# Application
FLASK_ENV=production
SECRET_KEY=your-super-secure-64-character-production-secret-key-here
JWT_SECRET_KEY=your-super-secure-jwt-secret-key-different-from-above
DEBUG=false
HOST=0.0.0.0
PORT=5000

# Database
DATABASE_URL=postgresql://pdf_user:secure_password@localhost:5432/pdf_smaller_prod
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_POOL_RECYCLE=3600
DB_POOL_TIMEOUT=30
DB_POOL_PRE_PING=true

# File Storage
UPLOAD_FOLDER=/var/app/uploads
MAX_FILE_SIZE=104857600  # 100MB
MAX_CONTENT_LENGTH=104857600
MAX_FILE_AGE_HOURS=1
CLEANUP_ENABLED=true

# Redis & Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_TIMEZONE=UTC
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_LOG_LEVEL=WARNING
CELERY_TASK_SOFT_TIME_LIMIT=300
CELERY_TASK_TIME_LIMIT=600

# Caching
CACHE_TYPE=redis
CACHE_REDIS_URL=redis://localhost:6379/1
CACHE_DEFAULT_TIMEOUT=600

# Security
ALLOWED_ORIGINS=https://pdfsmaller.site,https://www.pdfsmaller.site
SECURITY_HEADERS_ENABLED=true
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STORAGE_URL=redis://localhost:6379/2
RATE_LIMIT_DEFAULT=1000 per hour

# Logging
LOG_LEVEL=WARNING
LOG_FILE=/var/log/pdfsmaller/app.log
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5

# Stripe (Live Keys)
STRIPE_PUBLISHABLE_KEY=pk_live_your_live_publishable_key
STRIPE_SECRET_KEY=sk_live_your_live_secret_key
STRIPE_WEBHOOK_SECRET=whsec_your_live_webhook_secret
STRIPE_API_VERSION=2023-10-16

# Email
MAIL_SERVER=smtp.your-provider.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@domain.com
MAIL_PASSWORD=your-email-password
MAIL_DEFAULT_SENDER=noreply@pdfsmaller.site

# JWT
JWT_ACCESS_TOKEN_MINUTES=15
JWT_REFRESH_TOKEN_DAYS=7

# Monitoring
HEALTH_CHECK_ENABLED=true
METRICS_ENABLED=true
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
```

## Security Considerations

### Secret Key Generation

Generate secure secret keys:

```bash
# Generate SECRET_KEY
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(64))"

# Generate JWT_SECRET_KEY (should be different from SECRET_KEY)
python -c "import secrets; print('JWT_SECRET_KEY=' + secrets.token_urlsafe(64))"
```

### Environment File Security

1. **File Permissions:**
   ```bash
   chmod 600 .env.production
   chown pdfsmaller:pdfsmaller .env.production
   ```

2. **Git Ignore:**
   ```bash
   # Add to .gitignore
   .env*
   !.env.example
   ```

3. **Backup Security:**
   ```bash
   # Encrypt sensitive backups
   gpg --symmetric --cipher-algo AES256 .env.production
   ```

### Production Security Checklist

- [ ] Use strong, unique secret keys (64+ characters)
- [ ] Use PostgreSQL instead of SQLite
- [ ] Enable HTTPS with valid SSL certificates
- [ ] Configure proper CORS origins (no wildcards)
- [ ] Use live Stripe keys (not test keys)
- [ ] Enable security headers
- [ ] Set up proper file permissions
- [ ] Configure firewall rules
- [ ] Enable rate limiting
- [ ] Use secure Redis configuration
- [ ] Set up monitoring and alerting
- [ ] Regular security updates

## Validation and Testing

### Configuration Validation Script

Create `validate_config.py`:
```python
#!/usr/bin/env python3
"""Configuration validation script"""

import os
import sys
from urllib.parse import urlparse

def validate_config():
    """Validate environment configuration"""
    errors = []
    warnings = []
    
    # Required variables
    required_vars = [
        'SECRET_KEY',
        'DATABASE_URL',
        'REDIS_URL',
        'CELERY_BROKER_URL'
    ]
    
    for var in required_vars:
        if not os.environ.get(var):
            errors.append(f"Missing required variable: {var}")
    
    # Secret key validation
    secret_key = os.environ.get('SECRET_KEY', '')
    if len(secret_key) < 32:
        errors.append("SECRET_KEY must be at least 32 characters long")
    
    jwt_secret = os.environ.get('JWT_SECRET_KEY', '')
    if jwt_secret == secret_key:
        warnings.append("JWT_SECRET_KEY should be different from SECRET_KEY")
    
    # Database URL validation
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url:
        parsed = urlparse(db_url)
        if not parsed.scheme:
            errors.append("Invalid DATABASE_URL format")
        elif parsed.scheme == 'sqlite' and os.environ.get('FLASK_ENV') == 'production':
            warnings.append("SQLite not recommended for production")
    
    # Redis URL validation
    redis_url = os.environ.get('REDIS_URL', '')
    if redis_url:
        parsed = urlparse(redis_url)
        if parsed.scheme != 'redis':
            errors.append("Invalid REDIS_URL format")
    
    # Stripe validation for production
    if os.environ.get('FLASK_ENV') == 'production':
        stripe_vars = ['STRIPE_SECRET_KEY', 'STRIPE_PUBLISHABLE_KEY', 'STRIPE_WEBHOOK_SECRET']
        for var in stripe_vars:
            value = os.environ.get(var, '')
            if not value:
                warnings.append(f"Missing Stripe variable: {var}")
            elif var == 'STRIPE_SECRET_KEY' and value.startswith('sk_test_'):
                errors.append("Using test Stripe key in production")
    
    # File permissions
    upload_folder = os.environ.get('UPLOAD_FOLDER', '/tmp/pdf_uploads')
    if not os.path.exists(upload_folder):
        warnings.append(f"Upload folder does not exist: {upload_folder}")
    elif not os.access(upload_folder, os.W_OK):
        errors.append(f"Upload folder is not writable: {upload_folder}")
    
    # Print results
    if errors:
        print("❌ Configuration Errors:")
        for error in errors:
            print(f"  - {error}")
    
    if warnings:
        print("⚠️  Configuration Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    
    if not errors and not warnings:
        print("✅ Configuration is valid")
    
    return len(errors) == 0

if __name__ == '__main__':
    # Load environment file if specified
    if len(sys.argv) > 1:
        env_file = sys.argv[1]
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    if '=' in line and not line.startswith('#'):
                        key, value = line.strip().split('=', 1)
                        os.environ[key] = value
    
    valid = validate_config()
    sys.exit(0 if valid else 1)
```

### Usage Examples

```bash
# Validate current environment
python validate_config.py

# Validate specific environment file
python validate_config.py .env.production

# Validate in CI/CD pipeline
python validate_config.py .env.production || exit 1
```

### Testing Configuration

Create test script `test_config.py`:
```python
#!/usr/bin/env python3
"""Test configuration loading"""

import os
import tempfile
from src.config.config import Config, DevelopmentConfig, ProductionConfig

def test_config_loading():
    """Test configuration loading with different environments"""
    
    # Test development config
    os.environ['FLASK_ENV'] = 'development'
    config = Config.get_config()
    assert isinstance(config, DevelopmentConfig)
    assert config.DEBUG is True
    
    # Test production config
    os.environ['FLASK_ENV'] = 'production'
    config = Config.get_config()
    assert isinstance(config, ProductionConfig)
    assert config.DEBUG is False
    
    print("✅ Configuration loading tests passed")

def test_database_connection():
    """Test database connection"""
    from src.models.base import db
    from src.main.main import create_app
    
    app = create_app()
    with app.app_context():
        try:
            db.session.execute('SELECT 1')
            print("✅ Database connection successful")
        except Exception as e:
            print(f"❌ Database connection failed: {e}")
            return False
    return True

def test_redis_connection():
    """Test Redis connection"""
    import redis
    from src.config.config import Config
    
    try:
        r = redis.from_url(Config.REDIS_URL)
        r.ping()
        print("✅ Redis connection successful")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

if __name__ == '__main__':
    test_config_loading()
    test_database_connection()
    test_redis_connection()
```

This comprehensive environment configuration guide should help you properly configure the PDF Smaller backend for any deployment scenario while maintaining security and performance best practices.