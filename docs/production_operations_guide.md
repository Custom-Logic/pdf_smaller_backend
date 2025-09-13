# Production Operations Guide

## Overview

This guide provides comprehensive operational procedures for running the PDF Smaller Backend service in production environments. It covers deployment, monitoring, maintenance, troubleshooting, and disaster recovery procedures.

## Table of Contents

1. [Production Environment Setup](#production-environment-setup)
2. [Deployment Procedures](#deployment-procedures)
3. [Monitoring & Alerting](#monitoring--alerting)
4. [Maintenance Procedures](#maintenance-procedures)
5. [Troubleshooting Guide](#troubleshooting-guide)
6. [Disaster Recovery](#disaster-recovery)
7. [Performance Tuning](#performance-tuning)
8. [Security Operations](#security-operations)
9. [Backup & Recovery](#backup--recovery)
10. [Incident Response](#incident-response)

## Production Environment Setup

### Infrastructure Requirements

**Minimum Production Specifications:**
- **API Servers**: 2x instances (4 vCPU, 8GB RAM, 100GB SSD)
- **Worker Nodes**: 3x instances (8 vCPU, 16GB RAM, 200GB SSD)
- **Database**: PostgreSQL 14+ (4 vCPU, 16GB RAM, 500GB SSD with IOPS provisioning)
- **Cache Layer**: Redis 7+ (2 vCPU, 4GB RAM, 50GB SSD)
- **Load Balancer**: HAProxy or AWS ALB with SSL termination
- **Storage**: S3-compatible object storage with lifecycle policies

**Network Requirements:**
- **Bandwidth**: Minimum 1Gbps with burst capability
- **Latency**: < 10ms between services in same region
- **Security Groups**: Properly configured firewall rules
- **DNS**: Proper DNS configuration with health checks

### Environment Configuration

**Production Environment Variables:**
```bash
# Application Configuration
FLASK_ENV=production
FLASK_DEBUG=False
SECRET_KEY=<secure-random-key>
APP_NAME=pdf-smaller-backend
APP_VERSION=1.0.0

# Database Configuration
DATABASE_URL=postgresql://user:pass@db-host:5432/pdf_smaller_prod
DB_POOL_SIZE=25
DB_MAX_OVERFLOW=30
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600

# Redis Configuration
REDIS_URL=redis://redis-host:6379/0
REDIS_MAX_CONNECTIONS=50
REDIS_SOCKET_TIMEOUT=5
REDIS_SOCKET_CONNECT_TIMEOUT=5

# Celery Configuration
CELERY_BROKER_URL=redis://redis-host:6379/0
CELERY_RESULT_BACKEND=redis://redis-host:6379/0
CELERY_TASK_SERIALIZER=json
CELERY_RESULT_SERIALIZER=json
CELERY_ACCEPT_CONTENT=['json']
CELERY_TIMEZONE=UTC
CELERY_ENABLE_UTC=True

# File Storage Configuration
UPLOAD_FOLDER=/app/uploads
MAX_CONTENT_LENGTH=104857600  # 100MB
ALLOWED_EXTENSIONS=pdf
FILE_RETENTION_DAYS=7

# Security Configuration
CORS_ORIGINS=https://yourdomain.com
RATE_LIMIT_STORAGE_URL=redis://redis-host:6379/1
RATE_LIMIT_DEFAULT=100 per hour

# Monitoring Configuration
PROMETHEUS_METRICS_PORT=9090
LOG_LEVEL=INFO
LOG_FORMAT=json
SENTRY_DSN=<sentry-dsn>

# External Services
CLAMAV_HOST=clamav-host
CLAMAV_PORT=3310
CLAMAV_TIMEOUT=30
```

## Deployment Procedures

### Pre-Deployment Checklist

**Code Quality Verification:**
- [ ] All tests passing (unit, integration, e2e)
- [ ] Code review completed and approved
- [ ] Security scan completed (no critical vulnerabilities)
- [ ] Performance benchmarks within acceptable range
- [ ] Documentation updated

**Infrastructure Verification:**
- [ ] Database migrations tested in staging
- [ ] Configuration changes validated
- [ ] Resource capacity verified
- [ ] Monitoring and alerting configured
- [ ] Rollback plan prepared

### Blue-Green Deployment Process

**Step 1: Prepare Green Environment**
```bash
# Deploy to green environment
docker-compose -f docker-compose.prod.yml up -d --scale api=2 --scale worker=3

# Run health checks
curl -f http://green-env/health
curl -f http://green-env/health/deep

# Run smoke tests
python scripts/smoke_tests.py --env=green
```

**Step 2: Database Migration (if required)**
```bash
# Backup current database
pg_dump -h db-host -U user pdf_smaller_prod > backup_$(date +%Y%m%d_%H%M%S).sql

# Run migrations
flask db upgrade

# Verify migration success
flask db current
```

**Step 3: Traffic Switch**
```bash
# Update load balancer configuration
# Switch traffic from blue to green environment
# Monitor metrics for 5 minutes

# If successful, scale down blue environment
# If issues detected, immediate rollback
```

### Rolling Deployment Process

**Step 1: Deploy to First Instance**
```bash
# Stop first instance
docker-compose stop api-1

# Deploy new version
docker-compose up -d api-1

# Health check
curl -f http://api-1:5000/health

# Monitor for 2 minutes
```

**Step 2: Continue Rolling Deployment**
```bash
# Repeat for each instance with 2-minute intervals
# Monitor error rates and response times
# Automatic rollback if error rate > 1%
```

## Monitoring & Alerting

### Key Performance Indicators (KPIs)

**Application Metrics:**
- **Request Rate**: Requests per second
- **Response Time**: 95th percentile response time
- **Error Rate**: Percentage of failed requests
- **Queue Depth**: Number of pending tasks
- **Processing Time**: Average file processing time
- **Success Rate**: Percentage of successful file processing

**Infrastructure Metrics:**
- **CPU Utilization**: Per service and overall
- **Memory Usage**: Per service and overall
- **Disk Usage**: Storage utilization and I/O
- **Network Traffic**: Bandwidth utilization
- **Database Performance**: Query time, connections, locks

### Alert Thresholds

**Critical Alerts (Immediate Response Required):**
- Service unavailable (HTTP 5xx > 5% for 2 minutes)
- Database connection failures
- Disk usage > 90%
- Memory usage > 95%
- Queue depth > 1000 tasks

**Warning Alerts (Response Within 30 Minutes):**
- Response time > 2 seconds (95th percentile)
- Error rate > 1% for 5 minutes
- CPU usage > 80% for 10 minutes
- Memory usage > 85% for 10 minutes
- Disk usage > 80%

**Info Alerts (Response Within 2 Hours):**
- Deployment notifications
- Configuration changes
- Scheduled maintenance reminders

### Monitoring Dashboard Setup

**Grafana Dashboard Configuration:**
```json
{
  "dashboard": {
    "title": "PDF Smaller Backend - Production",
    "panels": [
      {
        "title": "Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(flask_http_requests_total[5m])",
            "legendFormat": "{{method}} {{endpoint}}"
          }
        ]
      },
      {
        "title": "Response Time",
        "type": "graph",
        "targets": [
          {
            "expr": "histogram_quantile(0.95, rate(flask_http_request_duration_seconds_bucket[5m]))",
            "legendFormat": "95th percentile"
          }
        ]
      },
      {
        "title": "Error Rate",
        "type": "singlestat",
        "targets": [
          {
            "expr": "rate(flask_http_requests_total{status=~'5..'}[5m]) / rate(flask_http_requests_total[5m]) * 100",
            "legendFormat": "Error Rate %"
          }
        ]
      }
    ]
  }
}
```

## Maintenance Procedures

### Daily Maintenance Tasks

**Automated Daily Tasks:**
- Log rotation and cleanup
- Temporary file cleanup
- Database statistics update
- Cache cleanup and optimization
- Security scan execution

**Manual Daily Checks:**
- Review error logs for patterns
- Check system resource utilization
- Verify backup completion
- Review security alerts
- Monitor queue depths and processing times

### Weekly Maintenance Tasks

**System Maintenance:**
- Security patch review and planning
- Performance trend analysis
- Capacity planning review
- Database maintenance (VACUUM, ANALYZE)
- SSL certificate expiration check

**Application Maintenance:**
- Dependency vulnerability scan
- Code quality metrics review
- Documentation updates
- Test coverage analysis
- Performance benchmark comparison

### Monthly Maintenance Tasks

**Infrastructure Review:**
- Cost optimization analysis
- Disaster recovery testing
- Security audit and compliance check
- Performance optimization review
- Capacity planning and scaling decisions

**Process Improvement:**
- Incident post-mortem reviews
- SLA compliance analysis
- Team training and knowledge sharing
- Tool and process optimization
- Documentation review and updates

## Troubleshooting Guide

### Common Issues and Solutions

**High Response Times**

*Symptoms:*
- API response times > 2 seconds
- User complaints about slow performance
- High CPU or memory usage

*Diagnosis:*
```bash
# Check system resources
top -p $(pgrep -f "gunicorn")
free -h
df -h

# Check database performance
psql -c "SELECT query, mean_time, calls FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"

# Check Redis performance
redis-cli --latency-history

# Check application logs
tail -f /var/log/pdf-smaller/app.log | grep -E "(ERROR|SLOW)"
```

*Solutions:*
- Scale up application instances
- Optimize slow database queries
- Increase Redis memory allocation
- Review and optimize application code
- Check for memory leaks

**High Error Rates**

*Symptoms:*
- HTTP 5xx errors > 1%
- Failed file processing jobs
- Database connection errors

*Diagnosis:*
```bash
# Check error logs
grep -E "(ERROR|CRITICAL)" /var/log/pdf-smaller/app.log | tail -50

# Check database connections
psql -c "SELECT count(*) FROM pg_stat_activity;"

# Check Redis connectivity
redis-cli ping

# Check external service connectivity
curl -I http://clamav-host:3310
```

*Solutions:*
- Restart failed services
- Increase database connection pool
- Check external service availability
- Review and fix application bugs
- Scale infrastructure if needed

**Queue Backup**

*Symptoms:*
- Queue depth > 1000 tasks
- Long processing delays
- Worker processes not consuming tasks

*Diagnosis:*
```bash
# Check Celery worker status
celery -A src.tasks.tasks inspect active
celery -A src.tasks.tasks inspect stats

# Check Redis queue status
redis-cli llen celery

# Check worker logs
tail -f /var/log/pdf-smaller/celery.log
```

*Solutions:*
- Scale up worker instances
- Restart stuck workers
- Clear failed tasks from queue
- Optimize task processing logic
- Check for resource constraints

### Emergency Procedures

**Service Outage Response**

1. **Immediate Actions (0-5 minutes):**
   - Acknowledge alerts
   - Check service status dashboard
   - Identify affected components
   - Initiate incident response team

2. **Assessment Phase (5-15 minutes):**
   - Determine root cause
   - Assess impact scope
   - Estimate recovery time
   - Communicate status to stakeholders

3. **Recovery Actions (15+ minutes):**
   - Execute recovery procedures
   - Monitor recovery progress
   - Validate service restoration
   - Document incident details

**Database Failure Response**

1. **Immediate Actions:**
   - Switch to read-only mode if possible
   - Activate database failover
   - Notify development team

2. **Recovery Actions:**
   - Restore from latest backup
   - Replay transaction logs
   - Validate data integrity
   - Resume normal operations

## Disaster Recovery

### Backup Strategy

**Database Backups:**
- **Full Backup**: Daily at 2 AM UTC
- **Incremental Backup**: Every 6 hours
- **Transaction Log Backup**: Every 15 minutes
- **Retention**: 30 days local, 90 days offsite

**File Storage Backups:**
- **Snapshot Backup**: Daily
- **Cross-region Replication**: Real-time
- **Retention**: 7 days local, 30 days offsite

**Configuration Backups:**
- **Infrastructure as Code**: Version controlled
- **Configuration Files**: Daily backup
- **Secrets**: Encrypted backup in secure vault

### Recovery Procedures

**Database Recovery:**
```bash
# Stop application services
docker-compose stop api worker

# Restore database from backup
pg_restore -h db-host -U user -d pdf_smaller_prod backup_file.sql

# Verify data integrity
psql -c "SELECT COUNT(*) FROM jobs;"

# Start services
docker-compose start api worker
```

**Full System Recovery:**
```bash
# Deploy infrastructure
terraform apply -var-file=prod.tfvars

# Restore database
# (see database recovery above)

# Deploy application
docker-compose -f docker-compose.prod.yml up -d

# Restore file storage
aws s3 sync s3://backup-bucket s3://prod-bucket

# Verify system health
curl -f http://api-host/health/deep
```

### Recovery Time Objectives (RTO)

- **Database Recovery**: 15 minutes
- **Application Recovery**: 10 minutes
- **Full System Recovery**: 60 minutes
- **Data Recovery Point**: 15 minutes (RPO)

## Performance Tuning

### Application Performance

**Flask/Gunicorn Optimization:**
```python
# gunicorn.conf.py
bind = "0.0.0.0:5000"
workers = 4
worker_class = "gevent"
worker_connections = 1000
max_requests = 1000
max_requests_jitter = 100
preload_app = True
timeout = 30
keepalive = 5
```

**Database Optimization:**
```sql
-- Create indexes for common queries
CREATE INDEX CONCURRENTLY idx_jobs_status_created ON jobs(status, created_at);
CREATE INDEX CONCURRENTLY idx_jobs_user_id ON jobs(user_id);

-- Update table statistics
ANALYZE jobs;
ANALYZE compression_jobs;

-- Optimize PostgreSQL configuration
-- shared_buffers = 2GB
-- effective_cache_size = 6GB
-- work_mem = 64MB
-- maintenance_work_mem = 512MB
```

**Redis Optimization:**
```redis
# redis.conf optimizations
maxmemory 4gb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
tcp-keepalive 300
timeout 0
```

### Infrastructure Performance

**Load Balancer Configuration:**
```haproxy
# haproxy.cfg
global
    maxconn 4096
    log stdout local0

defaults
    mode http
    timeout connect 5000ms
    timeout client 50000ms
    timeout server 50000ms
    option httplog

frontend pdf_frontend
    bind *:80
    bind *:443 ssl crt /etc/ssl/certs/cert.pem
    redirect scheme https if !{ ssl_fc }
    default_backend pdf_backend

backend pdf_backend
    balance roundrobin
    option httpchk GET /health
    server api1 api1:5000 check
    server api2 api2:5000 check
```

**Container Resource Limits:**
```yaml
# docker-compose.prod.yml
services:
  api:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
  
  worker:
    deploy:
      resources:
        limits:
          cpus: '4.0'
          memory: 8G
        reservations:
          cpus: '2.0'
          memory: 4G
```

## Security Operations

### Security Monitoring

**Log Analysis:**
```bash
# Monitor failed authentication attempts
grep "authentication failed" /var/log/pdf-smaller/security.log | tail -20

# Check for suspicious file uploads
grep "malware detected" /var/log/pdf-smaller/security.log

# Monitor rate limiting triggers
grep "rate limit exceeded" /var/log/pdf-smaller/app.log
```

**Security Scanning:**
```bash
# Daily vulnerability scan
nmap -sV -O target-host

# SSL certificate check
openssl s_client -connect api-host:443 -servername api-host

# Dependency vulnerability check
safety check --json
```

### Incident Response

**Security Incident Workflow:**

1. **Detection and Analysis:**
   - Identify security event
   - Assess severity and impact
   - Collect evidence
   - Determine response strategy

2. **Containment:**
   - Isolate affected systems
   - Block malicious traffic
   - Preserve evidence
   - Prevent further damage

3. **Eradication and Recovery:**
   - Remove malicious code/access
   - Patch vulnerabilities
   - Restore from clean backups
   - Validate system integrity

4. **Post-Incident Activities:**
   - Document lessons learned
   - Update security procedures
   - Improve monitoring and detection
   - Conduct security training

## Backup & Recovery

### Automated Backup Scripts

**Database Backup Script:**
```bash
#!/bin/bash
# backup_database.sh

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/backups/database"
DB_NAME="pdf_smaller_prod"

# Create backup
pg_dump -h $DB_HOST -U $DB_USER $DB_NAME | gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# Upload to S3
aws s3 cp $BACKUP_DIR/backup_$DATE.sql.gz s3://backup-bucket/database/

# Cleanup old backups (keep 30 days)
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +30 -delete

# Verify backup integrity
gunzip -t $BACKUP_DIR/backup_$DATE.sql.gz

echo "Database backup completed: backup_$DATE.sql.gz"
```

**File Storage Backup Script:**
```bash
#!/bin/bash
# backup_files.sh

DATE=$(date +%Y%m%d_%H%M%S)
SOURCE_DIR="/app/uploads"
BACKUP_BUCKET="s3://backup-bucket/files"

# Sync files to S3
aws s3 sync $SOURCE_DIR $BACKUP_BUCKET/$DATE/ --delete

# Create snapshot
aws ec2 create-snapshot --volume-id vol-12345678 --description "File storage backup $DATE"

echo "File storage backup completed: $DATE"
```

### Recovery Testing

**Monthly Recovery Test:**
```bash
#!/bin/bash
# test_recovery.sh

# Test database recovery
echo "Testing database recovery..."
pg_restore -h test-db-host -U user -d test_db latest_backup.sql
psql -h test-db-host -U user -d test_db -c "SELECT COUNT(*) FROM jobs;"

# Test application startup
echo "Testing application startup..."
docker-compose -f docker-compose.test.yml up -d
sleep 30
curl -f http://test-api:5000/health

# Cleanup test environment
docker-compose -f docker-compose.test.yml down
psql -h test-db-host -U user -c "DROP DATABASE test_db;"

echo "Recovery test completed successfully"
```

## Incident Response

### Incident Classification

**Severity Levels:**

**P0 - Critical (Response: Immediate)**
- Complete service outage
- Data loss or corruption
- Security breach
- SLA violation > 50%

**P1 - High (Response: 30 minutes)**
- Partial service degradation
- Performance issues affecting users
- Failed deployments
- SLA violation 10-50%

**P2 - Medium (Response: 2 hours)**
- Minor performance issues
- Non-critical feature failures
- Monitoring alerts
- SLA violation < 10%

**P3 - Low (Response: Next business day)**
- Documentation issues
- Minor bugs
- Enhancement requests
- Informational alerts

### Incident Response Team

**Roles and Responsibilities:**

**Incident Commander:**
- Overall incident coordination
- Communication with stakeholders
- Decision making authority
- Post-incident review leadership

**Technical Lead:**
- Technical investigation and resolution
- Coordination with engineering teams
- Implementation of fixes
- Technical documentation

**Communications Lead:**
- External communication
- Status page updates
- Customer notifications
- Media relations (if required)

### Post-Incident Review

**Review Process:**

1. **Timeline Creation:**
   - Document incident timeline
   - Identify key events and decisions
   - Note response times and actions

2. **Root Cause Analysis:**
   - Identify immediate cause
   - Identify contributing factors
   - Analyze system failures
   - Review human factors

3. **Action Items:**
   - Immediate fixes
   - Long-term improvements
   - Process changes
   - Training needs

4. **Documentation:**
   - Incident report
   - Lessons learned
   - Updated procedures
   - Knowledge base updates

---

## Appendices

### A. Emergency Contacts

**On-Call Rotation:**
- Primary: +1-555-0101
- Secondary: +1-555-0102
- Escalation: +1-555-0103

**Vendor Contacts:**
- Cloud Provider: support@cloudprovider.com
- Database Support: dba@company.com
- Security Team: security@company.com

### B. Runbook Quick Reference

**Common Commands:**
```bash
# Service status
docker-compose ps
systemctl status pdf-smaller

# Log viewing
tail -f /var/log/pdf-smaller/app.log
journalctl -u pdf-smaller -f

# Database queries
psql -c "SELECT COUNT(*) FROM jobs WHERE status='processing';"

# Redis operations
redis-cli llen celery
redis-cli flushdb

# Health checks
curl -f http://localhost:5000/health
curl -f http://localhost:5000/health/deep
```

### C. Configuration Templates

**Environment Configuration Template:**
```bash
# Copy and customize for each environment
cp config/production.env.template config/production.env

# Required customizations:
# - Database credentials
# - Redis connection
# - Secret keys
# - External service URLs
# - Monitoring endpoints
```

**Monitoring Configuration Template:**
```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'pdf-smaller-api'
    static_configs:
      - targets: ['api1:9090', 'api2:9090']
  
  - job_name: 'pdf-smaller-workers'
    static_configs:
      - targets: ['worker1:9090', 'worker2:9090', 'worker3:9090']
```

This production operations guide should be reviewed and updated quarterly to ensure accuracy and completeness. All team members should be familiar with the procedures outlined in this document.