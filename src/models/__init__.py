# src/models/__init__.py
from .base import db
from .job import Job, JobStatus  # This ensures the model is registered with SQLAlchemy

__all__ = ['db', 'Job', 'JobStatus']