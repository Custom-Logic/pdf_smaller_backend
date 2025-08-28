"""Subscription service for managing user subscriptions and usage limits"""
import logging
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from src.models import User, Subscription, Plan
from src.models.base import db

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for managing user subscriptions and usage tracking"""
    
    @staticmethod
    def get_user_subscription(user_id: int) -> Optional[Subscription]:
        """Get user's current subscription"""
        try:
            subscription = Subscription.query.filter_by(user_id=user_id).first()
            if subscription:
                # Reset daily usage if needed
                subscription.reset_daily_usage_if_needed()
            return subscription
        except Exception as e:
            logger.error(f"Error getting subscription for user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def get_all_plans() -> List[Plan]:
        """Get all available subscription plans"""
        try:
            return Plan.query.order_by(Plan.price_monthly.asc()).all()
        except Exception as e:
            logger.error(f"Error getting plans: {str(e)}")
            return []
    
    @staticmethod
    def get_plan_by_name(plan_name: str) -> Optional[Plan]:
        """Get plan by name"""
        try:
            return Plan.query.filter_by(name=plan_name).first()
        except Exception as e:
            logger.error(f"Error getting plan {plan_name}: {str(e)}")
            return None
    
    @staticmethod
    def get_plan_by_id(plan_id: int) -> Optional[Plan]:
        """Get plan by ID"""
        try:
            return Plan.query.get(plan_id)
        except Exception as e:
            logger.error(f"Error getting plan {plan_id}: {str(e)}")
            return None
    
    @staticmethod
    def create_subscription(user_id: int, plan_id: int, billing_cycle: str = 'monthly') -> Optional[Subscription]:
        """Create a new subscription for a user"""
        try:
            # Check if user already has a subscription
            existing_subscription = Subscription.query.filter_by(user_id=user_id).first()
            if existing_subscription:
                logger.warning(f"User {user_id} already has a subscription")
                return None
            
            # Verify plan exists
            plan = Plan.query.get(plan_id)
            if not plan:
                logger.error(f"Plan {plan_id} not found")
                return None
            
            # Verify user exists
            user = User.query.get(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return None
            
            # Create subscription
            subscription = Subscription(
                user_id=user_id,
                plan_id=plan_id,
                billing_cycle=billing_cycle
            )
            
            db.session.add(subscription)
            db.session.commit()
            
            logger.info(f"Created subscription for user {user_id} with plan {plan.name}")
            return subscription
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating subscription for user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def update_subscription_plan(user_id: int, new_plan_id: int) -> Optional[Subscription]:
        """Update user's subscription plan"""
        try:
            subscription = Subscription.query.filter_by(user_id=user_id).first()
            if not subscription:
                logger.error(f"No subscription found for user {user_id}")
                return None
            
            # Verify new plan exists
            new_plan = Plan.query.get(new_plan_id)
            if not new_plan:
                logger.error(f"Plan {new_plan_id} not found")
                return None
            
            old_plan_name = subscription.plan.name if subscription.plan else "Unknown"
            subscription.plan_id = new_plan_id
            
            # Reset usage when changing plans
            subscription.daily_usage_count = 0
            subscription.last_usage_reset = date.today()
            
            db.session.commit()
            
            logger.info(f"Updated subscription for user {user_id} from {old_plan_name} to {new_plan.name}")
            return subscription
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error updating subscription for user {user_id}: {str(e)}")
            return None
    
    @staticmethod
    def cancel_subscription(user_id: int) -> bool:
        """Cancel user's subscription (set to canceled status)"""
        try:
            subscription = Subscription.query.filter_by(user_id=user_id).first()
            if not subscription:
                logger.error(f"No subscription found for user {user_id}")
                return False
            
            subscription.status = 'canceled'
            db.session.commit()
            
            logger.info(f"Canceled subscription for user {user_id}")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error canceling subscription for user {user_id}: {str(e)}")
            return False
    
    @staticmethod
    def reactivate_subscription(user_id: int) -> bool:
        """Reactivate a canceled subscription"""
        try:
            subscription = Subscription.query.filter_by(user_id=user_id).first()
            if not subscription:
                logger.error(f"No subscription found for user {user_id}")
                return False
            
            subscription.status = 'active'
            db.session.commit()
            
            logger.info(f"Reactivated subscription for user {user_id}")
            return True
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error reactivating subscription for user {user_id}: {str(e)}")
            return False
    
    @staticmethod
    def check_compression_permission(user_id: int) -> Dict[str, Any]:
        """Check if user can perform compression and return detailed status"""
        try:
            subscription = SubscriptionService.get_user_subscription(user_id)
            
            if not subscription:
                return {
                    'can_compress': False,
                    'reason': 'No subscription found',
                    'daily_usage': 0,
                    'daily_limit': 0,
                    'plan_name': None
                }
            
            can_compress = subscription.can_compress()
            
            return {
                'can_compress': can_compress,
                'reason': 'Daily limit exceeded' if not can_compress and subscription.is_active() else None,
                'daily_usage': subscription.daily_usage_count,
                'daily_limit': subscription.plan.daily_compression_limit,
                'plan_name': subscription.plan.name,
                'is_active': subscription.is_active(),
                'max_file_size_mb': subscription.plan.max_file_size_mb,
                'bulk_processing': subscription.plan.bulk_processing,
                'priority_processing': subscription.plan.priority_processing,
                'api_access': subscription.plan.api_access
            }
            
        except Exception as e:
            logger.error(f"Error checking compression permission for user {user_id}: {str(e)}")
            return {
                'can_compress': False,
                'reason': 'System error',
                'daily_usage': 0,
                'daily_limit': 0,
                'plan_name': None
            }
    
    @staticmethod
    def increment_usage(user_id: int) -> bool:
        """Increment user's daily usage counter"""
        try:
            subscription = SubscriptionService.get_user_subscription(user_id)
            
            if not subscription:
                logger.error(f"No subscription found for user {user_id}")
                return False
            
            if not subscription.can_compress():
                logger.warning(f"User {user_id} attempted to compress but has reached daily limit")
                return False
            
            subscription.increment_usage()
            logger.info(f"Incremented usage for user {user_id} to {subscription.daily_usage_count}")
            return True
            
        except Exception as e:
            logger.error(f"Error incrementing usage for user {user_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_usage_statistics(user_id: int) -> Dict[str, Any]:
        """Get detailed usage statistics for a user"""
        try:
            subscription = SubscriptionService.get_user_subscription(user_id)
            
            if not subscription:
                return {
                    'daily_usage': 0,
                    'daily_limit': 0,
                    'usage_percentage': 0,
                    'remaining_compressions': 0,
                    'plan_name': None,
                    'is_active': False
                }
            
            daily_usage = subscription.daily_usage_count
            daily_limit = subscription.plan.daily_compression_limit
            usage_percentage = (daily_usage / daily_limit * 100) if daily_limit > 0 else 0
            remaining = max(0, daily_limit - daily_usage)
            
            return {
                'daily_usage': daily_usage,
                'daily_limit': daily_limit,
                'usage_percentage': round(usage_percentage, 2),
                'remaining_compressions': remaining,
                'plan_name': subscription.plan.name,
                'is_active': subscription.is_active(),
                'last_reset': subscription.last_usage_reset.isoformat() if subscription.last_usage_reset else None,
                'billing_cycle': subscription.billing_cycle,
                'current_period_end': subscription.current_period_end.isoformat() if subscription.current_period_end else None
            }
            
        except Exception as e:
            logger.error(f"Error getting usage statistics for user {user_id}: {str(e)}")
            return {
                'daily_usage': 0,
                'daily_limit': 0,
                'usage_percentage': 0,
                'remaining_compressions': 0,
                'plan_name': None,
                'is_active': False
            }
    
    @staticmethod
    def check_bulk_processing_permission(user_id: int) -> bool:
        """Check if user has permission for bulk processing"""
        try:
            subscription = SubscriptionService.get_user_subscription(user_id)
            
            if not subscription or not subscription.is_active():
                return False
            
            return subscription.plan.bulk_processing
            
        except Exception as e:
            logger.error(f"Error checking bulk processing permission for user {user_id}: {str(e)}")
            return False
    
    @staticmethod
    def check_api_access_permission(user_id: int) -> bool:
        """Check if user has API access permission"""
        try:
            subscription = SubscriptionService.get_user_subscription(user_id)
            
            if not subscription or not subscription.is_active():
                return False
            
            return subscription.plan.api_access
            
        except Exception as e:
            logger.error(f"Error checking API access permission for user {user_id}: {str(e)}")
            return False
    
    @staticmethod
    def get_max_file_size(user_id: int) -> int:
        """Get maximum file size allowed for user (in MB)"""
        try:
            subscription = SubscriptionService.get_user_subscription(user_id)
            
            if not subscription or not subscription.is_active():
                # Default to free tier limits if no active subscription
                free_plan = Plan.query.filter_by(name='free').first()
                return free_plan.max_file_size_mb if free_plan else 10
            
            return subscription.plan.max_file_size_mb
            
        except Exception as e:
            logger.error(f"Error getting max file size for user {user_id}: {str(e)}")
            return 10  # Default fallback
    
    @staticmethod
    def validate_subscription_status(user_id: int) -> Dict[str, Any]:
        """Validate and return comprehensive subscription status"""
        try:
            subscription = SubscriptionService.get_user_subscription(user_id)
            
            if not subscription:
                return {
                    'valid': False,
                    'reason': 'No subscription found',
                    'subscription': None
                }
            
            is_active = subscription.is_active()
            
            return {
                'valid': is_active,
                'reason': None if is_active else f'Subscription is {subscription.status}',
                'subscription': subscription.to_dict(),
                'permissions': {
                    'can_compress': subscription.can_compress(),
                    'bulk_processing': subscription.plan.bulk_processing,
                    'priority_processing': subscription.plan.priority_processing,
                    'api_access': subscription.plan.api_access,
                    'max_file_size_mb': subscription.plan.max_file_size_mb
                }
            }
            
        except Exception as e:
            logger.error(f"Error validating subscription status for user {user_id}: {str(e)}")
            return {
                'valid': False,
                'reason': 'System error',
                'subscription': None
            }