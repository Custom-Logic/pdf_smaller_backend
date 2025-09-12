# Security Guide

## Overview

This guide covers the comprehensive security measures implemented in the PDF Smaller Backend API. The security architecture follows defense-in-depth principles with multiple layers of protection.

## Table of Contents

1. [Security Architecture](#security-architecture)
2. [Authentication & Authorization](#authentication--authorization)
3. [Input Validation & Sanitization](#input-validation--sanitization)
4. [Rate Limiting](#rate-limiting)
5. [File Security](#file-security)
6. [Network Security](#network-security)
7. [Security Headers](#security-headers)
8. [Threat Detection](#threat-detection)
9. [Security Logging](#security-logging)
10. [CORS Configuration](#cors-configuration)
11. [Security Best Practices](#security-best-practices)
12. [Vulnerability Prevention](#vulnerability-prevention)
13. [Security Testing](#security-testing)
14. [Incident Response](#incident-response)

## Security Architecture

### Multi-Layer Security Model

```
┌─────────────────────────────────────────┐
│              Client Layer               │
├─────────────────────────────────────────┤
│         Network Security Layer          │
│  • HTTPS/TLS • CORS • Security Headers │
├─────────────────────────────────────────┤
│        Application Security Layer       │
│  • Rate Limiting • Input Validation    │
├─────────────────────────────────────────┤
│         Service Security Layer          │
│  • File Validation • Threat Detection  │
├─────────────────────────────────────────┤
│          Data Security Layer            │
│  • Secure Storage • Logging • Audit    │
└─────────────────────────────────────────┘
```

### Core Security Components

- **SecurityMiddleware**: Request/response security processing
- **TieredRateLimiter**: Advanced rate limiting with user tiers
- **FileValidator**: Comprehensive file security scanning
- **ThreatDetector**: Real-time threat detection and blocking
- **SecurityLogger**: Centralized security event logging

## Authentication & Authorization

### Current Implementation

**Note**: Based on the codebase analysis, user authentication has been identified as "dead weight" and is not implemented in the core API. The backend focuses solely on PDF processing functionality.

### Security Tokens

```python
# Generate security tokens for CSRF protection
from src.utils.security_utils import generate_security_token, validate_csrf_token

# Generate token
token = generate_security_token()

# Validate token
is_valid = validate_csrf_token(received_token, expected_token)
```

## Input Validation & Sanitization

### Request Data Sanitization

```python
from src.utils.security_utils import sanitize_request_data
from src.utils.validation import sanitize_input, sanitize_filename

# Sanitize request data
clean_data = sanitize_request_data(request_data)

# Sanitize individual inputs
clean_text = sanitize_input(user_input)
clean_filename = sanitize_filename(filename)
```

### Validation Rules

- **XSS Prevention**: HTML/JavaScript content stripped
- **SQL Injection Prevention**: Parameterized queries and input sanitization
- **Path Traversal Prevention**: Filename sanitization
- **File Type Validation**: Strict PDF-only policy
- **Size Limits**: 100MB maximum file size

### Implementation Example

```python
# File validation with security checks
def validate_upload(file):
    # Basic validation
    if not file or file.filename == '':
        return 'No file selected'
    
    # Extension validation
    if not file.filename.lower().endswith('.pdf'):
        return 'Only PDF files allowed'
    
    # Size validation
    if file_size > 100 * 1024 * 1024:
        return 'File too large'
    
    # Content validation
    validation_result = validate_file_content(file_data, filename)
    if not validation_result['valid']:
        return 'File validation failed'
```

## Rate Limiting

### Tiered Rate Limiting System

The system implements sophisticated rate limiting with different tiers:

#### Rate Limit Tiers

| Tier | Compression/min | Compression/hour | API/min | API/hour |
|------|----------------|------------------|---------|----------|
| Anonymous | 1 | 5 | 10 | 50 |
| Free | 2 | 10 | 30 | 200 |
| Premium | 10 | 100 | 100 | 1000 |
| Pro | 50 | 1000 | 500 | 5000 |

#### Implementation

```python
from src.utils.rate_limiter import (
    compression_rate_limit,
    auth_rate_limit,
    api_rate_limit
)

# Apply rate limiting to endpoints
@app.route('/api/compress')
@compression_rate_limit
def compress_pdf():
    # Compression logic
    pass

@app.route('/api/auth/login')
@auth_rate_limit
def login():
    # Authentication logic
    pass
```

#### Rate Limit Headers

The system adds standard rate limit headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
X-RateLimit-Retry-After: 60
```

## File Security

### Multi-Layer File Validation

1. **Basic Validation**
   - File presence check
   - Extension validation (.pdf only)
   - Size limits (100MB max)
   - Empty file detection

2. **Content Analysis**
   - MIME type verification
   - PDF structure validation
   - Malicious content detection
   - Embedded script detection

3. **Security Scanning**
   - Hash-based malware detection
   - Suspicious pattern analysis
   - Threat intelligence integration

### PDF Security Checks

```python
from src.utils.validation import check_pdf_security

# Comprehensive PDF security analysis
warnings = check_pdf_security(pdf_data)

# Check for:
# - Password protection
# - Embedded JavaScript
# - Form fields
# - External references
# - Suspicious metadata
```

### File Hash Tracking

```python
# Track malicious files
THREAT_TRACKING = {
    'malicious_files': set(),  # Known bad file hashes
    'suspicious_ips': {},      # IPs with suspicious activity
    'blocked_ips': set()       # Permanently blocked IPs
}
```

## Network Security

### HTTPS Enforcement

```python
from src.utils.security_middleware import require_https

@app.route('/sensitive-endpoint')
@require_https
def sensitive_operation():
    # HTTPS-only endpoint
    pass
```

### IP-Based Security

- **Client IP Detection**: X-Forwarded-For header parsing
- **Geolocation Filtering**: Optional country-based restrictions
- **IP Reputation**: Integration with threat intelligence
- **Automatic Blocking**: Suspicious IPs automatically blocked

## Security Headers

### Comprehensive Header Set

```python
# Security headers automatically added
SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'X-XSS-Protection': '1; mode=block',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
    'Content-Security-Policy': "default-src 'self'",
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'geolocation=(), microphone=(), camera=()'
}
```

### Content Security Policy (CSP)

```
default-src 'self';
script-src 'self' 'unsafe-inline';
style-src 'self' 'unsafe-inline';
img-src 'self' data:;
font-src 'self';
connect-src 'self';
frame-ancestors 'none';
```

## Threat Detection

### Real-Time Monitoring

```python
# Suspicious activity tracking
def track_suspicious_activity(activity_type, details):
    client_ip = get_client_ip()
    
    # Track by IP
    if client_ip not in THREAT_TRACKING['suspicious_ips']:
        THREAT_TRACKING['suspicious_ips'][client_ip] = []
    
    # Add activity record
    THREAT_TRACKING['suspicious_ips'][client_ip].append({
        'type': activity_type,
        'details': details,
        'timestamp': datetime.utcnow()
    })
    
    # Auto-block if threshold exceeded
    if len(THREAT_TRACKING['suspicious_ips'][client_ip]) > 10:
        THREAT_TRACKING['blocked_ips'].add(client_ip)
```

### Threat Categories

- **Suspicious User Agents**: Bot detection, scanner identification
- **Invalid Origins**: CORS violation attempts
- **Malicious Files**: Known bad file uploads
- **Rate Limit Violations**: Excessive request patterns
- **Authentication Failures**: Brute force attempts
- **Path Traversal**: Directory traversal attempts
- **XSS Attempts**: Cross-site scripting injection
- **SQL Injection**: Database attack attempts

## Security Logging

### Centralized Security Events

```python
from src.utils.security_utils import log_security_event

# Log security events with context
log_security_event('file_upload_blocked', {
    'filename': filename,
    'reason': 'malicious_content',
    'client_ip': client_ip,
    'user_agent': user_agent
}, severity='WARNING')
```

### Log Categories

- **INFO**: Normal security operations
- **WARNING**: Suspicious but not blocked activity
- **ERROR**: Security violations and blocks
- **CRITICAL**: Severe security incidents

### Sensitive Data Protection

```python
# Automatic sanitization of logs
from src.utils.logging_system import sanitize_for_logging

# Masks passwords, tokens, keys automatically
sanitized_data = sanitize_for_logging(request_data)
```

## CORS Configuration

### Secure CORS Setup

```python
from src.utils.cors_config import configure_secure_cors

# Allowed origins (no wildcards in production)
ALLOWED_ORIGINS = [
    'https://pdfsmaller.site',
    'https://www.pdfsmaller.site'
]

# Configure CORS with security
cors = configure_secure_cors(app)
```

### CORS Security Features

- **Origin Validation**: Strict whitelist enforcement
- **Credential Support**: Secure cookie handling
- **Method Restrictions**: Limited HTTP methods
- **Header Controls**: Restricted custom headers
- **Preflight Caching**: Optimized preflight responses

## Security Best Practices

### Development Guidelines

1. **Input Validation**
   ```python
   # Always validate and sanitize inputs
   @validate_request_data(['filename', 'compression_level'])
   def process_request(data):
       # Safe to use validated data
       pass
   ```

2. **Error Handling**
   ```python
   # Don't expose internal details
   try:
       process_file()
   except Exception as e:
       logger.error(f"Processing error: {str(e)}")
       return {'error': 'Processing failed'}, 500
   ```

3. **Secure Configuration**
   ```python
   # Use environment variables for secrets
   SECRET_KEY = os.environ.get('SECRET_KEY')
   if not SECRET_KEY or len(SECRET_KEY) < 32:
       raise ConfigurationError("Invalid secret key")
   ```

### Deployment Security

1. **Environment Separation**
   - Development: Relaxed security for testing
   - Staging: Production-like security
   - Production: Maximum security enforcement

2. **Secret Management**
   - Use environment variables
   - Rotate secrets regularly
   - Never commit secrets to version control

3. **Network Security**
   - Use HTTPS everywhere
   - Configure proper firewall rules
   - Implement network segmentation

## Vulnerability Prevention

### Common Attack Vectors

#### Cross-Site Scripting (XSS)
```python
# Prevention through input sanitization
from src.utils.validation import sanitize_input

clean_input = sanitize_input(user_input)
# Removes <script>, javascript:, on* attributes
```

#### SQL Injection
```python
# Use parameterized queries
from sqlalchemy import text

# Safe query
result = db.session.execute(
    text("SELECT * FROM users WHERE id = :user_id"),
    {'user_id': user_id}
)
```

#### Path Traversal
```python
# Secure filename handling
from src.utils.validation import sanitize_filename

safe_filename = sanitize_filename(uploaded_filename)
# Removes ../, \, and other dangerous patterns
```

#### File Upload Attacks
```python
# Comprehensive file validation
def secure_file_upload(file):
    # 1. Extension validation
    if not file.filename.lower().endswith('.pdf'):
        raise SecurityError("Invalid file type")
    
    # 2. Content validation
    if not validate_pdf_structure(file):
        raise SecurityError("Invalid PDF structure")
    
    # 3. Malware scanning
    if is_malicious_file(file):
        raise SecurityError("Malicious file detected")
```

### Security Headers Implementation

```python
# Automatic security header injection
@app.after_request
def add_security_headers(response):
    headers = get_security_headers()
    for header, value in headers.items():
        response.headers[header] = value
    return response
```

## Security Testing

### Automated Security Tests

```python
# Security test examples
class TestSecurity:
    def test_xss_prevention(self):
        malicious_input = '<script>alert("xss")</script>'
        clean_input = sanitize_input(malicious_input)
        assert '<script>' not in clean_input
    
    def test_file_upload_security(self):
        # Test malicious file rejection
        with open('malicious.pdf', 'rb') as f:
            result = validate_file(f)
            assert 'blocked' in result.lower()
    
    def test_rate_limiting(self):
        # Test rate limit enforcement
        for i in range(100):
            response = client.post('/api/compress')
        assert response.status_code == 429
```

### Security Audit Checklist

- [ ] Input validation on all endpoints
- [ ] Rate limiting configured
- [ ] Security headers present
- [ ] HTTPS enforced
- [ ] File upload restrictions
- [ ] Error handling doesn't leak info
- [ ] Logging captures security events
- [ ] CORS properly configured
- [ ] Dependencies up to date
- [ ] Security tests passing

## Incident Response

### Threat Detection Response

1. **Automatic Blocking**
   ```python
   # Immediate IP blocking for severe threats
   if threat_level == 'CRITICAL':
       THREAT_TRACKING['blocked_ips'].add(client_ip)
       log_security_event('ip_blocked', {
           'ip': client_ip,
           'reason': 'critical_threat'
       }, 'CRITICAL')
   ```

2. **Alert Generation**
   ```python
   # Send alerts for security incidents
   if security_incident_detected():
       send_security_alert({
           'type': 'security_breach',
           'severity': 'HIGH',
           'details': incident_details
       })
   ```

### Manual Response Procedures

1. **IP Blocking**
   ```bash
   # Block malicious IP
   redis-cli SADD blocked_ips "192.168.1.100"
   ```

2. **File Hash Blocking**
   ```bash
   # Block malicious file hash
   redis-cli SADD malicious_files "sha256hash"
   ```

3. **Emergency Shutdown**
   ```bash
   # Emergency service shutdown
   sudo systemctl stop pdfsmaller
   ```

### Recovery Procedures

1. **Assess Damage**
   - Review security logs
   - Check for data breaches
   - Identify affected systems

2. **Contain Threat**
   - Block malicious IPs
   - Remove malicious files
   - Update security rules

3. **Restore Service**
   - Apply security patches
   - Update configurations
   - Restart services

4. **Post-Incident**
   - Document incident
   - Update security measures
   - Conduct security review

## Configuration Reference

### Security Environment Variables

```bash
# Core security settings
SECRET_KEY=your-64-character-secret-key
SECURITY_HEADERS_ENABLED=true
RATE_LIMIT_ENABLED=true
CORS_ORIGINS=https://yourdomain.com

# File security
MAX_FILE_SIZE=104857600  # 100MB
ALLOWED_EXTENSIONS=pdf
MALWARE_SCANNING_ENABLED=true

# Threat detection
THREAT_DETECTION_ENABLED=true
AUTO_BLOCK_THRESHOLD=10
SUSPICIOUS_IP_TRACKING=true

# Logging
SECURITY_LOG_LEVEL=INFO
LOG_SENSITIVE_DATA=false
SECURITY_AUDIT_ENABLED=true
```

### Redis Security Configuration

```bash
# Redis security settings
REDIS_URL=redis://localhost:6379/0
REDIS_PASSWORD=your-redis-password
REDIS_SSL=true
REDIS_SSL_CERT_REQS=required
```

## Monitoring and Alerting

### Security Metrics

- **Blocked Requests**: Rate limit violations
- **Suspicious Activity**: Threat detection events
- **File Rejections**: Malicious file uploads
- **Authentication Failures**: Login attempt monitoring
- **Error Rates**: Security-related errors

### Alert Conditions

```python
# Configure security alerts
ALERT_THRESHOLDS = {
    'blocked_requests_per_hour': 100,
    'suspicious_ips_per_day': 50,
    'malicious_files_per_hour': 10,
    'security_errors_per_minute': 5
}
```

---

**Last Updated**: 2024-01-10  
**Version**: 1.0  
**Maintainer**: Security Team  
**Review Schedule**: Monthly

**Note**: This security guide reflects the current implementation focused on core PDF processing functionality without user authentication. All security measures are designed to protect the backend API and ensure safe file processing operations.
