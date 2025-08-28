"""Unit tests for subscription service"""
import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from src.services.subscription_service import SubscriptionService
from src.models import User, Subscription, Plan
from src.models.base import db


class TestSubscriptionService:
    """Test cases for SubscriptionService"""
    
    def test_get_user_subscription_exists(self, app, test_user, test_plan):
        """Test getting existing user subscription"""
        with app.app_context():
            # Create subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            db.session.add(subscription)
            db.session.commit()
            
            # Test service method
            result = SubscriptionService.get_user_subscription(test_user.id)
            
            assert result is not None
            assert result.user_id == test_user.id
            assert result.plan_id == test_plan.id
    
    def test_get_user_subscription_not_exists(self, app, test_user):
        """Test getting non-existent user subscription"""
        with app.app_context():
            result = SubscriptionService.get_user_subscription(test_user.id)
            assert result is None
    
    def test_get_all_plans(self, app):
        """Test getting all available plans"""
        with app.app_context():
            plans = SubscriptionService.get_all_plans()
            
            # Should have at least the default plans (free, premium, pro)
            assert len(plans) >= 3
            
            # Plans should be ordered by price
            for i in range(len(plans) - 1):
                assert plans[i].price_monthly <= plans[i + 1].price_monthly
    
    def test_get_plan_by_name(self, app):
        """Test getting plan by name"""
        with app.app_context():
            # Test existing plan
            free_plan = SubscriptionService.get_plan_by_name('free')
            assert free_plan is not None
            assert free_plan.name == 'free'
            
            # Test non-existent plan
            nonexistent = SubscriptionService.get_plan_by_name('nonexistent')
            assert nonexistent is None
    
    def test_get_plan_by_id(self, app, test_plan):
        """Test getting plan by ID"""
        with app.app_context():
            # Test existing plan
            plan = SubscriptionService.get_plan_by_id(test_plan.id)
            assert plan is not None
            assert plan.id == test_plan.id
            
            # Test non-existent plan
            nonexistent = SubscriptionService.get_plan_by_id(99999)
            assert nonexistent is None
    
    def test_create_subscription_success(self, app, test_user, test_plan):
        """Test successful subscription creation"""
        with app.app_context():
            subscription = SubscriptionService.create_subscription(
                user_id=test_user.id,
                plan_id=test_plan.id,
                billing_cycle='monthly'
            )
            
            assert subscription is not None
            assert subscription.user_id == test_user.id
            assert subscription.plan_id == test_plan.id
            assert subscription.billing_cycle == 'monthly'
            assert subscription.status == 'active'
    
    def test_create_subscription_duplicate(self, app, test_user, test_plan):
        """Test creating subscription for user who already has one"""
        with app.app_context():
            # Create first subscription
            first_sub = SubscriptionService.create_subscription(
                user_id=test_user.id,
                plan_id=test_plan.id
            )
            assert first_sub is not None
            
            # Try to create second subscription
            second_sub = SubscriptionService.create_subscription(
                user_id=test_user.id,
                plan_id=test_plan.id
            )
            assert second_sub is None
    
    def test_create_subscription_invalid_user(self, app, test_plan):
        """Test creating subscription for non-existent user"""
        with app.app_context():
            subscription = SubscriptionService.create_subscription(
                user_id=99999,
                plan_id=test_plan.id
            )
            assert subscription is None
    
    def test_create_subscription_invalid_plan(self, app, test_user):
        """Test creating subscription with non-existent plan"""
        with app.app_context():
            subscription = SubscriptionService.create_subscription(
                user_id=test_user.id,
                plan_id=99999
            )
            assert subscription is None
    
    def test_update_subscription_plan(self, app, test_user, test_plan):
        """Test updating subscription plan"""
        with app.app_context():
            # Create subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            db.session.add(subscription)
            db.session.commit()
            
            # Create another plan
            new_plan = Plan(
                name='new_test_plan',
                display_name='New Test Plan',
                price_monthly=Decimal('19.99'),
                daily_compression_limit=200,
                max_file_size_mb=50
            )
            db.session.add(new_plan)
            db.session.commit()
            
            # Update subscription
            updated_sub = SubscriptionService.update_subscription_plan(
                user_id=test_user.id,
                new_plan_id=new_plan.id
            )
            
            assert updated_sub is not None
            assert updated_sub.plan_id == new_plan.id
            assert updated_sub.daily_usage_count == 0  # Should reset usage
    
    def test_cancel_subscription(self, app, test_user, test_plan):
        """Test canceling subscription"""
        with app.app_context():
            # Create subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            db.session.add(subscription)
            db.session.commit()
            
            # Cancel subscription
            result = SubscriptionService.cancel_subscription(test_user.id)
            
            assert result is True
            
            # Verify status changed
            updated_sub = Subscription.query.filter_by(user_id=test_user.id).first()
            assert updated_sub.status == 'canceled'
    
    def test_reactivate_subscription(self, app, test_user, test_plan):
        """Test reactivating subscription"""
        with app.app_context():
            # Create canceled subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            subscription.status = 'canceled'
            db.session.add(subscription)
            db.session.commit()
            
            # Reactivate subscription
            result = SubscriptionService.reactivate_subscription(test_user.id)
            
            assert result is True
            
            # Verify status changed
            updated_sub = Subscription.query.filter_by(user_id=test_user.id).first()
            assert updated_sub.status == 'active'
    
    def test_check_compression_permission_allowed(self, app, test_user, test_plan):
        """Test compression permission check when allowed"""
        with app.app_context():
            # Create subscription with usage below limit
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            subscription.daily_usage_count = 5  # Below limit of 100
            db.session.add(subscription)
            db.session.commit()
            
            result = SubscriptionService.check_compression_permission(test_user.id)
            
            assert result['can_compress'] is True
            assert result['daily_usage'] == 5
            assert result['daily_limit'] == test_plan.daily_compression_limit
            assert result['plan_name'] == test_plan.name
    
    def test_check_compression_permission_denied(self, app, test_user, test_plan):
        """Test compression permission check when denied"""
        with app.app_context():
            # Create subscription at usage limit
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            subscription.daily_usage_count = test_plan.daily_compression_limit
            db.session.add(subscription)
            db.session.commit()
            
            result = SubscriptionService.check_compression_permission(test_user.id)
            
            assert result['can_compress'] is False
            assert result['reason'] == 'Daily limit exceeded'
            assert result['daily_usage'] == test_plan.daily_compression_limit
    
    def test_increment_usage_success(self, app, test_user, test_plan):
        """Test successful usage increment"""
        with app.app_context():
            # Create subscription with usage below limit
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            subscription.daily_usage_count = 5
            db.session.add(subscription)
            db.session.commit()
            
            result = SubscriptionService.increment_usage(test_user.id)
            
            assert result is True
            
            # Verify usage incremented
            updated_sub = Subscription.query.filter_by(user_id=test_user.id).first()
            assert updated_sub.daily_usage_count == 6
    
    def test_increment_usage_at_limit(self, app, test_user, test_plan):
        """Test usage increment when at limit"""
        with app.app_context():
            # Create subscription at usage limit
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            subscription.daily_usage_count = test_plan.daily_compression_limit
            db.session.add(subscription)
            db.session.commit()
            
            result = SubscriptionService.increment_usage(test_user.id)
            
            assert result is False
            
            # Verify usage not incremented
            updated_sub = Subscription.query.filter_by(user_id=test_user.id).first()
            assert updated_sub.daily_usage_count == test_plan.daily_compression_limit
    
    def test_get_usage_statistics(self, app, test_user, test_plan):
        """Test getting usage statistics"""
        with app.app_context():
            # Create subscription with some usage
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            subscription.daily_usage_count = 25
            db.session.add(subscription)
            db.session.commit()
            
            stats = SubscriptionService.get_usage_statistics(test_user.id)
            
            assert stats['daily_usage'] == 25
            assert stats['daily_limit'] == test_plan.daily_compression_limit
            assert stats['usage_percentage'] == 25.0  # 25/100 * 100
            assert stats['remaining_compressions'] == 75  # 100 - 25
            assert stats['plan_name'] == test_plan.name
            assert stats['is_active'] is True
    
    def test_check_bulk_processing_permission(self, app, test_user):
        """Test bulk processing permission check"""
        with app.app_context():
            # Create plan with bulk processing enabled
            bulk_plan = Plan(
                name='bulk_test_plan',
                display_name='Bulk Test Plan',
                price_monthly=Decimal('19.99'),
                daily_compression_limit=500,
                max_file_size_mb=50,
                bulk_processing=True
            )
            db.session.add(bulk_plan)
            db.session.commit()
            
            # Create subscription
            subscription = Subscription(user_id=test_user.id, plan_id=bulk_plan.id)
            db.session.add(subscription)
            db.session.commit()
            
            result = SubscriptionService.check_bulk_processing_permission(test_user.id)
            assert result is True
    
    def test_check_api_access_permission(self, app, test_user):
        """Test API access permission check"""
        with app.app_context():
            # Create plan with API access enabled
            api_plan = Plan(
                name='api_test_plan',
                display_name='API Test Plan',
                price_monthly=Decimal('29.99'),
                daily_compression_limit=1000,
                max_file_size_mb=100,
                api_access=True
            )
            db.session.add(api_plan)
            db.session.commit()
            
            # Create subscription
            subscription = Subscription(user_id=test_user.id, plan_id=api_plan.id)
            db.session.add(subscription)
            db.session.commit()
            
            result = SubscriptionService.check_api_access_permission(test_user.id)
            assert result is True
    
    def test_get_max_file_size(self, app, test_user, test_plan):
        """Test getting maximum file size"""
        with app.app_context():
            # Create subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            db.session.add(subscription)
            db.session.commit()
            
            max_size = SubscriptionService.get_max_file_size(test_user.id)
            assert max_size == test_plan.max_file_size_mb
    
    def test_get_max_file_size_no_subscription(self, app, test_user):
        """Test getting max file size when user has no subscription"""
        with app.app_context():
            max_size = SubscriptionService.get_max_file_size(test_user.id)
            
            # Should return free plan limit
            free_plan = Plan.query.filter_by(name='free').first()
            expected_size = free_plan.max_file_size_mb if free_plan else 10
            assert max_size == expected_size
    
    def test_validate_subscription_status_valid(self, app, test_user, test_plan):
        """Test subscription status validation for valid subscription"""
        with app.app_context():
            # Create active subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            db.session.add(subscription)
            db.session.commit()
            
            result = SubscriptionService.validate_subscription_status(test_user.id)
            
            assert result['valid'] is True
            assert result['reason'] is None
            assert result['subscription'] is not None
            assert 'permissions' in result
            assert result['permissions']['max_file_size_mb'] == test_plan.max_file_size_mb
    
    def test_validate_subscription_status_invalid(self, app, test_user, test_plan):
        """Test subscription status validation for invalid subscription"""
        with app.app_context():
            # Create canceled subscription
            subscription = Subscription(user_id=test_user.id, plan_id=test_plan.id)
            subscription.status = 'canceled'
            db.session.add(subscription)
            db.session.commit()
            
            result = SubscriptionService.validate_subscription_status(test_user.id)
            
            assert result['valid'] is False
            assert 'canceled' in result['reason']
            assert result['subscription'] is not None
    
    def test_validate_subscription_status_no_subscription(self, app, test_user):
        """Test subscription status validation when no subscription exists"""
        with app.app_context():
            result = SubscriptionService.validate_subscription_status(test_user.id)
            
            assert result['valid'] is False
            assert result['reason'] == 'No subscription found'
            assert result['subscription'] is None


