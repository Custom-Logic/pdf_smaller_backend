from .base import db, BaseModel
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import Numeric

class Plan(BaseModel):
    """Subscription plan model"""
    __tablename__ = 'plans'
    
    name = db.Column(db.String(100), unique=True, nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price_monthly = db.Column(Numeric(10, 2), nullable=False)
    price_yearly = db.Column(Numeric(10, 2))
    stripe_price_id_monthly = db.Column(db.String(255))
    stripe_price_id_yearly = db.Column(db.String(255))
    
    # Usage limits
    daily_compression_limit = db.Column(db.Integer, nullable=False, default=0)
    max_file_size_mb = db.Column(db.Integer, nullable=False, default=10)
    bulk_processing = db.Column(db.Boolean, default=False, nullable=False)
    priority_processing = db.Column(db.Boolean, default=False, nullable=False)
    api_access = db.Column(db.Boolean, default=False, nullable=False)
    
    # Relationships
    subscriptions = db.relationship('Subscription', backref='plan')
    
    def to_dict(self):
        """Convert plan to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'display_name': self.display_name,
            'description': self.description,
            'price_monthly': float(self.price_monthly) if self.price_monthly else None,
            'price_yearly': float(self.price_yearly) if self.price_yearly else None,
            'daily_compression_limit': self.daily_compression_limit,
            'max_file_size_mb': self.max_file_size_mb,
            'bulk_processing': self.bulk_processing,
            'priority_processing': self.priority_processing,
            'api_access': self.api_access,
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f'<Plan {self.name}>'

class Subscription(BaseModel):
    """User subscription model"""
    __tablename__ = 'subscriptions'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('plans.id'), nullable=False)
    
    # Stripe integration
    stripe_subscription_id = db.Column(db.String(255), unique=True)
    stripe_customer_id = db.Column(db.String(255))
    
    # Subscription status
    status = db.Column(db.String(50), nullable=False, default='active')  # active, canceled, past_due, unpaid
    billing_cycle = db.Column(db.String(20), nullable=False, default='monthly')  # monthly, yearly
    
    # Billing periods
    current_period_start = db.Column(db.DateTime, nullable=False)
    current_period_end = db.Column(db.DateTime, nullable=False)
    
    # Usage tracking
    daily_usage_count = db.Column(db.Integer, default=0, nullable=False)
    last_usage_reset = db.Column(db.Date, default=datetime.utcnow().date, nullable=False)
    
    def __init__(self, user_id, plan_id, billing_cycle='monthly'):
        self.user_id = user_id
        self.plan_id = plan_id
        self.billing_cycle = billing_cycle
        self.status = 'active'
        
        # Set initial billing period
        now = datetime.utcnow()
        self.current_period_start = now
        
        if billing_cycle == 'yearly':
            self.current_period_end = now + timedelta(days=365)
        else:
            self.current_period_end = now + timedelta(days=30)
    
    def is_active(self):
        """Check if subscription is currently active"""
        return (self.status == 'active' and 
                self.current_period_end > datetime.utcnow())
    
    def reset_daily_usage_if_needed(self):
        """Reset daily usage counter if it's a new day"""
        today = datetime.utcnow().date()
        if self.last_usage_reset < today:
            self.daily_usage_count = 0
            self.last_usage_reset = today
            db.session.commit()
    
    def can_compress(self):
        """Check if user can perform compression based on limits"""
        if not self.is_active():
            return False
        
        self.reset_daily_usage_if_needed()
        return self.daily_usage_count < self.plan.daily_compression_limit
    
    def increment_usage(self):
        """Increment daily usage counter"""
        self.reset_daily_usage_if_needed()
        self.daily_usage_count += 1
        db.session.commit()
    
    def to_dict(self):
        """Convert subscription to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'plan': self.plan.to_dict() if self.plan else None,
            'status': self.status,
            'billing_cycle': self.billing_cycle,
            'current_period_start': self.current_period_start.isoformat(),
            'current_period_end': self.current_period_end.isoformat(),
            'daily_usage_count': self.daily_usage_count,
            'daily_limit': self.plan.daily_compression_limit if self.plan else 0,
            'is_active': self.is_active(),
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f'<Subscription user_id={self.user_id} plan={self.plan.name if self.plan else None}>'