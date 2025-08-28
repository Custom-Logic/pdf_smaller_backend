"""Integration tests for Stripe service"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
import stripe
from src.services.stripe_service import StripeService
from src.models import User, Subscription, Plan
from src.models.base import db


class TestStripeService:
    """Test cases for StripeService"""
    
    @patch('src.services.stripe_service.stripe')
    def test_create_customer_success(self, mock_stripe, app, test_user):
        """Test successful Stripe customer creation"""
        with app.app_context():
            # Mock Stripe customer creation
            mock_customer = Mock()
            mock_customer.id = 'cus_test123'
            mock_stripe.Customer.create.return_value = mock_customer
            
            # Mock config
            app.config['STRIPE_SECRET_KEY'] = 'sk_test_123'
            
            customer_id = StripeService.create_customer(test_user)
            
            assert customer_id == 'cus_test123'
            mock_stripe.Customer.create.assert_called_once_with(
                email=test_user.email,
                name=test_user.name,
                metadata={'user_id': str(test_user.id)}
            )
    
    @patch('src.services.stripe_service.stripe')
    def test_create_customer_stripe_error(self, mock_stripe, app, test_user):
        """Test Stripe customer creation with Stripe error"""
        with app.app_context():
            # Create a proper Stripe error class
            class MockStripeError(Exception):
                pass
            
            mock_stripe.error.StripeError = MockStripeError
            mock_stripe.Customer.create.side_effect = MockStripeError("Test error")
            app.config['STRIPE_SECRET_KEY'] = 'sk_test_123'
            
            customer_id = StripeService.create_customer(test_user)
            
            assert customer_id is None
    
    @patch('src.services.stripe_service.stripe')
    def test_get_or_create_customer_existing(self, mock_stripe, app, test_user, test_plan):
        """Test getting existing Stripe customer"""
        with app.app_context():
            # Create subscription with existing customer ID
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            subscription.stripe_customer_id = 'cus_existing123'
            db.session.add(subscription)
            db.session.commit()
            
            # Mock Stripe customer retrieval
            mock_customer = Mock()
            mock_customer.id = 'cus_existing123'
            mock_stripe.Customer.retrieve.return_value = mock_customer
            
            app.config['STRIPE_SECRET_KEY'] = 'sk_test_123'
            
            customer_id = StripeService.get_or_create_customer(test_user)
            
            assert customer_id == 'cus_existing123'
            mock_stripe.Customer.retrieve.assert_called_once_with('cus_existing123')
    
    @patch('src.services.stripe_service.stripe')
    def test_get_or_create_customer_new(self, mock_stripe, app, test_user):
        """Test creating new Stripe customer when none exists"""
        with app.app_context():
            # Mock Stripe customer creation
            mock_customer = Mock()
            mock_customer.id = 'cus_new123'
            mock_stripe.Customer.create.return_value = mock_customer
            
            app.config['STRIPE_SECRET_KEY'] = 'sk_test_123'
            
            customer_id = StripeService.get_or_create_customer(test_user)
            
            assert customer_id == 'cus_new123'
            mock_stripe.Customer.create.assert_called_once()
    
    @patch('src.services.stripe_service.stripe')
    def test_create_subscription_success(self, mock_stripe, app, test_user):
        """Test successful Stripe subscription creation"""
        with app.app_context():
            # Create plan with Stripe price IDs
            plan = Plan(
                name='test_stripe_plan',
                display_name='Test Stripe Plan',
                price_monthly=Decimal('9.99'),
                daily_compression_limit=100,
                max_file_size_mb=25,
                stripe_price_id_monthly='price_monthly123',
                stripe_price_id_yearly='price_yearly123'
            )
            db.session.add(plan)
            db.session.commit()
            
            # Mock Stripe operations
            mock_customer = Mock()
            mock_customer.id = 'cus_test123'
            mock_stripe.Customer.create.return_value = mock_customer
            
            mock_payment_intent = Mock()
            mock_payment_intent.client_secret = 'pi_test_client_secret'
            
            mock_invoice = Mock()
            mock_invoice.payment_intent = mock_payment_intent
            
            mock_subscription = Mock()
            mock_subscription.id = 'sub_test123'
            mock_subscription.latest_invoice = mock_invoice
            mock_stripe.Subscription.create.return_value = mock_subscription
            
            app.config['STRIPE_SECRET_KEY'] = 'sk_test_123'
            
            result = StripeService.create_subscription(
                user_id=test_user.id,
                plan_id=plan.id,
                payment_method_id='pm_test123',
                billing_cycle='monthly'
            )
            
            assert result['success'] is True
            assert result['subscription_id'] == 'sub_test123'
            assert result['client_secret'] == 'pi_test_client_secret'
            
            # Verify local subscription was created
            subscription = Subscription.query.filter_by(user_id=test_user.id).first()
            assert subscription is not None
            assert subscription.stripe_subscription_id == 'sub_test123'
            assert subscription.stripe_customer_id == 'cus_test123'
    
    @patch('src.services.stripe_service.stripe')
    def test_create_subscription_user_not_found(self, mock_stripe, app):
        """Test subscription creation with invalid user"""
        with app.app_context():
            app.config['STRIPE_SECRET_KEY'] = 'sk_test_123'
            
            result = StripeService.create_subscription(
                user_id=99999,
                plan_id=1,
                payment_method_id='pm_test123'
            )
            
            assert result['success'] is False
            assert result['error'] == 'User not found'
    
    @patch('src.services.stripe_service.stripe')
    def test_create_subscription_plan_not_found(self, mock_stripe, app, test_user):
        """Test subscription creation with invalid plan"""
        with app.app_context():
            app.config['STRIPE_SECRET_KEY'] = 'sk_test_123'
            
            result = StripeService.create_subscription(
                user_id=test_user.id,
                plan_id=99999,
                payment_method_id='pm_test123'
            )
            
            assert result['success'] is False
            assert result['error'] == 'Plan not found'
    
    @patch('src.services.stripe_service.stripe')
    def test_create_subscription_duplicate(self, mock_stripe, app, test_user, test_plan):
        """Test subscription creation when user already has subscription"""
        with app.app_context():
            # Create existing subscription
            existing_subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            db.session.add(existing_subscription)
            db.session.commit()
            
            app.config['STRIPE_SECRET_KEY'] = 'sk_test_123'
            
            result = StripeService.create_subscription(
                user_id=test_user.id,
                plan_id=test_plan.id,
                payment_method_id='pm_test123'
            )
            
            assert result['success'] is False
            assert result['error'] == 'User already has a subscription'
    
    @patch('src.services.stripe_service.stripe')
    def test_cancel_subscription_success(self, mock_stripe, app, test_user, test_plan):
        """Test successful subscription cancellation"""
        with app.app_context():
            # Create subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            subscription.stripe_subscription_id = 'sub_test123'
            db.session.add(subscription)
            db.session.commit()
            
            # Mock Stripe cancellation
            mock_stripe_sub = Mock()
            mock_stripe_sub.canceled_at = 1234567890
            mock_stripe_sub.current_period_end = 1234567890
            mock_stripe.Subscription.modify.return_value = mock_stripe_sub
            
            app.config['STRIPE_SECRET_KEY'] = 'sk_test_123'
            
            result = StripeService.cancel_subscription(test_user.id)
            
            assert result['success'] is True
            assert 'canceled_at' in result
            
            # Verify local subscription status updated
            updated_subscription = Subscription.query.filter_by(user_id=test_user.id).first()
            assert updated_subscription.status == 'canceled'
    
    @patch('src.services.stripe_service.stripe')
    def test_cancel_subscription_not_found(self, mock_stripe, app, test_user):
        """Test cancellation when no subscription exists"""
        with app.app_context():
            app.config['STRIPE_SECRET_KEY'] = 'sk_test_123'
            
            result = StripeService.cancel_subscription(test_user.id)
            
            assert result['success'] is False
            assert result['error'] == 'No subscription found'
    
    def test_handle_webhook_no_secret(self, app):
        """Test webhook handling without webhook secret"""
        with app.app_context():
            # Don't set webhook secret
            result = StripeService.handle_webhook(b'test_payload', 'test_signature')
            
            assert result['success'] is False
            assert result['error'] == 'Webhook secret not configured'
    
    @patch('src.services.stripe_service.stripe')
    def test_handle_webhook_invalid_signature(self, mock_stripe, app):
        """Test webhook handling with invalid signature"""
        with app.app_context():
            app.config['STRIPE_WEBHOOK_SECRET'] = 'whsec_test123'
            
            # Create a proper signature verification error class
            class MockSignatureVerificationError(Exception):
                pass
            
            mock_stripe.error.SignatureVerificationError = MockSignatureVerificationError
            mock_stripe.Webhook.construct_event.side_effect = MockSignatureVerificationError("Invalid signature")
            
            result = StripeService.handle_webhook(b'test_payload', 'invalid_signature')
            
            assert result['success'] is False
            assert result['error'] == 'Invalid signature'
    
    @patch('src.services.stripe_service.stripe')
    def test_handle_webhook_payment_succeeded(self, mock_stripe, app, test_user, test_plan):
        """Test webhook handling for successful payment"""
        with app.app_context():
            # Create subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            subscription.stripe_subscription_id = 'sub_test123'
            subscription.status = 'pending'
            db.session.add(subscription)
            db.session.commit()
            
            # Mock webhook event
            mock_event = {
                'type': 'invoice.payment_succeeded',
                'data': {
                    'object': {
                        'subscription': 'sub_test123'
                    }
                }
            }
            mock_stripe.Webhook.construct_event.return_value = mock_event
            
            app.config['STRIPE_WEBHOOK_SECRET'] = 'whsec_test123'
            
            result = StripeService.handle_webhook(b'test_payload', 'test_signature')
            
            assert result['success'] is True
            
            # Verify subscription status updated
            updated_subscription = Subscription.query.filter_by(user_id=test_user.id).first()
            assert updated_subscription.status == 'active'
    
    @patch('src.services.stripe_service.stripe')
    def test_handle_webhook_payment_failed(self, mock_stripe, app, test_user, test_plan):
        """Test webhook handling for failed payment"""
        with app.app_context():
            # Create subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            subscription.stripe_subscription_id = 'sub_test123'
            subscription.status = 'active'
            db.session.add(subscription)
            db.session.commit()
            
            # Mock webhook event
            mock_event = {
                'type': 'invoice.payment_failed',
                'data': {
                    'object': {
                        'subscription': 'sub_test123'
                    }
                }
            }
            mock_stripe.Webhook.construct_event.return_value = mock_event
            
            app.config['STRIPE_WEBHOOK_SECRET'] = 'whsec_test123'
            
            result = StripeService.handle_webhook(b'test_payload', 'test_signature')
            
            assert result['success'] is True
            
            # Verify subscription status updated
            updated_subscription = Subscription.query.filter_by(user_id=test_user.id).first()
            assert updated_subscription.status == 'past_due'
    
    @patch('src.services.stripe_service.stripe')
    def test_handle_webhook_unhandled_event(self, mock_stripe, app):
        """Test webhook handling for unhandled event type"""
        with app.app_context():
            # Mock webhook event
            mock_event = {
                'type': 'customer.created',
                'data': {'object': {}}
            }
            mock_stripe.Webhook.construct_event.return_value = mock_event
            
            app.config['STRIPE_WEBHOOK_SECRET'] = 'whsec_test123'
            
            result = StripeService.handle_webhook(b'test_payload', 'test_signature')
            
            assert result['success'] is True
            assert result['message'] == 'Event type not handled'
    
    @patch('src.services.stripe_service.stripe')
    def test_get_subscription_details_success(self, mock_stripe, app):
        """Test getting subscription details from Stripe"""
        with app.app_context():
            # Mock Stripe subscription
            mock_customer = Mock()
            mock_customer.id = 'cus_test123'
            mock_customer.email = 'test@example.com'
            mock_customer.name = 'Test User'
            
            mock_invoice = Mock()
            mock_invoice.id = 'in_test123'
            mock_invoice.status = 'paid'
            mock_invoice.amount_paid = 999
            mock_invoice.currency = 'usd'
            
            mock_subscription = Mock()
            mock_subscription.id = 'sub_test123'
            mock_subscription.status = 'active'
            mock_subscription.current_period_start = 1234567890
            mock_subscription.current_period_end = 1234567890
            mock_subscription.cancel_at_period_end = False
            mock_subscription.customer = mock_customer
            mock_subscription.latest_invoice = mock_invoice
            
            mock_stripe.Subscription.retrieve.return_value = mock_subscription
            
            app.config['STRIPE_SECRET_KEY'] = 'sk_test_123'
            
            details = StripeService.get_subscription_details('sub_test123')
            
            assert details is not None
            assert details['id'] == 'sub_test123'
            assert details['status'] == 'active'
            assert details['customer']['email'] == 'test@example.com'
            assert details['latest_invoice']['status'] == 'paid'
    
    @patch('src.services.stripe_service.stripe')
    def test_get_subscription_details_stripe_error(self, mock_stripe, app):
        """Test getting subscription details with Stripe error"""
        with app.app_context():
            # Create a proper Stripe error class
            class MockStripeError(Exception):
                pass
            
            mock_stripe.error.StripeError = MockStripeError
            mock_stripe.Subscription.retrieve.side_effect = MockStripeError("Test error")
            
            app.config['STRIPE_SECRET_KEY'] = 'sk_test_123'
            
            details = StripeService.get_subscription_details('sub_test123')
            
            assert details is None


class TestStripeServiceConfiguration:
    """Test Stripe service configuration handling"""
    
    def test_stripe_key_not_configured(self, app):
        """Test behavior when Stripe API key is not configured"""
        with app.app_context():
            # Don't set Stripe key
            app.config.pop('STRIPE_SECRET_KEY', None)
            
            with pytest.raises(ValueError, match="Stripe API key not configured"):
                StripeService._get_stripe_key()
    
    def test_stripe_key_configured(self, app):
        """Test behavior when Stripe API key is configured"""
        with app.app_context():
            app.config['STRIPE_SECRET_KEY'] = 'sk_test_123'
            
            api_key = StripeService._get_stripe_key()
            assert api_key == 'sk_test_123'