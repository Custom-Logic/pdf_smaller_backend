import os
import logging
from src.main import create_app
from src.config.config import ConfigValidationError

# Create application instance
try:
    # Get configuration environment from environment variable
    config_name = os.environ.get('FLASK_ENV', 'production')
    app = create_app(config_name=config_name)
    
    # Log successful startup
    app.logger.info(f"PDF Smaller application started successfully in {config_name} mode")
    
except ConfigValidationError as e:
    logging.error(f"Configuration validation failed: {e}")
    raise
except Exception as e:
    logging.error(f"Application startup failed: {e}")
    raise

if __name__ == '__main__':
    # Development server (not for production)
    debug_mode = app.config.get('DEBUG', True)
    app.run(
        host='0.0.0.0', 
        port=int(os.environ.get('PORT', 5000)), 
        debug=debug_mode
    )