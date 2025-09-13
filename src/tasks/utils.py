"""Task utility classes for progress reporting and file management."""

import os
import tempfile
import shutil
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from datetime import datetime, timezone
from src.models.job import Job
from src.models.base import db
from src.utils.db_transaction import db_transaction, safe_db_operation


class ProgressReporter:
    """Handles progress reporting for long-running tasks."""
    
    def __init__(self, job: Job, total_steps: int = 100):
        """
        Initialize progress reporter.
        
        Args:
            job: Job instance to update
            total_steps: Total number of steps for the task
        """
        self.job = job
        self.total_steps = total_steps
        self.current_step = 0
        self.status_message = ""
    
    def update(self, step: int = None, message: str = None, percentage: float = None):
        """
        Update task progress.
        
        Args:
            step: Current step number
            message: Status message
            percentage: Direct percentage (0-100)
        """
        if step is not None:
            self.current_step = step
        if message is not None:
            self.status_message = message
        
        # Calculate percentage
        if percentage is not None:
            progress_pct = min(100, max(0, percentage))
        else:
            progress_pct = min(100, (self.current_step / self.total_steps) * 100)
        
        # Update job result with progress info
        if not self.job.result:
            self.job.result = {}
        
        self.job.result.update({
            'progress': {
                'percentage': round(progress_pct, 2),
                'current_step': self.current_step,
                'total_steps': self.total_steps,
                'message': self.status_message,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
        })
        
        # Use safe database operation for progress updates
        def update_progress():
            # Database changes are already made above, just need to commit
            pass
        
        safe_db_operation(
            update_progress,
            f"update_progress_{self.job.job_id}",
            max_retries=1,
            default_return=None
        )
    
    def complete(self, final_message: str = "Task completed successfully"):
        """Mark progress as complete."""
        self.update(step=self.total_steps, message=final_message, percentage=100)
    
    def increment(self, message: str = None):
        """Increment progress by one step."""
        self.update(step=self.current_step + 1, message=message)


class TemporaryFileManager:
    """Manages temporary files and directories for task processing."""
    
    def __init__(self, prefix: str = "pdf_task_"):
        """
        Initialize temporary file manager.
        
        Args:
            prefix: Prefix for temporary files/directories
        """
        self.prefix = prefix
        self.temp_files: List[str] = []
        self.temp_dirs: List[str] = []
    
    def create_temp_file(self, suffix: str = ".tmp", delete: bool = False) -> str:
        """
        Create a temporary file.
        
        Args:
            suffix: File suffix
            delete: Whether to auto-delete on close
        
        Returns:
            Path to temporary file
        """
        fd, path = tempfile.mkstemp(suffix=suffix, prefix=self.prefix, delete=delete)
        os.close(fd)  # Close file descriptor, keep the file
        self.temp_files.append(path)
        return path
    
    def create_temp_dir(self) -> str:
        """
        Create a temporary directory.
        
        Returns:
            Path to temporary directory
        """
        path = tempfile.mkdtemp(prefix=self.prefix)
        self.temp_dirs.append(path)
        return path
    
    def cleanup(self):
        """Clean up all temporary files and directories."""
        # Clean up temporary files
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception:
                pass  # Ignore cleanup errors
        
        # Clean up temporary directories
        for dir_path in self.temp_dirs:
            try:
                if os.path.exists(dir_path):
                    shutil.rmtree(dir_path)
            except Exception:
                pass  # Ignore cleanup errors
        
        # Clear lists
        self.temp_files.clear()
        self.temp_dirs.clear()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit with cleanup."""
        self.cleanup()


@contextmanager
def task_context(job: Job, total_steps: int = 100, temp_prefix: str = None):
    """
    Context manager that provides both progress reporting and temporary file management.
    
    Args:
        job: Job instance
        total_steps: Total steps for progress tracking
        temp_prefix: Prefix for temporary files
    
    Yields:
        Tuple of (ProgressReporter, TemporaryFileManager)
    """
    temp_prefix = temp_prefix or f"task_{job.task_type}_"
    
    with TemporaryFileManager(prefix=temp_prefix) as temp_manager:
        progress = ProgressReporter(job, total_steps)
        try:
            yield progress, temp_manager
        finally:
            # Cleanup is handled by TemporaryFileManager context manager
            pass


class TaskMetrics:
    """Collects and manages task execution metrics."""
    
    def __init__(self, job: Job):
        self.job = job
        self.start_time = datetime.now(timezone.utc)
        self.metrics = {
            'start_time': self.start_time.isoformat(),
            'files_processed': 0,
            'bytes_processed': 0,
            'errors_encountered': 0,
            'retries_attempted': 0
        }
    
    def record_file_processed(self, file_size: int = 0):
        """Record that a file was processed."""
        self.metrics['files_processed'] += 1
        self.metrics['bytes_processed'] += file_size
    
    def record_error(self):
        """Record an error occurrence."""
        self.metrics['errors_encountered'] += 1
    
    def record_retry(self):
        """Record a retry attempt."""
        self.metrics['retries_attempted'] += 1
    
    def finalize(self):
        """Finalize metrics and update job."""
        end_time = datetime.now(timezone.utc)
        self.metrics.update({
            'end_time': end_time.isoformat(),
            'duration_seconds': (end_time - self.start_time).total_seconds()
        })
        
        # Update job result with metrics
        if not self.job.result:
            self.job.result = {}
        
        self.job.result['metrics'] = self.metrics
        
        # Use safe database operation for metrics finalization
        def finalize_metrics():
            # Database changes are already made above, just need to commit
            pass
        
        safe_db_operation(
            finalize_metrics,
            f"finalize_metrics_{self.job.job_id}",
            max_retries=1,
            default_return=None
        )