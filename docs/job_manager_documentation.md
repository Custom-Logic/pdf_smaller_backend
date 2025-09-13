# Job Manager Documentation

## Overview

The `JobStatusManager` is a critical utility class that provides thread-safe, atomic operations for managing job lifecycle and status transitions in the PDF compression system. It implements robust database safety mechanisms to prevent race conditions and ensure data consistency in concurrent environments.

**Location:** `src/utils/job_manager.py`

### Key Features

- **Thread-Safe Operations**: Uses database row-level locking to prevent race conditions
- **Atomic Transactions**: All operations are wrapped in database transactions
- **Status Validation**: Enforces job state machine rules to prevent invalid transitions
- **Error Handling**: Comprehensive exception handling with automatic rollback
- **Job Lifecycle Management**: Complete CRUD operations for job status tracking

## Database Safety Mechanisms

### Row-Level Locking

The JobStatusManager uses PostgreSQL's `SELECT FOR UPDATE` to implement row-level locking:

```python
# Lock specific job row to prevent concurrent modifications
job = db.session.execute(
    select(Job).where(Job.job_id == job_id).with_for_update()
).scalar_one_or_none()
```

**Benefits:**
- Prevents lost updates in concurrent environments
- Ensures atomic read-modify-write operations
- Maintains data consistency across multiple workers

### Transaction Management

All operations use database transactions with automatic rollback:

```python
try:
    with db.session.begin():  # Automatic rollback on exception
        # Database operations here
        pass
except Exception as e:
    logger.error(f"Operation failed: {e}")
    db.session.rollback()  # Explicit rollback for clarity
    return False
```

**Key Properties:**
- **Atomicity**: All operations within a transaction succeed or fail together
- **Isolation**: Concurrent transactions don't interfere with each other
- **Automatic Rollback**: Failed operations don't leave partial state changes

### Race Condition Prevention

The system prevents common race conditions through:

1. **Job Creation Race**: `get_or_create_job()` uses row locking to handle concurrent job creation
2. **Status Update Race**: `update_job_status()` locks jobs before status changes
3. **Cleanup Race**: `cleanup_old_jobs()` uses atomic delete operations

## Exception Handling

### Three-Tier Error Handling

1. **Database Level**: Transaction rollback on SQL errors
2. **Application Level**: Graceful error handling with logging
3. **Service Level**: Error propagation to calling services

### Error Categories

| Error Type | Handling Strategy | Return Value |
|------------|------------------|-------------|
| Job Not Found | Log warning, return False/None | `False` or `None` |
| Invalid Transition | Log error, return False | `False` |
| Database Error | Log error, rollback, return False | `False` |
| System Error | Log error, rollback, re-raise | Exception |

### Logging Strategy

```python
# Context-rich error logging
logger.error(f"Failed to update job {job_id} status: {e}")
logger.info(f"Updated job {job_id} status to {status.value}")
```

## Status Transition Management

### Job State Machine

The system enforces a strict state machine for job status transitions:

```
PENDING → PROCESSING → COMPLETED
    ↓         ↓           ↑
  FAILED ← CANCELLED    (terminal)
    ↓
  PENDING (retry)
```

### Valid Transitions

| From State | To States | Notes |
|------------|-----------|-------|
| PENDING | PROCESSING, FAILED, CANCELLED | Initial state |
| PROCESSING | COMPLETED, FAILED, CANCELLED | Active processing |
| COMPLETED | (none) | Terminal state |
| FAILED | PENDING, CANCELLED | Retry allowed |
| CANCELLED | (none) | Terminal state |

### Transition Validation

```python
def _is_valid_transition(current_status: str, new_status: str) -> bool:
    """Validates status transitions according to state machine rules."""
    valid_transitions = {
        JobStatus.PENDING.value: [JobStatus.PROCESSING.value, JobStatus.FAILED.value],
        JobStatus.PROCESSING.value: [JobStatus.COMPLETED.value, JobStatus.FAILED.value],
        JobStatus.FAILED.value: [JobStatus.PENDING.value],  # Allow retry
        # Terminal states have no valid transitions
    }
    return new_status in valid_transitions.get(current_status, [])
```

## Usage Patterns

### Basic Job Creation

```python
from src.utils.job_manager import JobStatusManager
from src.models.job import JobType

# Create or retrieve existing job
job = JobStatusManager.get_or_create_job(
    job_id="compress_doc_123",
    job_type=JobType.COMPRESS,
    file_path="/uploads/document.pdf"
)
```

### Status Updates

```python
# Mark job as processing
success = JobStatusManager.update_job_status(
    job_id="compress_doc_123",
    status=JobStatus.PROCESSING
)

# Complete job with results
success = JobStatusManager.update_job_status(
    job_id="compress_doc_123",
    status=JobStatus.COMPLETED,
    result={
        "output_path": "/compressed/doc.pdf",
        "size_reduction": 0.65,
        "original_size": 1024000,
        "compressed_size": 358400
    }
)

# Handle job failure
success = JobStatusManager.update_job_status(
    job_id="compress_doc_123",
    status=JobStatus.FAILED,
    error_message="File not found: /uploads/document.pdf"
)
```

