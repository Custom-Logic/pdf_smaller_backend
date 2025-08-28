# PDF Smaller Backend - Complete Deployment Guide

This comprehensive guide covers deployment of the PDF Smaller backend with all implemented features including user authentication, subscription management, bulk processing, and enhanced security.

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
- PostgreSQL 13+ (SQLite for development)
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
JWT_SECRET_KEY=dev-jwt-secret-key-change-in-production
DEBUG=true

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

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Logging
LOG_LEVEL=DEBUG
LOG_FILE=app.log

# Rate Limiting
RATE_LIMIT_ENABLED=true

# Stripe (Test Keys)
STRIPE_PUBLISHABLE_KEY=pk_test_your_test_key
STRIPE_SECRET_KEY=sk_test_your_test_key
STRIPE_WEBHOOK_SECRET=whsec_test_your_webhook_secret

# Email (Optional for development)
MAIL_SERVER=localhost
MAIL_PORT=1025
MAIL_USE_TLS=false
```

#### Production (.env.production)
```bash
# Application Settings
FLASK_ENV=production
SECRET_KEY=your-super-secure-64-character-production-secret-key-here
JWT_SECRET_KEY=your-super-secure-jwt-secret-key-different-from-above
DEBUG=false

# Database
DATABASE_URL=postgresql://pdf_user:secure_password@localhost:5432/pdf_smaller_prod
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=30
DB_POOL_RECYCLE=3600

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
ALLOWED_ORIGINS=https://pdfsmaller.site,https://www.pdfsmaller.site

# Security
SECURITY_HEADERS_ENABLED=true
RATE_LIMIT_ENABLED=true
RATE_LIMIT_STORAGE_URL=redis://localhost:6379/1

# Logging
LOG_LEVEL=WARNING
LOG_FILE=/var/log/pdfsmaller/app.log
LOG_MAX_BYTES=10485760  # 10MB
LOG_BACKUP_COUNT=5

# Stripe (Live Keys)
STRIPE_PUBLISHABLE_KEY=pk_live_your_live_publishable_key
STRIPE_SECRET_KEY=sk_live_your_live_secret_key
STRIPE_WEBHOOK_SECRET=whsec_your_live_webhook_secret

# Email
MAIL_SERVER=smtp.your-provider.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@domain.com
MAIL_PASSWORD=your-email-password
MAIL_DEFAULT_SENDER=noreply@pdfsmaller.site

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

### 1. PostgreSQL Setup (Production)

#### Install PostgreSQL
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# CentOS/RHEL
sudo yum install postgresql-server postgresql-contrib
sudo postgresql-setup initdb
```

#### Create Database and User
```bash
sudo -u postgres psql

-- Create database
CREATE DATABASE pdf_smaller_prod;

-- Create user with secure password
CREATE USER pdf_user WITH PASSWORD 'your_secure_password_here';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE pdf_smaller_prod TO pdf_user;

-- Enable required extensions
\c pdf_smaller_prod
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

\q
```

#### Configure PostgreSQL
Edit `/etc/postgresql/13/main/postgresql.conf`:
```ini
# Connection settings
listen_addresses = 'localhost'
port = 5432
max_connections = 100

# Memory settings
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 4MB

# Logging
log_statement = 'mod'
log_min_duration_statement = 1000
```

Edit `/etc/postgresql/13/main/pg_hba.conf`:
```
# Local connections
local   pdf_smaller_prod    pdf_user                     md5
host    pdf_smaller_prod    pdf_user    127.0.0.1/32     md5
```

Restart PostgreSQL:
```bash
sudo systemctl restart postgresql
sudo systemctl enable postgresql
```

### 2. Database Initialization

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

### 3. Database Backup Configuration

Create backup script `/usr/local/bin/backup_pdfsmaller_db.sh`:
```bash
#!/bin/bash
BACKUP_DIR="/var/backups/pdfsmaller"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="pdf_smaller_prod"
DB_USER="pdf_user"

mkdir -p $BACKUP_DIR

# Create backup
pg_dump -h localhost -U $DB_USER $DB_NAME | gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# Keep only last 7 days of backups
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +7 -delete

