#!/usr/bin/env python3
"""Database management CLI script"""
import click
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask
from flask_jwt_extended import JWTManager
from src.config import Config
from src.database import init_database, create_default_plans
from src.models.base import db

@click.group()
def cli():
    """Database management commands"""
    pass

def create_db_app():
    """Create minimal app for database operations"""
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize extensions
    db.init_app(app)
    jwt = JWTManager(app)
    
    return app

@cli.command()
def init():
    """Initialize database with tables and default data"""
    app = create_db_app()
    with app.app_context():
        try:
            init_database(app)
            click.echo("✅ Database initialized successfully")
        except Exception as e:
            click.echo(f"❌ Database initialization failed: {str(e)}")
            sys.exit(1)

@cli.command()
def reset():
    """Reset database (WARNING: This will delete all data)"""
    if click.confirm('This will delete all data. Are you sure?'):
        app = create_db_app()
        with app.app_context():
            try:
                from src.database.init_db import reset_database
                reset_database(app)
                click.echo("✅ Database reset successfully")
            except Exception as e:
                click.echo(f"❌ Database reset failed: {str(e)}")
                sys.exit(1)

@cli.command()
def create_plans():
    """Create default subscription plans"""
    app = create_db_app()
    with app.app_context():
        try:
            create_default_plans()
            click.echo("✅ Default plans created successfully")
        except Exception as e:
            click.echo(f"❌ Failed to create default plans: {str(e)}")
            sys.exit(1)

@cli.command()
def migrate():
    """Create a new migration"""
    message = click.prompt('Migration message', default='Auto migration')
    app = create_db_app()
    with app.app_context():
        try:
            from src.database.migrations import create_migration
            create_migration(message)
            click.echo(f"✅ Migration created: {message}")
        except Exception as e:
            click.echo(f"❌ Migration creation failed: {str(e)}")
            sys.exit(1)

@cli.command()
def upgrade():
    """Apply pending migrations"""
    app = create_db_app()
    with app.app_context():
        try:
            from src.database.migrations import upgrade_database
            upgrade_database()
            click.echo("✅ Database upgraded successfully")
        except Exception as e:
            click.echo(f"❌ Database upgrade failed: {str(e)}")
            sys.exit(1)

@cli.command()
@click.option('--revision', '-r', default='-1', help='Revision to downgrade to')
def downgrade(revision):
    """Downgrade database to previous revision"""
    app = create_db_app()
    with app.app_context():
        try:
            from src.database.migrations import downgrade_database
            downgrade_database(revision)
            click.echo(f"✅ Database downgraded to revision: {revision}")
        except Exception as e:
            click.echo(f"❌ Database downgrade failed: {str(e)}")
            sys.exit(1)

@cli.command()
def status():
    """Show database status"""
    app = create_db_app()
    with app.app_context():
        try:
            # Initialize database first
            init_database(app)
            
            # Check database connection
            from sqlalchemy import text
            db.session.execute(text('SELECT 1'))
            click.echo("✅ Database connection: OK")
            
            # Check tables
            from src.models import User, Subscription, Plan, CompressionJob
            
            user_count = User.query.count()
            plan_count = Plan.query.count()
            subscription_count = Subscription.query.count()
            job_count = CompressionJob.query.count()
            
            click.echo(f"📊 Database Statistics:")
            click.echo(f"   Users: {user_count}")
            click.echo(f"   Plans: {plan_count}")
            click.echo(f"   Subscriptions: {subscription_count}")
            click.echo(f"   Compression Jobs: {job_count}")
            
        except Exception as e:
            click.echo(f"❌ Database status check failed: {str(e)}")
            sys.exit(1)

if __name__ == '__main__':
    cli()