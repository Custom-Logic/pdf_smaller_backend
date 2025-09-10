# PDF Smaller Backend - Deployment Guide

This guide covers deployment of the PDF Smaller backend for PDF compression processing with job management and file handling.

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Environment Setup](#environment-setup)
3. [Database Configuration](#database-configuration)
4. [Application Deployment](#application-deployment)
5. [Background Services](#background-services)
6. [Security Configuration](#security-configuration)
7. [Monitoring and Logging](#monitoring-and-logging)
8. [Maintenance Procedures](#maintenance-procedures)
9. [Troubleshooting Guide](#troubleshooting-guide)

## System Requirements

### Minimum Hardware Requirements

**Development Environment:**
- CPU: 2 cores
- RAM: 4GB
- Storage: 20GB SSD
- Network: Broadband internet

**Production Environment:**
- CPU: 4+ cores
- RAM: 8GB+ (16GB recommended)
- Storage: 100GB+ SSD
- Network: High-speed internet with low latency

### Software Dependencies

**Core Requirements:**
- Python 3.11+
- SQLite (built-in, no external database server required)
- Redis 6+
- Nginx (production)
- Ghostscript 9.50+

**Optional but Recommended:**
- Docker & Docker Compose
- Supervisor or systemd
- SSL certificate (Let's Encrypt)
- Monitoring tools (Prometheus, Grafana)

## Environment Setup

### 1. Environment Variables Configuration

Create environment-specific configuration files:

#### Development (.env.development)
```bash
# Application Settings
FLASK_ENV=development
SECRET_KEY=dev-secret-key-change-in-production
DEBUG=true

# Database (SQLite)
DATABASE_URL=sqlite:///pdf_smaller_dev.db

# File Storage
UPLOAD_FOLDER=./uploads/dev
MAX_FILE_SIZE=52428800  # 50MB
MAX_FILE_AGE_HOURS=24
CLEANUP_ENABLED=true

# Redis & Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Logging
LOG_LEVEL=DEBUG
LOG_FILE=app.log

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=100 per hour
```

#### Production (.env.production)
```bash
# Application Settings
FLASK_ENV=production
SECRET_KEY=your-super-secure-64-character-production-secret-key-here
DEBUG=false

# Database (SQLite)
DATABASE_URL=sqlite:////var/app/pdfsmaller/pdf_smaller_prod.db

# File Storage
UPLOAD_FOLDER=/var/app/uploads
MAX_FILE_SIZE=104857600  # 100MB
MAX_FILE_AGE_HOURS=1
CLEANUP_ENABLED=true

# Redis & Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
CELERY_WORKER_CONCURRENCY=4

# CORS
ALLOWED_ORIGINS=https://yourfrontend.com,https://www.yourfrontend.com

# Security
SECURITY_HEADERS_ENABLED=true
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=100 per hour
RATE_LIMIT_STORAGE_URL=redis://localhost:6379/1

# Logging
LOG_LEVEL=WARNING
LOG_FILE=/var/log/pdfsmaller/app.log
LOG_MAX_BYTES=10485760  # 10MB
LOG_BACKUP_COUNT=5

# Monitoring
HEALTH_CHECK_ENABLED=true
METRICS_ENABLED=true
```

### 2. Directory Structure Setup

```bash
# Create application directories
sudo mkdir -p /var/app/pdfsmaller
sudo mkdir -p /var/app/uploads
sudo mkdir -p /var/log/pdfsmaller
sudo mkdir -p /etc/pdfsmaller

# Set ownership
sudo useradd -m -s /bin/bash pdfsmaller
sudo chown -R pdfsmaller:pdfsmaller /var/app/pdfsmaller
sudo chown -R pdfsmaller:pdfsmaller /var/app/uploads
sudo chown -R pdfsmaller:pdfsmaller /var/log/pdfsmaller
```

## Database Configuration

### SQLite Database Setup

The application uses SQLite for both development and production environments. No external database server is required.

#### Database File Location
```bash
# Development
DATABASE_URL=sqlite:///pdf_smaller_dev.db

# Production
DATABASE_URL=sqlite:////var/app/pdfsmaller/pdf_smaller_prod.db
```

#### Database Initialization

```bash
# Navigate to application directory
cd /var/app/pdfsmaller

# Activate virtual environment
source venv/bin/activate

# Initialize database
python manage_db.py init

# Verify setup
python manage_db.py status
```

#### Database Backup Configuration

Create backup script `/usr/local/bin/backup_pdfsmaller_db.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/pdfsmaller"
DATE=$(date +%Y%m%d_%H%M%S)
DB_FILE="/var/app/pdfsmaller/pdf_smaller_prod.db"

mkdir -p $BACKUP_DIR

# Create backup
cp $DB_FILE $BACKUP_DIR/backup_$DATE.db
gzip $BACKUP_DIR/backup_$DATE.db

# Keep only last 7 days of backups
find $BACKUP_DIR -name "backup_*.db.gz" -mtime +7 -delete

echo "Database backup completed: backup_$DATE.db.gz"
```

Make executable and add to crontab:
```bash
sudo chmod +x /usr/local/bin/backup_pdfsmaller_db.sh
sudo crontab -e
# Add line for daily backup at 2 AM
0 2 * * * /usr/local/bin/backup_pdfsmaller_db.sh
```

## Application Deployment

### 1. Docker Deployment (Recommended)

#### Production Docker Compose
Create `docker-compose.prod.yml`:
```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "5000:5000"
    environment:
      - FLASK_ENV=production
    env_file:
      - .env.production
    volumes:
      - /var/app/uploads:/app/uploads
      - /var/log/pdfsmaller:/app/logs
      - sqlite_data:/app/data
    depends_on:
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery-worker:
    build: .
    command: celery -A celery_worker.celery worker --loglevel=info --concurrency=4 --queues=compression,cleanup
    environment:
      - FLASK_ENV=production
    env_file:
      - .env.production
    volumes:
      - /var/app/uploads:/app/uploads
      - /var/log/pdfsmaller:/app/logs
      - sqlite_data:/app/data
    depends_on:
      - redis
    restart: unless-stopped

  celery-beat:
    build: .
    command: celery -A celery_worker.celery beat --loglevel=info
    environment:
      - FLASK_ENV=production
    env_file:
      - .env.production
    volumes:
      - sqlite_data:/app/data
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/nginx/ssl
    depends_on:
      - app
    restart: unless-stopped

volumes:
  sqlite_data:
  redis_data:
```

#### Deploy with Docker
```bash
# Build and start services
docker-compose -f docker-compose.prod.yml up -d

# Initialize database
docker-compose -f docker-compose.prod.yml exec app python manage_db.py init

# Check status
docker-compose -f docker-compose.prod.yml ps
```

### 2. Manual Deployment

#### Install System Dependencies
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv python3-pip
sudo apt-get install redis-server
sudo apt-get install ghostscript
sudo apt-get install nginx
sudo apt-get install supervisor

# CentOS/RHEL
sudo yum install python3.11 python3.11-venv python3-pip
sudo yum install redis
sudo yum install ghostscript
sudo yum install nginx
sudo yum install supervisor
```

#### Application Setup
```bash
# Switch to application user
sudo su - pdfsmaller

# Clone repository
git clone <repository-url> /var/app/pdfsmaller
cd /var/app/pdfsmaller

# Create virtual environment
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Copy configuration
cp .env.production .env

# Initialize database
python manage_db.py init

# Test application
python app.py
```

#### Systemd Service Configuration

Create `/etc/systemd/system/pdfsmaller.service`:
```ini
[Unit]
Description=PDF Smaller Web Application
After=network.target redis.service
Wants=redis.service

[Service]
Type=exec
User=pdfsmaller
Group=pdfsmaller
WorkingDirectory=/var/app/pdfsmaller
Environment=PATH=/var/app/pdfsmaller/venv/bin
EnvironmentFile=/var/app/pdfsmaller/.env
ExecStart=/var/app/pdfsmaller/venv/bin/gunicorn --config gunicorn_conf.py app:app
ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=3
KillMode=mixed
TimeoutStopSec=5

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/pdfsmaller-celery.service`:
```ini
[Unit]
Description=PDF Smaller Celery Worker
After=network.target redis.service
Wants=redis.service

[Service]
Type=exec
User=pdfsmaller
Group=pdfsmaller
WorkingDirectory=/var/app/pdfsmaller
Environment=PATH=/var/app/pdfsmaller/venv/bin
EnvironmentFile=/var/app/pdfsmaller/.env
ExecStart=/var/app/pdfsmaller/venv/bin/celery -A celery_worker.celery worker --loglevel=info --concurrency=4 --queues=compression,cleanup
Restart=always
RestartSec=3
KillMode=mixed
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

Create `/etc/systemd/system/pdfsmaller-beat.service`:
```ini
[Unit]
Description=PDF Smaller Celery Beat Scheduler
After=network.target redis.service
Wants=redis.service

[Service]
Type=exec
User=pdfsmaller
Group=pdfsmaller
WorkingDirectory=/var/app/pdfsmaller
Environment=PATH=/var/app/pdfsmaller/venv/bin
EnvironmentFile=/var/app/pdfsmaller/.env
ExecStart=/var/app/pdfsmaller/venv/bin/celery -A celery_worker.celery beat --loglevel=info
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Enable and start services:
```bash
sudo systemctl daemon-reload
sudo systemctl enable pdfsmaller pdfsmaller-celery pdfsmaller-beat
sudo systemctl start pdfsmaller pdfsmaller-celery pdfsmaller-beat

# Check status
sudo systemctl status pdfsmaller
sudo systemctl status pdfsmaller-celery
sudo systemctl status pdfsmaller-beat
```

## Background Services

### 1. Redis Configuration

Edit `/etc/redis/redis.conf`:
```ini
# Network
bind 127.0.0.1
port 6379
protected-mode yes

# Memory
maxmemory 256mb
maxmemory-policy allkeys-lru

# Persistence
save 900 1
save 300 10
save 60 10000

# Security
requirepass your_redis_password_here

# Logging
loglevel notice
logfile /var/log/redis/redis-server.log
```

Restart Redis:
```bash
sudo systemctl restart redis-server
sudo systemctl enable redis-server
```

### 2. Celery Configuration

Create `/etc/supervisor/conf.d/pdfsmaller-celery.conf`:
```ini
[program:pdfsmaller-celery-worker]
command=/var/app/pdfsmaller/venv/bin/celery -A celery_worker.celery worker --loglevel=info --concurrency=4 --queues=compression,cleanup
directory=/var/app/pdfsmaller
user=pdfsmaller
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/pdfsmaller/celery-worker.log
environment=PATH="/var/app/pdfsmaller/venv/bin"

[program:pdfsmaller-celery-beat]
command=/var/app/pdfsmaller/venv/bin/celery -A celery_worker.celery beat --loglevel=info
directory=/var/app/pdfsmaller
user=pdfsmaller
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/pdfsmaller/celery-beat.log
environment=PATH="/var/app/pdfsmaller/venv/bin"
```

Start Supervisor:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start all
```

## Security Configuration

### 1. Nginx Configuration

Create `/etc/nginx/sites-available/pdfsmaller`:
```nginx
# Rate limiting
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

# Upstream servers
upstream pdfsmaller_app {
    server 127.0.0.1:5000 max_fails=3 fail_timeout=30s;
}

# HTTP to HTTPS redirect
server {
    listen 80;
    server_name yourserver.com www.yourserver.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name yourserver.com www.yourserver.com;

    # SSL Configuration
    ssl_certificate /etc/ssl/certs/yourserver.com.crt;
    ssl_certificate_key /etc/ssl/private/yourserver.com.key;
    
    # SSL Security
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self';" always;

    # File upload limits
    client_max_body_size 100M;
    client_body_timeout 60s;
    client_header_timeout 60s;

    # Compression
    gzip on;
    gzip_vary on;
    gzip_min_length 1024;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml application/xml+rss text/javascript;

    # Main application
    location / {
        proxy_pass http://pdfsmaller_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
        proxy_send_timeout 300s;
        
        # Rate limiting
        limit_req zone=api burst=20 nodelay;
    }

    # Health check endpoint (no rate limiting)
    location /api/health {
        proxy_pass http://pdfsmaller_app;
        access_log off;
    }

    # Static files (if any)
    location /static/ {
        alias /var/app/pdfsmaller/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security - deny access to sensitive files
    location ~ /\. {
        deny all;
    }
    
    location ~ \.(env|log|conf|db)$ {
        deny all;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/pdfsmaller /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 2. SSL Certificate Setup

#### Using Let's Encrypt (Recommended)
```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourserver.com -d www.yourserver.com

# Auto-renewal
sudo crontab -e
# Add line:
0 12 * * * /usr/bin/certbot renew --quiet
```

### 3. Firewall Configuration

```bash
# Enable UFW
sudo ufw enable

# Allow SSH
sudo ufw allow ssh

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Check status
sudo ufw status
```

## Monitoring and Logging

### 1. Application Logging

Configure logging in your application:
```python
# logging_config.py
import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logging(app):
    if not app.debug:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler(
            'logs/pdfsmaller.log', 
            maxBytes=10240000, 
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(logging.INFO)
        app.logger.info('PDF Smaller startup')
```

### 2. Health Check Endpoint

Ensure your application has a health check endpoint:
```python
@app.route('/api/health')
def health_check():
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        
        # Check Redis connection
        redis_client.ping()
        
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'redis': 'connected',
            'timestamp': datetime.utcnow().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500
```

### 3. Log Rotation

Create `/etc/logrotate.d/pdfsmaller`:
```
/var/log/pdfsmaller/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 pdfsmaller pdfsmaller
    postrotate
        systemctl reload pdfsmaller
    endscript
}
```

## Maintenance Procedures

### 1. Application Updates

```bash
#!/bin/bash
# update_app.sh

set -e

echo "Starting application update..."

# Stop services
sudo systemctl stop pdfsmaller pdfsmaller-celery pdfsmaller-beat

# Backup database
/usr/local/bin/backup_pdfsmaller_db.sh

# Update code
cd /var/app/pdfsmaller
sudo -u pdfsmaller git pull origin main

# Update dependencies
sudo -u pdfsmaller /var/app/pdfsmaller/venv/bin/pip install -r requirements.txt

# Run database migrations (if any)
sudo -u pdfsmaller /var/app/pdfsmaller/venv/bin/python manage_db.py upgrade

# Start services
sudo systemctl start pdfsmaller pdfsmaller-celery pdfsmaller-beat

# Check status
sudo systemctl status pdfsmaller

echo "Application update completed successfully!"
```

### 2. File Cleanup

Create cleanup script `/usr/local/bin/cleanup_old_files.sh`:
```bash
#!/bin/bash

# Remove files older than 24 hours from uploads directory
find /var/app/uploads -type f -mtime +1 -delete

# Remove empty directories
find /var/app/uploads -type d -empty -delete

# Clean up old log files
find /var/log/pdfsmaller -name "*.log.*" -mtime +30 -delete

echo "File cleanup completed"
```

Add to crontab:
```bash
sudo crontab -e
# Add line for hourly cleanup
0 * * * * /usr/local/bin/cleanup_old_files.sh
```

### 3. System Monitoring

Create monitoring script `/usr/local/bin/monitor_pdfsmaller.sh`:
```bash
#!/bin/bash

# Check if services are running
services=("pdfsmaller" "pdfsmaller-celery" "pdfsmaller-beat" "redis-server" "nginx")

for service in "${services[@]}"; do
    if ! systemctl is-active --quiet $service; then
        echo "WARNING: $service is not running"
        # Optionally send alert email or notification
    fi
done

# Check disk space
disk_usage=$(df /var/app | tail -1 | awk '{print $5}' | sed 's/%//')
if [ $disk_usage -gt 80 ]; then
    echo "WARNING: Disk usage is at ${disk_usage}%"
fi

# Check application health
health_response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:5000/api/health)
if [ $health_response -ne 200 ]; then
    echo "WARNING: Health check failed with status $health_response"
fi
```

Add to crontab:
```bash
sudo crontab -e
# Add line for monitoring every 5 minutes
*/5 * * * * /usr/local/bin/monitor_pdfsmaller.sh
```

## Troubleshooting Guide

### Common Issues

#### 1. Application Won't Start
```bash
# Check logs
sudo journalctl -u pdfsmaller -f

# Check configuration
sudo -u pdfsmaller /var/app/pdfsmaller/venv/bin/python -c "from app import app; print('Config OK')"

# Check database
sudo -u pdfsmaller /var/app/pdfsmaller/venv/bin/python manage_db.py status
```

#### 2. Celery Workers Not Processing Jobs
```bash
# Check worker status
sudo systemctl status pdfsmaller-celery

# Check Redis connection
redis-cli ping

# Monitor celery logs
sudo tail -f /var/log/pdfsmaller/celery-worker.log
```

#### 3. File Upload Issues
```bash
# Check upload directory permissions
ls -la /var/app/uploads

# Check disk space
df -h /var/app

# Check nginx configuration
sudo nginx -t
```

#### 4. High Memory Usage
```bash
# Check process memory usage
ps aux --sort=-%mem | head

# Monitor Redis memory
redis-cli info memory

# Check for memory leaks in application
sudo -u pdfsmaller /var/app/pdfsmaller/venv/bin/python -c "import psutil; print(f'Memory: {psutil.virtual_memory().percent}%')"
```

### Performance Optimization

#### 1. Database Optimization
```bash
# Vacuum SQLite database
sudo -u pdfsmaller sqlite3 /var/app/pdfsmaller/pdf_smaller_prod.db "VACUUM;"

# Analyze database
sudo -u pdfsmaller sqlite3 /var/app/pdfsmaller/pdf_smaller_prod.db "ANALYZE;"
```

#### 2. Redis Optimization
```bash
# Check Redis performance
redis-cli --latency-history

# Monitor Redis operations
redis-cli monitor
```

#### 3. Application Performance
```bash
# Monitor application metrics
curl http://localhost:5000/api/health

# Check response times
time curl -s http://localhost:5000/api/health > /dev/null
```

This deployment guide provides comprehensive instructions for deploying the PDF Smaller backend in both development and production environments, focusing on the core PDF processing functionality without authentication complexity.