# Database Setup Guide

This document explains how to set up and manage the SQLite database for the PDF Smaller backend.

**Database Technology**: SQLite (used for both development and production)
**Storage**: Local disk storage by design
**Dependencies**: No external database server required

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
# Database settings - SQLite only
SQLALCHEMY_DATABASE_URI = "sqlite:////root/app/pdf_smaller_backend/pdf_smaller_dev.db"
SQLALCHEMY_TRACK_MODIFICATIONS = False
```

### Environment Variables

- `DATABASE_URL`: SQLite database file path (optional override)
- `SECRET_KEY`: Application secret key
- `REDIS_URL`: Redis connection for task queue

## Testing

Run the database test suite:

```bash
python test_db_setup.py
```

This tests all models, relationships, and basic functionality.

## Production Setup

For production deployment:

1. SQLite database is used by default (no external database server needed)
2. Set secure values for `SECRET_KEY`
3. Ensure proper file permissions for SQLite database file
4. Run database initialization:
   ```bash
   python manage_db.py init
   ```

### SQLite Production Considerations

- SQLite handles concurrent reads efficiently for this application
- Database file should be on persistent storage
- Regular backups of the SQLite file are recommended
- No database server maintenance required

## Troubleshooting

### Common Issues

1. **Import errors**: Make sure all dependencies are installed
2. **Permission errors**: Check file permissions for SQLite database file and directory
3. **Database locked**: Ensure no other processes are accessing the SQLite file
4. **Disk space**: Verify sufficient disk space for SQLite database growth

### Logs

Database operations are logged using Python's logging module. Check application logs for detailed error information.