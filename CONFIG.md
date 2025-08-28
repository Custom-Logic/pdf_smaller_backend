# Configuration Guide

This document describes the configuration system for the PDF Smaller backend application.

## Overview

The application uses a hierarchical configuration system with environment-specific settings:

- **BaseConfig**: Common configuration shared across all environments
- **DevelopmentConfig**: Settings optimized for local development
- **TestingConfig**: Settings for running tests
- **ProductionConfig**: Settings for production deployment

## Environment Selection

The configuration is automatically selected based on the `FLASK_ENV` environment variable:

```bash
export FLASK_ENV=development  # Uses DevelopmentConfig
export FLASK_ENV=testing      # Uses TestingConfig  
export FLASK_ENV=production   # Uses ProductionConfig
```

If `FLASK_ENV` is not set, `DevelopmentConfig` is used by default.

## Configuration Categories

### Basic Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | Auto-generated | Flask secret key for sessions and CSRF |
| `MAX_CONTENT_LENGTH` | 100MB | Maximum request size |

### Database Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///pdf_smaller.db` | Database connection URL |
| `DB_POOL_RECYCLE` | 300 | Database connection pool recycle time (seconds) |
| `DB_POOL_TIMEOUT` | 20 | Database connection timeout (seconds) |
| `DB_MAX_OVERFLOW` | 0 | Maximum database connection overflow |

### JWT Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | Same as SECRET_KEY | JWT signing key |
| `JWT_ACCESS_TOKEN_MINUTES` | 15 | Access token expiration (minutes) |
| `JWT_REFRESH_TOKEN_DAYS` | 7 | Refresh token expiration (days) |
| `JWT_ALGORITHM` | HS256 | JWT signing algorithm |

### File Handling

| Variable | Default | Description |
|----------|---------|-------------|
| `UPLOAD_FOLDER` | `/tmp/pdf_uploads` | Directory for uploaded files |
| `MAX_FILE_AGE_HOURS` | 1 | How long to keep files (hours) |
| `MAX_FILE_SIZE` | 50MB | Maximum individual file size |
| `DEFAULT_COMPRESSION_LEVEL` | medium | Default PDF compression level |

### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `ALLOWED_ORIGINS` | `http://localhost:3000,https://pdfsmaller.site` | CORS allowed origins |

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection for rate limiting |
| `RATE_LIMIT_STRATEGY` | fixed-window | Rate limiting strategy |
| `RATE_LIMIT_DEFAULT` | 100 per hour | Default rate limit |

### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | INFO | Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |
| `LOG_FILE` | app.log | Log file path |
| `LOG_FORMAT` | Standard format | Log message format |
| `LOG_MAX_BYTES` | 10MB | Maximum log file size |
| `LOG_BACKUP_COUNT` | 5 | Number of log file backups |

### Payment Processing (Stripe)

| Variable | Default | Description |
|----------|---------|-------------|
| `STRIPE_PUBLISHABLE_KEY` | None | Stripe publishable key |
| `STRIPE_SECRET_KEY` | None | Stripe secret key |
| `STRIPE_WEBHOOK_SECRET` | None | Stripe webhook endpoint secret |
| `STRIPE_API_VERSION` | 2023-10-16 | Stripe API version |

### Task Queue (Celery)

| Variable | Default | Description |
|----------|---------|-------------|
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` | Celery message broker |
| `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` | Celery result backend |
| `CELERY_TIMEZONE` | UTC | Celery timezone |

### Email (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `MAIL_SERVER` | None | SMTP server hostname |
| `MAIL_PORT` | 587 | SMTP server port |
| `MAIL_USE_TLS` | true | Use TLS for email |
| `MAIL_USERNAME` | None | SMTP username |
| `MAIL_PASSWORD` | None | SMTP password |
| `MAIL_DEFAULT_SENDER` | None | Default sender email |

### Monitoring

| Variable | Default | Description |
|----------|---------|-------------|
| `HEALTH_CHECK_ENABLED` | true | Enable health check endpoints |
| `METRICS_ENABLED` | false | Enable metrics collection |

## Environment-Specific Configurations

### Development Environment

- **Debug mode**: Enabled
- **Database**: SQLite (`pdf_smaller_dev.db`)
- **Logging**: DEBUG level
- **Security**: Relaxed (no security headers)
- **CORS**: Allows localhost origins
- **Token expiry**: Extended (60 minutes)

### Testing Environment

- **Debug mode**: Enabled
- **Testing mode**: Enabled
- **Database**: In-memory SQLite
- **CSRF**: Disabled
- **Token expiry**: Short (5 minutes)
- **Celery**: Eager execution (synchronous)
- **Stripe**: Test keys only

### Production Environment

- **Debug mode**: Disabled
- **Database**: PostgreSQL (recommended)
- **Logging**: WARNING level
- **Security**: Full security headers enabled
- **Rate limiting**: Stricter limits
- **Validation**: Additional production-specific checks

## Configuration Validation

The system includes automatic configuration validation that checks:

- Required settings are present
- Secret keys are sufficiently long and secure
- File paths are accessible
- Database connections are valid
- Log levels are valid
- Compression levels are valid

### Running Validation

```python
from src.config.config import validate_current_config

