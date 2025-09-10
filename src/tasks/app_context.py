"""
Push Flask application context into Celery tasks.
Import this module ONCE in tasks.py and forget about the problem.
"""
from flask import has_app_context, current_app
from celery.signals import task_prerun, task_postrun

def _ensure_context(sender, **kwargs):
    """Guarantee app-context for every task."""
    if not has_app_context():
        sender.app.app_context().push()

task_prerun.connect(_ensure_context, weak=False)
task_postrun.connect(lambda **_: None, weak=False)   # pop is automatic