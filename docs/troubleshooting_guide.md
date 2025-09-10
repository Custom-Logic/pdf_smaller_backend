# PDF Smaller Backend - Troubleshooting Guide

This guide helps diagnose and resolve common issues with the PDF Smaller backend service.

## Table of Contents

1. [General Diagnostics](#general-diagnostics)
2. [Application Startup Issues](#application-startup-issues)
3. [Database Problems](#database-problems)
4. [File Processing Issues](#file-processing-issues)
5. [Celery Worker Issues](#celery-worker-issues)
6. [Performance Issues](#performance-issues)
7. [Security and Rate Limiting](#security-and-rate-limiting)
8. [Deployment Issues](#deployment-issues)
9. [Monitoring and Logging](#monitoring-and-logging)
10. [Emergency Procedures](#emergency-procedures)

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
```

**Solutions:**

1. **Database Optimization**
   ```sql
   -- Add missing indexes (run in SQLite)
   CREATE INDEX IF NOT EXISTS idx_jobs_status ON compression_jobs(status);
   CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON compression_jobs(created_at);
   
   -- Analyze database
   ANALYZE;
   ```

2. **Application Tuning**
   ```bash
   # Increase Gunicorn workers
   echo "GUNICORN_WORKERS=4" >> .env
   echo "GUNICORN_WORKER_CLASS=gevent" >> .env
   ```

3. **Caching Implementation**
   ```bash
   # Enable Redis caching
   echo "CACHE_TYPE=redis" >> .env
   echo "CACHE_REDIS_URL=redis://localhost:6379/1" >> .env
   ```

### Issue: High Memory Usage

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