#!/usr/bin/env python3
"""
Setup script for PDF Smaller backend application
"""
import os
import sys
import secrets
import subprocess
from pathlib import Path

def generate_secret_key(length=64):
    """Generate a secure random secret key"""
    return secrets.token_urlsafe(length)

def create_env_file():
    """Create .env file from .env.example if it doesn't exist"""
    env_example = Path('.env.example')
    env_file = Path('.env')
    
    if env_file.exists():
        print("✓ .env file already exists")
        return
    
    if not env_example.exists():
        print("✗ .env.example file not found")
        return
    
    # Read example file
    with open(env_example, 'r') as f:
        content = f.read()
    
    # Generate secure keys
    secret_key = generate_secret_key()
    jwt_secret_key = generate_secret_key()
    
    # Replace placeholder values
    content = content.replace(
        'your-super-secret-key-change-this-in-production-make-it-at-least-32-characters',
        secret_key
    )
    content = content.replace(
        'your-jwt-secret-key-change-this-too',
        jwt_secret_key
    )
    
    # Write .env file
    with open(env_file, 'w') as f:
        f.write(content)
    
    print("✓ Created .env file with secure random keys")

def install_dependencies():
    """Install Python dependencies"""
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                      check=True)
        print("✓ Python dependencies installed")
    except subprocess.CalledProcessError:
        print("✗ Failed to install Python dependencies")
        return False
    return True

def setup_database():
    """Initialize database"""
    try:
        # Import after dependencies are installed
        from flask import Flask
        from src.main.main import create_app
        from src.models.base import db
        
        app = create_app('development')
        
        with app.app_context():
            # Create all tables
            db.create_all()
            print("✓ Database tables created")
            
            # Run any initial data setup
            setup_initial_data(db)
            
    except Exception as e:
        print(f"✗ Database setup failed: {e}")
        return False
    return True

def setup_initial_data(db):
    """Setup initial data like subscription plans"""
    try:
        from src.models.subscription import Plan
        
        # Check if plans already exist
        if Plan.query.first():
            print("✓ Subscription plans already exist")
            return
        
        # Create default subscription plans
        plans = [
            Plan(
                name='Free',
                stripe_price_id='price_free',
                price=0,
                compressions_per_day=10,
                max_file_size=10 * 1024 * 1024,  # 10MB
                bulk_processing=False,
                priority_processing=False
            ),
            Plan(
                name='Premium',
                stripe_price_id='price_premium',
                price=999,  # $9.99
                compressions_per_day=500,
                max_file_size=50 * 1024 * 1024,  # 50MB
                bulk_processing=True,
                priority_processing=False
            ),
            Plan(
                name='Pro',
                stripe_price_id='price_pro',
                price=1999,  # $19.99
                compressions_per_day=-1,  # Unlimited
                max_file_size=100 * 1024 * 1024,  # 100MB
                bulk_processing=True,
                priority_processing=True
            )
        ]
        
        for plan in plans:
            db.session.add(plan)
        
        db.session.commit()
        print("✓ Default subscription plans created")
        
    except Exception as e:
        print(f"✗ Failed to create initial data: {e}")

def create_directories():
    """Create necessary directories"""
    directories = [
        'uploads',
        'logs',
        'instance'
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    
    print("✓ Created necessary directories")

def check_system_dependencies():
    """Check if system dependencies are installed"""
    dependencies = {
        'ghostscript': ['gs', '--version'],
        'redis': ['redis-cli', '--version']
    }
    
    missing = []
    
    for name, command in dependencies.items():
        try:
            subprocess.run(command, capture_output=True, check=True)
            print(f"✓ {name} is installed")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print(f"✗ {name} is not installed")
            missing.append(name)
    
    if missing:
        print("\nPlease install the following system dependencies:")
        for dep in missing:
            if dep == 'ghostscript':
                print("  - Ghostscript: apt-get install ghostscript (Ubuntu/Debian) or brew install ghostscript (macOS)")
            elif dep == 'redis':
                print("  - Redis: apt-get install redis-server (Ubuntu/Debian) or brew install redis (macOS)")
        return False
    
    return True

def main():
    """Main setup function"""
    print("PDF Smaller Backend Setup")
    print("=" * 30)
    
    # Change to script directory
    script_dir = Path(__file__).parent.parent
    os.chdir(script_dir)
    
    # Check system dependencies
    if not check_system_dependencies():
        print("\n✗ Setup failed: Missing system dependencies")
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    # Create .env file
    create_env_file()
    
    # Install Python dependencies
    if not install_dependencies():
        print("\n✗ Setup failed: Could not install Python dependencies")
        sys.exit(1)
    
    # Setup database
    if not setup_database():
        print("\n✗ Setup failed: Database setup failed")
        sys.exit(1)
    
    print("\n" + "=" * 30)
    print("✓ Setup completed successfully!")
    print("\nNext steps:")
    print("1. Review and update .env file with your configuration")
    print("2. Start Redis server: redis-server")
    print("3. Run the application: python app.py")
    print("4. Or use Docker: docker-compose -f docker-compose.dev.yml up")

if __name__ == '__main__':
    main()