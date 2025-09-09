import logging
import os

from flask import Flask, jsonify
from sqlalchemy import text

from src.config.config import get_config, validate_current_config, ConfigValidationError
from src.database import init_database
from src.models.base import db
from src.routes import compression_bp, extended_features_bp
from src.utils import setup_logging
from src.utils.cors_config import configure_secure_cors
from src.utils.error_handlers import register_error_handlers
from src.utils.scheduler import start_background_scheduler

import sentry_sdk

def create_app(config_name=None, config_override=None):
    """
    Application factory function with enhanced configuration management
    
    Args:
        config_name (str): Configuration environment name ('development', 'testing', 'production')
        config_override (object): Configuration object to override default config
    
    Returns:
        Flask: Configured Flask application instance
    """

    sentry_sdk.init(
        dsn="https://ad33a061c36eab16eaba8e51bb76e4f9@o544206.ingest.us.sentry.io/4509991179124736",
        # Add data like request headers and IP for users,
        # see https://docs.sentry.io/platforms/python/data-management/data-collected/ for more info
        send_default_pii=True,
    )
    # Create Flask application
    app = Flask(__name__)
    
    # Load configuration
    try:
        if config_override:
            app.config.from_object(config_override)
        else:
            config_class = get_config(config_name)
            app.config.from_object(config_class)
        
        # Validate configuration
        if not app.config.get('TESTING', False):
            validate_current_config()
            
    except ConfigValidationError as e:
        logging.error(f"Configuration validation failed: {e}")
        if not app.config.get('TESTING', False):
            raise
    
    # Setup logging early
    log_level = app.config.get('LOG_LEVEL', 'INFO')
    setup_logging(log_level=log_level)
    
    # Log configuration summary (excluding sensitive data)
    config_class = get_config(config_name) if not config_override else config_override
    if hasattr(config_class, 'get_config_summary'):
        config_summary = config_class.get_config_summary()
        app.logger.info(f"Application starting with configuration: {config_summary}")
    with app.app_context():
        # Initialize extensions

        initialize_extensions(app)
        
        # Register error handlers
        register_error_handlers(app)
        
        # Initialize security and middleware
        initialize_security(app)
        
        # Register blueprints
        register_blueprints(app)
        
        # Setup background tasks
        initialize_background_tasks(app)
        
        # Register health check endpoints
        register_health_checks(app)
        # Register configuration endpoint (development only)
        if app.config.get('DEBUG', False):
            register_debug_endpoints(app)
        
        app.logger.info("Application factory completed successfully")
        return app


def initialize_extensions(app):
    """Initialize Flask extensions"""

    # Initialize database FIRST
    from src.models import db
    db.init_app(app)

    # Import models AFTER db is initialized

    # Initialize database tables
    init_database(app)

    # ... rest of your code ...



def initialize_security(app):
    """Initialize CORS"""
    
    # Configure secure CORS
    try:
        allowed_origins = app.config.get('ALLOWED_ORIGINS', [])
        secure_cors = configure_secure_cors(app, allowed_origins)
        app.secure_cors = secure_cors
        app.logger.info(f"CORS configured for origins: {allowed_origins}")
    except Exception as e:
        app.logger.error(f"CORS configuration failed: {e}")
        raise


def register_blueprints(app):
    """Register application blueprints"""
    
    blueprints = [
        (compression_bp, '/api'),
        (extended_features_bp, '/api')
    ]
    
    for blueprint, url_prefix in blueprints:
        try:
            app.register_blueprint(blueprint, url_prefix=url_prefix)
            app.logger.info(f"Registered blueprint: {blueprint.name} at {url_prefix}")
        except Exception as e:
            app.logger.error(f"Failed to register blueprint {blueprint.name}: {e}")
            raise


