"""Unit tests for subscription models"""
import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from src.models import Plan, Subscription, User
from src.models.base import db


class TestPlanModel:
    """Test cases for Plan model"""
    
    def test_plan_creation(self, app):
        """Test creating a new plan"""
        with app.app_context():
            plan = Plan(
                name='test_plan',
                display_name='Test Plan',
                description='A test subscription plan',
                price_monthly=Decimal('9.99'),
                price_yearly=Decimal('99.99'),
                daily_compression_limit=100,
                max_file_size_mb=25,
                bulk_processing=True,
                priority_processing=False,
                api_access=True
            )
            
            db.session.add(plan)
            db.session.commit()
            
            assert plan.id is not None
            assert plan.name == 'test_plan'
            assert plan.display_name == 'Test Plan'
            assert plan.description == 'A test subscription plan'
            assert plan.price_monthly == Decimal('9.99')
            assert plan.price_yearly == Decimal('99.99')
            assert plan.daily_compression_limit == 100
            assert plan.max_file_size_mb == 25
            assert plan.bulk_processing is True
            assert plan.priority_processing is False
            assert plan.api_access is True
            assert plan.created_at is not None
    
    def test_plan_to_dict(self, app):
        """Test plan serialization to dictionary"""
        with app.app_context():
            plan = Plan(
                name='premium_test',
                display_name='Premium Plan',
                description='Premium features',
                price_monthly=Decimal('19.99'),
                daily_compression_limit=500,
                max_file_size_mb=50,
                bulk_processing=True
            )
            
            db.session.add(plan)
            db.session.commit()
            
            plan_dict = plan.to_dict()
            
            assert plan_dict['id'] == plan.id
            assert plan_dict['name'] == 'premium_test'
            assert plan_dict['display_name'] == 'Premium Plan'
            assert plan_dict['description'] == 'Premium features'
            assert plan_dict['price_monthly'] == 19.99
            assert plan_dict['daily_compression_limit'] == 500
            assert plan_dict['max_file_size_mb'] == 50
            assert plan_dict['bulk_processing'] is True
            assert 'created_at' in plan_dict
    
    def test_plan_unique_name_constraint(self, app):
        """Test that plan names must be unique"""
        with app.app_context():
            plan1 = Plan(
                name='duplicate',
                display_name='First Plan',
                price_monthly=Decimal('9.99'),
                daily_compression_limit=100,
                max_file_size_mb=10
            )
            
            plan2 = Plan(
                name='duplicate',
                display_name='Second Plan',
                price_monthly=Decimal('19.99'),
                daily_compression_limit=200,
                max_file_size_mb=20
            )
            
            db.session.add(plan1)
            db.session.commit()
            
            db.session.add(plan2)
            
            with pytest.raises(Exception):  # Should raise integrity error
                db.session.commit()


