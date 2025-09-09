"""Database initialization and setup utilities"""
from src.models.base import db
from src.models import Job
import logging

logger = logging.getLogger(__name__)


def init_database(app):
    """Initialize database tables and create default data"""
    with app.app_context():
        try:
            from src.models import db

            # Debug info
            import os
            db_uri = app.config['SQLALCHEMY_DATABASE_URI']
            print(f"Database URI: {db_uri}")

            # Create all tables
            db.create_all()
            print("Database tables created successfully")

            # Verify
            if 'sqlite' in db_uri:
                db_path = db_uri.replace('sqlite:///', '')
                if os.path.exists(db_path):
                    print(f"Database file created: {db_path}")
                else:
                    print("WARNING: Database file not found")

        except Exception as e:
            print(f"Database initialization failed: {str(e)}")
            import traceback
            traceback.print_exc()
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