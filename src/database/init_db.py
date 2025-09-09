"""Database initialization and setup utilities"""
from src.models.base import db
from src.models import CompressionJob, Job
import logging

logger = logging.getLogger(__name__)

def init_database(app):
    """Initialize database tables and create default data"""
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            logger.info("Database tables created successfully")
            logger.info("Database initialization completed")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
            raise

def reset_database(app):
    """Reset database - WARNING: This will delete all data"""
    with app.app_context():
        try:
            # Drop all tables
            db.drop_all()
            logger.warning("All database tables dropped")
            
            # Recreate tables
            db.create_all()
            logger.info("Database tables recreated")
            
            logger.info("Database reset completed")
            
        except Exception as e:
            logger.error(f"Database reset failed: {str(e)}")
            raise