echo "Database backup completed: backup_$DATE.sql.gz"
```

Add to crontab:
```bash
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
    depends_on:
      - postgres
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  celery-worker:
    build: .
    command: celery -A celery_worker.celery worker --loglevel=info --concurrency=4
    environment:
      - FLASK_ENV=production
    env_file:
      - .env.production
    volumes:
      - /var/app/uploads:/app/uploads
      - /var/log/pdfsmaller:/app/logs
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  celery-beat:
    build: .
    command: celery -A celery_worker.celery beat --loglevel=info
    environment:
      - FLASK_ENV=production
    env_file:
      - .env.production
    depends_on:
      - postgres
      - redis
    restart: unless-stopped

  postgres:
    image: postgres:13
    environment:
      POSTGRES_DB: pdf_smaller_prod
      POSTGRES_USER: pdf_user
      POSTGRES_PASSWORD: your_secure_password_here
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./backups:/backups
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
  postgres_data:
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
sudo apt-get install postgresql postgresql-contrib
sudo apt-get install redis-server
sudo apt-get install ghostscript
sudo apt-get install nginx
sudo apt-get install supervisor

# CentOS/RHEL
sudo yum install python3.11 python3.11-venv python3-pip
sudo yum install postgresql postgresql-server
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
After=network.target postgresql.service redis.service
Wants=postgresql.service redis.service

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
command=/var/app/pdfsmaller/venv/bin/celery -A celery_worker.celery worker --loglevel=info --concurrency=4
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
limit_req_zone $binary_remote_addr zone=auth:10m rate=5r/s;

# Upstream servers
upstream pdfsmaller_app {
    server 127.0.0.1:5000 max_fails=3 fail_timeout=30s;
}

# HTTP to HTTPS redirect
server {
    listen 80;
    server_name pdfsmaller.site www.pdfsmaller.site;
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name pdfsmaller.site www.pdfsmaller.site;

    # SSL Configuration
    ssl_certificate /etc/ssl/certs/pdfsmaller.site.crt;
    ssl_certificate_key /etc/ssl/private/pdfsmaller.site.key;
    
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

    # Authentication endpoints with stricter rate limiting
    location ~ ^/api/auth/(login|register|refresh) {
        proxy_pass http://pdfsmaller_app;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Stricter rate limiting for auth
        limit_req zone=auth burst=5 nodelay;
    }

    # Health check endpoint (no rate limiting)
    location /health {
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
    
    location ~ \.(env|log|conf)$ {
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
# Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d pdfsmaller.site -d www.pdfsmaller.site

# Test renewal
sudo certbot renew --dry-run

# Setup auto-renewal
echo "0 12 * * * /usr/bin/certbot renew --quiet" | sudo crontab -
```

### 3. Firewall Configuration

```bash
# Install UFW
sudo apt-get install ufw

# Default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH
sudo ufw allow ssh

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Allow PostgreSQL (local only)
sudo ufw allow from 127.0.0.1 to any port 5432

# Allow Redis (local only)
sudo ufw allow from 127.0.0.1 to any port 6379

# Enable firewall
sudo ufw enable

# Check status
sudo ufw status verbose
```

## Monitoring and Logging

### 1. Application Logging

Configure structured logging in `src/config/config.py`:
```python
LOGGING_CONFIG = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'detailed': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
        'json': {
            'format': '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}'
        }
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/pdfsmaller/app.log',
            'maxBytes': 10485760,  # 10MB
            'backupCount': 5,
            'formatter': 'detailed'
        },
        'security': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': '/var/log/pdfsmaller/security.log',
            'maxBytes': 10485760,
            'backupCount': 10,
            'formatter': 'json'
        }
    },
    'loggers': {
        'pdfsmaller': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': False
        },
        'security': {
            'handlers': ['security'],
            'level': 'WARNING',
            'propagate': False
        }
    }
}
```

### 2. Health Check Endpoints

The application includes comprehensive health checks:
- `/health` - Basic application health
- `/health/db` - Database connectivity
- `/health/redis` - Redis connectivity
- `/health/celery` - Celery worker status

### 3. Log Rotation

Create `/etc/logrotate.d/pdfsmaller`:
```
/var/log/pdfsmaller/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 pdfsmaller pdfsmaller
    postrotate
        systemctl reload pdfsmaller
    endscript
}
```

### 4. Monitoring with Prometheus (Optional)

Install Prometheus and Grafana:
```bash
# Add Prometheus user
sudo useradd --no-create-home --shell /bin/false prometheus

# Download and install Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
tar xvf prometheus-2.40.0.linux-amd64.tar.gz
sudo cp prometheus-2.40.0.linux-amd64/prometheus /usr/local/bin/
sudo cp prometheus-2.40.0.linux-amd64/promtool /usr/local/bin/