### Custom Operations with Locking

```python
def update_job_progress(job, progress_percent, current_step):
    """Custom operation to update job progress."""
    job.progress = progress_percent
    job.current_step = current_step
    return f"Updated to {progress_percent}% - {current_step}"

# Execute with automatic locking
result = JobStatusManager.execute_with_job_lock(
    job_id="compress_doc_123",
    operation=update_job_progress,
    progress_percent=75,
    current_step="Applying compression algorithms"
)
```

### Status Monitoring

```python
# Check current status
status = JobStatusManager.get_job_status("compress_doc_123")
if status == JobStatus.COMPLETED.value:
    print("Job finished successfully")

# Check if job is finished
if JobStatusManager.is_job_terminal("compress_doc_123"):
    print("Job has finished, safe to cleanup resources")
```

### Maintenance Operations

```python
# Clean up old jobs (default: 30 days)
deleted_count = JobStatusManager.cleanup_old_jobs()
print(f"Cleaned up {deleted_count} old jobs")

# Clean up jobs older than 7 days
deleted_count = JobStatusManager.cleanup_old_jobs(days_old=7)
```

## Architecture Integration

### Service Layer Integration

The JobStatusManager integrates with the service layer through:

- **Task Services**: `src/services/tasks/` - Job creation and status updates
- **File Services**: `src/services/file_service.py` - File operation tracking
- **Celery Tasks**: `src/tasks/` - Background job processing

### Database Integration

- **Job Model**: `src/models/job.py` - Core job entity
- **Database**: `src/database.py` - Database session management
- **Migrations**: Database schema evolution support

### Related Files

- `src/models/job.py` - Job model with business logic methods
- `src/enums/job_status.py` - JobStatus enum definitions
- `src/services/tasks/` - Task service implementations
- `src/tasks/` - Celery task definitions
- `tests/test_job_manager.py` - Comprehensive test suite

## Developer Guidelines

### Best Practices

1. **Always Use JobStatusManager**: Never directly modify job status in the database
2. **Handle Return Values**: Check boolean returns from status update methods
3. **Use Appropriate Methods**: Choose the right method for your use case
4. **Log Operations**: Include context in log messages for debugging
5. **Test Concurrency**: Test your code under concurrent conditions

### Common Patterns

```python
# Pattern 1: Safe job creation
job = JobStatusManager.get_or_create_job(job_id, job_type, file_path)
if not job:
    logger.error(f"Failed to create job {job_id}")
    return None

# Pattern 2: Status update with validation
if not JobStatusManager.update_job_status(job_id, JobStatus.PROCESSING):
    logger.error(f"Failed to mark job {job_id} as processing")
    return False

# Pattern 3: Terminal state checking
if JobStatusManager.is_job_terminal(job_id):
    # Safe to perform cleanup operations
    cleanup_resources(job_id)
```

### Anti-Patterns to Avoid

```python
# DON'T: Direct database access
job = Job.query.filter_by(job_id=job_id).first()
job.status = 'completed'  # Race condition risk!
db.session.commit()

# DON'T: Ignore return values
JobStatusManager.update_job_status(job_id, JobStatus.FAILED)  # No error handling

# DON'T: Skip validation
JobStatusManager.update_job_status(
    job_id, JobStatus.COMPLETED, 
    validate_transition=False  # Dangerous!
)
```

## Troubleshooting

### Common Issues

#### Issue: "Job not found" errors
**Cause**: Job ID doesn't exist or was cleaned up
**Solution**: Verify job creation and check cleanup policies

#### Issue: "Invalid status transition" errors
**Cause**: Attempting invalid state machine transition
**Solution**: Review job state machine rules and current job status

#### Issue: Database deadlocks
**Cause**: Multiple processes trying to lock the same jobs
**Solution**: Implement retry logic and reduce lock duration

#### Issue: Memory issues during cleanup
**Cause**: Cleaning up too many jobs at once
**Solution**: Implement batch processing in cleanup operations

### Debugging Tips

1. **Enable Debug Logging**: Set log level to DEBUG for detailed operation logs
2. **Check Job History**: Review job status changes in the database
3. **Monitor Lock Waits**: Use database monitoring to identify lock contention
4. **Test Isolation**: Test individual operations in isolation

### Performance Considerations

- **Batch Operations**: Group multiple status updates when possible
- **Index Usage**: Ensure proper database indexes on job_id and status columns
- **Connection Pooling**: Use database connection pooling for better performance
- **Cleanup Scheduling**: Run cleanup operations during low-traffic periods

## Testing

Comprehensive test coverage is available in `tests/test_job_manager.py`, including:

- Unit tests for all public methods
- Concurrency tests for race condition prevention
- Integration tests with the database
- Error handling and edge case tests

Run tests with:
```bash
pytest tests/test_job_manager.py -v
```

## Related Documentation

- [Architecture Guide](architecture_guide.md) - Overall system architecture
- [Development Guide](development_guide.md) - Development best practices
- [Tasks Module Documentation](tasks_module.md) - Celery task system
- [Database Schema](database_schema.md) - Database design and relationships