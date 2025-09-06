from .auth_routes import auth_bp
from .compression_routes import compression_bp
from .subscription_routes import subscription_bp
from .admin_routes import admin_bp
from .extended_features_routes import extended_features_bp

__all__ = ['auth_bp', 'compression_bp', 'subscription_bp', 'admin_bp', 'extended_features_bp']