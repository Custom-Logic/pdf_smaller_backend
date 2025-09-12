# Database Consistency Fixes

**Priority:** 🟡 Medium  
**Estimated Effort:** 3-4 hours  
**Risk Level:** Medium-High  

## Overview

The codebase has inconsistent database operation patterns, potential race conditions, and mixed transaction handling that could lead to data integrity issues.

## Issues Identified

### 1. Inconsistent Job Status Updates

**Problem:** Multiple ways of updating job status with different error handling:

```python
# Pattern 1: Using model methods (good)
job.mark_as_completed(result)
db.session.commit()

# Pattern 2: Direct attribute assignment (inconsistent)
job.status = JobStatus.FAILED.value
job.error = str(e)
db.session.commit()

# Pattern 3: Mixed approach
job.mark_as_processing()
db.session.commit()
# Later...
job.status = JobStatus.COMPLETED.value
db.session.commit()
```

**Issues:**
- Inconsistent status update patterns
- Some updates use model methods, others use direct assignment
- No guarantee of atomic updates
- Potential for status inconsistencies

### 2. Race Conditions in Job Processing

**Problem:** Multiple processes could modify the same job simultaneously:

```python
# In tasks.py - potential race condition
job = Job.query.filter_by(job_id=job_id).first()
if not job:
    job = Job(job_id=job_id, task_type='compress', ...)
    db.session.add(job)

job.mark_as_processing()  # Could conflict with other processes
db.session.commit()
```

**Scenarios:**
- Multiple workers picking up the same job
- Concurrent status updates
- Job creation race conditions
- File cleanup conflicts

### 3. Transaction Boundary Inconsistencies

**Problem:** Inconsistent transaction handling across operations:

```python
# Pattern 1: Single transaction (good)
try:
    job.mark_as_completed(result)
    # Other related operations
    db.session.commit()
except Exception:
    db.session.rollback()
    raise

# Pattern 2: Multiple separate transactions (potential inconsistency)
job.mark_as_processing()
db.session.commit()  # Transaction 1

# ... processing ...

job.mark_as_completed(result)
db.session.commit()  # Transaction 2

# Pattern 3: No explicit transaction handling
job.status = JobStatus.FAILED.value
db.session.commit()  # Could leave inconsistent state if fails
```

### 4. Missing Database Constraints

**Problem:** Database schema may be missing constraints to prevent inconsistent states:

```python
# Potential issues in Job model:
class Job(db.Model):
    job_id = db.Column(db.String(36), primary_key=True)  # No uniqueness constraint?
    status = db.Column(db.String(20), nullable=False)    # No enum constraint?
    created_at = db.Column(db.DateTime)                  # No default value?
    # Missing indexes for common queries?
```

### 5. Inconsistent Error Handling in Database Operations

**Problem:** Different error handling for database operations:

```python
# Pattern 1: Comprehensive error handling
try:
    job.mark_as_failed(str(e))
    db.session.commit()
except (DBAPIError, OperationalError, IntegrityError) as db_err:
    db.session.rollback()
    logger.error(f"Database error: {db_err}")

# Pattern 2: Minimal error handling
try:
    job.status = JobStatus.FAILED.value
    db.session.commit()
except Exception as db_err:
    logger.error(f"Failed to update job status: {db_err}")
    # No rollback!

# Pattern 3: No error handling
job.mark_as_completed(result)
db.session.commit()  # Could fail silently
```

## Solutions

### Solution 1: Implement Job Status Manager with Locking

**Action Plan:** Create a centralized job status manager with proper locking

**Implementation:**

