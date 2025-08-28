# PDF Smaller Backend - Troubleshooting Guide

This guide provides solutions to common issues encountered when deploying and running the PDF Smaller backend application.

## Table of Contents

1. [General Diagnostics](#general-diagnostics)
2. [Application Startup Issues](#application-startup-issues)
3. [Database Problems](#database-problems)
4. [Authentication Issues](#authentication-issues)
5. [File Processing Problems](#file-processing-problems)
6. [Celery and Background Tasks](#celery-and-background-tasks)
7. [Performance Issues](#performance-issues)
8. [Security and Rate Limiting](#security-and-rate-limiting)
9. [Deployment Issues](#deployment-issues)
10. [Monitoring and Logging](#monitoring-and-logging)

## General Diagnostics

### Quick Health Check

```bash
# Check application health
curl -f http://localhost:5000/health

# Check database health
curl -f http://localhost:5000/health/db

# Check Redis health
curl -f http://localhost:5000/health/redis

# Check all services status
sudo systemctl status pdfsmaller pdfsmaller-celery pdfsmaller-beat
```

### Log Analysis

```bash
# Application logs
tail -f /var/log/pdfsmaller/app.log

# System service logs
sudo journalctl -u pdfsmaller -f
sudo journalctl -u pdfsmaller-celery -f

# Nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log

# PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-13-main.log
```

### Configuration Validation

```bash
cd /var/app/pdfsmaller
source venv/bin/activate

# Validate configuration
python -c "
from src.config.config import validate_current_config
try:
    validate_current_config()
    print('✓ Configuration is valid')
except Exception as e:
    print(f'✗ Configuration error: {e}')
"

# Check environment variables
python -c "
import os
required_vars = ['SECRET_KEY', 'DATABASE_URL', 'REDIS_URL']
for var in required_vars:
    value = os.environ.get(var)
    if value:
        print(f'✓ {var}: {value[:20]}...')
    else:
        print(f'✗ {var}: Not set')
"
```

## Application Startup Issues

### Issue: Service Fails to Start

**Symptoms:**
- `systemctl start pdfsmaller` fails
- "Failed to start" error messages
- Service immediately exits

**Diagnosis:**
```bash
# Check service status
sudo systemctl status pdfsmaller

# Check detailed logs
sudo journalctl -u pdfsmaller --no-pager

# Test manual startup
cd /var/app/pdfsmaller
source venv/bin/activate
python app.py
```

**Common Causes & Solutions:**

1. **Missing Environment Variables**
   ```bash
   # Check .env file exists and is readable
   ls -la /var/app/pdfsmaller/.env
   
   # Verify critical variables
   grep -E "SECRET_KEY|DATABASE_URL" /var/app/pdfsmaller/.env
   ```

2. **Python Path Issues**
   ```bash
   # Verify virtual environment
   /var/app/pdfsmaller/venv/bin/python --version
   
   # Check installed packages
   /var/app/pdfsmaller/venv/bin/pip list | grep -E "flask|sqlalchemy"
   ```

3. **Port Already in Use**
   ```bash
   # Check what's using port 5000
   sudo netstat -tlnp | grep :5000
   
   # Kill conflicting process if needed
   sudo kill $(sudo lsof -t -i:5000)
   ```

### Issue: Import Errors

**Symptoms:**
- `ModuleNotFoundError` or `ImportError`
- "No module named 'src'" errors

**Solutions:**
```bash
# Reinstall dependencies
cd /var/app/pdfsmaller
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"

# Verify package structure
ls -la src/
```

### Issue: Permission Errors

**Symptoms:**
- "Permission denied" errors
- Cannot write to log files or upload directories

**Solutions:**
```bash
# Fix ownership
sudo chown -R pdfsmaller:pdfsmaller /var/app/pdfsmaller
sudo chown -R pdfsmaller:pdfsmaller /var/app/uploads
sudo chown -R pdfsmaller:pdfsmaller /var/log/pdfsmaller

# Fix permissions
chmod 755 /var/app/pdfsmaller
chmod 755 /var/app/uploads
chmod 644 /var/app/pdfsmaller/.env
```

## Database Problems

### Issue: Database Connection Failed

**Symptoms:**
- "Connection refused" errors
- "Authentication failed" errors
- Timeout errors

**Diagnosis:**
```bash
# Test PostgreSQL connection
sudo -u postgres psql -c "SELECT version();"

# Test application database connection
sudo -u postgres psql pdf_smaller_prod -c "SELECT COUNT(*) FROM users;"

# Check PostgreSQL status
sudo systemctl status postgresql
```

**Solutions:**

1. **PostgreSQL Not Running**
   ```bash
   sudo systemctl start postgresql
   sudo systemctl enable postgresql
   ```

2. **Wrong Connection String**
   ```bash
   # Check DATABASE_URL format
   echo $DATABASE_URL
   # Should be: postgresql://username:password@host:port/database
   ```

3. **Authentication Issues**
   ```bash
   # Reset user password
   sudo -u postgres psql
   ALTER USER pdf_user WITH PASSWORD 'new_secure_password';
   \q
   
   # Update .env file with new password
   ```

4. **Database Doesn't Exist**
   ```bash
   # Create database
   sudo -u postgres createdb pdf_smaller_prod
   
   # Initialize tables
   cd /var/app/pdfsmaller
   source venv/bin/activate
   python manage_db.py init
   ```

### Issue: Database Migration Errors

**Symptoms:**
- "Table already exists" errors
- "Column does not exist" errors
- Schema mismatch errors

**Solutions:**
```bash
# Check current database schema
sudo -u postgres psql pdf_smaller_prod -c "\dt"

# Reset database (⚠️ This will delete all data)
cd /var/app/pdfsmaller
source venv/bin/activate
python manage_db.py reset

# Or manually fix schema issues
sudo -u postgres psql pdf_smaller_prod
-- Add missing columns, indexes, etc.
```

### Issue: Database Performance Problems

**Symptoms:**
- Slow query responses
- High CPU usage from PostgreSQL
- Connection pool exhaustion

**Diagnosis:**
```bash
# Check active connections
sudo -u postgres psql pdf_smaller_prod -c "
SELECT count(*) as active_connections 
FROM pg_stat_activity 
WHERE state = 'active';
"

# Check slow queries
sudo -u postgres psql pdf_smaller_prod -c "
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;
"
```

**Solutions:**
```bash
# Optimize database
sudo -u postgres psql pdf_smaller_prod -c "VACUUM ANALYZE;"

# Add missing indexes
sudo -u postgres psql pdf_smaller_prod -c "
CREATE INDEX CONCURRENTLY idx_compression_jobs_user_created 
ON compression_jobs(user_id, created_at);
"

# Adjust connection pool settings in .env
echo "DB_POOL_SIZE=10" >> .env
echo "DB_MAX_OVERFLOW=20" >> .env
```

## Authentication Issues

### Issue: JWT Token Problems

**Symptoms:**
- "Invalid token" errors
- "Token expired" errors
- Authentication randomly fails

**Diagnosis:**
```bash
# Check JWT configuration
python -c "
import os
print('JWT_SECRET_KEY set:', bool(os.environ.get('JWT_SECRET_KEY')))
print('JWT_ACCESS_TOKEN_MINUTES:', os.environ.get('JWT_ACCESS_TOKEN_MINUTES', '15'))
"

# Test token generation
python -c "
from src.services.auth_service import AuthService
from src.main.main import create_app
app = create_app()
with app.app_context():
    # Test token creation (requires valid user)
    pass
"
```

**Solutions:**

1. **Missing or Weak JWT Secret**
   ```bash
   # Generate strong JWT secret
   python -c "import secrets; print(secrets.token_urlsafe(64))"
   
   # Update .env file
   echo "JWT_SECRET_KEY=your_generated_secret_here" >> .env
   ```

2. **Clock Synchronization Issues**
   ```bash
   # Check system time
   date
   
   # Sync time if needed
   sudo ntpdate -s time.nist.gov
   ```

3. **Token Expiration Too Short**
   ```bash
   # Increase token lifetime in .env
   echo "JWT_ACCESS_TOKEN_MINUTES=60" >> .env
   echo "JWT_REFRESH_TOKEN_DAYS=30" >> .env
   ```

### Issue: Password Hashing Problems

**Symptoms:**
- Login always fails with correct password
- "Invalid credentials" errors
- Password reset doesn't work

**Solutions:**
```bash
# Test password hashing
python -c "
from werkzeug.security import generate_password_hash, check_password_hash
password = 'test123'
hash_val = generate_password_hash(password)
print('Hash generated:', bool(hash_val))
print('Verification works:', check_password_hash(hash_val, password))
"

# Reset user password manually
python -c "
from src.models import User
from src.models.base import db
from src.main.main import create_app
app = create_app()
with app.app_context():
    user = User.query.filter_by(email='user@example.com').first()
    if user:
        user.set_password('newpassword123')
        db.session.commit()
        print('Password updated')
    else:
        print('User not found')
"
```

## File Processing Problems

### Issue: File Upload Failures

**Symptoms:**
- "File too large" errors
- Upload timeouts
- "Invalid file type" errors

**Diagnosis:**
```bash
# Check upload directory
ls -la /var/app/uploads/
df -h /var/app/uploads/

# Check file size limits
grep -E "MAX_FILE_SIZE|MAX_CONTENT_LENGTH" /var/app/pdfsmaller/.env

# Check Nginx limits
grep client_max_body_size /etc/nginx/sites-available/pdfsmaller
```

**Solutions:**

1. **Increase File Size Limits**
   ```bash
   # Update application limits
   echo "MAX_FILE_SIZE=104857600" >> .env  # 100MB
   echo "MAX_CONTENT_LENGTH=104857600" >> .env
   
   # Update Nginx limits
   sudo sed -i 's/client_max_body_size.*/client_max_body_size 100M;/' /etc/nginx/sites-available/pdfsmaller
   sudo systemctl reload nginx
   ```

2. **Fix Upload Directory Permissions**
   ```bash
   sudo mkdir -p /var/app/uploads
   sudo chown -R pdfsmaller:pdfsmaller /var/app/uploads
   sudo chmod 755 /var/app/uploads
   ```

3. **Free Up Disk Space**
   ```bash
   # Clean old uploads
   find /var/app/uploads -type f -mtime +1 -delete
   
   # Clean logs
   sudo logrotate -f /etc/logrotate.d/pdfsmaller
   ```

### Issue: PDF Compression Failures

**Symptoms:**
- "Ghostscript error" messages
- Compression jobs fail
- Output files are corrupted

**Diagnosis:**
```bash
# Test Ghostscript installation
gs --version

# Test basic PDF processing
gs -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -dPDFSETTINGS=/screen -dNOPAUSE -dQUIET -dBATCH -sOutputFile=test_output.pdf test_input.pdf

# Check compression service logs
grep -i "compression" /var/log/pdfsmaller/app.log
```

**Solutions:**

1. **Install/Update Ghostscript**
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install ghostscript
   
   # Verify installation
   which gs
   gs --help
   ```

2. **Fix Ghostscript Permissions**
   ```bash
   # Check Ghostscript policy
   cat /etc/ImageMagick-6/policy.xml | grep -i pdf
   
   # If PDF processing is disabled, enable it
   sudo sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml
   ```

3. **Test with Different Settings**
   ```bash
   # Test different compression levels
   python -c "
   from src.services.compression_service import CompressionService
   service = CompressionService('/tmp')
   # Test with a sample PDF file
   "
   ```

## Celery and Background Tasks

### Issue: Celery Workers Not Starting

**Symptoms:**
- No active workers
- Tasks remain in pending state
- "No workers available" errors

**Diagnosis:**
```bash
# Check Celery worker status
celery -A celery_worker.celery inspect active

# Check Redis connection
redis-cli ping

# Check worker processes
ps aux | grep celery
```

**Solutions:**

1. **Start Celery Workers**
   ```bash
   # Using systemd
   sudo systemctl start pdfsmaller-celery
   sudo systemctl status pdfsmaller-celery
   
   # Manual start for debugging
   cd /var/app/pdfsmaller
   source venv/bin/activate
   celery -A celery_worker.celery worker --loglevel=debug
   ```

2. **Fix Redis Connection**
   ```bash
   # Check Redis status
   sudo systemctl status redis-server
   
   # Test connection
   redis-cli -u $REDIS_URL ping
   
   # Restart Redis if needed
   sudo systemctl restart redis-server
   ```

3. **Clear Stuck Tasks**
   ```bash
   # Purge all tasks
   celery -A celery_worker.celery purge
   
   # Or clear specific queue
   redis-cli del celery
   ```

### Issue: Tasks Failing Silently

**Symptoms:**
- Tasks marked as successful but no output
- No error messages in logs
- Results not saved

**Diagnosis:**
```bash
# Check task results
celery -A celery_worker.celery result task_id_here

# Check worker logs
tail -f /var/log/pdfsmaller/celery-worker.log

# Inspect failed tasks
celery -A celery_worker.celery events
```

**Solutions:**

1. **Enable Detailed Logging**
   ```bash
   # Update Celery configuration
   echo "CELERY_WORKER_LOG_LEVEL=DEBUG" >> .env
   
   # Restart workers
   sudo systemctl restart pdfsmaller-celery
   ```

2. **Check Task Implementation**
   ```python
   # Test task directly
   from src.tasks.compression_tasks import process_bulk_compression
   result = process_bulk_compression.delay(job_id)
   print(result.get())
   ```

### Issue: Memory Leaks in Workers

**Symptoms:**
- Workers consuming increasing memory
- Out of memory errors
- Workers being killed by system

**Solutions:**
```bash
# Limit worker memory
echo "CELERY_WORKER_MAX_TASKS_PER_CHILD=50" >> .env
echo "CELERY_WORKER_MAX_MEMORY_PER_CHILD=200000" >> .env  # 200MB

# Reduce concurrency
echo "CELERY_WORKER_CONCURRENCY=2" >> .env

# Restart workers
sudo systemctl restart pdfsmaller-celery
```

## Performance Issues

### Issue: Slow Response Times

**Symptoms:**
- API requests taking too long
- Timeouts in frontend
- High server load

**Diagnosis:**
```bash
# Check system resources
top
htop
iotop

# Check database performance
sudo -u postgres psql pdf_smaller_prod -c "
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 5;
"

# Check application metrics
curl http://localhost:5000/metrics
```

**Solutions:**

1. **Database Optimization**
   ```sql
   -- Add missing indexes
   CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
   CREATE INDEX CONCURRENTLY idx_jobs_user_status ON compression_jobs(user_id, status);
   
   -- Update statistics
   ANALYZE;
   ```

2. **Application Tuning**
   ```bash
   # Increase Gunicorn workers
   echo "GUNICORN_WORKERS=4" >> .env
   echo "GUNICORN_WORKER_CLASS=gevent" >> .env
   
   # Enable connection pooling
   echo "DB_POOL_SIZE=20" >> .env
   echo "DB_MAX_OVERFLOW=30" >> .env
   ```

3. **Caching Implementation**
   ```bash
   # Enable Redis caching
   echo "CACHE_TYPE=redis" >> .env
   echo "CACHE_REDIS_URL=redis://localhost:6379/1" >> .env
   ```

### Issue: High Memory Usage

**Symptoms:**
- System running out of memory
- Processes being killed
- Swap usage high

**Solutions:**
```bash
# Monitor memory usage
free -h
ps aux --sort=-%mem | head -10

# Reduce worker processes
echo "GUNICORN_WORKERS=2" >> .env
echo "CELERY_WORKER_CONCURRENCY=1" >> .env

# Add swap space
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## Security and Rate Limiting

### Issue: Rate Limiting Not Working

**Symptoms:**
- Users can exceed rate limits
- No rate limit headers in responses
- Rate limiting errors in logs

**Diagnosis:**
```bash
# Check Redis connection for rate limiting
redis-cli -n 1 ping

# Test rate limiting
for i in {1..20}; do curl -I http://localhost:5000/api/auth/login; done

# Check rate limit configuration
grep -i rate /var/app/pdfsmaller/.env
```

**Solutions:**

1. **Fix Redis Configuration**
   ```bash
   # Ensure Redis is running
   sudo systemctl start redis-server
   
   # Update rate limit Redis URL
   echo "RATE_LIMIT_STORAGE_URL=redis://localhost:6379/1" >> .env
   ```

2. **Enable Rate Limiting**
   ```bash
   echo "RATE_LIMIT_ENABLED=true" >> .env
   sudo systemctl restart pdfsmaller
   ```

### Issue: CORS Errors

**Symptoms:**
- "CORS policy" errors in browser
- Cross-origin requests blocked
- OPTIONS requests failing

**Solutions:**
```bash
# Update CORS origins
echo "ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com" >> .env

# Check Nginx CORS headers
grep -A 10 "add_header.*Access-Control" /etc/nginx/sites-available/pdfsmaller

# Restart services
sudo systemctl restart pdfsmaller nginx
```

## Deployment Issues

### Issue: Docker Container Problems

**Symptoms:**
- Containers failing to start
- Build errors
- Network connectivity issues

**Diagnosis:**
```bash
# Check container status
docker-compose ps

# Check container logs
docker-compose logs app
docker-compose logs celery-worker

# Check network connectivity
docker-compose exec app ping postgres
docker-compose exec app ping redis
```

**Solutions:**

1. **Rebuild Containers**
   ```bash
   docker-compose down
   docker-compose build --no-cache
   docker-compose up -d
   ```

2. **Fix Environment Variables**
   ```bash
   # Check .env file is properly loaded
   docker-compose config
   
   # Update environment variables
   docker-compose down
   # Edit .env file
   docker-compose up -d
   ```

### Issue: SSL Certificate Problems

**Symptoms:**
- Certificate expired warnings
- "Not secure" in browser
- SSL handshake failures

**Solutions:**
```bash
# Check certificate expiry
openssl x509 -in /etc/ssl/certs/pdfsmaller.site.crt -text -noout | grep "Not After"

# Renew Let's Encrypt certificate
sudo certbot renew

# Test SSL configuration
sudo nginx -t
openssl s_client -connect pdfsmaller.site:443
```

## Monitoring and Logging

### Issue: Logs Not Being Generated

**Symptoms:**
- Empty log files
- No application logs
- Missing error information

**Solutions:**
```bash
# Check log file permissions
ls -la /var/log/pdfsmaller/

# Fix permissions
sudo chown pdfsmaller:pdfsmaller /var/log/pdfsmaller/app.log
sudo chmod 644 /var/log/pdfsmaller/app.log

# Test logging
python -c "
import logging
logging.basicConfig(filename='/var/log/pdfsmaller/test.log', level=logging.INFO)
logging.info('Test log message')
print('Log test completed')
"
```

### Issue: Log Files Growing Too Large

**Symptoms:**
- Disk space running out
- Large log files
- System performance degraded

**Solutions:**
```bash
# Implement log rotation
sudo tee /etc/logrotate.d/pdfsmaller << EOF
/var/log/pdfsmaller/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 pdfsmaller pdfsmaller
}
EOF

# Force log rotation
sudo logrotate -f /etc/logrotate.d/pdfsmaller

# Clean large logs immediately
sudo truncate -s 0 /var/log/pdfsmaller/app.log
```

## Emergency Procedures

### Complete System Recovery

If the system is completely broken:

```bash
# 1. Stop all services
sudo systemctl stop pdfsmaller pdfsmaller-celery pdfsmaller-beat nginx

# 2. Restore from backup
sudo cp -r /var/backups/pdfsmaller/latest_backup/* /var/app/pdfsmaller/

# 3. Restore database
sudo -u postgres psql -c "DROP DATABASE IF EXISTS pdf_smaller_prod;"
sudo -u postgres psql -c "CREATE DATABASE pdf_smaller_prod;"
gunzip -c /var/backups/pdfsmaller/database.sql.gz | sudo -u postgres psql pdf_smaller_prod

# 4. Start services
sudo systemctl start postgresql redis-server
sudo systemctl start pdfsmaller pdfsmaller-celery pdfsmaller-beat nginx

# 5. Verify recovery
curl -f http://localhost:5000/health
```

### Quick Diagnostic Script

Create `/usr/local/bin/pdfsmaller_diagnostics.sh`:
```bash
#!/bin/bash

echo "=== PDF Smaller Diagnostics ==="
echo "Date: $(date)"
echo

echo "=== Service Status ==="
systemctl is-active pdfsmaller pdfsmaller-celery pdfsmaller-beat postgresql redis-server nginx

echo
echo "=== Disk Space ==="
df -h /var/app/uploads /var/log/pdfsmaller

echo
echo "=== Memory Usage ==="
free -h

echo
echo "=== Process Status ==="
ps aux | grep -E "(python|celery|nginx|postgres|redis)" | grep -v grep

echo
echo "=== Network Connectivity ==="
curl -s -o /dev/null -w "Health Check: %{http_code}\n" http://localhost:5000/health
curl -s -o /dev/null -w "Database Health: %{http_code}\n" http://localhost:5000/health/db
curl -s -o /dev/null -w "Redis Health: %{http_code}\n" http://localhost:5000/health/redis

echo
echo "=== Recent Errors ==="
tail -5 /var/log/pdfsmaller/app.log | grep -i error
```

Make it executable and run:
```bash
sudo chmod +x /usr/local/bin/pdfsmaller_diagnostics.sh
/usr/local/bin/pdfsmaller_diagnostics.sh
```

This troubleshooting guide should help resolve most common issues. For persistent problems, check the application logs and consider reaching out to the development team with specific error messages and system information.