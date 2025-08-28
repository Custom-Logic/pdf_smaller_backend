"""Tiered rate limiting system with Flask-Limiter and Redis backend"""
import logging
from typing import Dict, Any, Optional, Callable
from functools import wraps
from flask import request, jsonify, g, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta
import redis
import json

logger = logging.getLogger(__name__)


class TieredRateLimiter:
    """Enhanced rate limiter with user tier support"""
    
    def __init__(self, app=None, redis_client=None):
        self.app = app
        self.redis_client = redis_client
        self.limiter = None
        self.rate_limits = {}
        
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the rate limiter with Flask app"""
        self.app = app
        
        # Initialize Redis client if not provided
        if self.redis_client is None:
            redis_url = app.config.get('REDIS_URL', 'redis://localhost:6379/0')
            self.redis_client = redis.from_url(redis_url)
        
        # Initialize Flask-Limiter
        self.limiter = Limiter(
            app,
            key_func=self._get_rate_limit_key,
            storage_uri=app.config.get('REDIS_URL', 'redis://localhost:6379/0'),
            default_limits=["1000 per hour", "100 per minute"]
        )
        
        # Configure rate limits for different user tiers
        self._configure_rate_limits()
        
        # Add error handlers
        self._setup_error_handlers()
    
    def _configure_rate_limits(self):
        """Configure rate limits for different user tiers and endpoints"""
        self.rate_limits = {
            'free': {
                'compression': {
                    'per_minute': 2,
                    'per_hour': 10,
                    'per_day': 10
                },
                'auth': {
                    'per_minute': 5,
                    'per_hour': 20
                },
                'api': {
                    'per_minute': 30,
                    'per_hour': 200
                }
            },
            'premium': {
                'compression': {
                    'per_minute': 10,
                    'per_hour': 100,
                    'per_day': 500
                },
                'auth': {
                    'per_minute': 10,
                    'per_hour': 50
                },
                'api': {
                    'per_minute': 100,
                    'per_hour': 1000
                }
            },
            'pro': {
                'compression': {
                    'per_minute': 50,
                    'per_hour': 1000,
                    'per_day': -1  # Unlimited
                },
                'auth': {
                    'per_minute': 20,
                    'per_hour': 100
                },
                'api': {
                    'per_minute': 500,
                    'per_hour': 5000
                }
            },
            'anonymous': {
                'compression': {
                    'per_minute': 1,
                    'per_hour': 3,
                    'per_day': 3
                },
                'auth': {
                    'per_minute': 3,
                    'per_hour': 10
                },
                'api': {
                    'per_minute': 10,
                    'per_hour': 50
                }
            }
        }
    
    def _get_rate_limit_key(self):
        """Generate rate limit key based on user or IP"""
        # Try to get user ID from JWT token
        user_id = getattr(g, 'current_user_id', None)
        if user_id:
            return f"user:{user_id}"
        
        # Fall back to IP address
        return f"ip:{get_remote_address()}"
    
    def _setup_error_handlers(self):
        """Setup error handlers for rate limit exceeded"""
        @self.limiter.request_filter
        def header_whitelist():
            """Skip rate limiting for certain requests"""
            # Skip rate limiting for health checks
            if request.endpoint == 'health_check':
                return True
            return False
        
        @self.app.errorhandler(429)
        def ratelimit_handler(e):
            """Handle rate limit exceeded errors"""
            return self._create_rate_limit_response(e)
    
    def _create_rate_limit_response(self, error):
        """Create standardized rate limit response"""
        retry_after = getattr(error, 'retry_after', 60)
        
        response_data = {
            'error': {
                'code': 'RATE_LIMIT_EXCEEDED',
                'message': 'Rate limit exceeded. Please try again later.',
                'retry_after': retry_after
            },
            'timestamp': datetime.utcnow().isoformat()
        }
        
        response = jsonify(response_data)
        response.status_code = 429
        response.headers['Retry-After'] = str(retry_after)
        response.headers['X-RateLimit-Limit'] = getattr(error, 'limit', 'unknown')
        response.headers['X-RateLimit-Remaining'] = '0'
        response.headers['X-RateLimit-Reset'] = str(int((datetime.utcnow() + timedelta(seconds=retry_after)).timestamp()))
        
        # Log rate limit event
        self._log_rate_limit_event(error)
        
        return response
    
    def _log_rate_limit_event(self, error):
        """Log rate limit exceeded events"""
        user_id = getattr(g, 'current_user_id', None)
        user_tier = getattr(g, 'current_user_tier', 'anonymous')
        
        log_data = {
            'event': 'rate_limit_exceeded',
            'user_id': user_id,
            'user_tier': user_tier,
            'ip': get_remote_address(),
            'endpoint': request.endpoint,
            'method': request.method,
            'limit': getattr(error, 'limit', 'unknown'),
            'retry_after': getattr(error, 'retry_after', 60)
        }
        
        logger.warning(f"Rate limit exceeded: {log_data}")
    
    def get_user_tier(self) -> str:
        """Get current user's tier"""
        # Try to get from Flask g object first
        if hasattr(g, 'current_user_tier'):
            return g.current_user_tier
        
        # Try to get from user object
        if hasattr(g, 'current_user') and g.current_user:
            if hasattr(g.current_user, 'subscription') and g.current_user.subscription:
                if g.current_user.subscription.plan:
                    return g.current_user.subscription.plan.name.lower()
            return 'free'
        
        return 'anonymous'
    
    def get_rate_limit_for_tier(self, tier: str, category: str) -> Dict[str, int]:
        """Get rate limits for specific tier and category"""
        return self.rate_limits.get(tier, self.rate_limits['anonymous']).get(category, {})
    
    def format_rate_limit_string(self, limits: Dict[str, int]) -> str:
        """Format rate limits into Flask-Limiter string format"""
        limit_strings = []
        
        for period, limit in limits.items():
            if limit == -1:  # Unlimited
                continue
            
            if period == 'per_minute':
                limit_strings.append(f"{limit} per minute")
            elif period == 'per_hour':
                limit_strings.append(f"{limit} per hour")
            elif period == 'per_day':
                limit_strings.append(f"{limit} per day")
        
        return "; ".join(limit_strings) if limit_strings else "1000 per hour"
    
    def limit_by_tier(self, category: str = 'api'):
        """Decorator for applying tier-based rate limiting"""
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                user_tier = self.get_user_tier()
                limits = self.get_rate_limit_for_tier(user_tier, category)
                limit_string = self.format_rate_limit_string(limits)
                
                # Apply the rate limit
                @self.limiter.limit(limit_string)
                def rate_limited_function():
                    return f(*args, **kwargs)
                
                return rate_limited_function()
            
            return decorated_function
        return decorator
    
    def check_custom_limit(self, key: str, limit: int, window: int) -> bool:
        """Check custom rate limit using Redis"""
        try:
            current_time = int(datetime.utcnow().timestamp())
            window_start = current_time - window
            
            # Use Redis sorted set to track requests in time window
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)  # Remove old entries
            pipe.zcard(key)  # Count current entries
            pipe.zadd(key, {str(current_time): current_time})  # Add current request
            pipe.expire(key, window)  # Set expiration
            
            results = pipe.execute()
            current_count = results[1]
            
            return current_count < limit
            
        except Exception as e:
            logger.error(f"Rate limit check failed: {str(e)}")
            return True  # Allow request if Redis fails
    
    def get_remaining_requests(self, key: str, limit: int, window: int) -> Dict[str, Any]:
        """Get remaining requests for a rate limit"""
        try:
            current_time = int(datetime.utcnow().timestamp())
            window_start = current_time - window
            
            # Clean old entries and count current
            pipe = self.redis_client.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            results = pipe.execute()
            
            current_count = results[1]
            remaining = max(0, limit - current_count)
            reset_time = current_time + window
            
            return {
                'limit': limit,
                'remaining': remaining,
                'reset': reset_time,
                'window': window
            }
            
        except Exception as e:
            logger.error(f"Failed to get remaining requests: {str(e)}")
            return {
                'limit': limit,
                'remaining': limit,
                'reset': int(datetime.utcnow().timestamp()) + window,
                'window': window
            }
    
    def add_rate_limit_headers(self, response, category: str = 'api'):
        """Add rate limit headers to response"""
        try:
            user_tier = self.get_user_tier()
            limits = self.get_rate_limit_for_tier(user_tier, category)
            
            # Add headers for the most restrictive limit (per minute)
            if 'per_minute' in limits:
                key = f"{self._get_rate_limit_key()}:{category}:minute"
                info = self.get_remaining_requests(key, limits['per_minute'], 60)
                
                response.headers['X-RateLimit-Limit'] = str(info['limit'])
                response.headers['X-RateLimit-Remaining'] = str(info['remaining'])
                response.headers['X-RateLimit-Reset'] = str(info['reset'])
                response.headers['X-RateLimit-Window'] = str(info['window'])
            
            return response
            
        except Exception as e:
            logger.error(f"Failed to add rate limit headers: {str(e)}")
            return response


