# Environment Configuration Guide

This guide covers all environment variables and configuration options for the PDF Smaller backend service.

## Table of Contents

1. [Configuration Overview](#configuration-overview)
2. [Environment Variables Reference](#environment-variables-reference)
3. [Environment-Specific Configurations](#environment-specific-configurations)
4. [Security Considerations](#security-considerations)
5. [Validation and Testing](#validation-and-testing)

## Configuration Overview

### Configuration Hierarchy

The application loads configuration in the following order:
1. Default values from config classes
2. Environment variables from `.env` files
3. System environment variables (highest priority)

### Environment Selection

The application environment is determined by the `FLASK_ENV` variable:
- `development` - Development environment with debug features
- `production` - Production environment with optimizations
- `testing` - Testing environment with test-specific settings

## Environment Variables Reference

### Core Application Settings

| Variable | Default | Description | Example |
|----------|---------|-------------|----------|
| `FLASK_ENV` | `development` | Application environment | `production` |
| `SECRET_KEY` | *Required* | Flask secret key for sessions | `your-secret-key-here` |
| `DEBUG` | `false` | Enable debug mode | `true` |
| `HOST` | `127.0.0.1` | Server host address | `0.0.0.0` |
| `PORT` | `5000` | Server port | `8080` |

### Database Configuration

| Variable | Default | Description | Example |
|----------|---------|-------------|----------|
| `DATABASE_URL` | `sqlite:///pdf_smaller.db` | Database connection URL | `sqlite:///data/app.db` |
| `DB_POOL_SIZE` | `10` | Database connection pool size | `20` |
| `DB_MAX_OVERFLOW` | `20` | Max overflow connections | `30` |
| `DB_POOL_RECYCLE` | `3600` | Connection recycle time (seconds) | `7200` |
| `DB_POOL_TIMEOUT` | `30` | Connection timeout (seconds) | `60` |
| `DB_POOL_PRE_PING` | `true` | Enable connection pre-ping | `false` |

### File Storage

| Variable | Default | Description | Example |
|----------|---------|-------------|----------|
| `UPLOAD_FOLDER` | `./uploads` | Directory for uploaded files | `/var/app/uploads` |
| `MAX_FILE_SIZE` | `52428800` | Max file size in bytes (50MB) | `104857600` |
| `MAX_CONTENT_LENGTH` | `52428800` | Max request content length | `104857600` |
| `MAX_FILE_AGE_HOURS` | `24` | Hours before file cleanup | `1` |
| `CLEANUP_ENABLED` | `true` | Enable automatic file cleanup | `false` |

### Redis and Caching

| Variable | Default | Description | Example |
|----------|---------|-------------|----------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL | `redis://redis:6379/0` |
| `CACHE_TYPE` | `redis` | Cache backend type | `simple` |
| `CACHE_REDIS_URL` | `redis://localhost:6379/1` | Cache Redis URL | `redis://redis:6379/1` |
| `CACHE_DEFAULT_TIMEOUT` | `300` | Default cache timeout (seconds) | `600` |

### Celery Background Processing

| Variable | Default | Description | Example |
|----------|---------|-------------|----------|
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery broker URL | `redis://redis:6379/0` |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` | Celery result backend | `redis://redis:6379/0` |
| `CELERY_TIMEZONE` | `UTC` | Celery timezone | `America/New_York` |
| `CELERY_WORKER_CONCURRENCY` | `2` | Worker process count | `4` |
| `CELERY_WORKER_LOG_LEVEL` | `INFO` | Worker log level | `WARNING` |
| `CELERY_TASK_SOFT_TIME_LIMIT` | `300` | Soft task timeout (seconds) | `600` |
| `CELERY_TASK_TIME_LIMIT` | `600` | Hard task timeout (seconds) | `1200` |
| `CELERY_TASK_ALWAYS_EAGER` | `false` | Execute tasks synchronously | `true` |

### Security and CORS

| Variable | Default | Description | Example |
|----------|---------|-------------|----------|
| `ALLOWED_ORIGINS` | `*` | CORS allowed origins | `https://example.com` |
| `SECURITY_HEADERS_ENABLED` | `true` | Enable security headers | `false` |
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting | `false` |
| `RATE_LIMIT_STORAGE_URL` | `redis://localhost:6379/2` | Rate limit storage | `memory://` |
| `RATE_LIMIT_DEFAULT` | `100 per hour` | Default rate limit | `1000 per hour` |
| `WTF_CSRF_ENABLED` | `true` | Enable CSRF protection | `false` |

### Logging Configuration

| Variable | Default | Description | Example |
|----------|---------|-------------|----------|
| `LOG_LEVEL` | `INFO` | Logging level | `DEBUG` |
| `LOG_FILE` | `app.log` | Log file path | `/var/log/app.log` |
| `LOG_MAX_BYTES` | `10485760` | Max log file size (10MB) | `52428800` |
| `LOG_BACKUP_COUNT` | `3` | Number of backup log files | `5` |

### Monitoring and Health Checks

| Variable | Default | Description | Example |
|----------|---------|-------------|----------|
| `HEALTH_CHECK_ENABLED` | `true` | Enable health check endpoint | `false` |
| `METRICS_ENABLED` | `false` | Enable metrics collection | `true` |
| `SENTRY_DSN` | `None` | Sentry error tracking DSN | `https://...@sentry.io/...` |

### AI Configuration (OpenRouter)

| Variable | Default | Description | Example |
|----------|---------|-------------|----------|
| `OPENROUTER_API_KEY` | *Required* | OpenRouter API key for AI services | `sk-or-v1-...` |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter API base URL | `https://openrouter.ai/api/v1` |
| `OPENROUTER_DEFAULT_MODEL` | `deepseek/deepseek-v3-free` | Default AI model for processing | `moonshot/moonshot-k2-premium` |
| `OPENROUTER_MAX_TOKENS` | `4000` | Maximum tokens per AI request | `8000` |
| `OPENROUTER_TIMEOUT` | `30` | API request timeout (seconds) | `60` |
| `OPENROUTER_REFERER` | `https://www.pdfsmaller.site` | HTTP referer for API requests | `https://yourdomain.com` |
| `OPENROUTER_TITLE` | `PDF Smaller` | Application title for API requests | `Your App Name` |

**Available Models:**
- **DeepSeek V3**: `deepseek/deepseek-v3`, `deepseek/deepseek-v3-free`, `deepseek/deepseek-chat`, `deepseek/deepseek-coder`, `deepseek/deepseek-r1`
- **Moonshot K2**: `moonshot/moonshot-k2-free`, `moonshot/moonshot-k2-premium`, `moonshot/moonshot-v1-8k`, `moonshot/moonshot-v1-32k`, `moonshot/moonshot-v1-128k`
- **OpenAI**: `openai/gpt-4-turbo`, `openai/gpt-4`, `openai/gpt-3.5-turbo`
- **Anthropic**: `anthropic/claude-3-opus`, `anthropic/claude-3-sonnet`, `anthropic/claude-3-haiku`
- **Other**: `google/gemini-pro`, `mistral/mistral-large`, `meta/llama-3-70b`

## Environment-Specific Configurations

### Development Environment

Create `.env.development`:
```bash
# Application
FLASK_ENV=development
SECRET_KEY=dev-secret-key-change-in-production
DEBUG=true
HOST=127.0.0.1
PORT=5000

# Database
DATABASE_URL=sqlite:///pdf_smaller_dev.db

# File Storage
UPLOAD_FOLDER=./uploads/dev
MAX_FILE_SIZE=52428800  # 50MB
MAX_FILE_AGE_HOURS=24
CLEANUP_ENABLED=false

# Redis & Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_WORKER_CONCURRENCY=2
CELERY_WORKER_LOG_LEVEL=DEBUG

# Caching
CACHE_TYPE=redis
CACHE_REDIS_URL=redis://localhost:6379/1
CACHE_DEFAULT_TIMEOUT=300

# Security (Relaxed for development)
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
SECURITY_HEADERS_ENABLED=false
RATE_LIMIT_ENABLED=false

# Logging
LOG_LEVEL=DEBUG
LOG_FILE=dev.log

# Monitoring
HEALTH_CHECK_ENABLED=true
METRICS_ENABLED=false

# AI Configuration (OpenRouter)
OPENROUTER_API_KEY=your-openrouter-api-key-here
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_DEFAULT_MODEL=deepseek/deepseek-v3-free
OPENROUTER_MAX_TOKENS=4000
OPENROUTER_TIMEOUT=30
OPENROUTER_REFERER=http://localhost:3000
OPENROUTER_TITLE=PDF Smaller Dev
```

### Testing Environment

Create `.env.testing`:
```bash
# Application
FLASK_ENV=testing
SECRET_KEY=test-secret-key-for-testing-only
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

# Monitoring
HEALTH_CHECK_ENABLED=true
METRICS_ENABLED=false

# AI Configuration (OpenRouter) - Use test API key or mock
OPENROUTER_API_KEY=test-api-key-or-mock
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_DEFAULT_MODEL=deepseek/deepseek-v3-free
OPENROUTER_MAX_TOKENS=1000
OPENROUTER_TIMEOUT=10
OPENROUTER_REFERER=http://localhost:3000
OPENROUTER_TITLE=PDF Smaller Test
```

### Production Environment

Create `.env.production`:
```bash
# Application
FLASK_ENV=production
SECRET_KEY=your-super-secure-64-character-production-secret-key-here
DEBUG=false
HOST=0.0.0.0
PORT=5000

# Database
DATABASE_URL=sqlite:///data/pdf_smaller_prod.db
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

# Monitoring
HEALTH_CHECK_ENABLED=true
METRICS_ENABLED=true
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id

# AI Configuration (OpenRouter)
OPENROUTER_API_KEY=your-production-openrouter-api-key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_DEFAULT_MODEL=deepseek/deepseek-v3-free
OPENROUTER_MAX_TOKENS=4000
OPENROUTER_TIMEOUT=30
OPENROUTER_REFERER=https://www.pdfsmaller.site
OPENROUTER_TITLE=PDF Smaller
```

## Security Considerations

### Secret Key Generation

Generate secure secret keys:

```bash
# Generate SECRET_KEY
python -c "import secrets; print('SECRET_KEY=' + secrets.token_urlsafe(64))"
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
- [ ] Use SQLite with proper file permissions or external database
- [ ] Enable HTTPS with valid SSL certificates
- [ ] Configure proper CORS origins (no wildcards)
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
    
    # Database URL validation
    db_url = os.environ.get('DATABASE_URL', '')
    if db_url:
        parsed = urlparse(db_url)
        if not parsed.scheme:
            errors.append("Invalid DATABASE_URL format")
    
    # Redis URL validation
    redis_url = os.environ.get('REDIS_URL', '')
    if redis_url:
        parsed = urlparse(redis_url)
        if parsed.scheme != 'redis':
            errors.append("Invalid REDIS_URL format")
    
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

This environment configuration guide provides all the necessary settings for deploying and running the PDF Smaller backend service in different environments while maintaining security and performance best practices.