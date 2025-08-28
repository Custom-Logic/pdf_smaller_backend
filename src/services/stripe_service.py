"""Stripe payment processing service"""
import logging
import stripe
from datetime import datetime
from typing import Optional, Dict, Any, List
from flask import current_app
from src.models import User, Subscription, Plan
from src.models.base import db
from src.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


class StripeService:
    """Service for handling Stripe payment processing"""
    
    def __init__(self):
        """Initialize Stripe service with API key"""
        self.stripe_api_key = current_app.config.get('STRIPE_SECRET_KEY')
        if self.stripe_api_key:
            stripe.api_key = self.stripe_api_key
        else:
            logger.warning("Stripe API key not configured")
    
    @staticmethod
    def _get_stripe_key():
        """Get Stripe API key from config"""
        api_key = current_app.config.get('STRIPE_SECRET_KEY')
        if not api_key:
            raise ValueError("Stripe API key not configured")
        stripe.api_key = api_key
        return api_key
    
    @staticmethod
    def create_customer(user: User) -> Optional[str]:
        """Create a Stripe customer for a user"""
        try:
            StripeService._get_stripe_key()
            
            customer = stripe.Customer.create(
                email=user.email,
                name=user.name,
                metadata={
                    'user_id': str(user.id)
                }
            )
            
            logger.info(f"Created Stripe customer {customer.id} for user {user.id}")
            return customer.id
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error creating customer for user {user.id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error creating Stripe customer for user {user.id}: {str(e)}")
            return None
    
    @staticmethod
    def get_or_create_customer(user: User) -> Optional[str]:
        """Get existing Stripe customer or create new one"""
        try:
            # Check if user already has a subscription with Stripe customer ID
            subscription = Subscription.query.filter_by(user_id=user.id).first()
            if subscription and subscription.stripe_customer_id:
                # Verify customer exists in Stripe
                try:
                    StripeService._get_stripe_key()
                    stripe.Customer.retrieve(subscription.stripe_customer_id)
                    return subscription.stripe_customer_id
                except stripe.error.InvalidRequestError:
                    # Customer doesn't exist, create new one
                    pass
            
            # Create new customer
            return StripeService.create_customer(user)
            
        except Exception as e:
            logger.error(f"Error getting/creating Stripe customer for user {user.id}: {str(e)}")
            return None
    
    @staticmethod
    def create_subscription(user_id: int, plan_id: int, payment_method_id: str, billing_cycle: str = 'monthly') -> Dict[str, Any]:
        """Create a Stripe subscription"""
        try:
            StripeService._get_stripe_key()
            
            # Get user and plan
            user = User.query.get(user_id)
            if not user:
                return {'success': False, 'error': 'User not found'}
            
            plan = Plan.query.get(plan_id)
            if not plan:
                return {'success': False, 'error': 'Plan not found'}
            
            # Check if user already has a subscription
            existing_subscription = Subscription.query.filter_by(user_id=user_id).first()
            if existing_subscription:
                return {'success': False, 'error': 'User already has a subscription'}
            
            # Get or create Stripe customer
            customer_id = StripeService.get_or_create_customer(user)
            if not customer_id:
                return {'success': False, 'error': 'Failed to create Stripe customer'}
            
            # Attach payment method to customer
            stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id
            )
            
            # Set as default payment method
            stripe.Customer.modify(
                customer_id,
                invoice_settings={'default_payment_method': payment_method_id}
            )
            
            # Get the appropriate Stripe price ID
            stripe_price_id = plan.stripe_price_id_yearly if billing_cycle == 'yearly' else plan.stripe_price_id_monthly
            
            if not stripe_price_id:
                return {'success': False, 'error': f'Stripe price ID not configured for {billing_cycle} billing'}
            
            # Create Stripe subscription
            stripe_subscription = stripe.Subscription.create(
                customer=customer_id,
                items=[{'price': stripe_price_id}],
                payment_behavior='default_incomplete',
                payment_settings={'save_default_payment_method': 'on_subscription'},
                expand=['latest_invoice.payment_intent'],
                metadata={
                    'user_id': str(user_id),
                    'plan_id': str(plan_id)
                }
            )
            
            # Create local subscription record
            subscription = Subscription(
                user_id=user_id,
                plan_id=plan_id,
                billing_cycle=billing_cycle
            )
            subscription.stripe_subscription_id = stripe_subscription.id
            subscription.stripe_customer_id = customer_id
            subscription.status = 'pending'  # Will be updated by webhook
            
            db.session.add(subscription)
            db.session.commit()
            
            logger.info(f"Created Stripe subscription {stripe_subscription.id} for user {user_id}")
            
            return {
                'success': True,
                'subscription_id': stripe_subscription.id,
                'client_secret': stripe_subscription.latest_invoice.payment_intent.client_secret,
                'subscription': subscription.to_dict()
            }
            
        except stripe.error.StripeError as e:
            db.session.rollback()
            logger.error(f"Stripe error creating subscription for user {user_id}: {str(e)}")
            return {'success': False, 'error': f'Payment processing error: {str(e)}'}
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating subscription for user {user_id}: {str(e)}")
            return {'success': False, 'error': 'Internal server error'}
    
    @staticmethod
    def cancel_subscription(user_id: int) -> Dict[str, Any]:
        """Cancel a Stripe subscription"""
        try:
            StripeService._get_stripe_key()
            
            # Get user's subscription
            subscription = Subscription.query.filter_by(user_id=user_id).first()
            if not subscription:
                return {'success': False, 'error': 'No subscription found'}
            
            if not subscription.stripe_subscription_id:
                return {'success': False, 'error': 'No Stripe subscription ID found'}
            
            # Cancel in Stripe
            stripe_subscription = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            # Update local subscription status
            subscription.status = 'canceled'
            db.session.commit()
            
            logger.info(f"Canceled Stripe subscription {subscription.stripe_subscription_id} for user {user_id}")
            
            return {
                'success': True,
                'canceled_at': stripe_subscription.canceled_at,
                'current_period_end': stripe_subscription.current_period_end
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error canceling subscription for user {user_id}: {str(e)}")
            return {'success': False, 'error': f'Payment processing error: {str(e)}'}
        except Exception as e:
            logger.error(f"Error canceling subscription for user {user_id}: {str(e)}")
            return {'success': False, 'error': 'Internal server error'}
    
    @staticmethod
    def update_subscription_plan(user_id: int, new_plan_id: int) -> Dict[str, Any]:
        """Update a Stripe subscription to a new plan"""
        try:
            StripeService._get_stripe_key()
            
            # Get user's subscription
            subscription = Subscription.query.filter_by(user_id=user_id).first()
            if not subscription:
                return {'success': False, 'error': 'No subscription found'}
            
            if not subscription.stripe_subscription_id:
                return {'success': False, 'error': 'No Stripe subscription ID found'}
            
            # Get new plan
            new_plan = Plan.query.get(new_plan_id)
            if not new_plan:
                return {'success': False, 'error': 'New plan not found'}
            
            # Get appropriate Stripe price ID
            stripe_price_id = (new_plan.stripe_price_id_yearly 
                             if subscription.billing_cycle == 'yearly' 
                             else new_plan.stripe_price_id_monthly)
            
            if not stripe_price_id:
                return {'success': False, 'error': f'Stripe price ID not configured for {subscription.billing_cycle} billing'}
            
            # Get current Stripe subscription
            stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
            
            # Update subscription in Stripe
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                items=[{
                    'id': stripe_subscription['items']['data'][0].id,
                    'price': stripe_price_id,
                }],
                proration_behavior='create_prorations'
            )
            
            # Update local subscription
            subscription.plan_id = new_plan_id
            subscription.daily_usage_count = 0  # Reset usage
            db.session.commit()
            
            logger.info(f"Updated Stripe subscription {subscription.stripe_subscription_id} to plan {new_plan.name}")
            
            return {
                'success': True,
                'subscription': subscription.to_dict()
            }
            
        except stripe.error.StripeError as e:
            db.session.rollback()
            logger.error(f"Stripe error updating subscription for user {user_id}: {str(e)}")
            return {'success': False, 'error': f'Payment processing error: {str(e)}'}
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating subscription for user {user_id}: {str(e)}")
            return {'success': False, 'error': 'Internal server error'}
    
    @staticmethod
    def handle_webhook(payload: bytes, signature: str) -> Dict[str, Any]:
        """Handle Stripe webhook events"""
        try:
            webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
            if not webhook_secret:
                logger.error("Stripe webhook secret not configured")
                return {'success': False, 'error': 'Webhook secret not configured'}
            
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
            
            logger.info(f"Received Stripe webhook: {event['type']}")
            
            # Handle different event types
            if event['type'] == 'invoice.payment_succeeded':
                return StripeService._handle_payment_succeeded(event['data']['object'])
            
            elif event['type'] == 'invoice.payment_failed':
                return StripeService._handle_payment_failed(event['data']['object'])
            
            elif event['type'] == 'customer.subscription.updated':
                return StripeService._handle_subscription_updated(event['data']['object'])
            
            elif event['type'] == 'customer.subscription.deleted':
                return StripeService._handle_subscription_deleted(event['data']['object'])
            
            else:
                logger.info(f"Unhandled webhook event type: {event['type']}")
                return {'success': True, 'message': 'Event type not handled'}
            
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Stripe webhook signature verification failed: {str(e)}")
            return {'success': False, 'error': 'Invalid signature'}
        except Exception as e:
            logger.error(f"Error handling Stripe webhook: {str(e)}")
            return {'success': False, 'error': 'Webhook processing error'}
    
    @staticmethod
    def _handle_payment_succeeded(invoice) -> Dict[str, Any]:
        """Handle successful payment webhook"""
        try:
            subscription_id = invoice.get('subscription')
            if not subscription_id:
                return {'success': False, 'error': 'No subscription ID in invoice'}
            
            # Find local subscription
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=subscription_id
            ).first()
            
            if not subscription:
                logger.warning(f"No local subscription found for Stripe subscription {subscription_id}")
                return {'success': False, 'error': 'Local subscription not found'}
            
            # Update subscription status
            subscription.status = 'active'
            db.session.commit()
            
            logger.info(f"Payment succeeded for subscription {subscription_id}")
            return {'success': True, 'message': 'Payment processed successfully'}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error handling payment succeeded webhook: {str(e)}")
            return {'success': False, 'error': 'Error processing payment success'}
    
    @staticmethod
    def _handle_payment_failed(invoice) -> Dict[str, Any]:
        """Handle failed payment webhook"""
        try:
            subscription_id = invoice.get('subscription')
            if not subscription_id:
                return {'success': False, 'error': 'No subscription ID in invoice'}
            
            # Find local subscription
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=subscription_id
            ).first()
            
            if not subscription:
                logger.warning(f"No local subscription found for Stripe subscription {subscription_id}")
                return {'success': False, 'error': 'Local subscription not found'}
            
            # Update subscription status
            subscription.status = 'past_due'
            db.session.commit()
            
            logger.warning(f"Payment failed for subscription {subscription_id}")
            return {'success': True, 'message': 'Payment failure processed'}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error handling payment failed webhook: {str(e)}")
            return {'success': False, 'error': 'Error processing payment failure'}
    
    @staticmethod
    def _handle_subscription_updated(stripe_subscription) -> Dict[str, Any]:
        """Handle subscription updated webhook"""
        try:
            subscription_id = stripe_subscription.get('id')
            
            # Find local subscription
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=subscription_id
            ).first()
            
            if not subscription:
                logger.warning(f"No local subscription found for Stripe subscription {subscription_id}")
                return {'success': False, 'error': 'Local subscription not found'}
            
            # Update subscription status and periods
            subscription.status = stripe_subscription.get('status', subscription.status)
            
            if stripe_subscription.get('current_period_start'):
                subscription.current_period_start = datetime.fromtimestamp(
                    stripe_subscription['current_period_start']
                )
            
            if stripe_subscription.get('current_period_end'):
                subscription.current_period_end = datetime.fromtimestamp(
                    stripe_subscription['current_period_end']
                )
            
            db.session.commit()
            
            logger.info(f"Updated subscription {subscription_id}")
            return {'success': True, 'message': 'Subscription updated'}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error handling subscription updated webhook: {str(e)}")
            return {'success': False, 'error': 'Error updating subscription'}
    
    @staticmethod
    def _handle_subscription_deleted(stripe_subscription) -> Dict[str, Any]:
        """Handle subscription deleted webhook"""
        try:
            subscription_id = stripe_subscription.get('id')
            
            # Find local subscription
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=subscription_id
            ).first()
            
            if not subscription:
                logger.warning(f"No local subscription found for Stripe subscription {subscription_id}")
                return {'success': False, 'error': 'Local subscription not found'}
            
            # Update subscription status
            subscription.status = 'canceled'
            db.session.commit()
            
            logger.info(f"Subscription {subscription_id} deleted")
            return {'success': True, 'message': 'Subscription deletion processed'}
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error handling subscription deleted webhook: {str(e)}")
            return {'success': False, 'error': 'Error processing subscription deletion'}
    
    @staticmethod
    def get_subscription_details(subscription_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed subscription information from Stripe"""
        try:
            StripeService._get_stripe_key()
            
            stripe_subscription = stripe.Subscription.retrieve(
                subscription_id,
                expand=['latest_invoice', 'customer']
            )
            
            return {
                'id': stripe_subscription.id,
                'status': stripe_subscription.status,
                'current_period_start': stripe_subscription.current_period_start,
                'current_period_end': stripe_subscription.current_period_end,
                'cancel_at_period_end': stripe_subscription.cancel_at_period_end,
                'customer': {
                    'id': stripe_subscription.customer.id,
                    'email': stripe_subscription.customer.email,
                    'name': stripe_subscription.customer.name
                },
                'latest_invoice': {
                    'id': stripe_subscription.latest_invoice.id,
                    'status': stripe_subscription.latest_invoice.status,
                    'amount_paid': stripe_subscription.latest_invoice.amount_paid,
                    'currency': stripe_subscription.latest_invoice.currency
                } if stripe_subscription.latest_invoice else None
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Stripe error getting subscription details {subscription_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error getting subscription details {subscription_id}: {str(e)}")
            return None