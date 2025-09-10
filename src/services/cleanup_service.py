"""Cleanup service for managing file retention and job cleanup policies"""
import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from src.models import Job, JobStatus
from src.models.base import db

logger = logging.getLogger(__name__)


class CleanupService:
    """Service for managing file cleanup and job retention policies"""

    # Default retention periods (in hours) - now job-based instead of user-based
    DEFAULT_RETENTION_PERIODS = {
        'completed': 24,  # 1 day for completed jobs
        'failed': 24,  # 1 day for failed jobs
        'pending': 1,  # 1 hour for pending jobs (shouldn't stay pending long)
        'processing': 4  # 4 hours for processing jobs (should complete by then)
    }

    # File cleanup settings
    TEMP_FILE_MAX_AGE_HOURS = 1  # Clean up temp files after 1 hour

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
                    error_msg = f"Error cleaning up job {job.job_id}: {str(e)}"
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
    def _get_expired_jobs() -> List[Job]:
        """Get all jobs that have expired based on retention policies"""
        try:
            expired_jobs = []

            # Get jobs older than retention period based on status
            for status, retention_hours in CleanupService.DEFAULT_RETENTION_PERIODS.items():
                cutoff_time = datetime.utcnow() - timedelta(hours=retention_hours)

                # Query jobs with this status that are older than cutoff
                jobs = Job.query \
                    .filter(Job.status == status) \
                    .filter(Job.created_at < cutoff_time) \
                    .all()

                expired_jobs.extend(jobs)

            # Remove duplicates (in case a job matches multiple criteria)
            unique_jobs = list({job.job_id: job for job in expired_jobs}.values())

            return unique_jobs

        except Exception as e:
            logger.error(f"Error getting expired jobs: {str(e)}")
            return []

    @staticmethod
    def _cleanup_job_files(job: Job) -> float:
        """
        Clean up files associated with a compression job
        Returns space freed in MB
        """
        space_freed_mb = 0
        files_deleted = 0

        try:
            # List of file paths to clean up
            file_paths = []

            # Check result data for file paths
            if job.result and isinstance(job.result, dict):
                # Check for various possible file path fields in result
                for path_key in ['output_path', 'result_path', 'file_path', 'temp_path']:
                    if path_key in job.result and job.result[path_key]:
                        file_path = job.result[path_key]
                        if os.path.exists(file_path):
                            file_paths.append(file_path)

                # Check for temp_files array
                if 'temp_files' in job.result and isinstance(job.result['temp_files'], list):
                    for temp_file in job.result['temp_files']:
                        if os.path.exists(temp_file):
                            file_paths.append(temp_file)

            # Check input data for file paths
            if job.input_data and isinstance(job.input_data, dict):
                for path_key in ['input_path', 'upload_path', 'original_path']:
                    if path_key in job.input_data and job.input_data[path_key]:
                        file_path = job.input_data[path_key]
                        if os.path.exists(file_path):
                            file_paths.append(file_path)

            # Remove duplicates
            file_paths = list(set(file_paths))

            # Delete files and calculate space freed
            for file_path in file_paths:
                try:
                    if os.path.exists(file_path):
                        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                        os.remove(file_path)
                        space_freed_mb += file_size_mb
                        files_deleted += 1
                        logger.debug(f"Deleted file: {file_path} ({file_size_mb:.2f}MB)")

                except Exception as e:
                    logger.warning(f"Could not delete file {file_path}: {str(e)}")

            if files_deleted > 0:
                logger.info(f"Cleaned up {files_deleted} files for job {job.job_id}, "
                            f"freed {space_freed_mb:.2f}MB")

        except Exception as e:
            logger.error(f"Error cleaning up files for job {job.job_id}: {str(e)}")

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
                    # Skip directories
                    if os.path.isdir(file_path):
                        continue

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
            stats['total_jobs'] = Job.query.count()

            # Get job counts by status
            status_counts = db.session.query(
                Job.status,
                db.func.count(Job.job_id)
            ).group_by(Job.status).all()

            for status, count in status_counts:
                stats['jobs_by_status'][status] = count

            # Get expired jobs
            expired_jobs = CleanupService._get_expired_jobs()
            stats['expired_jobs'] = len(expired_jobs)

            # Calculate estimated space to free
            for job in expired_jobs:
                # Try to estimate file sizes from input_data and result
                if job.input_data and isinstance(job.input_data, dict):
                    if 'file_size' in job.input_data:
                        stats['estimated_space_to_free_mb'] += job.input_data['file_size'] / (1024 * 1024)
                    elif 'total_size' in job.input_data:
                        stats['estimated_space_to_free_mb'] += job.input_data['total_size'] / (1024 * 1024)

            # Get jobs by age categories
            now = datetime.utcnow()
            age_categories = {
                'less_than_1_hour': timedelta(hours=1),
                'less_than_1_day': timedelta(days=1),
                'less_than_1_week': timedelta(days=7),
                'older_than_1_week': None
            }

            for category, age_limit in age_categories.items():
                if age_limit:
                    cutoff = now - age_limit
                    if category == 'less_than_1_hour':
                        count = Job.query.filter(Job.created_at >= cutoff).count()
                    else:
                        # Get the previous category's time limit
                        category_keys = list(age_categories.keys())
                        prev_index = category_keys.index(category) - 1
                        if prev_index >= 0:
                            prev_limit = age_categories[category_keys[prev_index]]
                            prev_cutoff = now - prev_limit
                            count = Job.query.filter(
                                Job.created_at >= cutoff,
                                Job.created_at < prev_cutoff
                            ).count()
                        else:
                            count = 0
                else:
                    # Older than 1 week
                    cutoff = now - timedelta(days=7)
                    count = Job.query.filter(Job.created_at < cutoff).count()

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