# Create directories
sudo mkdir /etc/prometheus
sudo mkdir /var/lib/prometheus
sudo chown prometheus:prometheus /etc/prometheus
sudo chown prometheus:prometheus /var/lib/prometheus
```

Create Prometheus configuration `/etc/prometheus/prometheus.yml`:
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'pdfsmaller'
    static_configs:
      - targets: ['localhost:5000']
    metrics_path: '/metrics'
    scrape_interval: 30s
```

## Maintenance Procedures

### 1. Regular Maintenance Tasks

Create maintenance script `/usr/local/bin/pdfsmaller_maintenance.sh`:
```bash
#!/bin/bash

LOG_FILE="/var/log/pdfsmaller/maintenance.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')

echo "[$DATE] Starting maintenance tasks" >> $LOG_FILE

# 1. Clean up expired files
cd /var/app/pdfsmaller
source venv/bin/activate
python -c "
from src.services.cleanup_service import CleanupService
result = CleanupService.cleanup_expired_jobs()
print(f'Cleaned up {result[\"jobs_cleaned\"]} expired jobs')
result = CleanupService.cleanup_temp_files('/var/app/uploads')
print(f'Cleaned up {result[\"files_cleaned\"]} temporary files')
" >> $LOG_FILE 2>&1

# 2. Database maintenance
sudo -u postgres psql pdf_smaller_prod -c "VACUUM ANALYZE;" >> $LOG_FILE 2>&1

# 3. Log rotation check
logrotate -f /etc/logrotate.d/pdfsmaller >> $LOG_FILE 2>&1

# 4. Check disk space
df -h /var/app/uploads >> $LOG_FILE 2>&1

echo "[$DATE] Maintenance tasks completed" >> $LOG_FILE
```

Add to crontab:
```bash
sudo crontab -e
# Daily maintenance at 3 AM
0 3 * * * /usr/local/bin/pdfsmaller_maintenance.sh
```

### 2. Update Procedures

Create update script `/usr/local/bin/update_pdfsmaller.sh`:
```bash
#!/bin/bash

APP_DIR="/var/app/pdfsmaller"
BACKUP_DIR="/var/backups/pdfsmaller"
DATE=$(date +%Y%m%d_%H%M%S)

echo "Starting PDF Smaller update process..."

# 1. Create backup
mkdir -p $BACKUP_DIR
cp -r $APP_DIR $BACKUP_DIR/app_backup_$DATE

# 2. Stop services
sudo systemctl stop pdfsmaller pdfsmaller-celery pdfsmaller-beat

# 3. Update code
cd $APP_DIR
git pull origin main

# 4. Update dependencies
source venv/bin/activate
pip install -r requirements.txt

# 5. Run database migrations (if any)
python manage_db.py upgrade

# 6. Start services
sudo systemctl start pdfsmaller pdfsmaller-celery pdfsmaller-beat

# 7. Verify deployment
sleep 10
curl -f http://localhost:5000/health || {
    echo "Health check failed, rolling back..."
    sudo systemctl stop pdfsmaller pdfsmaller-celery pdfsmaller-beat
    rm -rf $APP_DIR
    cp -r $BACKUP_DIR/app_backup_$DATE $APP_DIR
    sudo systemctl start pdfsmaller pdfsmaller-celery pdfsmaller-beat
    exit 1
}

echo "Update completed successfully"
```

### 3. Backup Procedures

Create comprehensive backup script `/usr/local/bin/full_backup_pdfsmaller.sh`:
```bash
#!/bin/bash

BACKUP_ROOT="/var/backups/pdfsmaller"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="$BACKUP_ROOT/full_backup_$DATE"

mkdir -p $BACKUP_DIR

# 1. Database backup
pg_dump -h localhost -U pdf_user pdf_smaller_prod | gzip > $BACKUP_DIR/database.sql.gz

# 2. Application files backup
tar -czf $BACKUP_DIR/application.tar.gz -C /var/app pdfsmaller

# 3. Configuration backup
cp /var/app/pdfsmaller/.env $BACKUP_DIR/
cp -r /etc/nginx/sites-available/pdfsmaller $BACKUP_DIR/nginx.conf
cp -r /etc/systemd/system/pdfsmaller* $BACKUP_DIR/

# 4. Upload files backup (if not too large)
UPLOAD_SIZE=$(du -s /var/app/uploads | cut -f1)
if [ $UPLOAD_SIZE -lt 1048576 ]; then  # Less than 1GB
    tar -czf $BACKUP_DIR/uploads.tar.gz -C /var/app uploads
fi

# 5. Clean old backups (keep 7 days)
find $BACKUP_ROOT -name "full_backup_*" -mtime +7 -exec rm -rf {} \;

echo "Full backup completed: $BACKUP_DIR"
```

