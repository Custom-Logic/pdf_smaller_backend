from flask import Flask
from flask_cors import CORS

from src.main.routes import compression_bp
from src.utils import setup_logging
from src.config import Config

def create_app():
    """Application factory function"""
    # Setup logging
    setup_logging()
    
    app = Flask(__name__)
    
    # Configuration
    app.config.from_object(Config)
    
    # Enable CORS
    CORS(app, origins=app.config.get('ALLOWED_ORIGINS', ['*']))
    
    # Register blueprints
    app.register_blueprint(compression_bp, url_prefix='/api')
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'pdf-compression-server'}
    
    return app


