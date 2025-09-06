from .base import db, BaseModel
import json

class CompressionJob(BaseModel):
    """Compression job tracking model"""
    __tablename__ = 'compression_jobs'
    
    # Job details
    job_type = db.Column(db.String(50), nullable=False)  # 'single' or 'bulk'
    status = db.Column(db.String(50), nullable=False, default='pending')  # pending, processing, completed, failed
    
    # File information
    original_filename = db.Column(db.String(500))
    file_count = db.Column(db.Integer, default=1, nullable=False)
    completed_count = db.Column(db.Integer, default=0, nullable=False)
    
    # Compression settings (stored as JSON)
    settings = db.Column(db.JSON)
    
    # File paths
    input_path = db.Column(db.String(500))
    result_path = db.Column(db.String(500))
    
    # Processing details
    original_size_bytes = db.Column(db.BigInteger)
    compressed_size_bytes = db.Column(db.BigInteger)
    compression_ratio = db.Column(db.Float)
    
    # Timing
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    
    # Error handling
    error_message = db.Column(db.Text)
    
    # Celery task tracking
    task_id = db.Column(db.String(255))
    
    def __init__(self, job_type, original_filename=None, settings=None):
        self.job_type = job_type
        self.original_filename = original_filename
        self.settings = settings or {}
        self.status = 'pending'
    
    def set_settings(self, settings_dict):
        """Set compression settings from dictionary"""
        self.settings = settings_dict
    
    def get_settings(self):
        """Get compression settings as dictionary"""
        return self.settings or {}
    
    def calculate_compression_ratio(self):
        """Calculate and store compression ratio"""
        if self.original_size_bytes and self.compressed_size_bytes:
            self.compression_ratio = (
                (self.original_size_bytes - self.compressed_size_bytes) / 
                self.original_size_bytes * 100
            )
        return self.compression_ratio
    
    def get_progress_percentage(self):
        """Get job progress as percentage"""
        if self.file_count == 0:
            return 0
        return (self.completed_count / self.file_count) * 100
    
    def is_completed(self):
        """Check if job is completed (successfully or with error)"""
        return self.status in ['completed', 'failed']
    
    def is_successful(self):
        """Check if job completed successfully"""
        return self.status == 'completed'
    
    def mark_as_processing(self):
        """Mark job as currently processing"""
        from datetime import datetime
        self.status = 'processing'
        self.started_at = datetime.utcnow()
    
    def mark_as_completed(self):
        """Mark job as successfully completed"""
        from datetime import datetime
        self.status = 'completed'
        self.completed_at = datetime.utcnow()
        self.completed_count = self.file_count
    
    def mark_as_failed(self, error_message=None):
        """Mark job as failed with optional error message"""
        from datetime import datetime
        self.status = 'failed'
        self.completed_at = datetime.utcnow()
        if error_message:
            self.error_message = error_message
    
    def to_dict(self):
        """Convert job to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'job_type': self.job_type,
            'status': self.status,
            'original_filename': self.original_filename,
            'file_count': self.file_count,
            'completed_count': self.completed_count,
            'progress_percentage': self.get_progress_percentage(),
            'settings': self.get_settings(),
            'original_size_bytes': self.original_size_bytes,
            'compressed_size_bytes': self.compressed_size_bytes,
            'compression_ratio': self.compression_ratio,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'error_message': self.error_message,
            'task_id': self.task_id,
            'is_completed': self.is_completed(),
            'is_successful': self.is_successful()
        }
    
    def __repr__(self):
        return f'<CompressionJob {self.id} {self.job_type} {self.status}>'