# Celery Background Processing Setup

This document explains how to set up and use Celery for background processing of bulk PDF compression tasks.

## Prerequisites

1. **Redis Server**: Celery uses Redis as a message broker and result backend
2. **Python Dependencies**: Install required packages from requirements.txt

## Installation

### 1. Install Redis

#### Windows
```bash
# Using Chocolatey
choco install redis-64

# Or download from: https://github.com/microsoftarchive/redis/releases
```

#### Linux/macOS
```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# macOS with Homebrew
brew install redis
```

#### Docker (Recommended for development)
```bash
docker run -d -p 6379:6379 --name redis redis:7-alpine
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

## Configuration

The Celery configuration is defined in `src/config/config.py`:

```python
# Celery settings
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')
```

### Environment Variables

Set these environment variables for production:

```bash
export CELERY_BROKER_URL=redis://your-redis-host:6379/0
export CELERY_RESULT_BACKEND=redis://your-redis-host:6379/0
```

## Running Celery

### Development Setup

#### Option 1: Using Scripts (Recommended)

**Linux/macOS:**
```bash
chmod +x scripts/start_celery.sh
./scripts/start_celery.sh
```

**Windows:**
```cmd
scripts\start_celery.bat
```

#### Option 2: Manual Commands

**Start Redis:**
```bash
redis-server
```

**Start Celery Worker:**
```bash
celery -A celery_worker.celery worker --loglevel=info --concurrency=2 --queues=compression,cleanup
```

**Start Celery Beat (for periodic tasks):**
```bash
celery -A celery_worker.celery beat --loglevel=info
```

### Production Setup with Docker Compose

Use the provided `docker_compose.yml`:

```bash
docker-compose up -d
```

This starts:
- Main Flask application
- Redis server
- Celery worker
- Celery beat scheduler

## Usage

### 1. Async Bulk Compression

```python
from src.services.bulk_compression_service import BulkCompressionService

# Initialize service
bulk_service = BulkCompressionService('/path/to/upload/folder')

# Create and queue a bulk job
job = bulk_service.create_bulk_job(user_id, files, compression_settings)
task_id = bulk_service.process_bulk_job_async(job.id)

# Check task status
status = bulk_service.get_task_status(task_id)
print(f"Task state: {status['state']}")
print(f"Progress: {status.get('progress', 0)}%")
```

### 2. Job Progress Tracking

```python
# Get job progress from database
progress = bulk_service.get_job_progress(job_id)
print(f"Completed: {progress['completed_count']}/{progress['file_count']}")

# Get Celery task status
if job.task_id:
    task_status = bulk_service.get_task_status(job.task_id)
    print(f"Task progress: {task_status.get('progress', 0)}%")
```

### 3. API Integration

The bulk compression endpoints automatically use Celery for background processing:

```bash
# Start bulk compression (returns immediately with job ID)
POST /api/compress/bulk
{
    "files": [...],
    "compression_level": "medium",
    "image_quality": 80
}

# Check job status
GET /api/compress/jobs/{job_id}

# Download results when complete
GET /api/compress/download/{job_id}
```

## Task Types

### 1. Bulk Compression Task
- **Name**: `src.tasks.compression_tasks.process_bulk_compression`
- **Queue**: `compression`
- **Purpose**: Process multiple PDF files asynchronously
- **Timeout**: 10 minutes hard limit, 5 minutes soft limit

### 2. Cleanup Task
- **Name**: `src.tasks.compression_tasks.cleanup_expired_jobs`
- **Queue**: `cleanup`
- **Schedule**: Every hour
- **Purpose**: Clean up expired job files and directories

## Monitoring

### 1. Celery Flower (Web UI)

Install and run Flower for monitoring:

```bash
pip install flower
celery -A celery_worker.celery flower
```

Access at: http://localhost:5555

### 2. Redis CLI

Monitor Redis queues:

```bash
redis-cli
> LLEN celery  # Check queue length
> KEYS celery-task-meta-*  # List task results
```

### 3. Application Logs

Check logs for task execution:

```bash
tail -f app.log
```

## Error Handling

### Common Issues

1. **Redis Connection Error**
   - Ensure Redis server is running
   - Check CELERY_BROKER_URL configuration
   - Verify network connectivity

2. **Task Not Found**
   - Ensure worker is running with correct queues
   - Check task import in celery_worker.py

3. **Memory Issues**
   - Adjust worker concurrency: `--concurrency=1`
   - Set worker memory limits: `--max-tasks-per-child=50`

### Task Retry Logic

Tasks automatically retry on failure:
- **Max retries**: 3
- **Retry delay**: 60 seconds
- **Exponential backoff**: Enabled

## Performance Tuning

### Worker Configuration

```bash
# High throughput
celery -A celery_worker.celery worker --concurrency=4 --prefetch-multiplier=1

# Memory constrained
celery -A celery_worker.celery worker --concurrency=1 --max-tasks-per-child=10

# CPU intensive
celery -A celery_worker.celery worker --concurrency=2 --pool=solo
```

### Queue Routing

Tasks are routed to specific queues:
- `compression`: Bulk compression tasks
- `cleanup`: File cleanup tasks

### Resource Limits

Configure in `src/celery_app.py`:
- **Soft time limit**: 300 seconds (5 minutes)
- **Hard time limit**: 600 seconds (10 minutes)
- **Result expiration**: 3600 seconds (1 hour)

## Security Considerations

1. **Redis Security**
   - Use Redis AUTH in production
   - Configure firewall rules
   - Use SSL/TLS for Redis connections

2. **Task Security**
   - Validate all task inputs
   - Sanitize file paths
   - Implement rate limiting

3. **File Security**
   - Automatic cleanup of temporary files
   - Secure file permissions
   - Virus scanning integration

## Testing

Run Celery integration tests:

```bash
# Run all Celery tests
python -m pytest tests/test_celery_tasks.py -v

# Run specific test
python -m pytest tests/test_celery_tasks.py::TestCeleryConfiguration::test_celery_app_creation -v
```

## Troubleshooting

### Debug Mode

Enable debug logging:

```python
# In celery_app.py
celery.conf.update(
    worker_log_level='DEBUG',
    task_track_started=True,
    task_send_sent_event=True,
)
```

### Task Inspection

```bash
# List active tasks
celery -A celery_worker.celery inspect active

# List scheduled tasks
celery -A celery_worker.celery inspect scheduled

# Purge all tasks
celery -A celery_worker.celery purge
```

### Performance Monitoring

```bash
# Worker statistics
celery -A celery_worker.celery inspect stats

# Queue lengths
celery -A celery_worker.celery inspect active_queues
```