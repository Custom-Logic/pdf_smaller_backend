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

## Production Best Practices

### 1. High Availability Setup

#### Load Balancer Configuration
For production environments handling high traffic, implement load balancing:

```nginx
# /etc/nginx/conf.d/pdfsmaller-lb.conf
upstream pdfsmaller_backend {
    least_conn;
    server 10.0.1.10:5000 max_fails=3 fail_timeout=30s weight=1;
    server 10.0.1.11:5000 max_fails=3 fail_timeout=30s weight=1;
    server 10.0.1.12:5000 max_fails=3 fail_timeout=30s weight=1;
    
    # Health check
    keepalive 32;
}

server {
    listen 443 ssl http2;
    server_name api.yourserver.com;
    
    location / {
        proxy_pass http://pdfsmaller_backend;
        proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

#### Redis Cluster Setup
For production resilience, configure Redis in cluster mode:

```bash
# Redis cluster configuration
# /etc/redis/redis-cluster.conf
port 7000
cluster-enabled yes
cluster-config-file nodes-7000.conf
cluster-node-timeout 5000
appendonly yes

# Start cluster nodes
redis-server /etc/redis/redis-cluster.conf

# Initialize cluster
redis-cli --cluster create 127.0.0.1:7000 127.0.0.1:7001 127.0.0.1:7002 --cluster-replicas 0
```

### 2. Performance Optimization

#### Gunicorn Production Configuration
Create optimized `gunicorn_conf.py`:

```python
# gunicorn_conf.py
import multiprocessing
import os

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "gevent"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 50
preload_app = True

# Timeouts
timeout = 300
keepalive = 2
graceful_timeout = 30

# Logging
accesslog = "/var/log/pdfsmaller/gunicorn-access.log"
errorlog = "/var/log/pdfsmaller/gunicorn-error.log"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s'

# Process naming
proc_name = 'pdfsmaller'

# Server mechanics
daemon = False
pidfile = '/var/run/pdfsmaller/gunicorn.pid'
user = 'pdfsmaller'
group = 'pdfsmaller'
tmp_upload_dir = None

# SSL (if terminating SSL at application level)
# keyfile = '/etc/ssl/private/server.key'
# certfile = '/etc/ssl/certs/server.crt'
```

#### Celery Production Configuration
Optimize Celery for production workloads:

```python
# celery_config.py
from kombu import Queue

# Broker settings
broker_url = 'redis://localhost:6379/0'
result_backend = 'redis://localhost:6379/0'

# Task routing
task_routes = {
    'app.tasks.compress_pdf': {'queue': 'compression'},
    'app.tasks.cleanup_files': {'queue': 'cleanup'},
    'app.tasks.health_check': {'queue': 'monitoring'}
}

# Queue configuration
task_default_queue = 'default'
task_queues = (
    Queue('compression', routing_key='compression'),
    Queue('cleanup', routing_key='cleanup'),
    Queue('monitoring', routing_key='monitoring'),
    Queue('default', routing_key='default'),
)

# Performance settings
worker_prefetch_multiplier = 1
task_acks_late = True
worker_max_tasks_per_child = 1000

# Serialization
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']

# Monitoring
worker_send_task_events = True
task_send_sent_event = True

# Result backend settings
result_expires = 3600  # 1 hour
result_backend_transport_options = {
    'master_name': 'mymaster',
    'visibility_timeout': 3600,
}
```

### 3. Security Hardening

#### Application Security
```python
# security_config.py
from flask_talisman import Talisman
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

def configure_security(app):
    # Content Security Policy
    csp = {
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline'",
        'style-src': "'self' 'unsafe-inline'",
        'img-src': "'self' data:",
        'font-src': "'self'",
        'connect-src': "'self'",
        'frame-ancestors': "'none'"
    }
    
    # Security headers
    Talisman(app, 
        force_https=True,
        strict_transport_security=True,
        content_security_policy=csp,
        referrer_policy='strict-origin-when-cross-origin'
    )
    
    # Rate limiting
    limiter = Limiter(
        app,
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"]
    )
    
    return limiter
```

#### System Security
```bash
# /etc/security/limits.conf
pdfsmaller soft nofile 65536
pdfsmaller hard nofile 65536
pdfsmaller soft nproc 32768
pdfsmaller hard nproc 32768

# Disable unnecessary services
sudo systemctl disable bluetooth
sudo systemctl disable cups
sudo systemctl disable avahi-daemon

# Configure fail2ban
sudo apt-get install fail2ban

# /etc/fail2ban/jail.local
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[nginx-http-auth]
enabled = true
filter = nginx-http-auth
logpath = /var/log/nginx/error.log

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
logpath = /var/log/nginx/error.log
```

## Advanced Monitoring and Alerting

### 1. Prometheus Integration

#### Application Metrics
```python
# metrics.py
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from flask import Response
import time

# Metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('http_request_duration_seconds', 'HTTP request duration')
ACTIVE_JOBS = Gauge('active_compression_jobs', 'Number of active compression jobs')
FILE_SIZE_PROCESSED = Counter('file_size_processed_bytes_total', 'Total bytes processed')
COMPRESSION_RATIO = Histogram('compression_ratio', 'PDF compression ratio achieved')

