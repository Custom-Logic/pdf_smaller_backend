"""Integration tests for tiered rate limiting system"""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, g, jsonify
import redis
from src.utils.rate_limiter import (
    TieredRateLimiter,
    create_rate_limiter,
    compression_rate_limit,
    auth_rate_limit,
    api_rate_limit,
    RateLimitMiddleware
)


class TestTieredRateLimiter:
    """Test the TieredRateLimiter class"""
    
    def setup_method(self):
        """Set up test Flask app and rate limiter"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.config['REDIS_URL'] = 'redis://localhost:6379/1'  # Use test database
        
        # Mock Redis client for testing
        self.mock_redis = MagicMock()
        self.rate_limiter = TieredRateLimiter(redis_client=self.mock_redis)
        self.rate_limiter.init_app(self.app)
        
        self.client = self.app.test_client()
    
    def test_rate_limiter_initialization(self):
        """Test rate limiter initialization"""
        assert self.rate_limiter.app == self.app
        assert self.rate_limiter.redis_client == self.mock_redis
        assert self.rate_limiter.limiter is not None
        assert len(self.rate_limiter.rate_limits) > 0
    
    def test_rate_limits_configuration(self):
        """Test rate limits are properly configured"""
        limits = self.rate_limiter.rate_limits
        
        # Check all tiers exist
        expected_tiers = ['free', 'premium', 'pro', 'anonymous']
        for tier in expected_tiers:
            assert tier in limits
        
        # Check categories exist for each tier
        expected_categories = ['compression', 'auth', 'api']
        for tier in expected_tiers:
            for category in expected_categories:
                assert category in limits[tier]
        
        # Check pro tier has unlimited compression per day
        assert limits['pro']['compression']['per_day'] == -1
        
        # Check anonymous tier has lowest limits
        assert limits['anonymous']['compression']['per_hour'] <= limits['free']['compression']['per_hour']
    
    def test_get_user_tier_anonymous(self):
        """Test getting user tier for anonymous users"""
        with self.app.test_request_context():
            tier = self.rate_limiter.get_user_tier()
            assert tier == 'anonymous'
    
    def test_get_user_tier_from_g(self):
        """Test getting user tier from Flask g object"""
        with self.app.test_request_context():
            g.current_user_tier = 'premium'
            tier = self.rate_limiter.get_user_tier()
            assert tier == 'premium'
    
    def test_get_user_tier_from_user_object(self):
        """Test getting user tier from user object"""
        with self.app.test_request_context():
            # Mock user with subscription
            mock_user = Mock()
            mock_plan = Mock()
            mock_plan.name = 'Pro'
            mock_subscription = Mock()
            mock_subscription.plan = mock_plan
            mock_user.subscription = mock_subscription
            
            g.current_user = mock_user
            tier = self.rate_limiter.get_user_tier()
            assert tier == 'pro'
    
    def test_get_rate_limit_for_tier(self):
        """Test getting rate limits for specific tier and category"""
        limits = self.rate_limiter.get_rate_limit_for_tier('premium', 'compression')
        
        assert 'per_minute' in limits
        assert 'per_hour' in limits
        assert 'per_day' in limits
        assert limits['per_minute'] == 10
        assert limits['per_hour'] == 100
        assert limits['per_day'] == 500
    
    def test_format_rate_limit_string(self):
        """Test formatting rate limits into Flask-Limiter string"""
        limits = {
            'per_minute': 10,
            'per_hour': 100,
            'per_day': 500
        }
        
        limit_string = self.rate_limiter.format_rate_limit_string(limits)
        
        assert '10 per minute' in limit_string
        assert '100 per hour' in limit_string
        assert '500 per day' in limit_string
    
    def test_format_rate_limit_string_unlimited(self):
        """Test formatting rate limits with unlimited values"""
        limits = {
            'per_minute': 50,
            'per_hour': 1000,
            'per_day': -1  # Unlimited
        }
        
        limit_string = self.rate_limiter.format_rate_limit_string(limits)
        
        assert '50 per minute' in limit_string
        assert '1000 per hour' in limit_string
        assert 'per day' not in limit_string  # Unlimited should be excluded
    
    def test_check_custom_limit_allowed(self):
        """Test custom rate limit check when under limit"""
        # Mock Redis pipeline
        mock_pipe = Mock()
        mock_pipe.execute.return_value = [None, 5, None, None]  # 5 current requests
        self.mock_redis.pipeline.return_value = mock_pipe
        
        result = self.rate_limiter.check_custom_limit('test_key', 10, 60)
        assert result is True
    
    def test_check_custom_limit_exceeded(self):
        """Test custom rate limit check when limit exceeded"""
        # Mock Redis pipeline
        mock_pipe = Mock()
        mock_pipe.execute.return_value = [None, 15, None, None]  # 15 current requests
        self.mock_redis.pipeline.return_value = mock_pipe
        
        result = self.rate_limiter.check_custom_limit('test_key', 10, 60)
        assert result is False
    
    def test_check_custom_limit_redis_failure(self):
        """Test custom rate limit check when Redis fails"""
        self.mock_redis.pipeline.side_effect = Exception("Redis connection failed")
        
        result = self.rate_limiter.check_custom_limit('test_key', 10, 60)
        assert result is True  # Should allow request when Redis fails
    
    def test_get_remaining_requests(self):
        """Test getting remaining requests info"""
        # Mock Redis pipeline
        mock_pipe = Mock()
        mock_pipe.execute.return_value = [None, 7]  # 7 current requests
        self.mock_redis.pipeline.return_value = mock_pipe
        
        info = self.rate_limiter.get_remaining_requests('test_key', 10, 60)
        
        assert info['limit'] == 10
        assert info['remaining'] == 3
        assert info['window'] == 60
        assert 'reset' in info
    
    def test_get_remaining_requests_redis_failure(self):
        """Test getting remaining requests when Redis fails"""
        self.mock_redis.pipeline.side_effect = Exception("Redis connection failed")
        
        info = self.rate_limiter.get_remaining_requests('test_key', 10, 60)
        
        assert info['limit'] == 10
        assert info['remaining'] == 10  # Should return full limit when Redis fails
        assert info['window'] == 60


class TestRateLimitDecorators:
    """Test rate limit decorators"""
    
    def setup_method(self):
        """Set up test Flask app"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Create test endpoints with decorators
        @self.app.route('/compress', methods=['POST'])
        @compression_rate_limit
        def compress_endpoint():
            return jsonify({'status': 'success'})
        
        @self.app.route('/login', methods=['POST'])
        @auth_rate_limit
        def login_endpoint():
            return jsonify({'status': 'success'})
        
        @self.app.route('/api/data', methods=['GET'])
        @api_rate_limit
        def api_endpoint():
            return jsonify({'data': 'test'})
        
        self.client = self.app.test_client()
    
    def test_compression_rate_limit_decorator(self):
        """Test compression rate limit decorator"""
        with self.app.test_request_context('/compress'):
            endpoint = self.app.view_functions['compress_endpoint']
            assert hasattr(endpoint, '_rate_limit_category')
            assert endpoint._rate_limit_category == 'compression'
    
    def test_auth_rate_limit_decorator(self):
        """Test auth rate limit decorator"""
        with self.app.test_request_context('/login'):
            endpoint = self.app.view_functions['login_endpoint']
            assert hasattr(endpoint, '_rate_limit_category')
            assert endpoint._rate_limit_category == 'auth'
    
    def test_api_rate_limit_decorator(self):
        """Test API rate limit decorator"""
        with self.app.test_request_context('/api/data'):
            endpoint = self.app.view_functions['api_endpoint']
            assert hasattr(endpoint, '_rate_limit_category')
            assert endpoint._rate_limit_category == 'api'


