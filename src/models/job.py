from enum import Enum
from .base import db, BaseModel

class JobStatus(Enum):
    """Job status enum"""
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'


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

    # Primary key - client-provided ID
    job_id = db.Column(db.String(255), primary_key=True)

    session_id = db.Column(db.String(255))  # Optional client session tracking
    # Celery task tracking
    task_id = db.Column(db.String(255))  # Celery task ID
    # Job details
    task_type = db.Column(db.String(50), nullable=False)  # 'compress', 'convert', 'ocr', etc.
    status = db.Column(db.String(50), nullable=False, default=JobStatus.PENDING.value)
    # Input/output data
    input_data = db.Column(db.JSON)  # Store input parameters
    result = db.Column(db.JSON)  # Store output results
    # Error handling
    error = db.Column(db.Text)  # Error message if job failed

    def __init__(self, task_type=None, input_data=None, job_id=None, session_id=None):
        self.job_id = job_id  # Now required since it's the primary key
        self.task_type = task_type
        self.input_data = input_data or {}
        self.session_id = session_id
        self.status = JobStatus.PENDING.value

    # ... rest of your methods remain the same ...

    def to_dict(self):
        """Convert job to dictionary for JSON serialization"""
        return {
            'job_id': self.job_id,  # Fixed this line (was client_job_id)
            'task_type': self.task_type,
            'status': self.status,
            'input_data': self.input_data,
            'result': self.result,
            'session_id': self.session_id,  # Fixed this line (was client_session_id)
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'error': self.error,
            'task_id': self.task_id,
            'is_completed': self.is_completed(),
            'is_successful': self.is_successful()
        }

    def __repr__(self):
        return f'<Job {self.job_id} {self.task_type} {self.status}>'
