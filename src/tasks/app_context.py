"""Flask application context handling for Celery tasks.
This module is imported by tasks.py but context is now handled
by the ContextTask class in celery_app.py make_celery() function.
"""
# Context handling is now done via ContextTask class in make_celery()
# when Flask app is properly passed to make_celery(app)
pass