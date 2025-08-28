# Database Setup Guide

This document explains how to set up and manage the database for the PDF Smaller backend.

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Initialize the database:**
   ```bash
   python manage_db.py init
   ```

3. **Check database status:**
   ```bash
   python manage_db.py status
   ```

## Database Models

The application includes the following database models:

### User Model
- Stores user account information
- Handles password hashing and verification
- Relationships with subscriptions and compression jobs

### Plan Model
- Defines subscription plans (Free, Premium, Pro)
- Stores pricing and usage limits
- Default plans are created automatically

### Subscription Model
- Links users to their subscription plans
- Tracks usage and billing periods
- Handles usage limit enforcement

### CompressionJob Model
- Tracks PDF compression operations
- Stores job status and progress
- Links to user accounts

## Database Management Commands

The `manage_db.py` script provides several commands for database management:

### Initialize Database
```bash
python manage_db.py init
```
Creates all tables and default subscription plans.

### Check Status
```bash
python manage_db.py status
```
Shows database connection status and record counts.

### Reset Database (⚠️ Destructive)
```bash
python manage_db.py reset
```
Drops all tables and recreates them with default data.

### Create Default Plans
```bash
python manage_db.py create-plans
```
Creates the default subscription plans if they don't exist.

## Default Subscription Plans

The system creates three default plans:

### Free Plan
- 10 compressions per day
- 10MB max file size
- Single file processing only
- No API access

### Premium Plan
- 500 compressions per day
- 50MB max file size
- Bulk processing enabled
- API access included
- $9.99/month or $99.99/year

### Pro Plan
- Unlimited compressions
- 100MB max file size
- Bulk processing enabled
- Priority processing
- API access included
- $19.99/month or $199.99/year

## Configuration

Database configuration is handled in `src/config/config.py`:

```python
# Database settings
SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///pdf_smaller.db')
SQLALCHEMY_TRACK_MODIFICATIONS = False
```

### Environment Variables

- `DATABASE_URL`: Database connection string (defaults to SQLite)
- `SECRET_KEY`: Application secret key
- `JWT_SECRET_KEY`: JWT token signing key

## Testing

Run the database test suite:

```bash
python test_db_setup.py
```

This tests all models, relationships, and basic functionality.

## Production Setup

For production deployment:

1. Set `DATABASE_URL` to your PostgreSQL connection string
2. Set secure values for `SECRET_KEY` and `JWT_SECRET_KEY`
3. Run database initialization:
   ```bash
   python manage_db.py init
   ```

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure all dependencies are installed
2. **Permission errors**: Check file permissions for SQLite database
3. **Connection errors**: Verify DATABASE_URL is correct for your setup

### Logs

Database operations are logged using Python's logging module. Check application logs for detailed error information.