try:
    validate_current_config()
    print("Configuration is valid")
except ConfigValidationError as e:
    print(f"Configuration error: {e}")
```

## Subscription Plans Configuration

The system includes built-in subscription plan configurations:

### Free Plan
- **Price**: $0
- **Compressions**: 10 per day
- **Max file size**: 10MB
- **Bulk processing**: No
- **Priority processing**: No

### Premium Plan
- **Price**: $9.99/month
- **Compressions**: 500 per day
- **Max file size**: 50MB
- **Bulk processing**: Yes
- **Priority processing**: No

### Pro Plan
- **Price**: $19.99/month
- **Compressions**: Unlimited
- **Max file size**: 100MB
- **Bulk processing**: Yes
- **Priority processing**: Yes

## Rate Limiting Configuration

Different rate limits apply based on user subscription tier:

### Free Users
- **Compression**: 10 per day
- **API calls**: 50 per hour
- **Authentication**: 5 per minute

### Premium Users
- **Compression**: 500 per day
- **API calls**: 1000 per hour
- **Authentication**: 10 per minute

### Pro Users
- **Compression**: 10000 per day
- **API calls**: 5000 per hour
- **Authentication**: 20 per minute

## Example Configuration Files

### Development (.env.development)

```bash
FLASK_ENV=development
SECRET_KEY=your-development-secret-key-here-make-it-long
DATABASE_URL=sqlite:///pdf_smaller_dev.db
UPLOAD_FOLDER=./uploads/dev
LOG_LEVEL=DEBUG
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
JWT_ACCESS_TOKEN_MINUTES=60
```

### Production (.env.production)

```bash
FLASK_ENV=production
SECRET_KEY=your-super-secure-production-secret-key
DATABASE_URL=postgresql://user:password@localhost/pdf_smaller_prod
UPLOAD_FOLDER=/var/app/uploads
LOG_LEVEL=WARNING
ALLOWED_ORIGINS=https://pdfsmaller.site,https://www.pdfsmaller.site
STRIPE_SECRET_KEY=sk_live_your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=whsec_your_webhook_secret
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
```

## Security Considerations

### Required for Production

1. **Set a strong SECRET_KEY**: At least 32 characters, randomly generated
2. **Use PostgreSQL**: SQLite is not recommended for production
3. **Configure Stripe properly**: Use live keys, not test keys
4. **Set up proper CORS**: Only allow your actual domain origins
5. **Use HTTPS**: Configure SSL/TLS termination
6. **Secure Redis**: Use authentication and network security
7. **File permissions**: Ensure upload folder has proper permissions

### Security Headers (Production)

The production configuration automatically includes security headers:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy: default-src 'self'`

## Troubleshooting

### Common Configuration Issues

1. **Database connection errors**: Check DATABASE_URL format and credentials
2. **File upload errors**: Verify UPLOAD_FOLDER exists and is writable
3. **JWT errors**: Ensure JWT_SECRET_KEY is set and secure
4. **Rate limiting errors**: Check Redis connection and REDIS_URL
5. **Stripe errors**: Verify API keys and webhook secrets

### Configuration Debugging

Use the configuration summary to debug issues:

```python
from src.config.config import Config

summary = Config.get_config_summary()
print(summary)
```

This will show current configuration without exposing sensitive values.