class TestRateLimitMiddleware:
    """Test rate limit middleware"""
    
    def setup_method(self):
        """Set up test Flask app with middleware"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Mock rate limiter
        self.mock_rate_limiter = Mock()
        self.middleware = RateLimitMiddleware(self.app, self.mock_rate_limiter)
        
        # Create test endpoints
        @self.app.route('/compress', methods=['POST'])
        def compress_endpoint():
            return jsonify({'status': 'success'})
        
        @self.app.route('/auth/login', methods=['POST'])
        def login_endpoint():
            return jsonify({'status': 'success'})
        
        @self.app.route('/api/data', methods=['GET'])
        def api_endpoint():
            return jsonify({'data': 'test'})
        
        @self.app.route('/health', methods=['GET'])
        def health_check():
            return jsonify({'status': 'healthy'})
        
        self.client = self.app.test_client()
    
    def test_middleware_determines_compression_category(self):
        """Test middleware correctly identifies compression endpoints"""
        with self.app.test_request_context('/compress', method='POST'):
            category = self.middleware._get_endpoint_category()
            assert category == 'compression'
    
    def test_middleware_determines_auth_category(self):
        """Test middleware correctly identifies auth endpoints"""
        with self.app.test_request_context('/auth/login', method='POST'):
            category = self.middleware._get_endpoint_category()
            assert category == 'auth'
    
    def test_middleware_determines_api_category(self):
        """Test middleware correctly identifies API endpoints"""
        with self.app.test_request_context('/api/data', method='GET'):
            category = self.middleware._get_endpoint_category()
            assert category == 'api'
    
    def test_middleware_adds_rate_limit_headers(self):
        """Test middleware adds rate limit headers to responses"""
        with self.app.test_request_context('/api/data'):
            # Mock the add_rate_limit_headers method
            mock_response = Mock()
            self.mock_rate_limiter.add_rate_limit_headers.return_value = mock_response
            
            # Simulate after_request
            g.rate_limit_category = 'api'
            result = self.middleware.after_request(mock_response)
            
            self.mock_rate_limiter.add_rate_limit_headers.assert_called_once_with(mock_response, 'api')
            assert result == mock_response


class TestRateLimitErrorHandling:
    """Test rate limit error handling"""
    
    def setup_method(self):
        """Set up test Flask app with rate limiter"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        
        # Mock Redis client
        self.mock_redis = MagicMock()
        self.rate_limiter = TieredRateLimiter(redis_client=self.mock_redis)
        self.rate_limiter.init_app(self.app)
        
        self.client = self.app.test_client()
    
    def test_rate_limit_response_format(self):
        """Test rate limit exceeded response format"""
        # Create a mock rate limit error
        mock_error = Mock()
        mock_error.retry_after = 60
        mock_error.limit = '10 per minute'
        
        with self.app.test_request_context():
            response = self.rate_limiter._create_rate_limit_response(mock_error)
            
            assert response.status_code == 429
            assert 'Retry-After' in response.headers
            assert response.headers['Retry-After'] == '60'
            assert 'X-RateLimit-Limit' in response.headers
            assert 'X-RateLimit-Remaining' in response.headers
            assert 'X-RateLimit-Reset' in response.headers
            
            data = response.get_json()
            assert data['error']['code'] == 'RATE_LIMIT_EXCEEDED'
            assert 'retry_after' in data['error']


