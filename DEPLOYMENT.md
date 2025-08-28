# Deployment Guide

This guide covers deployment options for the PDF Smaller backend application.

## Quick Start

### Development Setup

1. **Clone and setup**:
   ```bash
   cd pdf_smaller_backend
   python scripts/setup.py
   ```

2. **Start services**:
   ```bash
   # Start Redis
   redis-server
   
   # Start the application
   python app.py
   ```

3. **Or use Docker**:
   ```bash
   docker-compose -f docker-compose.dev.yml up
   ```

### Production Setup

1. **Environment Configuration**:
   ```bash
   cp .env.example .env
   # Edit .env with production values
   ```

2. **Docker Deployment**:
   ```bash
   docker-compose up -d
   ```

## Deployment Options

### 1. Docker Deployment (Recommended)

#### Production with Docker Compose

```bash
# Set environment variables
export SECRET_KEY="your-production-secret-key"
export JWT_SECRET_KEY="your-jwt-secret-key"
export STRIPE_SECRET_KEY="sk_live_your_stripe_key"
export STRIPE_WEBHOOK_SECRET="whsec_your_webhook_secret"
export ALLOWED_ORIGINS="https://yourdomain.com"

# Deploy
docker-compose up -d

# With Nginx (for SSL termination)
docker-compose --profile production up -d
```

#### Development with Docker

```bash
docker-compose -f docker-compose.dev.yml up
```

### 2. Manual Deployment

#### System Requirements

- Python 3.11+
- PostgreSQL 12+
- Redis 6+
- Ghostscript
- Nginx (for production)

#### Installation Steps

1. **Install system dependencies**:
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install python3.11 python3.11-venv python3-pip
   sudo apt-get install postgresql postgresql-contrib
   sudo apt-get install redis-server
   sudo apt-get install ghostscript
   sudo apt-get install nginx
   
   # CentOS/RHEL
   sudo yum install python3.11 python3.11-venv python3-pip
   sudo yum install postgresql postgresql-server
   sudo yum install redis
   sudo yum install ghostscript
   sudo yum install nginx
   ```

2. **Setup application**:
   ```bash
   # Create application user
   sudo useradd -m -s /bin/bash pdfsmaller
   sudo su - pdfsmaller
   
   # Clone repository
   git clone <repository-url> pdf_smaller_backend
   cd pdf_smaller_backend
   
   # Create virtual environment
   python3.11 -m venv venv
   source venv/bin/activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Setup configuration
   cp .env.example .env
   # Edit .env with your settings
   
   # Run setup script
   python scripts/setup.py
   ```

3. **Configure database**:
   ```bash
   # Create database and user
   sudo -u postgres psql
   CREATE DATABASE pdf_smaller;
   CREATE USER pdf_user WITH PASSWORD 'secure_password';
   GRANT ALL PRIVILEGES ON DATABASE pdf_smaller TO pdf_user;
   \q
   
   # Update DATABASE_URL in .env
   DATABASE_URL=postgresql://pdf_user:secure_password@localhost:5432/pdf_smaller
   ```

4. **Setup systemd services**:

   Create `/etc/systemd/system/pdfsmaller.service`:
   ```ini
   [Unit]
   Description=PDF Smaller Web Application
   After=network.target postgresql.service redis.service
   
   [Service]
   Type=exec
   User=pdfsmaller
   Group=pdfsmaller
   WorkingDirectory=/home/pdfsmaller/pdf_smaller_backend
   Environment=PATH=/home/pdfsmaller/pdf_smaller_backend/venv/bin
   EnvironmentFile=/home/pdfsmaller/pdf_smaller_backend/.env
   ExecStart=/home/pdfsmaller/pdf_smaller_backend/venv/bin/gunicorn --config gunicorn_conf.py app:app
   Restart=always
   RestartSec=3
   
   [Install]
   WantedBy=multi-user.target
   ```

   Create `/etc/systemd/system/pdfsmaller-celery.service`:
   ```ini
   [Unit]
   Description=PDF Smaller Celery Worker
   After=network.target redis.service
   
   [Service]
   Type=exec
   User=pdfsmaller
   Group=pdfsmaller
   WorkingDirectory=/home/pdfsmaller/pdf_smaller_backend
   Environment=PATH=/home/pdfsmaller/pdf_smaller_backend/venv/bin
   EnvironmentFile=/home/pdfsmaller/pdf_smaller_backend/.env
   ExecStart=/home/pdfsmaller/pdf_smaller_backend/venv/bin/celery -A celery_worker.celery worker --loglevel=info --concurrency=2
   Restart=always
   RestartSec=3
   
   [Install]
   WantedBy=multi-user.target
   ```

   Enable and start services:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable pdfsmaller pdfsmaller-celery
   sudo systemctl start pdfsmaller pdfsmaller-celery
   ```

### 3. Cloud Deployment

#### AWS Deployment

1. **Using AWS ECS with Fargate**:
   - Build and push Docker image to ECR
   - Create ECS task definition
   - Setup RDS PostgreSQL instance
   - Setup ElastiCache Redis cluster
   - Configure Application Load Balancer

2. **Using AWS Elastic Beanstalk**:
   - Create application zip file
   - Deploy to Elastic Beanstalk environment
   - Configure RDS and ElastiCache add-ons

#### Google Cloud Platform