Create `src/utils/job_manager.py`:
```python
from typing import Dict, Any, Optional, Callable
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from src.models import Job, JobStatus
from src.models.base import db
import logging

logger = logging.getLogger(__name__)

class JobManager:
    """Thread-safe job management with proper locking and transactions"""
    
    @staticmethod
    def get_or_create_job(job_id: str, task_type: str, input_data: Dict[str, Any]) -> Job:
        """Get existing job or create new one with proper locking"""
        with db.session.begin():  # Explicit transaction
            # Use SELECT FOR UPDATE to prevent race conditions
            job = db.session.execute(
                select(Job).where(Job.job_id == job_id).with_for_update()
            ).scalar_one_or_none()
            
            if not job:
                job = Job(
                    job_id=job_id,
                    task_type=task_type,
                    input_data=input_data,
                    status=JobStatus.PENDING.value
                )
                db.session.add(job)
                db.session.flush()  # Ensure ID is assigned
                logger.info(f"Created new job {job_id} with type {task_type}")
            
            return job
    
    @staticmethod
    def update_job_status(job_id: str, status: JobStatus, 
                         result: Dict[str, Any] = None, 
                         error_message: str = None,
                         validate_transition: bool = True) -> bool:
        """Atomically update job status with validation"""
        try:
            with db.session.begin():
                # Lock the job row for update
                job = db.session.execute(
                    select(Job).where(Job.job_id == job_id).with_for_update()
                ).scalar_one_or_none()
                
                if not job:
                    logger.error(f"Job {job_id} not found for status update")
                    return False
                
                # Validate status transition if requested
                if validate_transition and not JobManager._is_valid_transition(job.status, status.value):
                    logger.error(f"Invalid status transition for job {job_id}: {job.status} -> {status.value}")
                    return False
                
                # Update job using model methods for consistency
                if status == JobStatus.PROCESSING:
                    job.mark_as_processing()
                elif status == JobStatus.COMPLETED:
                    job.mark_as_completed(result or {})
                elif status == JobStatus.FAILED:
                    job.mark_as_failed(error_message or "Unknown error")
                else:
                    job.status = status.value
                
                logger.info(f"Updated job {job_id} status to {status.value}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to update job {job_id} status: {e}")
            return False
    
    @staticmethod
    def _is_valid_transition(current_status: str, new_status: str) -> bool:
        """Validate job status transitions"""
        valid_transitions = {
            JobStatus.PENDING.value: [JobStatus.PROCESSING.value, JobStatus.FAILED.value],
            JobStatus.PROCESSING.value: [JobStatus.COMPLETED.value, JobStatus.FAILED.value],
            JobStatus.COMPLETED.value: [],  # Terminal state
            JobStatus.FAILED.value: [JobStatus.PROCESSING.value]  # Allow retry
        }
        
        return new_status in valid_transitions.get(current_status, [])
    
    @staticmethod
    def execute_with_job_lock(job_id: str, operation: Callable[[Job], Any]) -> Any:
        """Execute operation with job locked for update"""
        with db.session.begin():
            job = db.session.execute(
                select(Job).where(Job.job_id == job_id).with_for_update()
            ).scalar_one_or_none()
            
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            return operation(job)
```

### Solution 2: Enhance Job Model with Better Constraints

**Action Plan:** Add database constraints and improve model methods

**Implementation:**

Update `src/models/job.py`:
```python
from sqlalchemy import Index, CheckConstraint
from datetime import datetime, timezone

class Job(db.Model):
    __tablename__ = 'jobs'
    
    # Add unique constraint on job_id
    job_id = db.Column(db.String(36), primary_key=True, unique=True, nullable=False)
    
    # Add enum constraint for status
    status = db.Column(
        db.String(20), 
        nullable=False,
        default=JobStatus.PENDING.value
    )
    
    # Add default timestamp
    created_at = db.Column(
        db.DateTime(timezone=True), 
        nullable=False, 
        default=lambda: datetime.now(timezone.utc)
    )
    
    updated_at = db.Column(
        db.DateTime(timezone=True), 
        nullable=False, 
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Add constraints
    __table_args__ = (
        CheckConstraint(
            status.in_([s.value for s in JobStatus]),
            name='valid_status'
        ),
        CheckConstraint(
            'created_at <= updated_at',
            name='valid_timestamps'
        ),
        # Add indexes for common queries
        Index('idx_job_status_created', 'status', 'created_at'),
        Index('idx_job_updated', 'updated_at'),
    )
    
    def mark_as_processing(self) -> None:
        """Mark job as processing with timestamp update"""
        self.status = JobStatus.PROCESSING.value
        self.updated_at = datetime.now(timezone.utc)
    
    def mark_as_completed(self, result: Dict[str, Any] = None) -> None:
        """Mark job as completed with result and timestamp"""
        self.status = JobStatus.COMPLETED.value
        self.result = result or {}
        self.updated_at = datetime.now(timezone.utc)
    
    def mark_as_failed(self, error_message: str) -> None:
        """Mark job as failed with error and timestamp"""
        self.status = JobStatus.FAILED.value
        self.error = error_message
        self.updated_at = datetime.now(timezone.utc)
    
    def is_terminal(self) -> bool:
        """Check if job is in terminal state"""
        return self.status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]
    
    def can_transition_to(self, new_status: JobStatus) -> bool:
        """Check if transition to new status is valid"""
        return JobManager._is_valid_transition(self.status, new_status.value)
```

