"""Database migration utilities using Flask-Migrate"""
from flask_migrate import Migrate
import logging

logger = logging.getLogger(__name__)

def setup_migrations(app, db):
    """Setup Flask-Migrate for database migrations"""
    try:
        migrate = Migrate(app, db)
        logger.info("Database migrations configured successfully")
        return migrate
    except Exception as e:
        logger.error(f"Failed to setup database migrations: {str(e)}")
        raise

def create_migration(message="Auto migration"):
    """Create a new migration file"""
    try:
        from flask_migrate import migrate as create_migrate
        create_migrate(message=message)
        logger.info(f"Migration created: {message}")
    except Exception as e:
        logger.error(f"Failed to create migration: {str(e)}")
        raise

def upgrade_database():
    """Apply pending migrations to database"""
    try:
        from flask_migrate import upgrade
        upgrade()
        logger.info("Database upgraded successfully")
    except Exception as e:
        logger.error(f"Database upgrade failed: {str(e)}")
        raise

def downgrade_database(revision="-1"):
    """Downgrade database to previous revision"""
    try:
        from flask_migrate import downgrade
        downgrade(revision=revision)
        logger.info(f"Database downgraded to revision: {revision}")
    except Exception as e:
        logger.error(f"Database downgrade failed: {str(e)}")
        raise