"""Database transaction management utilities.

This module provides a robust transaction context manager and related utilities
for safe database operations with automatic rollback on errors.
"""

import logging
from contextlib import contextmanager
from typing import Optional, Any, Callable, TypeVar, Generic
from functools import wraps
from sqlalchemy.exc import SQLAlchemyError, DBAPIError, OperationalError, IntegrityError
from src.models.base import db

logger = logging.getLogger(__name__)

T = TypeVar('T')


class DatabaseTransactionError(Exception):
    """Custom exception for database transaction errors.
    
    This exception is raised when database operations fail and provides
    additional context about the failure type and recovery options.
    """
    
    def __init__(self, message: str, original_error: Optional[Exception] = None, 
                 operation: Optional[str] = None, rollback_attempted: bool = False):
        super().__init__(message)
        self.original_error = original_error
        self.operation = operation
        self.rollback_attempted = rollback_attempted
        
    def __str__(self) -> str:
        base_msg = super().__str__()
        if self.operation:
            base_msg = f"[{self.operation}] {base_msg}"
        if self.original_error:
            base_msg += f" (Original: {type(self.original_error).__name__}: {self.original_error})"
        if self.rollback_attempted:
            base_msg += " [Rollback attempted]"
        return base_msg


@contextmanager
def db_transaction(operation_name: Optional[str] = None, 
                  auto_commit: bool = True,
                  raise_on_error: bool = True):
    """Database transaction context manager with automatic rollback.
    
    Provides a safe way to execute database operations within a transaction
    with automatic rollback on any exception.
    
    Args:
        operation_name: Optional name for logging and error context
        auto_commit: Whether to automatically commit on success (default: True)
        raise_on_error: Whether to re-raise exceptions after rollback (default: True)
        
    Yields:
        The database session for performing operations
        
    Raises:
        DatabaseTransactionError: If database operation fails and raise_on_error is True
        
    Example:
        ```python
        try:
            with db_transaction("update_job_status") as session:
                job = session.query(Job).filter_by(job_id=job_id).first()
                job.status = JobStatus.COMPLETED.value
                # Automatic commit on success
        except DatabaseTransactionError as e:
            logger.error(f"Transaction failed: {e}")
            return False
        ```
    """
    rollback_attempted = False
    
    try:
        # Begin transaction (if not already in one)
        if not db.session.in_transaction():
            db.session.begin()
            
        logger.debug(f"Starting transaction: {operation_name or 'unnamed'}")
        
        yield db.session
        
        # Commit if auto_commit is enabled and no exception occurred
        if auto_commit:
            db.session.commit()
            logger.debug(f"Transaction committed: {operation_name or 'unnamed'}")
            
    except (SQLAlchemyError, DBAPIError) as db_error:
        rollback_attempted = True
        try:
            db.session.rollback()
            logger.warning(f"Database transaction rolled back for {operation_name or 'unnamed'}: {db_error}")
        except Exception as rollback_error:
            logger.error(f"Failed to rollback transaction for {operation_name or 'unnamed'}: {rollback_error}")
            
        if raise_on_error:
            raise DatabaseTransactionError(
                f"Database operation failed: {db_error}",
                original_error=db_error,
                operation=operation_name,
                rollback_attempted=True
            )
            
    except Exception as general_error:
        rollback_attempted = True
        try:
            db.session.rollback()
            logger.warning(f"General transaction rolled back for {operation_name or 'unnamed'}: {general_error}")
        except Exception as rollback_error:
            logger.error(f"Failed to rollback transaction for {operation_name or 'unnamed'}: {rollback_error}")
            
        if raise_on_error:
            raise DatabaseTransactionError(
                f"Transaction failed due to unexpected error: {general_error}",
                original_error=general_error,
                operation=operation_name,
                rollback_attempted=True
            )


