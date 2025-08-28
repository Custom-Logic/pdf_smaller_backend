"""Subscription management API routes"""
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging
from src.services.subscription_service import SubscriptionService
from src.services.stripe_service import StripeService
from src.models import User, Plan
from src.utils.validation import validate_json_request, validate_required_fields

logger = logging.getLogger(__name__)

# Create blueprint
subscription_bp = Blueprint('subscription', __name__, url_prefix='/api/subscriptions')


def get_current_user_id():
    """Get current user ID from JWT token"""
    return int(get_jwt_identity())

# Rate limiter will be initialized in the app factory
limiter = None


@subscription_bp.route('', methods=['GET'])
@jwt_required()
def get_subscription_info():
    """Get user's subscription information and usage statistics"""
    try:
        user_id = get_current_user_id()
        
        # Get subscription details
        subscription = SubscriptionService.get_user_subscription(user_id)
        if not subscription:
            return jsonify({
                'error': 'No subscription found',
                'subscription': None,
                'usage': SubscriptionService.get_usage_statistics(user_id)
            }), 404
        
        # Get usage statistics
        usage_stats = SubscriptionService.get_usage_statistics(user_id)
        
        # Validate subscription status
        status = SubscriptionService.validate_subscription_status(user_id)
        
        return jsonify({
            'subscription': subscription.to_dict(),
            'usage': usage_stats,
            'status': status,
            'permissions': status.get('permissions', {})
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting subscription info for user {user_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@subscription_bp.route('/plans', methods=['GET'])
def get_available_plans():
    """Get all available subscription plans"""
    try:
        plans = SubscriptionService.get_all_plans()
        
        return jsonify({
            'plans': [plan.to_dict() for plan in plans]
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting available plans: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@subscription_bp.route('/create', methods=['POST'])
@jwt_required()
def create_subscription():
    """Create a new subscription with Stripe payment"""
    try:
        user_id = get_current_user_id()
        
        # Validate request data
        if not validate_json_request(request):
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        data = request.get_json()
        required_fields = ['plan_id', 'payment_method_id']
        if not validate_required_fields(data, required_fields):
            return jsonify({'error': 'Missing required fields: plan_id, payment_method_id'}), 400
        
        plan_id = data.get('plan_id')
        payment_method_id = data.get('payment_method_id')
        billing_cycle = data.get('billing_cycle', 'monthly')
        
        # Validate billing cycle
        if billing_cycle not in ['monthly', 'yearly']:
            return jsonify({'error': 'Invalid billing cycle. Must be monthly or yearly'}), 400
        
        # Validate plan exists
        plan = SubscriptionService.get_plan_by_id(plan_id)
        if not plan:
            return jsonify({'error': 'Invalid plan ID'}), 400
        
        # Check if user already has a subscription
        existing_subscription = SubscriptionService.get_user_subscription(user_id)
        if existing_subscription:
            return jsonify({'error': 'User already has an active subscription'}), 409
        
        # Create subscription with Stripe
        result = StripeService.create_subscription(
            user_id=user_id,
            plan_id=plan_id,
            payment_method_id=payment_method_id,
            billing_cycle=billing_cycle
        )
        
        if not result['success']:
            return jsonify({'error': result['error']}), 400
        
        logger.info(f"Created subscription for user {user_id} with plan {plan.name}")
        
        return jsonify({
            'message': 'Subscription created successfully',
            'subscription': result['subscription'],
            'client_secret': result['client_secret'],
            'subscription_id': result['subscription_id']
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating subscription for user {user_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@subscription_bp.route('/cancel', methods=['POST'])
@jwt_required()
def cancel_subscription():
    """Cancel user's subscription"""
    try:
        user_id = get_jwt_identity()
        
        # Check if user has a subscription
        subscription = SubscriptionService.get_user_subscription(user_id)
        if not subscription:
            return jsonify({'error': 'No active subscription found'}), 404
        
        # Cancel subscription in Stripe
        result = StripeService.cancel_subscription(user_id)
        
        if not result['success']:
            return jsonify({'error': result['error']}), 400
        
        logger.info(f"Canceled subscription for user {user_id}")
        
        return jsonify({
            'message': 'Subscription canceled successfully',
            'canceled_at': result.get('canceled_at'),
            'current_period_end': result.get('current_period_end')
        }), 200
        
    except Exception as e:
        logger.error(f"Error canceling subscription for user {user_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@subscription_bp.route('/update-plan', methods=['POST'])
@jwt_required()
def update_subscription_plan():
    """Update user's subscription plan"""
    try:
        user_id = get_jwt_identity()
        
        # Validate request data
        if not validate_json_request(request):
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        data = request.get_json()
        required_fields = ['new_plan_id']
        if not validate_required_fields(data, required_fields):
            return jsonify({'error': 'Missing required field: new_plan_id'}), 400
        
        new_plan_id = data.get('new_plan_id')
        
        # Validate new plan exists
        new_plan = SubscriptionService.get_plan_by_id(new_plan_id)
        if not new_plan:
            return jsonify({'error': 'Invalid plan ID'}), 400
        
        # Check if user has a subscription
        subscription = SubscriptionService.get_user_subscription(user_id)
        if not subscription:
            return jsonify({'error': 'No active subscription found'}), 404
        
        # Check if it's the same plan
        if subscription.plan_id == new_plan_id:
            return jsonify({'error': 'User is already on this plan'}), 400
        
        # Update subscription plan in Stripe
        result = StripeService.update_subscription_plan(user_id, new_plan_id)
        
        if not result['success']:
            return jsonify({'error': result['error']}), 400
        
        logger.info(f"Updated subscription plan for user {user_id} to {new_plan.name}")
        
        return jsonify({
            'message': 'Subscription plan updated successfully',
            'subscription': result['subscription']
        }), 200
        
    except Exception as e:
        logger.error(f"Error updating subscription plan for user {user_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@subscription_bp.route('/usage', methods=['GET'])
@jwt_required()
def get_usage_statistics():
    """Get detailed usage statistics for the user"""
    try:
        user_id = get_jwt_identity()
        
        # Get usage statistics
        usage_stats = SubscriptionService.get_usage_statistics(user_id)
        
        # Get compression permissions
        permissions = SubscriptionService.check_compression_permission(user_id)
        
        return jsonify({
            'usage': usage_stats,
            'permissions': permissions
        }), 200
        
    except Exception as e:
        logger.error(f"Error getting usage statistics for user {user_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@subscription_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    try:
        payload = request.get_data()
        signature = request.headers.get('Stripe-Signature')
        
        if not signature:
            logger.warning("Stripe webhook received without signature")
            return jsonify({'error': 'Missing signature'}), 400
        
        # Handle webhook
        result = StripeService.handle_webhook(payload, signature)
        
        if not result['success']:
            logger.error(f"Webhook processing failed: {result['error']}")
            return jsonify({'error': result['error']}), 400
        
        return jsonify({'message': result.get('message', 'Webhook processed successfully')}), 200
        
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        return jsonify({'error': 'Webhook processing error'}), 500


@subscription_bp.route('/permissions', methods=['GET'])
@jwt_required()
def check_permissions():
    """Check user's subscription permissions"""
    try:
        user_id = get_jwt_identity()
        
        # Get comprehensive permission check
        compression_permission = SubscriptionService.check_compression_permission(user_id)
        bulk_permission = SubscriptionService.check_bulk_processing_permission(user_id)
        api_permission = SubscriptionService.check_api_access_permission(user_id)
        max_file_size = SubscriptionService.get_max_file_size(user_id)
        
        return jsonify({
            'compression': compression_permission,
            'bulk_processing': bulk_permission,
            'api_access': api_permission,
            'max_file_size_mb': max_file_size
        }), 200
        
    except Exception as e:
        logger.error(f"Error checking permissions for user {user_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


@subscription_bp.route('/reactivate', methods=['POST'])
@jwt_required()
def reactivate_subscription():
    """Reactivate a canceled subscription"""
    try:
        user_id = get_jwt_identity()
        
        # Check if user has a subscription
        subscription = SubscriptionService.get_user_subscription(user_id)
        if not subscription:
            return jsonify({'error': 'No subscription found'}), 404
        
        if subscription.status == 'active':
            return jsonify({'error': 'Subscription is already active'}), 400
        
        # Reactivate subscription
        success = SubscriptionService.reactivate_subscription(user_id)
        
        if not success:
            return jsonify({'error': 'Failed to reactivate subscription'}), 400
        
        logger.info(f"Reactivated subscription for user {user_id}")
        
        return jsonify({
            'message': 'Subscription reactivated successfully'
        }), 200
        
    except Exception as e:
        logger.error(f"Error reactivating subscription for user {user_id}: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500


# Error handlers for the blueprint
@subscription_bp.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded"""
    return jsonify({
        'error': 'Rate limit exceeded',
        'message': 'Too many requests. Please try again later.'
    }), 429


@subscription_bp.errorhandler(400)
def bad_request_handler(e):
    """Handle bad request errors"""
    return jsonify({
        'error': 'Bad request',
        'message': str(e.description) if hasattr(e, 'description') else 'Invalid request'
    }), 400


@subscription_bp.errorhandler(401)
def unauthorized_handler(e):
    """Handle unauthorized errors"""
    return jsonify({
        'error': 'Unauthorized',
        'message': 'Authentication required'
    }), 401


@subscription_bp.errorhandler(404)
def not_found_handler(e):
    """Handle not found errors"""
    return jsonify({
        'error': 'Not found',
        'message': 'Resource not found'
    }), 404


@subscription_bp.errorhandler(500)
def internal_error_handler(e):
    """Handle internal server errors"""
    logger.error(f"Internal server error in subscription routes: {str(e)}")
    return jsonify({
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500