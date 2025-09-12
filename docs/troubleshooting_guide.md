# PDF Smaller Backend - Troubleshooting Guide

This guide helps diagnose and resolve common issues with the PDF Smaller backend service.

## Table of Contents

1. [General Diagnostics](#general-diagnostics)
2. [Advanced Debugging Techniques](#advanced-debugging-techniques)
3. [Application Startup Issues](#application-startup-issues)
4. [Database Problems](#database-problems)
5. [File Processing Issues](#file-processing-issues)
6. [Celery Worker Issues](#celery-worker-issues)
7. [Performance Issues](#performance-issues)
8. [Security and Rate Limiting](#security-and-rate-limiting)
9. [API and Network Issues](#api-and-network-issues)
10. [Service Integration Problems](#service-integration-problems)
11. [Deployment Issues](#deployment-issues)
12. [Monitoring and Logging](#monitoring-and-logging)
13. [Emergency Procedures](#emergency-procedures)

## General Diagnostics

### Quick Health Check

```bash
# Check application health
curl http://localhost:5000/health

# Check database connectivity
curl http://localhost:5000/health/db

# Check Redis connectivity
curl http://localhost:5000/health/redis

# Check service status
sudo systemctl status pdfsmaller
sudo systemctl status pdfsmaller-celery
sudo systemctl status redis-server
```

### Log Analysis

```bash
# Application logs
tail -f /var/log/pdfsmaller/app.log

# Celery worker logs
tail -f /var/log/pdfsmaller/celery-worker.log

# System logs
sudo journalctl -u pdfsmaller -f
sudo journalctl -u pdfsmaller-celery -f

# SQLite database logs (if using WAL mode)
ls -la /var/app/pdfsmaller/data/
```

### Configuration Validation

```bash
# Check environment variables
cd /var/app/pdfsmaller
source venv/bin/activate
python -c "from src.config import Config; print('Config loaded successfully')"

# Validate required environment variables
grep -E '^(FLASK_|DATABASE_|REDIS_|UPLOAD_)' .env
```

## Advanced Debugging Techniques

### Python Debugging

#### Using Python Debugger (pdb)

```python
# Add breakpoint in code
import pdb; pdb.set_trace()

# Or use the newer breakpoint() function (Python 3.7+)
breakpoint()

# Debug remotely
import pdb
pdb.set_trace()
```

#### Remote Debugging with VS Code

```python
# Install debugpy
pip install debugpy

# Add to your application
import debugpy
debugpy.listen(5678)
debugpy.wait_for_client()  # Optional: wait for debugger to attach
```

#### Memory Profiling

```bash
# Install memory profiler
pip install memory-profiler psutil

# Profile memory usage
python -m memory_profiler src/app.py

# Line-by-line memory profiling
@profile
def your_function():
    # Your code here
    pass

python -m memory_profiler your_script.py
```

#### CPU Profiling

```bash
# Profile with cProfile
python -m cProfile -o profile.stats src/app.py

# Analyze profile results
python -c "
import pstats
p = pstats.Stats('profile.stats')
p.sort_stats('cumulative').print_stats(20)
p.sort_stats('time').print_stats(20)
"

# Visual profiling with snakeviz
pip install snakeviz
snakeviz profile.stats
```

### Application State Debugging

#### Flask Application Context

```python
# Debug Flask application context
from flask import current_app, g, request, session

# Check current application state
print(f"App name: {current_app.name}")
print(f"Config: {current_app.config}")
print(f"Request: {request.method} {request.url}")

# Debug request context
with app.test_request_context('/api/compress', method='POST'):
    print(f"Endpoint: {request.endpoint}")
    print(f"View args: {request.view_args}")
```

#### Database State Debugging

```python
# Debug SQLAlchemy queries
import logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

# Check database connections
from src.database import db
print(f"Database URL: {db.engine.url}")
print(f"Connection pool: {db.engine.pool.status()}")

# Debug specific queries
from sqlalchemy import text
result = db.session.execute(text("SELECT * FROM compression_jobs LIMIT 5"))
for row in result:
    print(row)
```

### Service-Level Debugging

#### Celery Task Debugging

```python
# Debug Celery tasks
from celery import current_task
from src.tasks.compression_tasks import process_pdf_compression

# Test task directly
result = process_pdf_compression.apply(args=['/path/to/file.pdf', {'quality': 'medium'}])
print(f"Task result: {result.result}")
print(f"Task state: {result.state}")

# Debug task execution
@app.task(bind=True)
def debug_task(self, *args, **kwargs):
    print(f"Task ID: {self.request.id}")
    print(f"Task args: {args}")
    print(f"Task kwargs: {kwargs}")
    return 'Task completed'
```

#### Service Method Debugging

```python
# Debug service methods
from src.services.compression_service import CompressionService

service = CompressionService()

# Add debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Test service methods
try:
    result = service.compress_pdf('/path/to/test.pdf', '/path/to/output.pdf')
    logger.debug(f"Compression result: {result}")
except Exception as e:
    logger.error(f"Compression failed: {e}", exc_info=True)
```

### Network and API Debugging

#### HTTP Request Debugging

```bash
# Debug HTTP requests with curl
curl -v -X POST http://localhost:5000/api/compress \
  -F "file=@test.pdf" \
  -F "compressionLevel=medium"

# Debug with httpie (more user-friendly)
http --form POST localhost:5000/api/compress \
  file@test.pdf \
  compressionLevel=medium

# Monitor network traffic
sudo tcpdump -i lo -A -s 0 'port 5000'

# Use Wireshark for detailed analysis
# wireshark -i lo -f "port 5000"
```

#### API Response Debugging

```python
# Debug API responses
import requests
import json

response = requests.post(
    'http://localhost:5000/api/compress',
    files={'file': open('test.pdf', 'rb')},
    data={'compressionLevel': 'medium'}
)

print(f"Status Code: {response.status_code}")
print(f"Headers: {dict(response.headers)}")
print(f"Response: {response.text}")

# Debug with session for cookie persistence
session = requests.Session()
response = session.post('http://localhost:5000/api/compress', ...)
```

### Log Analysis and Debugging

#### Structured Log Analysis

```bash
# Parse JSON logs
cat /var/log/pdfsmaller/app.log | jq '.level == "ERROR"'

# Filter logs by timestamp
cat /var/log/pdfsmaller/app.log | jq 'select(.timestamp > "2024-01-15T10:00:00")'

# Count error types
cat /var/log/pdfsmaller/app.log | jq -r '.message' | sort | uniq -c | sort -nr

# Real-time log monitoring with filtering
tail -f /var/log/pdfsmaller/app.log | grep -E '(ERROR|CRITICAL)'
```

#### Log Correlation

```bash
# Correlate logs across services
#!/bin/bash
JOB_ID="$1"
echo "=== Application Logs ==="
grep "$JOB_ID" /var/log/pdfsmaller/app.log
echo "=== Celery Logs ==="
grep "$JOB_ID" /var/log/pdfsmaller/celery-worker.log
echo "=== System Logs ==="
journalctl -u pdfsmaller --since "1 hour ago" | grep "$JOB_ID"
```

### Environment and Configuration Debugging

#### Environment Variable Debugging

```bash
# Check all environment variables
env | grep -E '(FLASK|DATABASE|REDIS|CELERY)' | sort

# Debug environment loading
python -c "
import os
from src.config import Config
config = Config()
for key, value in config.__dict__.items():
    if not key.startswith('_'):
        print(f'{key}: {value}')
"
```

#### Configuration Validation Script

```python
#!/usr/bin/env python3
# config_debug.py

import os
import sys
from pathlib import Path

def validate_config():
    """Validate application configuration"""
    errors = []
    warnings = []
    
    # Check required environment variables
    required_vars = [
        'FLASK_APP', 'DATABASE_URL', 'REDIS_URL', 'UPLOAD_FOLDER'
    ]
    
    for var in required_vars:
        if not os.getenv(var):
            errors.append(f"Missing required environment variable: {var}")
    
    # Check file paths
    upload_folder = os.getenv('UPLOAD_FOLDER', '/tmp/uploads')
    if not Path(upload_folder).exists():
        warnings.append(f"Upload folder does not exist: {upload_folder}")
    
    # Check database connectivity
    try:
        from src.database import db
        db.engine.execute('SELECT 1')
        print("✓ Database connection successful")
    except Exception as e:
        errors.append(f"Database connection failed: {e}")
    
    # Check Redis connectivity
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        r.ping()
        print("✓ Redis connection successful")
    except Exception as e:
        errors.append(f"Redis connection failed: {e}")
    
    # Print results
    if errors:
        print("\n❌ Configuration Errors:")
        for error in errors:
            print(f"  - {error}")
    
    if warnings:
        print("\n⚠️  Configuration Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    
    if not errors and not warnings:
        print("\n✅ Configuration is valid")
    
    return len(errors) == 0

if __name__ == '__main__':
    if not validate_config():
        sys.exit(1)
```

### Performance Debugging

#### Request Timing Analysis

```python
# Add timing middleware
from flask import Flask, request, g
import time

app = Flask(__name__)

@app.before_request
def before_request():
    g.start_time = time.time()

@app.after_request
def after_request(response):
    total_time = time.time() - g.start_time
    response.headers['X-Response-Time'] = str(total_time)
    print(f"Request {request.method} {request.path} took {total_time:.3f}s")
    return response
```

#### Database Query Analysis

```python
# Monitor slow queries
from sqlalchemy import event
from sqlalchemy.engine import Engine
import time
import logging

logging.basicConfig()
logger = logging.getLogger("myapp.sqltime")
logger.setLevel(logging.DEBUG)

@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    conn.info.setdefault('query_start_time', []).append(time.time())
    logger.debug("Start Query: %s", statement)

@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    total = time.time() - conn.info['query_start_time'].pop(-1)
    logger.debug("Query Complete in %.3fs", total)
    if total > 0.1:  # Log slow queries
        logger.warning("Slow query (%.3fs): %s", total, statement)
```

## Application Startup Issues

### Symptoms
- Application fails to start
- "Connection refused" errors
- Import errors in logs

### Diagnosis

```bash
# Check if port is in use
sudo netstat -tlnp | grep :5000

# Check Python path and imports
cd /var/app/pdfsmaller
source venv/bin/activate
python -c "import src; print('Imports successful')"

# Check database file permissions
ls -la data/pdf_smaller.db
```

### Solutions

1. **Missing Environment Variables**
   ```bash
   # Check required variables
   echo "FLASK_APP=src.app:create_app" >> .env
   echo "FLASK_ENV=production" >> .env
   echo "DATABASE_URL=sqlite:///data/pdf_smaller.db" >> .env
   echo "REDIS_URL=redis://localhost:6379/0" >> .env
   ```

2. **Python Path Issues**
   ```bash
   # Add current directory to Python path
   export PYTHONPATH=/var/app/pdfsmaller:$PYTHONPATH
   
   # Or update systemd service
   sudo systemctl edit pdfsmaller
   # Add: Environment="PYTHONPATH=/var/app/pdfsmaller"
   ```

3. **Port Already in Use**
   ```bash
   # Find process using port 5000
   sudo lsof -i :5000
   
   # Kill process or change port
   echo "PORT=5001" >> .env
   ```

4. **Permission Errors**
   ```bash
   # Fix file permissions
   sudo chown -R pdfsmaller:pdfsmaller /var/app/pdfsmaller
   sudo chmod -R 755 /var/app/pdfsmaller
   sudo chmod 644 /var/app/pdfsmaller/.env
   ```

## Database Problems

### Issue: Database Connection Failures

**Symptoms:**
- "Database locked" errors
- "No such file or directory" for database
- Connection timeout errors

**Solutions:**

1. **SQLite Database Issues**
   ```bash
   # Check database file exists and is accessible
   ls -la /var/app/pdfsmaller/data/pdf_smaller.db
   
   # Test database connection
   sqlite3 /var/app/pdfsmaller/data/pdf_smaller.db ".tables"
   
   # Fix permissions
   sudo chown pdfsmaller:pdfsmaller /var/app/pdfsmaller/data/pdf_smaller.db
   sudo chmod 664 /var/app/pdfsmaller/data/pdf_smaller.db
   ```

2. **Database Initialization**
   ```bash
   cd /var/app/pdfsmaller
   source venv/bin/activate
   flask db upgrade
   ```

3. **Database Backup and Recovery**
   ```bash
   # Backup database
   cp /var/app/pdfsmaller/data/pdf_smaller.db /var/backups/pdf_smaller_$(date +%Y%m%d_%H%M%S).db
   
   # Restore from backup
   cp /var/backups/pdf_smaller_20231201_120000.db /var/app/pdfsmaller/data/pdf_smaller.db
   ```

## File Processing Issues

### Issue: Upload Failures

**Symptoms:**
- "File too large" errors
- Upload timeouts
- "Permission denied" errors

**Diagnosis:**
```bash
# Check upload directory
ls -la /var/app/uploads/

# Check disk space
df -h /var/app/uploads/

# Check file permissions
ls -la /var/app/uploads/temp/
```

**Solutions:**

1. **File Size Limits**
   ```bash
   # Update application limits
   echo "MAX_CONTENT_LENGTH=104857600" >> .env  # 100MB
   
   # Update Nginx limits
   sudo nano /etc/nginx/sites-available/pdfsmaller
   # Add: client_max_body_size 100M;
   sudo nginx -t && sudo systemctl reload nginx
   ```

2. **Permission Issues**
   ```bash
   # Fix upload directory permissions
   sudo chown -R pdfsmaller:pdfsmaller /var/app/uploads/
   sudo chmod -R 755 /var/app/uploads/
   ```

3. **Disk Space Issues**
   ```bash
   # Clean old files
   find /var/app/uploads/temp/ -type f -mtime +1 -delete
   find /var/app/uploads/processed/ -type f -mtime +7 -delete
   ```

### Issue: PDF Compression Failures

**Symptoms:**
- Ghostscript errors in logs
- "Command not found" errors
- Compressed files larger than originals

**Solutions:**

1. **Ghostscript Installation**
   ```bash
   # Install Ghostscript
   sudo apt update
   sudo apt install ghostscript
   
   # Verify installation
   gs --version
   which gs
   ```

2. **Ghostscript Permissions**
   ```bash
   # Check Ghostscript policy
   sudo nano /etc/ImageMagick-6/policy.xml
   # Ensure PDF policy allows read/write
   
   # Test Ghostscript
   gs -dNOPAUSE -dBATCH -sDEVICE=pdfwrite -dCompatibilityLevel=1.4 -sOutputFile=test_output.pdf test_input.pdf
   ```

3. **Compression Settings**
   ```bash
   # Test compression settings
   echo "PDF_COMPRESSION_QUALITY=medium" >> .env
   echo "PDF_COMPRESSION_DPI=150" >> .env
   ```

## Celery Worker Issues

### Issue: Workers Not Starting

**Symptoms:**
- No worker processes running
- Tasks stuck in pending state
- "No workers available" errors

**Diagnosis:**
```bash
# Check Celery worker status
sudo systemctl status pdfsmaller-celery

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
   from src.tasks.compression_tasks import process_pdf_compression
   result = process_pdf_compression.delay(file_path, settings)
   print(result.get())
   ```

### Issue: Memory Leaks in Workers

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

**Diagnosis:**
```bash
# Check system resources
top
htop
iotop

# Check database performance
sqlite3 /var/app/pdfsmaller/data/pdf_smaller.db ".timer on" ".explain query plan SELECT * FROM compression_jobs LIMIT 10;"

# Check application metrics
curl http://localhost:5000/health

# Profile application performance
python -m cProfile -o profile_output.prof src/app.py
python -c "import pstats; p = pstats.Stats('profile_output.prof'); p.sort_stats('cumulative').print_stats(20)"

# Check network latency
ping -c 10 localhost
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:5000/health
```

**Create curl-format.txt for detailed timing:**
```bash
cat > curl-format.txt << EOF
     time_namelookup:  %{time_namelookup}\n
        time_connect:  %{time_connect}\n
     time_appconnect:  %{time_appconnect}\n
    time_pretransfer:  %{time_pretransfer}\n
       time_redirect:  %{time_redirect}\n
  time_starttransfer:  %{time_starttransfer}\n
                     ----------\n
          time_total:  %{time_total}\n
EOF
```

**Solutions:**

1. **Database Optimization**
   ```sql
   -- Add missing indexes (run in SQLite)
   CREATE INDEX IF NOT EXISTS idx_jobs_status ON compression_jobs(status);
   CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON compression_jobs(created_at);
   CREATE INDEX IF NOT EXISTS idx_jobs_user_id ON compression_jobs(user_id);
   CREATE INDEX IF NOT EXISTS idx_jobs_task_type ON compression_jobs(task_type);
   
   -- Analyze database
   ANALYZE;
   
   -- Enable WAL mode for better concurrency
   PRAGMA journal_mode=WAL;
   PRAGMA synchronous=NORMAL;
   PRAGMA cache_size=10000;
   PRAGMA temp_store=memory;
   ```

2. **Application Tuning**
   ```bash
   # Increase Gunicorn workers (CPU cores * 2 + 1)
   echo "GUNICORN_WORKERS=4" >> .env
   echo "GUNICORN_WORKER_CLASS=gevent" >> .env
   echo "GUNICORN_WORKER_CONNECTIONS=1000" >> .env
   echo "GUNICORN_MAX_REQUESTS=1000" >> .env
   echo "GUNICORN_MAX_REQUESTS_JITTER=100" >> .env
   
   # Optimize Flask configuration
   echo "FLASK_THREADED=true" >> .env
   echo "FLASK_PROCESSES=1" >> .env
   ```

3. **Caching Implementation**
   ```bash
   # Enable Redis caching
   echo "CACHE_TYPE=redis" >> .env
   echo "CACHE_REDIS_URL=redis://localhost:6379/1" >> .env
   echo "CACHE_DEFAULT_TIMEOUT=300" >> .env
   
   # Enable response caching
   echo "RESPONSE_CACHE_ENABLED=true" >> .env
   echo "RESPONSE_CACHE_TIMEOUT=60" >> .env
   ```

4. **File System Optimization**
   ```bash
   # Use tmpfs for temporary files
   sudo mkdir -p /tmp/pdfsmaller
   sudo mount -t tmpfs -o size=1G tmpfs /tmp/pdfsmaller
   echo "TEMP_DIR=/tmp/pdfsmaller" >> .env
   
   # Add to /etc/fstab for persistence
   echo "tmpfs /tmp/pdfsmaller tmpfs defaults,size=1G 0 0" | sudo tee -a /etc/fstab
   ```

### Issue: High Memory Usage

**Diagnosis:**
```bash
# Monitor memory usage in real-time
free -h
ps aux --sort=-%mem | head -10
watch -n 1 'ps aux --sort=-%mem | head -10'

# Check for memory leaks
valgrind --tool=memcheck --leak-check=full python src/app.py

# Monitor Python memory usage
python -c "
import psutil
import os
process = psutil.Process(os.getpid())
print(f'Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB')
"

# Check swap usage
swapon --show
cat /proc/swaps
```

**Solutions:**
```bash
# Monitor memory usage
free -h
ps aux --sort=-%mem | head -10

# Reduce worker processes
echo "GUNICORN_WORKERS=2" >> .env
echo "CELERY_WORKER_CONCURRENCY=1" >> .env
echo "CELERY_WORKER_MAX_MEMORY_PER_CHILD=200000" >> .env  # 200MB
echo "CELERY_WORKER_MAX_TASKS_PER_CHILD=100" >> .env

# Optimize Python garbage collection
echo "PYTHONOPTIMIZE=1" >> .env
echo "PYTHONDONTWRITEBYTECODE=1" >> .env

# Add swap space
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Configure swappiness
echo 'vm.swappiness=10' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### Issue: CPU Bottlenecks

**Diagnosis:**
```bash
# Monitor CPU usage
top -p $(pgrep -f "python.*app")
htop
sar -u 1 10  # If sysstat is installed

# Check CPU-intensive processes
ps aux --sort=-%cpu | head -10

# Profile CPU usage
python -m cProfile -s cumulative src/app.py
```

**Solutions:**
```bash
# Optimize Ghostscript operations
echo "GS_THREADS=2" >> .env
echo "GS_MEMORY_LIMIT=100MB" >> .env

# Use process pooling for CPU-intensive tasks
echo "MULTIPROCESSING_ENABLED=true" >> .env
echo "PROCESS_POOL_SIZE=2" >> .env

# Optimize Celery for CPU-bound tasks
echo "CELERY_TASK_ROUTES={'src.tasks.compression_tasks.*': {'queue': 'cpu_intensive'}}" >> .env
```

### Issue: Disk I/O Bottlenecks

**Diagnosis:**
```bash
# Monitor disk I/O
iotop -o
sar -d 1 10

# Check disk usage and performance
df -h
du -sh /var/app/pdfsmaller/uploads/*

# Test disk performance
dd if=/dev/zero of=/tmp/testfile bs=1M count=1024 oflag=direct
rm /tmp/testfile
```

**Solutions:**
```bash
# Use SSD for uploads directory
sudo mkdir -p /mnt/ssd/uploads
sudo mount /dev/nvme0n1p1 /mnt/ssd
echo "UPLOAD_FOLDER=/mnt/ssd/uploads" >> .env

# Optimize file operations
echo "FILE_BUFFER_SIZE=65536" >> .env  # 64KB buffer
echo "ASYNC_FILE_OPERATIONS=true" >> .env

# Enable file system caching
echo 'vm.dirty_ratio=15' | sudo tee -a /etc/sysctl.conf
echo 'vm.dirty_background_ratio=5' | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

## Security and Rate Limiting

### Issue: Rate Limiting Not Working

**Diagnosis:**
```bash
# Check Redis connection for rate limiting
redis-cli -n 1 ping

# Test rate limiting
for i in {1..20}; do curl -I http://localhost:5000/api/compress; done

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

**Solutions:**
```bash
# Update CORS origins
echo "ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com" >> .env

# Check Nginx CORS headers
grep -A 10 "add_header.*Access-Control" /etc/nginx/sites-available/pdfsmaller

# Restart services
sudo systemctl restart pdfsmaller nginx
```

## API and Network Issues

### Issue: API Endpoints Not Responding

**Symptoms:**
- 404 errors for valid endpoints
- Connection refused errors
- Timeout errors

**Diagnosis:**
```bash
# Check if application is running
curl -I http://localhost:5000/health

# Check port binding
sudo netstat -tlnp | grep :5000

# Check application logs
tail -f /var/log/pdfsmaller/app.log

# Test with different methods
curl -X GET http://localhost:5000/api/health
curl -X POST http://localhost:5000/api/compress
```

**Solutions:**

1. **Fix Route Registration**
   ```python
   # Check route registration in app.py
   from flask import Flask
   app = Flask(__name__)
   
   # Debug routes
   with app.app_context():
       for rule in app.url_map.iter_rules():
           print(f"{rule.endpoint}: {rule.rule} [{', '.join(rule.methods)}]")
   ```

2. **Fix WSGI Configuration**
   ```bash
   # Check Gunicorn binding
   echo "GUNICORN_BIND=0.0.0.0:5000" >> .env
   
   # Restart application
   sudo systemctl restart pdfsmaller
   ```

### Issue: File Upload Failures

**Symptoms:**
- "File too large" errors
- "Invalid file type" errors
- Upload timeouts

**Diagnosis:**
```bash
# Check file size limits
grep -i max_content_length /var/app/pdfsmaller/src/config.py

# Check Nginx limits
grep -i client_max_body_size /etc/nginx/sites-available/pdfsmaller

# Test file upload
curl -F "file=@test.pdf" http://localhost:5000/api/compress
```

**Solutions:**

1. **Increase File Size Limits**
   ```bash
   # Application limit
   echo "MAX_CONTENT_LENGTH=104857600" >> .env  # 100MB
   
   # Nginx limit
   sudo sed -i 's/client_max_body_size.*/client_max_body_size 100M;/' /etc/nginx/sites-available/pdfsmaller
   sudo nginx -t && sudo systemctl reload nginx
   ```

2. **Fix File Validation**
   ```python
   # Check allowed file types
   ALLOWED_EXTENSIONS = {'pdf'}
   
   def allowed_file(filename):
       return '.' in filename and \
              filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
   ```

### Issue: JSON Response Errors

**Symptoms:**
- Malformed JSON responses
- Encoding errors
- Missing response headers

**Solutions:**

1. **Fix JSON Serialization**
   ```python
   from flask import jsonify
   import json
   from datetime import datetime
   
   class DateTimeEncoder(json.JSONEncoder):
       def default(self, obj):
           if isinstance(obj, datetime):
               return obj.isoformat()
           return super().default(obj)
   
   # Use proper JSON responses
   return jsonify({'status': 'success', 'data': data})
   ```

2. **Set Proper Headers**
   ```python
   from flask import Flask, jsonify
   
   app = Flask(__name__)
   
   @app.after_request
   def after_request(response):
       response.headers['Content-Type'] = 'application/json'
       response.headers['Access-Control-Allow-Origin'] = '*'
       return response
   ```

## Service Integration Problems

### Issue: Ghostscript Integration Failures

**Symptoms:**
- "gs: command not found" errors
- PDF compression failures
- Permission denied errors

**Diagnosis:**
```bash
# Check Ghostscript installation
which gs
gs --version

# Test Ghostscript directly
gs -dNOPAUSE -dBATCH -sDEVICE=pdfwrite -sOutputFile=test_output.pdf test_input.pdf

# Check permissions
ls -la $(which gs)
```

**Solutions:**

1. **Install/Update Ghostscript**
   ```bash
   # Ubuntu/Debian
   sudo apt update
   sudo apt install ghostscript
   
   # CentOS/RHEL
   sudo yum install ghostscript
   
   # Verify installation
   gs --version
   ```

2. **Fix Ghostscript Policies**
   ```bash
   # Check ImageMagick policy (affects Ghostscript)
   sudo nano /etc/ImageMagick-6/policy.xml
   
   # Ensure PDF policy allows read/write
   # <policy domain="coder" rights="read|write" pattern="PDF" />
   ```

3. **Configure Ghostscript Path**
   ```bash
   # Set Ghostscript path in environment
   echo "GHOSTSCRIPT_PATH=/usr/bin/gs" >> .env
   
   # Or update system PATH
   export PATH="/usr/bin:$PATH"
   ```

### Issue: Redis Connection Problems

**Symptoms:**
- "Connection refused" to Redis
- Celery workers not starting
- Task queue failures

**Diagnosis:**
```bash
# Check Redis status
sudo systemctl status redis-server

# Test Redis connection
redis-cli ping

# Check Redis configuration
sudo nano /etc/redis/redis.conf

# Check Redis logs
sudo tail -f /var/log/redis/redis-server.log
```

**Solutions:**

1. **Start Redis Service**
   ```bash
   sudo systemctl start redis-server
   sudo systemctl enable redis-server
   ```

2. **Fix Redis Configuration**
   ```bash
   # Allow connections from localhost
   sudo sed -i 's/bind 127.0.0.1/bind 0.0.0.0/' /etc/redis/redis.conf
   
   # Disable protected mode for development
   sudo sed -i 's/protected-mode yes/protected-mode no/' /etc/redis/redis.conf
   
   sudo systemctl restart redis-server
   ```

3. **Update Redis URL**
   ```bash
   # Check current Redis URL
   echo $REDIS_URL
   
   # Update if needed
   echo "REDIS_URL=redis://localhost:6379/0" >> .env
   ```

### Issue: Database Lock Errors

**Symptoms:**
- "Database is locked" errors
- SQLite busy errors
- Transaction deadlocks

**Diagnosis:**
```bash
# Check database file permissions
ls -la /var/app/pdfsmaller/data/pdf_smaller.db

# Check for long-running transactions
sqlite3 /var/app/pdfsmaller/data/pdf_smaller.db "PRAGMA busy_timeout;"

# Check database integrity
sqlite3 /var/app/pdfsmaller/data/pdf_smaller.db "PRAGMA integrity_check;"
```

**Solutions:**

1. **Enable WAL Mode**
   ```sql
   -- Connect to database and enable WAL mode
   sqlite3 /var/app/pdfsmaller/data/pdf_smaller.db
   PRAGMA journal_mode=WAL;
   PRAGMA synchronous=NORMAL;
   PRAGMA busy_timeout=30000;
   .quit
   ```

2. **Fix Database Permissions**
   ```bash
   sudo chown pdfsmaller:pdfsmaller /var/app/pdfsmaller/data/pdf_smaller.db*
   sudo chmod 664 /var/app/pdfsmaller/data/pdf_smaller.db*
   ```

3. **Implement Connection Pooling**
   ```python
   # In config.py
   SQLALCHEMY_ENGINE_OPTIONS = {
       'pool_timeout': 20,
       'pool_recycle': 3600,
       'pool_pre_ping': True
   }
   ```

### Issue: External API Integration Failures

**Symptoms:**
- AI service API errors
- Authentication failures
- Rate limiting errors

**Diagnosis:**
```bash
# Test API connectivity
curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
     https://openrouter.ai/api/v1/models

# Check API key configuration
echo $OPENROUTER_API_KEY | wc -c  # Should be > 10

# Test with different endpoints
curl -v https://api.openai.com/v1/models
```

**Solutions:**

1. **Verify API Keys**
   ```bash
   # Check API key format
   echo "OPENROUTER_API_KEY=sk-or-..." >> .env
   echo "OPENAI_API_KEY=sk-..." >> .env
   
   # Test API key validity
   curl -H "Authorization: Bearer $OPENROUTER_API_KEY" \
        https://openrouter.ai/api/v1/auth/key
   ```

2. **Implement Retry Logic**
   ```python
   import requests
   from requests.adapters import HTTPAdapter
   from urllib3.util.retry import Retry
   
   def create_session_with_retries():
       session = requests.Session()
       retry_strategy = Retry(
           total=3,
           backoff_factor=1,
           status_forcelist=[429, 500, 502, 503, 504]
       )
       adapter = HTTPAdapter(max_retries=retry_strategy)
       session.mount("http://", adapter)
       session.mount("https://", adapter)
       return session
   ```

3. **Handle Rate Limits**
   ```python
   import time
   from functools import wraps
   
   def rate_limit_handler(func):
       @wraps(func)
       def wrapper(*args, **kwargs):
           max_retries = 3
           for attempt in range(max_retries):
               try:
                   return func(*args, **kwargs)
               except requests.exceptions.HTTPError as e:
                   if e.response.status_code == 429:
                       wait_time = 2 ** attempt
                       time.sleep(wait_time)
                       continue
                   raise
           raise Exception("Max retries exceeded")
       return wrapper
   ```

## Deployment Issues

### Issue: Docker Container Problems

**Diagnosis:**
```bash
# Check container status
docker-compose ps

# Check container logs
docker-compose logs app
docker-compose logs celery-worker

# Check network connectivity
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
sudo systemctl stop pdfsmaller pdfsmaller-celery nginx

# 2. Restore from backup
sudo cp -r /var/backups/pdfsmaller/latest_backup/* /var/app/pdfsmaller/

# 3. Restore database
cp /var/backups/pdfsmaller/pdf_smaller.db /var/app/pdfsmaller/data/

# 4. Start services
sudo systemctl start redis-server
sudo systemctl start pdfsmaller pdfsmaller-celery nginx

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
systemctl is-active pdfsmaller pdfsmaller-celery redis-server nginx

echo
echo "=== Disk Space ==="
df -h /var/app/uploads /var/log/pdfsmaller

echo
echo "=== Memory Usage ==="
free -h

echo
echo "=== Process Status ==="
ps aux | grep -E "(python|celery|nginx|redis)" | grep -v grep

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

This troubleshooting guide focuses on core PDF processing functionality and should help resolve most common issues with the simplified backend service.