class TestSubscriptionServiceEdgeCases:
    """Test edge cases and error handling for SubscriptionService"""
    
    def test_operations_with_invalid_user_id(self, app):
        """Test service operations with invalid user ID"""
        with app.app_context():
            invalid_user_id = 99999
            
            # All operations should handle invalid user gracefully
            assert SubscriptionService.get_user_subscription(invalid_user_id) is None
            assert SubscriptionService.cancel_subscription(invalid_user_id) is False
            assert SubscriptionService.reactivate_subscription(invalid_user_id) is False
            assert SubscriptionService.increment_usage(invalid_user_id) is False
            
            # Permission checks should return safe defaults
            permission = SubscriptionService.check_compression_permission(invalid_user_id)
            assert permission['can_compress'] is False
            
            assert SubscriptionService.check_bulk_processing_permission(invalid_user_id) is False
            assert SubscriptionService.check_api_access_permission(invalid_user_id) is False
            
            # Should return default file size
            assert SubscriptionService.get_max_file_size(invalid_user_id) == 10
    
    def test_usage_statistics_no_subscription(self, app, test_user):
        """Test usage statistics when user has no subscription"""
        with app.app_context():
            stats = SubscriptionService.get_usage_statistics(test_user.id)
            
            assert stats['daily_usage'] == 0
            assert stats['daily_limit'] == 0
            assert stats['usage_percentage'] == 0
            assert stats['remaining_compressions'] == 0
            assert stats['plan_name'] is None
            assert stats['is_active'] is False