class TestSubscriptionModel:
    """Test cases for Subscription model"""
    
    def test_subscription_creation(self, app, test_user, test_plan):
        """Test creating a new subscription"""
        with app.app_context():
            subscription = Subscription(
                user_id=test_user.id,
                plan_id=test_plan.id,
                billing_cycle='monthly'
            )
            
            db.session.add(subscription)
            db.session.commit()
            
            assert subscription.id is not None
            assert subscription.user_id == test_user.id
            assert subscription.plan_id == test_plan.id
            assert subscription.status == 'active'
            assert subscription.billing_cycle == 'monthly'
            assert subscription.daily_usage_count == 0
            assert subscription.current_period_start is not None
            assert subscription.current_period_end is not None
            assert subscription.created_at is not None
    
    def test_subscription_yearly_billing_cycle(self, app, test_user, test_plan):
        """Test subscription with yearly billing cycle"""
        with app.app_context():
            subscription = Subscription(
                user_id=test_user.id,
                plan_id=test_plan.id,
                billing_cycle='yearly'
            )
            
            db.session.add(subscription)
            db.session.commit()
            
            # Check that yearly subscription has ~365 day period
            period_length = subscription.current_period_end - subscription.current_period_start
            assert period_length.days >= 365
            assert subscription.billing_cycle == 'yearly'
    
    def test_subscription_is_active(self, app, test_user, test_plan):
        """Test subscription active status checking"""
        with app.app_context():
            # Create active subscription
            subscription = Subscription(
                user_id=test_user.id,
                plan_id=test_plan.id
            )
            db.session.add(subscription)
            db.session.commit()
            
            assert subscription.is_active() is True
            
            # Test expired subscription
            subscription.current_period_end = datetime.utcnow() - timedelta(days=1)
            db.session.commit()
            
            assert subscription.is_active() is False
            
            # Test canceled subscription
            subscription.current_period_end = datetime.utcnow() + timedelta(days=30)
            subscription.status = 'canceled'
            db.session.commit()
            
            assert subscription.is_active() is False
    
    def test_daily_usage_reset(self, app, test_user, test_plan):
        """Test daily usage counter reset functionality"""
        with app.app_context():
            subscription = Subscription(
                user_id=test_user.id,
                plan_id=test_plan.id
            )
            
            # Set usage from yesterday
            subscription.daily_usage_count = 5
            subscription.last_usage_reset = date.today() - timedelta(days=1)
            
            db.session.add(subscription)
            db.session.commit()
            
            # Reset should occur when checking
            subscription.reset_daily_usage_if_needed()
            
            assert subscription.daily_usage_count == 0
            assert subscription.last_usage_reset == date.today()
    
    def test_can_compress_within_limits(self, app, test_user, test_plan):
        """Test compression permission within daily limits"""
        with app.app_context():
            subscription = Subscription(
                user_id=test_user.id,
                plan_id=test_plan.id
            )
            subscription.daily_usage_count = 5  # Below limit of 100
            
            db.session.add(subscription)
            db.session.commit()
            
            assert subscription.can_compress() is True
    
    def test_can_compress_at_limit(self, app, test_user, test_plan):
        """Test compression permission at daily limit"""
        with app.app_context():
            subscription = Subscription(
                user_id=test_user.id,
                plan_id=test_plan.id
            )
            subscription.daily_usage_count = test_plan.daily_compression_limit
            
            db.session.add(subscription)
            db.session.commit()
            
            assert subscription.can_compress() is False
    
    def test_increment_usage(self, app, test_user, test_plan):
        """Test usage counter increment"""
        with app.app_context():
            subscription = Subscription(
                user_id=test_user.id,
                plan_id=test_plan.id
            )
            
            db.session.add(subscription)
            db.session.commit()
            
            initial_count = subscription.daily_usage_count or 0
            subscription.increment_usage()
            
            assert subscription.daily_usage_count == initial_count + 1
    
    def test_subscription_to_dict(self, app, test_user, test_plan):
        """Test subscription serialization to dictionary"""
        with app.app_context():
            subscription = Subscription(
                user_id=test_user.id,
                plan_id=test_plan.id,
                billing_cycle='yearly'
            )
            
            db.session.add(subscription)
            db.session.commit()
            
            sub_dict = subscription.to_dict()
            
            assert sub_dict['id'] == subscription.id
            assert sub_dict['user_id'] == test_user.id
            assert sub_dict['status'] == 'active'
            assert sub_dict['billing_cycle'] == 'yearly'
            assert sub_dict['daily_usage_count'] == 0
            assert sub_dict['daily_limit'] == test_plan.daily_compression_limit
            assert sub_dict['is_active'] is True
            assert 'plan' in sub_dict
            assert 'current_period_start' in sub_dict
            assert 'current_period_end' in sub_dict
            assert 'created_at' in sub_dict
    
    def test_user_unique_subscription_constraint(self, app, test_user, test_plan):
        """Test that users can only have one subscription"""
        with app.app_context():
            subscription1 = Subscription(
                user_id=test_user.id,
                plan_id=test_plan.id
            )
            
            subscription2 = Subscription(
                user_id=test_user.id,
                plan_id=test_plan.id
            )
            
            db.session.add(subscription1)
            db.session.commit()
            
            db.session.add(subscription2)
            
            with pytest.raises(Exception):  # Should raise integrity error
                db.session.commit()
    
    def test_subscription_plan_relationship(self, app, test_user, test_plan):
        """Test subscription-plan relationship"""
        with app.app_context():
            subscription = Subscription(
                user_id=test_user.id,
                plan_id=test_plan.id
            )
            
            db.session.add(subscription)
            db.session.commit()
            
            # Test relationship access
            assert subscription.plan is not None
            assert subscription.plan.id == test_plan.id
            assert subscription.plan.name == test_plan.name
            
            # Test backref
            assert len(test_plan.subscriptions) > 0
            assert any(sub.id == subscription.id for sub in test_plan.subscriptions)
    
    def test_subscription_user_relationship(self, app, test_user, test_plan):
        """Test subscription-user relationship"""
        with app.app_context():
            subscription = Subscription(
                user_id=test_user.id,
                plan_id=test_plan.id
            )
            
            db.session.add(subscription)
            db.session.commit()
            
            # Test relationship access
            assert subscription.user is not None
            assert subscription.user.id == test_user.id
            assert subscription.user.email == test_user.email
            
            # Test backref
            assert test_user.subscription is not None
            assert test_user.subscription.id == subscription.id


class TestSubscriptionValidation:
    """Test subscription model validation and edge cases"""
    
    def test_subscription_status_values(self, app, test_user, test_plan):
        """Test different subscription status values"""
        with app.app_context():
            statuses = ['active', 'canceled', 'past_due', 'unpaid']
            
            for status in statuses:
                subscription = Subscription(
                    user_id=test_user.id,
                    plan_id=test_plan.id
                )
                subscription.status = status
                
                db.session.add(subscription)
                db.session.commit()
                
                assert subscription.status == status
                
                # Clean up for next iteration
                db.session.delete(subscription)
                db.session.commit()
    
    def test_subscription_billing_cycles(self, app, test_user, test_plan):
        """Test different billing cycle values"""
        with app.app_context():
            cycles = ['monthly', 'yearly']
            
            for cycle in cycles:
                subscription = Subscription(
                    user_id=test_user.id,
                    plan_id=test_plan.id,
                    billing_cycle=cycle
                )
                
                db.session.add(subscription)
                db.session.commit()
                
                assert subscription.billing_cycle == cycle
                
                # Verify period length matches billing cycle
                period_length = subscription.current_period_end - subscription.current_period_start
                if cycle == 'yearly':
                    assert period_length.days >= 365
                else:  # monthly
                    assert 28 <= period_length.days <= 31
                
                # Clean up for next iteration
                db.session.delete(subscription)
                db.session.commit()