def setup_metrics(app):
    @app.before_request
    def before_request():
        request.start_time = time.time()
    
    @app.after_request
    def after_request(response):
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.endpoint or 'unknown',
            status=response.status_code
        ).inc()
        
        if hasattr(request, 'start_time'):
            REQUEST_DURATION.observe(time.time() - request.start_time)
        
        return response
    
    @app.route('/metrics')
    def metrics():
        return Response(generate_latest(), mimetype='text/plain')
```

#### Prometheus Configuration
```yaml
# /etc/prometheus/prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

rule_files:
  - "pdfsmaller_rules.yml"

scrape_configs:
  - job_name: 'pdfsmaller'
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/metrics'
    scrape_interval: 30s
    
  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']
    
  - job_name: 'nginx'
    static_configs:
      - targets: ['localhost:9113']

alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - localhost:9093
```

#### Alert Rules
```yaml
# /etc/prometheus/pdfsmaller_rules.yml
groups:
  - name: pdfsmaller_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors per second"
      
      - alert: HighResponseTime
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High response time detected"
          description: "95th percentile response time is {{ $value }} seconds"
      
      - alert: ServiceDown
        expr: up == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Service is down"
          description: "{{ $labels.instance }} has been down for more than 1 minute"
      
      - alert: HighDiskUsage
        expr: (node_filesystem_size_bytes - node_filesystem_free_bytes) / node_filesystem_size_bytes > 0.8
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High disk usage"
          description: "Disk usage is above 80%"
```

### 2. Grafana Dashboard

#### Dashboard Configuration
```json
{
  "dashboard": {
    "title": "PDF Smaller Backend Monitoring",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(http_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          },
          {
            "expr": "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "50th percentile"
          }
        ]
      },
      {
        "title": "Active Jobs",
        "type": "singlestat",
        "targets": [
          {
            "expr": "active_compression_jobs",
            "legendFormat": "Active Jobs"
          }
        ]
      },
      {
        "title": "Compression Efficiency",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.50, rate(compression_ratio_bucket[5m]))",
            "legendFormat": "Median Compression Ratio"
          }
        ]
      }
    ]
  }
}
```

## Scaling Strategies

### 1. Horizontal Scaling

#### Multi-Instance Deployment
```yaml
# docker-compose.scale.yml
version: '3.8'

services:
  app:
    build: .
    deploy:
      replicas: 3
    environment:
      - FLASK_ENV=production
    env_file:
      - .env.production
    volumes:
      - shared_uploads:/app/uploads
      - shared_data:/app/data
    depends_on:
      - redis
    
  celery-worker:
    build: .
    command: celery -A celery_worker.celery worker --loglevel=info --concurrency=2
    deploy:
      replicas: 6
    environment:
      - FLASK_ENV=production
    env_file:
      - .env.production
    volumes:
      - shared_uploads:/app/uploads
      - shared_data:/app/data
    depends_on:
      - redis

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf
    depends_on:
      - app

volumes:
  shared_uploads:
    driver: local
    driver_opts:
      type: nfs
      o: addr=nfs-server.local,rw
      device: ":/var/nfs/uploads"
  shared_data:
    driver: local
    driver_opts:
      type: nfs
      o: addr=nfs-server.local,rw
      device: ":/var/nfs/data"
```

#### Auto-scaling with Docker Swarm
```bash
# Initialize swarm
docker swarm init

# Deploy stack
docker stack deploy -c docker-compose.scale.yml pdfsmaller

# Scale services
docker service scale pdfsmaller_app=5
docker service scale pdfsmaller_celery-worker=10
```

### 2. Vertical Scaling

#### Resource Optimization
```bash
# /etc/systemd/system/pdfsmaller.service.d/override.conf
[Service]
# Memory limits
MemoryMax=2G
MemoryHigh=1.5G

# CPU limits
CPUQuota=200%

# I/O limits
IOWeight=500

# Process limits
LimitNOFILE=65536
LimitNPROC=32768
```

#### Database Scaling
```python
# database_config.py
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

def create_optimized_engine(database_url):
    return create_engine(
        database_url,
        poolclass=QueuePool,
        pool_size=20,
        max_overflow=30,
        pool_pre_ping=True,
        pool_recycle=3600,
        echo=False
    )
```

### 3. Performance Monitoring

#### Resource Usage Tracking
```bash
#!/bin/bash
# /usr/local/bin/performance_monitor.sh

# CPU usage
cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')

# Memory usage
mem_usage=$(free | grep Mem | awk '{printf "%.2f", $3/$2 * 100.0}')

# Disk I/O
disk_io=$(iostat -x 1 1 | grep -E "(sda|nvme)" | awk '{print $10}' | tail -1)

# Network usage
net_rx=$(cat /proc/net/dev | grep eth0 | awk '{print $2}')
net_tx=$(cat /proc/net/dev | grep eth0 | awk '{print $10}')

# Log metrics
echo "$(date): CPU=${cpu_usage}% MEM=${mem_usage}% DISK_IO=${disk_io}% NET_RX=${net_rx} NET_TX=${net_tx}" >> /var/log/pdfsmaller/performance.log

# Send to monitoring system
curl -X POST http://localhost:9090/api/v1/write \
  -H 'Content-Type: application/x-protobuf' \
  --data-binary @<(echo "cpu_usage ${cpu_usage}")
```

This comprehensive deployment guide provides production-ready instructions for deploying the PDF Smaller backend with high availability, security, monitoring, and scaling capabilities, focusing on the core PDF processing functionality without authentication complexity.