1. **Using Cloud Run**:
   - Build and push to Container Registry
   - Deploy to Cloud Run
   - Setup Cloud SQL PostgreSQL
   - Setup Memorystore Redis

#### Heroku Deployment

1. **Setup**:
   ```bash
   # Install Heroku CLI and login
   heroku login
   
   # Create application
   heroku create your-app-name
   
   # Add PostgreSQL and Redis add-ons
   heroku addons:create heroku-postgresql:hobby-dev
   heroku addons:create heroku-redis:hobby-dev
   
   # Set environment variables
   heroku config:set FLASK_ENV=production
   heroku config:set SECRET_KEY="your-secret-key"
   heroku config:set JWT_SECRET_KEY="your-jwt-key"
   heroku config:set STRIPE_SECRET_KEY="your-stripe-key"
   
   # Deploy
   git push heroku main
   ```

## Configuration

### Environment Variables

See [CONFIG.md](CONFIG.md) for detailed configuration options.

### Critical Production Settings

```bash
# Security
SECRET_KEY="generate-a-secure-64-character-random-string"
JWT_SECRET_KEY="generate-another-secure-random-string"

# Database
DATABASE_URL="postgresql://user:password@host:5432/database"

# Stripe (Live Keys)
STRIPE_SECRET_KEY="sk_live_your_live_secret_key"
STRIPE_WEBHOOK_SECRET="whsec_your_webhook_secret"

# CORS
ALLOWED_ORIGINS="https://yourdomain.com,https://www.yourdomain.com"

# File Storage
UPLOAD_FOLDER="/var/app/uploads"
MAX_FILE_SIZE=104857600  # 100MB

# Logging
LOG_LEVEL=WARNING
LOG_FILE="/var/log/pdfsmaller/app.log"
```

## SSL/TLS Configuration

### Nginx Configuration

Create `/etc/nginx/sites-available/pdfsmaller`:

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/ssl/certs/yourdomain.com.crt;
    ssl_certificate_key /etc/ssl/private/yourdomain.com.key;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512:ECDHE-RSA-AES256-GCM-SHA384:DHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;

    client_max_body_size 100M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    location /health {
        proxy_pass http://127.0.0.1:5000/health;
        access_log off;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/pdfsmaller /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Monitoring and Logging

### Log Files

- Application logs: `/var/log/pdfsmaller/app.log`
- Celery logs: `/var/log/pdfsmaller/celery.log`
- Nginx logs: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`

### Health Checks

- Application health: `GET /health`
- Database health: `GET /health/db`
- Redis health: `GET /health/redis`

### Monitoring Setup

1. **Prometheus + Grafana**:
   - Enable metrics in configuration
   - Setup Prometheus to scrape metrics endpoint
   - Create Grafana dashboards

2. **ELK Stack**:
   - Configure structured logging
   - Ship logs to Elasticsearch
   - Create Kibana dashboards

## Backup and Recovery

### Database Backup

```bash
# Create backup
pg_dump -h localhost -U pdf_user pdf_smaller > backup_$(date +%Y%m%d_%H%M%S).sql

# Restore backup
psql -h localhost -U pdf_user pdf_smaller < backup_file.sql
```

### File Storage Backup

```bash
# Backup uploads directory
tar -czf uploads_backup_$(date +%Y%m%d_%H%M%S).tar.gz /var/app/uploads/

# Restore uploads
tar -xzf uploads_backup.tar.gz -C /
```

## Scaling

### Horizontal Scaling

1. **Load Balancer**: Use Nginx, HAProxy, or cloud load balancer
2. **Multiple App Instances**: Run multiple Gunicorn processes
3. **Celery Workers**: Scale worker processes based on queue length
4. **Database**: Use read replicas for read-heavy workloads

### Vertical Scaling

1. **CPU**: Increase Gunicorn workers and Celery concurrency
2. **Memory**: Increase based on file processing requirements
3. **Storage**: Use SSD for better I/O performance

## Troubleshooting

### Common Issues

1. **Database Connection Errors**:
   - Check DATABASE_URL format
   - Verify database server is running
   - Check network connectivity and firewall rules

2. **File Upload Errors**:
   - Verify UPLOAD_FOLDER exists and is writable
   - Check disk space
   - Verify MAX_CONTENT_LENGTH setting

3. **Celery Task Failures**:
   - Check Redis connection
   - Verify Celery worker is running
   - Check worker logs for errors

4. **High Memory Usage**:
   - Monitor file processing queue
   - Implement file cleanup policies
   - Consider processing limits

### Debug Commands

```bash
# Check application status
systemctl status pdfsmaller

# View application logs
journalctl -u pdfsmaller -f

# Check Celery worker status
celery -A celery_worker.celery inspect active

# Test database connection
python -c "from src.main.main import create_app; from src.models.base import db; app = create_app(); app.app_context().push(); db.session.execute('SELECT 1')"

# Test Redis connection
redis-cli ping
```

## Security Checklist

- [ ] Use strong, unique SECRET_KEY and JWT_SECRET_KEY
- [ ] Enable HTTPS with valid SSL certificates
- [ ] Configure proper CORS origins
- [ ] Use production Stripe keys (not test keys)
- [ ] Set up proper file permissions
- [ ] Configure firewall rules
- [ ] Enable database SSL connections
- [ ] Set up regular security updates
- [ ] Configure rate limiting
- [ ] Enable security headers
- [ ] Set up monitoring and alerting
- [ ] Regular backup testing