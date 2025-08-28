#!/usr/bin/env python3
"""Test script to verify database setup"""
import os
import sys
import tempfile

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_jwt_extended import JWTManager
from src.models.base import db
from src.models import User, Subscription, Plan, CompressionJob
from src.database import create_free_subscription_for_user

class TestConfig:
    """Test configuration"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret-key'
    JWT_SECRET_KEY = 'test-jwt-secret'

def test_database_setup():
    """Test database models and relationships"""
    print("🧪 Testing database setup...")
    
    # Create test app with in-memory database
    app = Flask(__name__)
    app.config.from_object(TestConfig)
    
    # Initialize extensions
    db.init_app(app)
    jwt = JWTManager(app)
    
    with app.app_context():
        try:
            # Initialize database
            db.create_all()
            
            # Create default plans
            from src.database.init_db import create_default_plans
            create_default_plans()
            
            # Test 1: Check if tables are created
            print("✅ Database tables created successfully")
            
            # Test 2: Check if default plans exist
            plans = Plan.query.all()
            assert len(plans) == 3, f"Expected 3 plans, got {len(plans)}"
            print(f"✅ Default plans created: {[p.name for p in plans]}")
            
            # Test 3: Create a test user
            user = User(
                email="test@example.com",
                password="testpassword123",
                name="Test User"
            )
            db.session.add(user)
            db.session.commit()
            print("✅ User creation successful")
            
            # Test 4: Test password hashing
            assert user.check_password("testpassword123"), "Password verification failed"
            assert not user.check_password("wrongpassword"), "Password should not match"
            print("✅ Password hashing and verification working")
            
            # Test 5: Create free subscription for user
            subscription = create_free_subscription_for_user(user.id)
            assert subscription is not None, "Failed to create subscription"
            assert subscription.plan.name == 'free', "Subscription should be free plan"
            print("✅ Free subscription creation successful")
            
            # Test 6: Test subscription usage tracking
            assert subscription.can_compress(), "User should be able to compress"
            subscription.increment_usage()
            assert subscription.daily_usage_count == 1, "Usage count should be 1"
            print("✅ Usage tracking working")
            
            # Test 7: Create a compression job
            job = CompressionJob(
                user_id=user.id,
                job_type='single',
                original_filename='test.pdf',
                settings={'quality': 'medium'}
            )
            db.session.add(job)
            db.session.commit()
            
            assert job.get_settings()['quality'] == 'medium', "Settings not stored correctly"
            assert job.get_progress_percentage() == 0, "Initial progress should be 0"
            print("✅ Compression job creation successful")
            
            # Test 8: Test job status updates
            job.mark_as_processing()
            assert job.status == 'processing', "Job status should be processing"
            
            job.mark_as_completed()
            assert job.status == 'completed', "Job status should be completed"
            assert job.is_successful(), "Job should be marked as successful"
            print("✅ Job status tracking working")
            
            # Test 9: Test relationships
            user_jobs = user.compression_jobs
            assert len(user_jobs) == 1, "User should have 1 job"
            assert user_jobs[0].id == job.id, "Job relationship incorrect"
            print("✅ Database relationships working")
            
            # Test 10: Test serialization
            user_dict = user.to_dict()
            assert 'password_hash' not in user_dict, "Password hash should not be in dict"
            assert user_dict['email'] == 'test@example.com', "Email not serialized correctly"
            
            subscription_dict = subscription.to_dict()
            assert 'plan' in subscription_dict, "Plan should be in subscription dict"
            
            job_dict = job.to_dict()
            assert job_dict['status'] == 'completed', "Job status not serialized correctly"
            print("✅ Model serialization working")
            
            print("\n🎉 All database tests passed successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ Database test failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

if __name__ == '__main__':
    success = test_database_setup()
    sys.exit(0 if success else 1)