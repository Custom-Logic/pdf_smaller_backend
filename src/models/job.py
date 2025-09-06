from enum import Enum
from .base import db, BaseModel

class JobStatus(Enum):
    """Job status enum"""
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'

class Job(BaseModel):
    """Generic job tracking model"""
    __tablename__ = 'jobs'
    
    # Job details
    task_type = db.Column(db.String(50), nullable=False)  # 'compress', 'convert', 'ocr', etc.
    status = db.Column(db.String(50), nullable=False, default=JobStatus.PENDING.value)
    
    # Input/output data
    input_data = db.Column(db.JSON)  # Store input parameters
    result = db.Column(db.JSON)  # Store output results
    
    # Client tracking
    client_job_id = db.Column(db.String(255))  # Optional client-provided ID
    client_session_id = db.Column(db.String(255))  # Optional client session tracking
    
    # Error handling
    error = db.Column(db.Text)  # Error message if job failed
    
    # Celery task tracking
    task_id = db.Column(db.String(255))  # Celery task ID
    
    def __init__(self, id=None, task_type=None, input_data=None, client_job_id=None, client_session_id=None):
        if id:
            self.id = id
        self.task_type = task_type
        self.input_data = input_data or {}
        self.client_job_id = client_job_id
        self.client_session_id = client_session_id
        self.status = JobStatus.PENDING.value
    
    def mark_as_processing(self):
        """Mark job as currently processing"""
        from datetime import datetime
        self.status = JobStatus.PROCESSING.value
        self.updated_at = datetime.utcnow()
    
    def mark_as_completed(self, result=None):
        """Mark job as successfully completed"""
        from datetime import datetime
        self.status = JobStatus.COMPLETED.value
        self.updated_at = datetime.utcnow()
        if result:
            self.result = result
    
    def mark_as_failed(self, error=None):
        """Mark job as failed with optional error message"""
        from datetime import datetime
        self.status = JobStatus.FAILED.value
        self.updated_at = datetime.utcnow()
        if error:
            self.error = error
    
    def is_completed(self):
        """Check if job is completed (successfully or with error)"""
        return self.status in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]
    
    def is_successful(self):
        """Check if job completed successfully"""
        return self.status == JobStatus.COMPLETED.value
    
    def to_dict(self):
        """Convert job to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'task_type': self.task_type,
            'status': self.status,
            'input_data': self.input_data,
            'result': self.result,
            'client_job_id': self.client_job_id,
            'client_session_id': self.client_session_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'error': self.error,
            'task_id': self.task_id,
            'is_completed': self.is_completed(),
            'is_successful': self.is_successful()
        }
    
    def __repr__(self):
        return f'<Job {self.id} {self.task_type} {self.status}>'