### Solution 3: Implement Database Migration for Constraints

**Action Plan:** Create migration to add missing constraints and indexes

**Implementation:**

Create `migrations/add_job_constraints.py`:
```python
"""Add database constraints and indexes for job consistency"""

def upgrade():
    # Add status constraint
    op.create_check_constraint(
        'valid_status',
        'jobs',
        "status IN ('pending', 'processing', 'completed', 'failed')"
    )
    
    # Add timestamp constraint
    op.create_check_constraint(
        'valid_timestamps',
        'jobs',
        'created_at <= updated_at'
    )
    
    # Add indexes for performance
    op.create_index(
        'idx_job_status_created',
        'jobs',
        ['status', 'created_at']
    )
    
    op.create_index(
        'idx_job_updated',
        'jobs',
        ['updated_at']
    )
    
    # Add updated_at column if it doesn't exist
    op.add_column(
        'jobs',
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False,
                 server_default=sa.func.now())
    )

def downgrade():
    op.drop_constraint('valid_status', 'jobs')
    op.drop_constraint('valid_timestamps', 'jobs')
    op.drop_index('idx_job_status_created', 'jobs')
    op.drop_index('idx_job_updated', 'jobs')
    op.drop_column('jobs', 'updated_at')
```

### Solution 4: Update All Task Functions to Use JobManager

**Action Plan:** Replace manual job handling with JobManager throughout tasks

**Implementation:**

```python
# Update all task functions like this:
@celery_app.task(bind=True, max_retries=3, name='tasks.compress_task')
def compress_task(self, job_id: str, file_data: bytes, compression_settings: Dict[str, Any],
                  original_filename: str = None) -> Dict[str, Any]:
    try:
        # Use JobManager for consistent job handling
        job = JobManager.get_or_create_job(
            job_id=job_id,
            task_type='compress',
            input_data={
                'compression_settings': compression_settings,
                'file_size': len(file_data),
                'original_filename': original_filename
            }
        )
        
        # Update status to processing
        JobManager.update_job_status(job_id, JobStatus.PROCESSING)
        
        # Process file
        result = compression_service.process_file_data(
            file_data=file_data,
            settings=compression_settings,
            original_filename=original_filename
        )
        
        # Update status to completed
        JobManager.update_job_status(job_id, JobStatus.COMPLETED, result=result)
        
        logger.info(f"Compression job {job_id} completed successfully")
        return result
        
    except Exception as exc:
        # Update status to failed
        JobManager.update_job_status(job_id, JobStatus.FAILED, error_message=str(exc))
        
        # Use centralized error handling
        handle_task_error(self, exc, job_id)
```

## Implementation Plan

### Phase 1: Create JobManager (1.5 hours)
1. Implement `JobManager` class
2. Add comprehensive tests
3. Test locking and transaction behavior
4. Validate status transition logic

### Phase 2: Enhance Job Model (1 hour)
1. Add database constraints to model
2. Enhance model methods
3. Add validation methods
4. Update existing tests

### Phase 3: Database Migration (30 minutes)
1. Create migration script
2. Test migration on development database
3. Verify constraints work correctly
4. Test rollback procedures

### Phase 4: Update Tasks and Routes (2 hours)
1. Update all task functions to use JobManager
2. Update route handlers
3. Remove manual job handling code
4. Test all job operations

## Testing Requirements