## Troubleshooting Guide

### Common Issues and Solutions

#### 1. Application Won't Start

**Symptoms:**
- Service fails to start
- Connection refused errors
- Import errors

**Diagnosis:**
```bash
# Check service status
sudo systemctl status pdfsmaller

# Check logs
sudo journalctl -u pdfsmaller -f

# Test configuration
cd /var/app/pdfsmaller
source venv/bin/activate
python -c "from src.config.config import validate_current_config; validate_current_config()"
```

**Solutions:**
- Verify environment variables are set correctly
- Check database connectivity
- Ensure all dependencies are installed
- Verify file permissions

#### 2. Database Connection Issues

**Symptoms:**
- Database connection errors
- Authentication failures
- Timeout errors

**Diagnosis:**
```bash
# Test database connection
sudo -u postgres psql pdf_smaller_prod

# Check PostgreSQL status
sudo systemctl status postgresql

# Test from application
cd /var/app/pdfsmaller
source venv/bin/activate
python -c "
from src.models.base import db
from src.main.main import create_app
app = create_app()
with app.app_context():
    db.session.execute('SELECT 1')
    print('Database connection successful')
"
```

**Solutions:**
- Verify DATABASE_URL format
- Check PostgreSQL is running
- Verify user permissions
- Check network connectivity

#### 3. Celery Tasks Not Processing

**Symptoms:**
- Tasks stuck in pending state
- No worker processes
- Redis connection errors

**Diagnosis:**
```bash
# Check Celery worker status
celery -A celery_worker.celery inspect active

# Check Redis connection
redis-cli ping

# Check task queue
redis-cli llen celery
```

**Solutions:**
- Restart Celery workers
- Check Redis connectivity
- Verify task routing configuration
- Check worker logs for errors

#### 4. File Upload Issues

**Symptoms:**
- File upload failures
- Permission denied errors
- Disk space errors

**Diagnosis:**
```bash
# Check upload directory permissions
ls -la /var/app/uploads

# Check disk space
df -h /var/app/uploads

# Check file size limits
grep MAX_FILE_SIZE /var/app/pdfsmaller/.env
```

**Solutions:**
- Fix directory permissions
- Free up disk space
- Adjust file size limits
- Check Nginx client_max_body_size

#### 5. High Memory Usage

**Symptoms:**
- Out of memory errors
- Slow performance
- Process killed by OOM killer

**Diagnosis:**
```bash
# Check memory usage
free -h
ps aux | grep -E "(python|celery)" | sort -k4 -nr

# Check for memory leaks
top -p $(pgrep -f "python.*app.py")
```

**Solutions:**
- Reduce Celery worker concurrency
- Implement file processing limits
- Add swap space
- Optimize database queries
- Enable automatic cleanup

#### 6. SSL/TLS Issues

**Symptoms:**
- Certificate errors
- Mixed content warnings
- HTTPS redirect loops

**Diagnosis:**
```bash
# Test SSL certificate
openssl s_client -connect pdfsmaller.site:443

# Check certificate expiry
openssl x509 -in /etc/ssl/certs/pdfsmaller.site.crt -text -noout | grep "Not After"

# Test Nginx configuration
sudo nginx -t
```

**Solutions:**
- Renew SSL certificates
- Fix Nginx configuration
- Check certificate chain
- Verify DNS settings

### Performance Optimization

#### 1. Database Optimization

```sql
-- Add indexes for common queries
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_compression_jobs_user_id ON compression_jobs(user_id);
CREATE INDEX idx_compression_jobs_status ON compression_jobs(status);
CREATE INDEX idx_compression_jobs_created_at ON compression_jobs(created_at);

-- Analyze tables
ANALYZE users;
ANALYZE subscriptions;
ANALYZE compression_jobs;
```

#### 2. Application Optimization

```python
# Enable connection pooling
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 20,
    'max_overflow': 30,
    'pool_recycle': 3600,
    'pool_pre_ping': True
}

# Enable query optimization
SQLALCHEMY_RECORD_QUERIES = False
SQLALCHEMY_TRACK_MODIFICATIONS = False
```

#### 3. Caching Configuration

```python
# Redis caching for rate limiting and sessions
CACHE_TYPE = 'redis'
CACHE_REDIS_URL = 'redis://localhost:6379/1'
CACHE_DEFAULT_TIMEOUT = 300
```

This comprehensive deployment guide covers all aspects of deploying the PDF Smaller backend in production, including security, monitoring, and maintenance procedures. Follow the sections relevant to your deployment method and environment.