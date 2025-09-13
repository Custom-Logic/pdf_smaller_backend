# src/models/__init__.py
from src.models.base import db
from src.models.job import Job, JobStatus  # This ensures the model is registered with SQLAlchemy

__all__ = ['db', 'Job', 'JobStatus']