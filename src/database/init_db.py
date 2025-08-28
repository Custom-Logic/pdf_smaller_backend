"""Database initialization and setup utilities"""
from src.models.base import db
from src.models import User, Subscription, Plan, CompressionJob
import logging

logger = logging.getLogger(__name__)

def init_database(app):
    """Initialize database tables and create default data"""
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            logger.info("Database tables created successfully")
            
            # Create default plans if they don't exist
            create_default_plans()
            logger.info("Database initialization completed")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
            raise

def create_default_plans():
    """Create default subscription plans"""
    plans_data = [
        {
            'name': 'free',
            'display_name': 'Free',
            'description': 'Basic PDF compression with daily limits',
            'price_monthly': 0.00,
            'price_yearly': 0.00,
            'daily_compression_limit': 10,
            'max_file_size_mb': 10,
            'bulk_processing': False,
            'priority_processing': False,
            'api_access': False
        },
        {
            'name': 'premium',
            'display_name': 'Premium',
            'description': 'Enhanced compression with bulk processing',
            'price_monthly': 9.99,
            'price_yearly': 99.99,
            'daily_compression_limit': 500,
            'max_file_size_mb': 50,
            'bulk_processing': True,
            'priority_processing': False,
            'api_access': True
        },
        {
            'name': 'pro',
            'display_name': 'Pro',
            'description': 'Unlimited compression with priority processing',
            'price_monthly': 19.99,
            'price_yearly': 199.99,
            'daily_compression_limit': 999999,  # Effectively unlimited
            'max_file_size_mb': 100,
            'bulk_processing': True,
            'priority_processing': True,
            'api_access': True
        }
    ]
    
    for plan_data in plans_data:
        # Check if plan already exists
        existing_plan = Plan.query.filter_by(name=plan_data['name']).first()
        if not existing_plan:
            plan = Plan(**plan_data)
            db.session.add(plan)
            logger.info(f"Created default plan: {plan_data['name']}")
    
    try:
        db.session.commit()
        logger.info("Default plans created successfully")
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create default plans: {str(e)}")
        raise

def create_free_subscription_for_user(user_id):
    """Create a free subscription for a new user"""
    try:
        # Get the free plan
        free_plan = Plan.query.filter_by(name='free').first()
        if not free_plan:
            raise ValueError("Free plan not found. Please run database initialization.")
        
        # Check if user already has a subscription
        existing_subscription = Subscription.query.filter_by(user_id=user_id).first()
        if existing_subscription:
            logger.warning(f"User {user_id} already has a subscription")
            return existing_subscription
        
        # Create free subscription
        subscription = Subscription(user_id=user_id, plan_id=free_plan.id)
        db.session.add(subscription)
        db.session.commit()
        
        logger.info(f"Created free subscription for user {user_id}")
        return subscription
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create free subscription for user {user_id}: {str(e)}")
        raise

def reset_database(app):
    """Reset database - WARNING: This will delete all data"""
    with app.app_context():
        try:
            db.drop_all()
            logger.warning("All database tables dropped")
            
            db.create_all()
            logger.info("Database tables recreated")
            
            create_default_plans()
            logger.info("Database reset completed")
            
        except Exception as e:
            logger.error(f"Database reset failed: {str(e)}")
            raise