import os
import logging
from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate

from src.routes import auth_bp, compression_bp, subscription_bp, admin_bp, extended_features_bp
from src.utils import setup_logging
from src.utils.scheduler import start_background_scheduler
from src.utils.rate_limiter import create_rate_limiter, RateLimitMiddleware
from src.utils.security_middleware import create_security_middleware
from src.utils.cors_config import configure_secure_cors
from src.utils.error_handlers import register_error_handlers
from src.config.config import get_config, validate_current_config, ConfigValidationError
from src.models.base import db
from src.database import init_database, setup_migrations

# Global extensions
migrate = Migrate()
jwt = JWTManager()

def create_app(config_name=None, config_override=None):
    """
    Application factory function with enhanced configuration management
    
    Args:
        config_name (str): Configuration environment name ('development', 'testing', 'production')
        config_override (object): Configuration object to override default config
    
    Returns:
        Flask: Configured Flask application instance
    """
    
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
    setup_logging(app)
    
    # Log configuration summary (excluding sensitive data)
    config_class = get_config(config_name) if not config_override else config_override
    if hasattr(config_class, 'get_config_summary'):
        config_summary = config_class.get_config_summary()
        app.logger.info(f"Application starting with configuration: {config_summary}")
    
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
    
    # Initialize database
    db.init_app(app)
    
    # Initialize database migrations
    migrate.init_app(app, db)
    
    # Setup JWT
    jwt.init_app(app)
    
    # Configure JWT callbacks
    configure_jwt_callbacks(app)
    
    # Initialize Celery (if not in testing mode)
    if not app.config.get('TESTING', False):
        try:
            from src.celery_app import make_celery
            celery = make_celery(app)
            app.celery = celery
            app.logger.info("Celery initialized successfully")
        except Exception as e:
            app.logger.warning(f"Celery initialization failed: {e}")
    
    # Initialize database tables
    init_database(app)


def configure_jwt_callbacks(app):
    """Configure JWT callbacks for token management"""
    
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):
        return jsonify({
            'error': {
                'code': 'TOKEN_EXPIRED',
                'message': 'The token has expired'
            }
        }), 401
    
    @jwt.invalid_token_loader
    def invalid_token_callback(error):
        return jsonify({
            'error': {
                'code': 'INVALID_TOKEN',
                'message': 'Invalid token'
            }
        }), 401
    
    @jwt.unauthorized_loader
    def missing_token_callback(error):
        return jsonify({
            'error': {
                'code': 'MISSING_TOKEN',
                'message': 'Authorization token is required'
            }
        }), 401


def initialize_security(app):
    """Initialize security middleware and CORS"""
    
    # Initialize security middleware (must be before CORS and rate limiting)
    try:
        security_middleware = create_security_middleware(app)
        app.security_middleware = security_middleware
        app.logger.info("Security middleware initialized")
    except Exception as e:
        app.logger.error(f"Security middleware initialization failed: {e}")
        raise
    
    # Configure secure CORS
    try:
        allowed_origins = app.config.get('ALLOWED_ORIGINS', [])
        secure_cors = configure_secure_cors(app, allowed_origins)
        app.secure_cors = secure_cors
        app.logger.info(f"CORS configured for origins: {allowed_origins}")
    except Exception as e:
        app.logger.error(f"CORS configuration failed: {e}")
        raise
    
    # Initialize rate limiting
    try:
        rate_limiter = create_rate_limiter(app)
        rate_limit_middleware = RateLimitMiddleware(app, rate_limiter)
        app.rate_limiter = rate_limiter
        app.logger.info("Rate limiting initialized")
    except Exception as e:
        app.logger.warning(f"Rate limiting initialization failed: {e}")


def register_blueprints(app):
    """Register application blueprints"""
    
    blueprints = [
        (auth_bp, '/api/auth'),
        (compression_bp, '/api'),
        (subscription_bp, '/api/subscriptions'),
        (admin_bp, '/api/admin'),
		(extended_features_bp, '/api')
    ]
    
    for blueprint, url_prefix in blueprints:
        try:
            app.register_blueprint(blueprint)
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
            db.session.execute('SELECT 1')
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
        """Redis health check endpoint"""
        try:
            if hasattr(app, 'rate_limiter') and app.rate_limiter:
                # Test Redis connection through rate limiter
                app.rate_limiter.storage.storage.ping()
                return jsonify({
                    'status': 'healthy',
                    'redis': 'connected'
                })
            else:
                return jsonify({
                    'status': 'unknown',
                    'redis': 'not_configured'
                })
        except Exception as e:
            app.logger.error(f"Redis health check failed: {e}")
            return jsonify({
                'status': 'unhealthy',
                'redis': 'disconnected',
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