def transactional(operation_name: Optional[str] = None, 
                 auto_commit: bool = True,
                 raise_on_error: bool = True):
    """Decorator to wrap functions in a database transaction.
    
    Args:
        operation_name: Optional name for logging (defaults to function name)
        auto_commit: Whether to automatically commit on success
        raise_on_error: Whether to re-raise exceptions after rollback
        
    Example:
        ```python
        @transactional("update_job_status")
        def update_job_status(job_id: str, status: JobStatus):
            job = Job.query.filter_by(job_id=job_id).first()
            if job:
                job.status = status.value
                return True
            return False
        ```
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            op_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            with db_transaction(op_name, auto_commit, raise_on_error):
                return func(*args, **kwargs)
                
        return wrapper
    return decorator


def safe_db_operation(operation: Callable[[], T], 
                     operation_name: Optional[str] = None,
                     max_retries: int = 3,
                     default_return: Optional[T] = None) -> Optional[T]:
    """Execute a database operation with retry logic and error handling.
    
    Args:
        operation: Function to execute within transaction
        operation_name: Optional name for logging
        max_retries: Maximum number of retry attempts
        default_return: Value to return if all attempts fail
        
    Returns:
        Result of the operation or default_return if all attempts fail
        
    Example:
        ```python
        def update_job():
            job = Job.query.filter_by(job_id=job_id).first()
            job.status = JobStatus.COMPLETED.value
            return job
            
        result = safe_db_operation(update_job, "update_job_status", max_retries=2)
        ```
    """
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            with db_transaction(operation_name, auto_commit=True, raise_on_error=True):
                return operation()
                
        except DatabaseTransactionError as e:
            last_error = e
            
            # Check if this is a retryable error
            if isinstance(e.original_error, (OperationalError, DBAPIError)):
                if attempt < max_retries:
                    logger.warning(f"Retrying database operation {operation_name} (attempt {attempt + 1}/{max_retries}): {e}")
                    continue
                    
            # Non-retryable error or max retries reached
            logger.error(f"Database operation {operation_name} failed permanently: {e}")
            break
            
        except Exception as e:
            last_error = e
            logger.error(f"Unexpected error in database operation {operation_name}: {e}")
            break
    
    logger.error(f"All attempts failed for operation {operation_name}. Last error: {last_error}")
    return default_return


def get_or_create_with_lock(model_class, filter_kwargs: dict, 
                           create_kwargs: Optional[dict] = None,
                           operation_name: Optional[str] = None) -> tuple[Any, bool]:
    """Get existing record or create new one with proper locking to prevent race conditions.
    
    Args:
        model_class: SQLAlchemy model class
        filter_kwargs: Dictionary of filter conditions
        create_kwargs: Additional fields for creation (merged with filter_kwargs)
        operation_name: Optional name for logging
        
    Returns:
        Tuple of (instance, created) where created is True if new record was created
        
    Example:
        ```python
        job, created = get_or_create_with_lock(
            Job, 
            {'job_id': job_id},
            {'task_type': 'compress', 'status': JobStatus.PENDING.value},
            "get_or_create_job"
        )
        ```
    """
    op_name = operation_name or f"get_or_create_{model_class.__name__}"
    
    with db_transaction(op_name, auto_commit=True, raise_on_error=True):
        # Try to get existing record with row lock
        query = db.session.query(model_class).filter_by(**filter_kwargs)
        
        # Use SELECT FOR UPDATE to prevent race conditions
        existing = query.with_for_update().first()
        
        if existing:
            logger.debug(f"Found existing {model_class.__name__} with {filter_kwargs}")
            return existing, False
            
        # Create new record
        create_data = filter_kwargs.copy()
        if create_kwargs:
            create_data.update(create_kwargs)
            
        new_instance = model_class(**create_data)
        db.session.add(new_instance)
        db.session.flush()  # Ensure ID is assigned before commit
        
        logger.debug(f"Created new {model_class.__name__} with {create_data}")
        return new_instance, True