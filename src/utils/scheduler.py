"""Scheduler utilities for background tasks and cleanup operations"""
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, Any

from flask import Flask

from src.services.cleanup_service import CleanupService

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Simple task scheduler for running periodic cleanup operations"""
    
    def __init__(self):
        self.tasks = {}
        self.running = False
        self.thread = None
    
    def add_task(self, name: str, func: Callable, interval_hours: int):
        """Add a periodic task to the scheduler"""
        self.tasks[name] = {
            'function': func,
            'interval_hours': interval_hours,
            'last_run': None,
            'next_run': datetime.utcnow()
        }
        logger.info(f"Added scheduled task: {name} (every {interval_hours} hours)")
    
    def start(self):
        """Start the scheduler in a background thread"""
        if self.running:
            logger.warning("Scheduler is already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        logger.info("Task scheduler started")
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("Task scheduler stopped")
    
    def _run_scheduler(self):
        """Main scheduler loop"""
        while self.running:
            try:
                current_time = datetime.utcnow()
                
                for task_name, task_info in self.tasks.items():
                    if current_time >= task_info['next_run']:
                        try:
                            logger.info(f"Running scheduled task: {task_name}")
                            result = task_info['function']()
                            
                            # Update task timing
                            task_info['last_run'] = current_time
                            task_info['next_run'] = current_time + timedelta(hours=task_info['interval_hours'])
                            
                            logger.info(f"Completed scheduled task: {task_name}")
                            if isinstance(result, dict) and 'jobs_cleaned' in result:
                                logger.info(f"Task {task_name} result: {result}")
                            
                        except Exception as e:
                            logger.error(f"Error running scheduled task {task_name}: {str(e)}")
                            # Still update next run time to avoid continuous failures
                            task_info['next_run'] = current_time + timedelta(hours=task_info['interval_hours'])
                
                # Sleep for 1 minute before checking again
                time.sleep(60)
                
            except Exception as e:
                logger.error(f"Error in scheduler loop: {str(e)}")
                time.sleep(60)  # Continue after error
    
    def get_task_status(self) -> Dict[str, Any]:
        """Get status of all scheduled tasks"""
        status = {
            'running': self.running,
            'tasks': {}
        }
        
        current_time = datetime.utcnow()
        
        for task_name, task_info in self.tasks.items():
            status['tasks'][task_name] = {
                'interval_hours': task_info['interval_hours'],
                'last_run': task_info['last_run'].isoformat() if task_info['last_run'] else None,
                'next_run': task_info['next_run'].isoformat(),
                'minutes_until_next_run': int((task_info['next_run'] - current_time).total_seconds() / 60)
            }
        
        return status


# Global scheduler instance
scheduler = TaskScheduler()


def setup_cleanup_scheduler(upload_folder: str, app: Flask):
    """Set up the cleanup scheduler with default tasks"""
    with app.app_context():
        def cleanup_expired_jobs():
            """Wrapper for expired jobs cleanup"""
            return CleanupService.cleanup_expired_jobs()

        def cleanup_temp_files():
            """Wrapper for temp files cleanup"""
            return CleanupService.cleanup_temp_files(upload_folder)
    
        # Add cleanup tasks
        scheduler.add_task('cleanup_expired_jobs', cleanup_expired_jobs, interval_hours=6)  # Every 6 hours
        scheduler.add_task('cleanup_temp_files', cleanup_temp_files, interval_hours=1)      # Every hour

        return scheduler


def start_background_scheduler(upload_folder: str, app: Flask):
    """Start the background scheduler with cleanup tasks"""
    try:
        setup_cleanup_scheduler(upload_folder, app)
        scheduler.start()
        logger.info("Background cleanup scheduler started successfully")
    except Exception as e:
        logger.error(f"Failed to start background scheduler: {str(e)}")


def stop_background_scheduler():
    """Stop the background scheduler"""
    try:
        scheduler.stop()
        logger.info("Background cleanup scheduler stopped successfully")
    except Exception as e:
        logger.error(f"Error stopping background scheduler: {str(e)}")