### Concurrency Tests
```python
import threading
import time

def test_concurrent_job_creation():
    """Test that concurrent job creation doesn't create duplicates"""
    job_id = str(uuid.uuid4())
    results = []
    
    def create_job():
        job = JobManager.get_or_create_job(job_id, 'test', {})
        results.append(job.id)
    
    threads = [threading.Thread(target=create_job) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    
    # Should only have one unique job ID
    assert len(set(results)) == 1

def test_concurrent_status_updates():
    """Test concurrent status updates"""
    job_id = str(uuid.uuid4())
    JobManager.get_or_create_job(job_id, 'test', {})
    
    def update_status(status):
        return JobManager.update_job_status(job_id, status)
    
    # Try to update to different statuses concurrently
    # Only one should succeed based on transition rules
```

### Transaction Tests
```python
def test_job_transaction_rollback():
    """Test that failed operations roll back properly"""
    job_id = str(uuid.uuid4())
    
    # Simulate operation that fails after job creation
    with pytest.raises(Exception):
        with db.session.begin():
            JobManager.get_or_create_job(job_id, 'test', {})
            raise Exception("Simulated failure")
    
    # Job should not exist due to rollback
    job = Job.query.filter_by(job_id=job_id).first()
    assert job is None
```

### Constraint Tests
```python
def test_status_constraint():
    """Test that invalid status values are rejected"""
    with pytest.raises(IntegrityError):
        job = Job(job_id=str(uuid.uuid4()), task_type='test', status='invalid_status')
        db.session.add(job)
        db.session.commit()

def test_timestamp_constraint():
    """Test that timestamp constraints work"""
    with pytest.raises(IntegrityError):
        job = Job(
            job_id=str(uuid.uuid4()),
            task_type='test',
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc) - timedelta(hours=1)  # Invalid: updated < created
        )
        db.session.add(job)
        db.session.commit()
```

## Benefits

### Data Integrity
- Prevents duplicate jobs
- Ensures valid status transitions
- Maintains consistent timestamps
- Prevents orphaned job states

### Concurrency Safety
- Eliminates race conditions
- Proper database locking
- Atomic operations
- Consistent transaction boundaries

### Performance
- Optimized database queries
- Proper indexing
- Reduced lock contention
- Better query planning

## Risk Assessment

**Medium-High Risk Factors:**
- Database schema changes
- Changes to core job handling logic
- Potential for deadlocks with locking
- Migration could fail on large datasets

**Mitigation Strategies:**
- Implement changes incrementally
- Comprehensive testing including load testing
- Database migration testing on copy of production data
- Rollback plan for each phase

## Rollback Plan

**Phase-by-Phase Rollback:**
1. **JobManager issues:** Revert to manual job handling
2. **Model constraints issues:** Rollback database migration
3. **Task updates issues:** Revert task function changes
4. **Performance issues:** Adjust indexing and locking strategy

**Emergency Rollback:**
```bash
# Rollback database migration
flask db downgrade -1

# Revert code changes
git checkout HEAD~1 -- src/models/job.py
git checkout HEAD~1 -- src/utils/job_manager.py
git checkout HEAD~1 -- src/tasks/tasks.py
```

## Success Criteria

- ✅ No job duplicate creation under concurrent load
- ✅ All status transitions follow valid state machine
- ✅ Database constraints prevent invalid data
- ✅ All operations are atomic and consistent
- ✅ Performance is maintained or improved
- ✅ All existing functionality continues to work
- ✅ Comprehensive test coverage for concurrency scenarios

## Performance Considerations

### Database Performance
- Monitor query execution times
- Check for lock contention
- Verify index usage
- Watch for deadlock patterns

### Application Performance
- Monitor job processing throughput
- Check for increased latency
- Verify memory usage patterns
- Test under high concurrency

## Monitoring & Metrics

**Key Metrics to Track:**
- Job creation/update latency
- Database lock wait times
- Failed job status transitions
- Constraint violation rates
- Deadlock occurrences

**Alerts to Implement:**
- High database lock contention
- Unusual job status transition failures
- Database constraint violations
- Job processing bottlenecks
