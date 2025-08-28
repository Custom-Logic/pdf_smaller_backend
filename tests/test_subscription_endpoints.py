"""Integration tests for subscription API endpoints"""
import pytest
import json
from unittest.mock import patch, Mock
from decimal import Decimal
from src.models import User, Subscription, Plan
from src.models.base import db
from src.services.subscription_service import SubscriptionService


class TestSubscriptionEndpoints:
    """Test cases for subscription API endpoints"""
    
    def test_get_subscription_info_success(self, client, app, auth_headers, test_user, test_plan):
        """Test getting subscription info when user has subscription"""
        with app.app_context():
            # Create subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            db.session.add(subscription)
            db.session.commit()
            
            response = client.get('/api/subscriptions', headers=auth_headers)
            
            # Debug the response
            print(f"Status: {response.status_code}")
            print(f"Data: {response.data}")
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'subscription' in data
            assert 'usage' in data
            assert 'status' in data
            assert 'permissions' in data
            assert data['subscription']['user_id'] == test_user.id
    
    def test_get_subscription_info_no_subscription(self, client, app, auth_headers, test_user):
        """Test getting subscription info when user has no subscription"""
        with app.app_context():
            response = client.get('/api/subscriptions', headers=auth_headers)
            
            assert response.status_code == 404
            data = json.loads(response.data)
            assert data['error'] == 'No subscription found'
            assert data['subscription'] is None
            assert 'usage' in data
    
    def test_get_subscription_info_unauthorized(self, client, app):
        """Test getting subscription info without authentication"""
        with app.app_context():
            response = client.get('/api/subscriptions')
            
            assert response.status_code == 401
    
    def test_get_available_plans(self, client, app):
        """Test getting available subscription plans"""
        with app.app_context():
            response = client.get('/api/subscriptions/plans')
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'plans' in data
            assert len(data['plans']) >= 3  # Should have at least free, premium, pro
            
            # Check plan structure
            for plan in data['plans']:
                assert 'id' in plan
                assert 'name' in plan
                assert 'display_name' in plan
                assert 'price_monthly' in plan
                assert 'daily_compression_limit' in plan
    
    @patch('src.services.stripe_service.StripeService.create_subscription')
    def test_create_subscription_success(self, mock_stripe_create, client, app, auth_headers, test_user, test_plan):
        """Test successful subscription creation"""
        with app.app_context():
            # Mock Stripe response
            mock_stripe_create.return_value = {
                'success': True,
                'subscription_id': 'sub_test123',
                'client_secret': 'pi_test_client_secret',
                'subscription': {
                    'id': 1,
                    'user_id': test_user.id,
                    'plan_id': test_plan.id,
                    'status': 'active'
                }
            }
            
            data = {
                'plan_id': test_plan.id,
                'payment_method_id': 'pm_test123',
                'billing_cycle': 'monthly'
            }
            
            response = client.post('/api/subscriptions/create', 
                                 data=json.dumps(data),
                                 content_type='application/json',
                                 headers=auth_headers)
            
            assert response.status_code == 201
            response_data = json.loads(response.data)
            assert response_data['message'] == 'Subscription created successfully'
            assert 'subscription' in response_data
            assert 'client_secret' in response_data
            assert 'subscription_id' in response_data
    
    def test_create_subscription_missing_fields(self, client, app, auth_headers):
        """Test subscription creation with missing required fields"""
        with app.app_context():
            data = {
                'plan_id': 1
                # Missing payment_method_id
            }
            
            response = client.post('/api/subscriptions/create',
                                 data=json.dumps(data),
                                 content_type='application/json',
                                 headers=auth_headers)
            
            assert response.status_code == 400
            response_data = json.loads(response.data)
            assert 'Missing required fields' in response_data['error']
    
    def test_create_subscription_invalid_plan(self, client, app, auth_headers):
        """Test subscription creation with invalid plan ID"""
        with app.app_context():
            data = {
                'plan_id': 99999,
                'payment_method_id': 'pm_test123'
            }
            
            response = client.post('/api/subscriptions/create',
                                 data=json.dumps(data),
                                 content_type='application/json',
                                 headers=auth_headers)
            
            assert response.status_code == 400
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Invalid plan ID'
    
    def test_create_subscription_duplicate(self, client, app, auth_headers, test_user, test_plan):
        """Test subscription creation when user already has subscription"""
        with app.app_context():
            # Create existing subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            db.session.add(subscription)
            db.session.commit()
            
            data = {
                'plan_id': test_plan.id,
                'payment_method_id': 'pm_test123'
            }
            
            response = client.post('/api/subscriptions/create',
                                 data=json.dumps(data),
                                 content_type='application/json',
                                 headers=auth_headers)
            
            assert response.status_code == 409
            response_data = json.loads(response.data)
            assert response_data['error'] == 'User already has an active subscription'
    
    def test_create_subscription_invalid_billing_cycle(self, client, app, auth_headers, test_plan):
        """Test subscription creation with invalid billing cycle"""
        with app.app_context():
            data = {
                'plan_id': test_plan.id,
                'payment_method_id': 'pm_test123',
                'billing_cycle': 'invalid'
            }
            
            response = client.post('/api/subscriptions/create',
                                 data=json.dumps(data),
                                 content_type='application/json',
                                 headers=auth_headers)
            
            assert response.status_code == 400
            response_data = json.loads(response.data)
            assert 'Invalid billing cycle' in response_data['error']
    
    @patch('src.services.stripe_service.StripeService.cancel_subscription')
    def test_cancel_subscription_success(self, mock_stripe_cancel, client, app, auth_headers, test_user, test_plan):
        """Test successful subscription cancellation"""
        with app.app_context():
            # Create subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            db.session.add(subscription)
            db.session.commit()
            
            # Mock Stripe response
            mock_stripe_cancel.return_value = {
                'success': True,
                'canceled_at': 1234567890,
                'current_period_end': 1234567890
            }
            
            response = client.post('/api/subscriptions/cancel', headers=auth_headers)
            
            assert response.status_code == 200
            response_data = json.loads(response.data)
            assert response_data['message'] == 'Subscription canceled successfully'
            assert 'canceled_at' in response_data
    
    def test_cancel_subscription_no_subscription(self, client, app, auth_headers):
        """Test cancellation when user has no subscription"""
        with app.app_context():
            response = client.post('/api/subscriptions/cancel', headers=auth_headers)
            
            assert response.status_code == 404
            response_data = json.loads(response.data)
            assert response_data['error'] == 'No active subscription found'
    
    @patch('src.services.stripe_service.StripeService.update_subscription_plan')
    def test_update_subscription_plan_success(self, mock_stripe_update, client, app, auth_headers, test_user, test_plan):
        """Test successful subscription plan update"""
        with app.app_context():
            # Create subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            db.session.add(subscription)
            db.session.commit()
            
            # Create new plan
            new_plan = Plan(
                name='new_test_plan',
                display_name='New Test Plan',
                price_monthly=Decimal('19.99'),
                daily_compression_limit=200,
                max_file_size_mb=50
            )
            db.session.add(new_plan)
            db.session.commit()
            
            # Mock Stripe response
            mock_stripe_update.return_value = {
                'success': True,
                'subscription': {
                    'id': subscription.id,
                    'plan_id': new_plan.id
                }
            }
            
            data = {'new_plan_id': new_plan.id}
            
            response = client.post('/api/subscriptions/update-plan',
                                 data=json.dumps(data),
                                 content_type='application/json',
                                 headers=auth_headers)
            
            assert response.status_code == 200
            response_data = json.loads(response.data)
            assert response_data['message'] == 'Subscription plan updated successfully'
            assert 'subscription' in response_data
    
    def test_update_subscription_plan_same_plan(self, client, app, auth_headers, test_user, test_plan):
        """Test updating to the same plan"""
        with app.app_context():
            # Create subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            db.session.add(subscription)
            db.session.commit()
            
            data = {'new_plan_id': test_plan.id}
            
            response = client.post('/api/subscriptions/update-plan',
                                 data=json.dumps(data),
                                 content_type='application/json',
                                 headers=auth_headers)
            
            assert response.status_code == 400
            response_data = json.loads(response.data)
            assert response_data['error'] == 'User is already on this plan'
    
    def test_get_usage_statistics(self, client, app, auth_headers, test_user, test_plan):
        """Test getting usage statistics"""
        with app.app_context():
            # Create subscription with some usage
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            subscription.daily_usage_count = 25
            db.session.add(subscription)
            db.session.commit()
            
            response = client.get('/api/subscriptions/usage', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'usage' in data
            assert 'permissions' in data
            assert data['usage']['daily_usage'] == 25
            assert data['usage']['plan_name'] == test_plan.name
    
    def test_check_permissions(self, client, app, auth_headers, test_user, test_plan):
        """Test checking user permissions"""
        with app.app_context():
            # Create subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            db.session.add(subscription)
            db.session.commit()
            
            response = client.get('/api/subscriptions/permissions', headers=auth_headers)
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert 'compression' in data
            assert 'bulk_processing' in data
            assert 'api_access' in data
            assert 'max_file_size_mb' in data
            assert data['max_file_size_mb'] == test_plan.max_file_size_mb
    
    def test_reactivate_subscription_success(self, client, app, auth_headers, test_user, test_plan):
        """Test successful subscription reactivation"""
        with app.app_context():
            # Create canceled subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            subscription.status = 'canceled'
            db.session.add(subscription)
            db.session.commit()
            
            response = client.post('/api/subscriptions/reactivate', headers=auth_headers)
            
            assert response.status_code == 200
            response_data = json.loads(response.data)
            assert response_data['message'] == 'Subscription reactivated successfully'
            
            # Verify subscription is reactivated
            updated_subscription = Subscription.query.filter_by(user_id=test_user.id).first()
            assert updated_subscription.status == 'active'
    
    def test_reactivate_subscription_already_active(self, client, app, auth_headers, test_user, test_plan):
        """Test reactivating already active subscription"""
        with app.app_context():
            # Create active subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            db.session.add(subscription)
            db.session.commit()
            
            response = client.post('/api/subscriptions/reactivate', headers=auth_headers)
            
            assert response.status_code == 400
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Subscription is already active'
    
    @patch('src.services.stripe_service.StripeService.handle_webhook')
    def test_stripe_webhook_success(self, mock_handle_webhook, client, app):
        """Test successful Stripe webhook processing"""
        with app.app_context():
            mock_handle_webhook.return_value = {
                'success': True,
                'message': 'Webhook processed successfully'
            }
            
            headers = {'Stripe-Signature': 'test_signature'}
            payload = b'test_payload'
            
            response = client.post('/api/subscriptions/webhook',
                                 data=payload,
                                 headers=headers)
            
            assert response.status_code == 200
            response_data = json.loads(response.data)
            assert 'Webhook processed successfully' in response_data['message']
    
    def test_stripe_webhook_missing_signature(self, client, app):
        """Test Stripe webhook without signature"""
        with app.app_context():
            payload = b'test_payload'
            
            response = client.post('/api/subscriptions/webhook', data=payload)
            
            assert response.status_code == 400
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Missing signature'
    
    @patch('src.services.stripe_service.StripeService.handle_webhook')
    def test_stripe_webhook_processing_error(self, mock_handle_webhook, client, app):
        """Test Stripe webhook processing error"""
        with app.app_context():
            mock_handle_webhook.return_value = {
                'success': False,
                'error': 'Invalid signature'
            }
            
            headers = {'Stripe-Signature': 'invalid_signature'}
            payload = b'test_payload'
            
            response = client.post('/api/subscriptions/webhook',
                                 data=payload,
                                 headers=headers)
            
            assert response.status_code == 400
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Invalid signature'


class TestSubscriptionEndpointsValidation:
    """Test validation and error handling for subscription endpoints"""
    
    def test_create_subscription_invalid_json(self, client, app, auth_headers):
        """Test subscription creation with invalid JSON"""
        with app.app_context():
            response = client.post('/api/subscriptions/create',
                                 data='invalid json',
                                 content_type='application/json',
                                 headers=auth_headers)
            
            assert response.status_code == 400
            response_data = json.loads(response.data)
            assert response_data['error'] == 'Invalid JSON data'
    
    def test_update_plan_missing_json(self, client, app, auth_headers):
        """Test plan update without JSON data"""
        with app.app_context():
            response = client.post('/api/subscriptions/update-plan',
                                 headers=auth_headers)
            
            assert response.status_code == 400
    
    def test_endpoints_require_authentication(self, client, app):
        """Test that protected endpoints require authentication"""
        with app.app_context():
            protected_endpoints = [
                ('/api/subscriptions', 'GET'),
                ('/api/subscriptions/create', 'POST'),
                ('/api/subscriptions/cancel', 'POST'),
                ('/api/subscriptions/update-plan', 'POST'),
                ('/api/subscriptions/usage', 'GET'),
                ('/api/subscriptions/permissions', 'GET'),
                ('/api/subscriptions/reactivate', 'POST')
            ]
            
            for endpoint, method in protected_endpoints:
                if method == 'GET':
                    response = client.get(endpoint)
                else:
                    response = client.post(endpoint)
                
                assert response.status_code == 401