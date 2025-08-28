"""Cleanup service for managing file retention and job cleanup policies"""
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.models import CompressionJob
from src.models.base import db

logger = logging.getLogger(__name__)


class CleanupService:
    """Service for managing file cleanup and job retention policies"""
    
    # Default retention periods (in hours)
    DEFAULT_RETENTION_PERIODS = {
        'free': 24,      # 1 day for free users
        'premium': 168,  # 7 days for premium users
        'pro': 720       # 30 days for pro users
    }
    
    # File cleanup settings
    TEMP_FILE_MAX_AGE_HOURS = 1  # Clean up temp files after 1 hour
    FAILED_JOB_RETENTION_HOURS = 24  # Keep failed jobs for 24 hours
    
    @staticmethod
    def cleanup_expired_jobs() -> Dict[str, Any]:
        """
        Clean up expired compression jobs and their associated files
        Returns summary of cleanup operations
        """
        cleanup_summary = {
            'jobs_cleaned': 0,
            'files_deleted': 0,
            'errors': [],
            'total_space_freed_mb': 0
        }
        
        try:
            # Get all jobs that need cleanup
            expired_jobs = CleanupService._get_expired_jobs()
            
            for job in expired_jobs:
                try:
                    space_freed = CleanupService._cleanup_job_files(job)
                    cleanup_summary['total_space_freed_mb'] += space_freed
                    
                    # Delete the job record
                    db.session.delete(job)
                    cleanup_summary['jobs_cleaned'] += 1
                    
                except Exception as e:
                    error_msg = f"Error cleaning up job {job.id}: {str(e)}"
                    logger.error(error_msg)
                    cleanup_summary['errors'].append(error_msg)
            
            # Commit all deletions
            db.session.commit()
            
            logger.info(f"Cleanup completed: {cleanup_summary['jobs_cleaned']} jobs cleaned, "
                       f"{cleanup_summary['total_space_freed_mb']:.2f}MB freed")
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Error during cleanup process: {str(e)}"
            logger.error(error_msg)
            cleanup_summary['errors'].append(error_msg)
        
        return cleanup_summary
    
    @staticmethod
    def _get_expired_jobs() -> List[CompressionJob]:
        """Get all jobs that have expired based on retention policies"""
        try:
            expired_jobs = []
            
            # Get jobs older than retention period based on user plan
            for plan_name, retention_hours in CleanupService.DEFAULT_RETENTION_PERIODS.items():
                cutoff_time = datetime.utcnow() - timedelta(hours=retention_hours)
                
                # Query jobs for users with this plan that are older than cutoff
                jobs = db.session.query(CompressionJob)\
                    .join(CompressionJob.user)\
                    .join('subscription')\
                    .join('plan')\
                    .filter(CompressionJob.created_at < cutoff_time)\
                    .filter(db.text("plans.name = :plan_name"))\
                    .params(plan_name=plan_name)\
                    .all()
                
                expired_jobs.extend(jobs)
            
            # Also get failed jobs older than 24 hours regardless of plan
            failed_cutoff = datetime.utcnow() - timedelta(hours=CleanupService.FAILED_JOB_RETENTION_HOURS)
            failed_jobs = CompressionJob.query\
                .filter(CompressionJob.status == 'failed')\
                .filter(CompressionJob.created_at < failed_cutoff)\
                .all()
            
            expired_jobs.extend(failed_jobs)
            
            # Remove duplicates
            unique_jobs = list({job.id: job for job in expired_jobs}.values())
            
            return unique_jobs
            
        except Exception as e:
            logger.error(f"Error getting expired jobs: {str(e)}")
            return []
    
    @staticmethod
    def _cleanup_job_files(job: CompressionJob) -> float:
        """
        Clean up files associated with a compression job
        Returns space freed in MB
        """
        space_freed_mb = 0
        files_deleted = 0
        
        try:
            # List of file paths to clean up
            file_paths = []
            
            if job.input_path and os.path.exists(job.input_path):
                file_paths.append(job.input_path)
            
            if job.result_path and os.path.exists(job.result_path):
                file_paths.append(job.result_path)
            
            # Delete files and calculate space freed
            for file_path in file_paths:
                try:
                    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    os.remove(file_path)
                    space_freed_mb += file_size_mb
                    files_deleted += 1
                    logger.debug(f"Deleted file: {file_path} ({file_size_mb:.2f}MB)")
                    
                except Exception as e:
                    logger.warning(f"Could not delete file {file_path}: {str(e)}")
            
            if files_deleted > 0:
                logger.info(f"Cleaned up {files_deleted} files for job {job.id}, "
                           f"freed {space_freed_mb:.2f}MB")
            
        except Exception as e:
            logger.error(f"Error cleaning up files for job {job.id}: {str(e)}")
        
        return space_freed_mb
    
    @staticmethod
    def cleanup_temp_files(upload_folder: str) -> Dict[str, Any]:
        """
        Clean up temporary files older than specified age
        """
        cleanup_summary = {
            'files_deleted': 0,
            'space_freed_mb': 0,
            'errors': []
        }
        
        try:
            if not os.path.exists(upload_folder):
                return cleanup_summary
            
            cutoff_time = datetime.utcnow() - timedelta(hours=CleanupService.TEMP_FILE_MAX_AGE_HOURS)
            
            for filename in os.listdir(upload_folder):
                file_path = os.path.join(upload_folder, filename)
                
                try:
                    # Check if file is old enough to delete
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_mtime < cutoff_time:
                        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                        os.remove(file_path)
                        cleanup_summary['files_deleted'] += 1
                        cleanup_summary['space_freed_mb'] += file_size_mb
                        logger.debug(f"Deleted temp file: {file_path}")
                
                except Exception as e:
                    error_msg = f"Error deleting temp file {file_path}: {str(e)}"
                    logger.warning(error_msg)
                    cleanup_summary['errors'].append(error_msg)
            
            if cleanup_summary['files_deleted'] > 0:
                logger.info(f"Temp cleanup: {cleanup_summary['files_deleted']} files deleted, "
                           f"{cleanup_summary['space_freed_mb']:.2f}MB freed")
            
        except Exception as e:
            error_msg = f"Error during temp file cleanup: {str(e)}"
            logger.error(error_msg)
            cleanup_summary['errors'].append(error_msg)
        
        return cleanup_summary
    
    @staticmethod
    def get_cleanup_statistics() -> Dict[str, Any]:
        """Get statistics about jobs and files that can be cleaned up"""
        try:
            stats = {
                'total_jobs': 0,
                'expired_jobs': 0,
                'failed_jobs': 0,
                'estimated_space_to_free_mb': 0,
                'jobs_by_status': {},
                'jobs_by_age': {}
            }
            
            # Get total job count
            stats['total_jobs'] = CompressionJob.query.count()
            
            # Get job counts by status
            status_counts = db.session.query(
                CompressionJob.status,
                db.func.count(CompressionJob.id)
            ).group_by(CompressionJob.status).all()
            
            for status, count in status_counts:
                stats['jobs_by_status'][status] = count
            
            # Get expired jobs
            expired_jobs = CleanupService._get_expired_jobs()
            stats['expired_jobs'] = len(expired_jobs)
            
            # Calculate estimated space to free
            for job in expired_jobs:
                if job.original_size_bytes:
                    stats['estimated_space_to_free_mb'] += job.original_size_bytes / (1024 * 1024)
                if job.compressed_size_bytes:
                    stats['estimated_space_to_free_mb'] += job.compressed_size_bytes / (1024 * 1024)
            
            # Get jobs by age categories
            now = datetime.utcnow()
            age_categories = {
                'less_than_1_day': timedelta(days=1),
                'less_than_1_week': timedelta(days=7),
                'less_than_1_month': timedelta(days=30),
                'older_than_1_month': None
            }
            
            for category, age_limit in age_categories.items():
                if age_limit:
                    cutoff = now - age_limit
                    if category == 'less_than_1_day':
                        count = CompressionJob.query.filter(CompressionJob.created_at >= cutoff).count()
                    else:
                        prev_cutoff = now - list(age_categories.values())[list(age_categories.keys()).index(category) - 1]
                        count = CompressionJob.query.filter(
                            CompressionJob.created_at >= cutoff,
                            CompressionJob.created_at < prev_cutoff
                        ).count()
                else:
                    # Older than 1 month
                    cutoff = now - timedelta(days=30)
                    count = CompressionJob.query.filter(CompressionJob.created_at < cutoff).count()
                
                stats['jobs_by_age'][category] = count
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cleanup statistics: {str(e)}")
            return {
                'error': str(e),
                'total_jobs': 0,
                'expired_jobs': 0,
                'estimated_space_to_free_mb': 0
            }
    
    @staticmethod
    def force_cleanup_user_jobs(user_id: int) -> Dict[str, Any]:
        """
        Force cleanup of all jobs for a specific user (e.g., when user deletes account)
        """
        cleanup_summary = {
            'jobs_cleaned': 0,
            'files_deleted': 0,
            'space_freed_mb': 0,
            'errors': []
        }
        
        try:
            user_jobs = CompressionJob.query.filter_by(user_id=user_id).all()
            
            for job in user_jobs:
                try:
                    space_freed = CleanupService._cleanup_job_files(job)
                    cleanup_summary['space_freed_mb'] += space_freed
                    
                    db.session.delete(job)
                    cleanup_summary['jobs_cleaned'] += 1
                    
                except Exception as e:
                    error_msg = f"Error cleaning up job {job.id} for user {user_id}: {str(e)}"
                    logger.error(error_msg)
                    cleanup_summary['errors'].append(error_msg)
            
            db.session.commit()
            
            logger.info(f"Force cleanup for user {user_id}: {cleanup_summary['jobs_cleaned']} jobs cleaned")
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Error during force cleanup for user {user_id}: {str(e)}"
            logger.error(error_msg)
            cleanup_summary['errors'].append(error_msg)
        
        return cleanup_summary