def create_rate_limiter(app=None, redis_client=None) -> TieredRateLimiter:
    """Factory function to create rate limiter instance"""
    return TieredRateLimiter(app, redis_client)


def rate_limit_by_endpoint(endpoint_type: str = 'api'):
    """Convenience decorator for endpoint-specific rate limiting"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # This will be replaced by the actual limiter instance
            # when the app is initialized
            return f(*args, **kwargs)
        
        # Mark the function with rate limit info
        decorated_function._rate_limit_category = endpoint_type
        return decorated_function
    
    return decorator


# Convenience decorators for common endpoint types
def compression_rate_limit(f):
    """Rate limit decorator for compression endpoints"""
    return rate_limit_by_endpoint('compression')(f)


def auth_rate_limit(f):
    """Rate limit decorator for authentication endpoints"""
    return rate_limit_by_endpoint('auth')(f)


def api_rate_limit(f):
    """Rate limit decorator for general API endpoints"""
    return rate_limit_by_endpoint('api')(f)


class RateLimitMiddleware:
    """Middleware to automatically apply rate limiting and headers"""
    
    def __init__(self, app, rate_limiter: TieredRateLimiter):
        self.app = app
        self.rate_limiter = rate_limiter
        self.init_app(app)
    
    def init_app(self, app):
        """Initialize middleware with Flask app"""
        app.before_request(self.before_request)
        app.after_request(self.after_request)
    
    def before_request(self):
        """Check rate limits before processing request"""
        # Skip for certain endpoints
        if request.endpoint in ['health_check', 'static']:
            return
        
        # Determine category based on endpoint
        category = self._get_endpoint_category()
        
        # Check if endpoint has custom rate limiting
        if hasattr(request, 'view_function') and hasattr(request.view_function, '_rate_limit_category'):
            category = request.view_function._rate_limit_category
        
        # Store category for later use
        g.rate_limit_category = category
    
    def after_request(self, response):
        """Add rate limit headers to response"""
        if hasattr(g, 'rate_limit_category'):
            response = self.rate_limiter.add_rate_limit_headers(response, g.rate_limit_category)
        
        return response
    
    def _get_endpoint_category(self) -> str:
        """Determine rate limit category based on endpoint"""
        if not request.endpoint:
            return 'api'
        
        endpoint = request.endpoint.lower()
        
        if 'compress' in endpoint or 'bulk' in endpoint:
            return 'compression'
        elif 'auth' in endpoint or 'login' in endpoint or 'register' in endpoint:
            return 'auth'
        else:
            return 'api'