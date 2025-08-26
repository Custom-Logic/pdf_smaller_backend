import os
import logging
from flask import Flask
from flask_cors import CORS
from app.routes import compression_bp
from app.utils.logging_utils import setup_logging

def create_app():
    """Application factory function"""
    # Setup logging
    setup_logging()
    
    app = Flask(__name__)
    
    # Configuration
    app.config.from_object('config.Config')
    
    # Enable CORS
    CORS(app, origins=app.config.get('ALLOWED_ORIGINS', ['*']))
    
    # Register blueprints
    app.register_blueprint(compression_bp, url_prefix='/api')
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'pdf-compression-server'}
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=False)