def initialize_background_tasks(app):
    """Initialize background tasks and schedulers"""
    
    if app.config.get('TESTING', False):
        app.logger.info("Skipping background tasks in testing mode")
        return
    
    try:
        upload_folder = app.config.get('UPLOAD_FOLDER', '/tmp/pdf_uploads')
        
        # Ensure upload folder exists
        os.makedirs(upload_folder, exist_ok=True)
        
        # Start background scheduler for cleanup tasks
        start_background_scheduler(upload_folder)
        app.logger.info(f"Background scheduler started for folder: {upload_folder}")
        
    except Exception as e:
        app.logger.warning(f"Background task initialization failed: {e}")


def register_health_checks(app):
    """Register health check endpoints"""
    
    @app.route('/health')
    def health_check():
        """Basic health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'service': 'pdf-compression-server',
            'version': '1.0.0',
            'environment': app.config.get('FLASK_ENV', 'unknown')
        })
    
    @app.route('/health/db')
    def db_health_check():
        """Database health check endpoint"""
        try:
            # Simple database query to check connection
            db.session.execute(text('SELECT 1'))  # Wrap with text()
            db.session.commit()
            
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'database_type': 'sqlite' if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI'] else 'postgresql'
            })
        except Exception as e:
            app.logger.error(f"Database health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'database': 'disconnected',
                'error': str(e)
            }), 500

    @app.route('/health/redis')
    def redis_health_check():
        """Redis health check endpoint via Celery ping"""
        try:
            if hasattr(app, 'celery') and app.celery:
                # Simple ping test through Celery
                # This will test both broker and backend connections
                result = app.celery.control.ping(timeout=1)
                
                if result:
                    return jsonify({
                        'status': 'healthy',
                        'redis': 'connected',
                        'method': 'via_celery_ping',
                        'workers_responding': len(result),
                        'broker_url': app.config.get('CELERY_BROKER_URL', 'unknown')
                    })
                else:
                    return jsonify({
                        'status': 'unhealthy',
                        'redis': 'no_workers_responding',
                        'method': 'via_celery_ping'
                    }), 500
                    
            else:
                return jsonify({
                    'status': 'unknown',
                    'redis': 'celery_not_configured'
                })
        except Exception as e:
            app.logger.error(f"Redis health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'redis': 'disconnected',
                'method': 'via_celery_ping',
                'error': str(e)
            }), 500
            
def register_debug_endpoints(app):
    """Register debug endpoints (development only)"""
    
    @app.route('/debug/config')
    def debug_config():
        """Debug endpoint to view configuration summary"""
        if not app.config.get('DEBUG', False):
            return jsonify({'error': 'Debug mode not enabled'}), 404
        
        config_class = type(app.config)
        if hasattr(config_class, 'get_config_summary'):
            return jsonify(config_class.get_config_summary())
        else:
            return jsonify({'error': 'Configuration summary not available'})
    
    @app.route('/debug/routes')
    def debug_routes():
        """Debug endpoint to view all registered routes"""
        if not app.config.get('DEBUG', False):
            return jsonify({'error': 'Debug mode not enabled'}), 404
        
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                'endpoint': rule.endpoint,
                'methods': list(rule.methods),
                'rule': str(rule)
            })
        
        return jsonify({'routes': routes})

    @app.route('/debug/database')
    def debug_database():
        """Debug endpoint to check database status"""
        try:
            db_uri = app.config['SQLALCHEMY_DATABASE_URI']
            db_info = {
                'database_uri': db_uri,
                'database_type': 'sqlite' if 'sqlite' in db_uri else 'unknown',
                'current_working_directory': os.getcwd(),
                'database_file_exists': False,
                'tables_exist': False
            }

            if db_uri.startswith('sqlite:///') and db_uri != 'sqlite:///:memory:':
                db_path = db_uri.replace('sqlite:///', '')
                db_info['database_path'] = os.path.abspath(db_path)
                db_info['database_file_exists'] = os.path.exists(db_path)

                # Check if tables exist
                if db_info['database_file_exists']:
                    try:
                        # Try to query a table
                        from src.models.job import Job
                        count = db.session.query(Job).count()
                        db_info['tables_exist'] = True
                        db_info['job_count'] = count
                    except:
                        db_info['tables_exist'] = False

            return jsonify(db_info)

        except Exception as e:
            return jsonify({'error': str(e)}), 500