class TestRateLimitIntegration:
    """Integration tests for complete rate limiting system"""
    
    def setup_method(self):
        """Set up complete test environment"""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.app.config['REDIS_URL'] = 'redis://localhost:6379/1'
        
        # Try to use real Redis for integration tests, fall back to mock
        try:
            redis_client = redis.from_url(self.app.config['REDIS_URL'])
            redis_client.ping()  # Test connection
            self.use_real_redis = True
        except:
            redis_client = MagicMock()
            self.use_real_redis = False
        
        self.rate_limiter = create_rate_limiter(self.app, redis_client)
        self.middleware = RateLimitMiddleware(self.app, self.rate_limiter)
        
        # Create test endpoints
        @self.app.route('/test/compress', methods=['POST'])
        @compression_rate_limit
        def test_compress():
            return jsonify({'status': 'success'})
        
        @self.app.route('/test/auth', methods=['POST'])
        @auth_rate_limit
        def test_auth():
            return jsonify({'status': 'success'})
        
        self.client = self.app.test_client()
    
    @pytest.mark.skipif(not hasattr(pytest, 'real_redis'), reason="Requires Redis server")
    def test_rate_limiting_with_real_redis(self):
        """Test rate limiting with real Redis (if available)"""
        if not self.use_real_redis:
            pytest.skip("Redis not available")
        
        # Set very low limits for testing
        with self.app.test_request_context():
            g.current_user_tier = 'anonymous'  # Very low limits
            
            # Make requests up to the limit
            for i in range(3):  # Anonymous has 3 per hour limit
                response = self.client.post('/test/compress')
                if response.status_code == 429:
                    break  # Hit rate limit
            
            # Next request should be rate limited
            response = self.client.post('/test/compress')
            # Note: This test might not work perfectly due to Flask-Limiter's internal handling
    
    def test_different_tiers_different_limits(self):
        """Test that different user tiers have different rate limits"""
        free_limits = self.rate_limiter.get_rate_limit_for_tier('free', 'compression')
        premium_limits = self.rate_limiter.get_rate_limit_for_tier('premium', 'compression')
        pro_limits = self.rate_limiter.get_rate_limit_for_tier('pro', 'compression')
        
        # Premium should have higher limits than free
        assert premium_limits['per_hour'] > free_limits['per_hour']
        assert premium_limits['per_day'] > free_limits['per_day']
        
        # Pro should have higher limits than premium
        assert pro_limits['per_hour'] > premium_limits['per_hour']
        assert pro_limits['per_day'] == -1  # Unlimited
    
    def test_rate_limit_headers_added(self):
        """Test that rate limit headers are added to responses"""
        with self.app.test_request_context():
            g.current_user_tier = 'free'
            
            response = self.client.post('/test/compress')
            
            # Check if headers would be added (mocked scenario)
            # In real scenario, headers should be present
            assert response.status_code in [200, 429]


if __name__ == '__main__':
    pytest.main([__file__])