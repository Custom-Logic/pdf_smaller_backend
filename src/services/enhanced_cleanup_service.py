"""
Enhanced Cleanup Service with FileManager Integration

This service provides comprehensive cleanup functionality including:
- Scheduled cleanup tasks for expired files
- Storage quota management and enforcement
- Cleanup policies based on user tiers and retention rules
- Integration with FileManager for secure file operations

Requirements: 6.2, 6.3, 6.4
"""

import os
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from src.models import CompressionJob
from src.models.base import db
from src.services.file_manager import FileManager

from src.config import Config

logger = logging.getLogger(__name__)


class EnhancedCleanupService:
    """Enhanced cleanup service with FileManager integration and quota management"""
    
    # Default storage quota (in MB)
    DEFAULT_STORAGE_QUOTA = 1000  # 1GB default
    
    # Default file retention period (in hours)
    DEFAULT_RETENTION_PERIOD = 168  # 7 days default
    
    # Cleanup policies
    TEMP_FILE_MAX_AGE_HOURS = 1
    FAILED_JOB_RETENTION_HOURS = 24
    ORPHANED_FILE_MAX_AGE_HOURS = 48
    
    def __init__(self, file_manager: FileManager = None):
        """
        Initialize enhanced cleanup service
        
        Args:
            file_manager: FileManager instance for secure file operations
        """
        self.file_manager = file_manager or FileManager()
    
    def run_comprehensive_cleanup(self) -> Dict[str, Any]:
        """
        Run comprehensive cleanup including all cleanup policies
        
        Returns:
            Dictionary with cleanup results and statistics
        """
        cleanup_results = {
            'timestamp': datetime.utcnow().isoformat(),
            'total_files_deleted': 0,
            'total_space_freed_mb': 0,
            'operations': {},
            'errors': []
        }
        
        try:
            # 1. Clean up expired jobs and files
            expired_cleanup = self.cleanup_expired_jobs()
            cleanup_results['operations']['expired_jobs'] = expired_cleanup
            cleanup_results['total_files_deleted'] += expired_cleanup.get('files_deleted', 0)
            cleanup_results['total_space_freed_mb'] += expired_cleanup.get('space_freed_mb', 0)
            
            # 2. Clean up temporary files
            temp_cleanup = self.cleanup_temp_files()
            cleanup_results['operations']['temp_files'] = temp_cleanup
            cleanup_results['total_files_deleted'] += temp_cleanup.get('files_deleted', 0)
            cleanup_results['total_space_freed_mb'] += temp_cleanup.get('space_freed_mb', 0)
            
            # 3. Clean up orphaned files
            orphaned_cleanup = self.cleanup_orphaned_files()
            cleanup_results['operations']['orphaned_files'] = orphaned_cleanup
            cleanup_results['total_files_deleted'] += orphaned_cleanup.get('files_deleted', 0)
            cleanup_results['total_space_freed_mb'] += orphaned_cleanup.get('space_freed_mb', 0)
            
            # 4. Enforce storage quotas
            quota_cleanup = self.enforce_storage_quotas()
            cleanup_results['operations']['quota_enforcement'] = quota_cleanup
            cleanup_results['total_files_deleted'] += quota_cleanup.get('files_deleted', 0)
            cleanup_results['total_space_freed_mb'] += quota_cleanup.get('space_freed_mb', 0)
            
            # 5. Clean up failed jobs
            failed_cleanup = self.cleanup_failed_jobs()
            cleanup_results['operations']['failed_jobs'] = failed_cleanup
            cleanup_results['total_files_deleted'] += failed_cleanup.get('files_deleted', 0)
            cleanup_results['total_space_freed_mb'] += failed_cleanup.get('space_freed_mb', 0)
            
            logger.info(f"Comprehensive cleanup completed: {cleanup_results['total_files_deleted']} files deleted, "
                       f"{cleanup_results['total_space_freed_mb']:.2f}MB freed")
            
        except Exception as e:
            error_msg = f"Error during comprehensive cleanup: {str(e)}"
            logger.error(error_msg)
            cleanup_results['errors'].append(error_msg)
        
        return cleanup_results
    
    def cleanup_expired_jobs(self) -> Dict[str, Any]:
        """
        Clean up expired compression jobs based on default retention period
        
        Returns:
            Dictionary with cleanup statistics
        """
        cleanup_stats = {
            'jobs_cleaned': 0,
            'files_deleted': 0,
            'space_freed_mb': 0,
            'errors': []
        }
        
        try:
            # Get expired jobs
            expired_jobs = self._get_expired_jobs()
            
            for job in expired_jobs:
                try:
                    # Clean up job files using FileManager
                    space_freed = self._cleanup_job_files_secure(job)
                    cleanup_stats['space_freed_mb'] += space_freed
                    
                    # Delete job record
                    db.session.delete(job)
                    cleanup_stats['jobs_cleaned'] += 1
                    
                    logger.debug(f"Cleaned up expired job {job.id} for user {job.user_id}")
                    
                except Exception as e:
                    error_msg = f"Error cleaning up job {job.id}: {str(e)}"
                    logger.error(error_msg)
                    cleanup_stats['errors'].append(error_msg)
            
            db.session.commit()
            
            if cleanup_stats['jobs_cleaned'] > 0:
                logger.info(f"Expired jobs cleanup: {cleanup_stats['jobs_cleaned']} jobs cleaned, "
                           f"{cleanup_stats['space_freed_mb']:.2f}MB freed")
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Error during expired jobs cleanup: {str(e)}"
            logger.error(error_msg)
            cleanup_stats['errors'].append(error_msg)
        
        return cleanup_stats
    
    def cleanup_temp_files(self) -> Dict[str, Any]:
        """
        Clean up temporary files older than specified age
        
        Returns:
            Dictionary with cleanup statistics
        """
        cleanup_stats = {
            'files_deleted': 0,
            'space_freed_mb': 0,
            'errors': []
        }
        
        try:
            temp_folder = self.file_manager.temp_folder
            cutoff_time = datetime.utcnow() - timedelta(hours=self.TEMP_FILE_MAX_AGE_HOURS)
            
            if not os.path.exists(temp_folder):
                return cleanup_stats
            
            for filename in os.listdir(temp_folder):
                file_path = os.path.join(temp_folder, filename)
                
                try:
                    if os.path.isfile(file_path):
                        file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                        
                        if file_mtime < cutoff_time:
                            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                            
                            if os.remove(file_path):
                                cleanup_stats['files_deleted'] += 1
                                cleanup_stats['space_freed_mb'] += file_size_mb
                                logger.debug(f"Deleted temp file: {filename}")
                
                except Exception as e:
                    error_msg = f"Error deleting temp file {filename}: {str(e)}"
                    logger.warning(error_msg)
                    cleanup_stats['errors'].append(error_msg)
            
            if cleanup_stats['files_deleted'] > 0:
                logger.info(f"Temp files cleanup: {cleanup_stats['files_deleted']} files deleted, "
                           f"{cleanup_stats['space_freed_mb']:.2f}MB freed")
            
        except Exception as e:
            error_msg = f"Error during temp files cleanup: {str(e)}"
            logger.error(error_msg)
            cleanup_stats['errors'].append(error_msg)
        
        return cleanup_stats
    
    def cleanup_orphaned_files(self) -> Dict[str, Any]:
        """
        Clean up orphaned files that don't have corresponding database records
        
        Returns:
            Dictionary with cleanup statistics
        """
        cleanup_stats = {
            'files_deleted': 0,
            'space_freed_mb': 0,
            'errors': []
        }
        
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=self.ORPHANED_FILE_MAX_AGE_HOURS)
            
            # Check user storage directories
            user_folder = self.file_manager.user_folder
            results_folder = self.file_manager.results_folder
            
            for base_folder in [user_folder, results_folder]:
                if not os.path.exists(base_folder):
                    continue
                
                for user_dir in os.listdir(base_folder):
                    user_path = os.path.join(base_folder, user_dir)
                    
                    if not os.path.isdir(user_path):
                        continue
                    
                    try:
                        user_id = int(user_dir)
                    except ValueError:
                        continue  # Skip non-numeric directories
                    
                    # Check files in user directory
                    for filename in os.listdir(user_path):
                        file_path = os.path.join(user_path, filename)
                        
                        try:
                            if os.path.isfile(file_path):
                                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                                
                                if file_mtime < cutoff_time:
                                    # Check if file has corresponding job record
                                    if not self._file_has_job_record(file_path, user_id):
                                        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                                        
                                        # Use FileManager to safely delete
                                        if self.file_manager.delete_file(file_path, user_id):
                                            cleanup_stats['files_deleted'] += 1
                                            cleanup_stats['space_freed_mb'] += file_size_mb
                                            logger.debug(f"Deleted orphaned file: {file_path}")
                        
                        except Exception as e:
                            error_msg = f"Error processing file {file_path}: {str(e)}"
                            logger.warning(error_msg)
                            cleanup_stats['errors'].append(error_msg)
            
            if cleanup_stats['files_deleted'] > 0:
                logger.info(f"Orphaned files cleanup: {cleanup_stats['files_deleted']} files deleted, "
                           f"{cleanup_stats['space_freed_mb']:.2f}MB freed")
            
        except Exception as e:
            error_msg = f"Error during orphaned files cleanup: {str(e)}"
            logger.error(error_msg)
            cleanup_stats['errors'].append(error_msg)
        
        return cleanup_stats
    
    def enforce_storage_quotas(self) -> Dict[str, Any]:
        """
        Enforce storage quotas based on default quota
        
        Returns:
            Dictionary with quota enforcement statistics
        """
        cleanup_stats = {
            'users_processed': 0,
            'files_deleted': 0,
            'space_freed_mb': 0,
            'quota_violations': 0,
            'errors': []
        }
        
        try:
            # Get all users
            users = User.query.all()
            
            for user in users:
                try:
                    # Get user's storage usage
                    usage = self.file_manager.get_user_storage_usage(user.id)
                    
                    # Use default quota for all users
                    quota_mb = self.DEFAULT_STORAGE_QUOTA
                    
                    if usage['total_size_mb'] > quota_mb:
                        cleanup_stats['quota_violations'] += 1
                        
                        # Clean up oldest files until under quota
                        space_freed = self._cleanup_user_files_to_quota(user.id, quota_mb)
                        cleanup_stats['space_freed_mb'] += space_freed
                        
                        logger.info(f"Enforced default quota for user {user.id}: freed {space_freed:.2f}MB")
                    
                    cleanup_stats['users_processed'] += 1
                    
                except Exception as e:
                    error_msg = f"Error enforcing quota for user {user.id}: {str(e)}"
                    logger.error(error_msg)
                    cleanup_stats['errors'].append(error_msg)
            
            if cleanup_stats['quota_violations'] > 0:
                logger.info(f"Storage quota enforcement: {cleanup_stats['quota_violations']} violations resolved, "
                           f"{cleanup_stats['space_freed_mb']:.2f}MB freed")
            
        except Exception as e:
            error_msg = f"Error during storage quota enforcement: {str(e)}"
            logger.error(error_msg)
            cleanup_stats['errors'].append(error_msg)
        
        return cleanup_stats
    
    def cleanup_failed_jobs(self) -> Dict[str, Any]:
        """
        Clean up failed jobs older than retention period
        
        Returns:
            Dictionary with cleanup statistics
        """
        cleanup_stats = {
            'jobs_cleaned': 0,
            'files_deleted': 0,
            'space_freed_mb': 0,
            'errors': []
        }
        
        try:
            cutoff_time = datetime.utcnow() - timedelta(hours=self.FAILED_JOB_RETENTION_HOURS)
            
            failed_jobs = CompressionJob.query.filter(
                CompressionJob.status == 'failed',
                CompressionJob.created_at < cutoff_time
            ).all()
            
            for job in failed_jobs:
                try:
                    space_freed = self._cleanup_job_files_secure(job)
                    cleanup_stats['space_freed_mb'] += space_freed
                    
                    db.session.delete(job)
                    cleanup_stats['jobs_cleaned'] += 1
                    
                except Exception as e:
                    error_msg = f"Error cleaning up failed job {job.id}: {str(e)}"
                    logger.error(error_msg)
                    cleanup_stats['errors'].append(error_msg)
            
            db.session.commit()
            
            if cleanup_stats['jobs_cleaned'] > 0:
                logger.info(f"Failed jobs cleanup: {cleanup_stats['jobs_cleaned']} jobs cleaned, "
                           f"{cleanup_stats['space_freed_mb']:.2f}MB freed")
            
        except Exception as e:
            db.session.rollback()
            error_msg = f"Error during failed jobs cleanup: {str(e)}"
            logger.error(error_msg)
            cleanup_stats['errors'].append(error_msg)
        
        return cleanup_stats
    
    def get_cleanup_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive cleanup statistics and recommendations
        
        Returns:
            Dictionary with cleanup statistics and recommendations
        """
        try:
            stats = {
                'timestamp': datetime.utcnow().isoformat(),
                'total_jobs': CompressionJob.query.count(),
                'jobs_by_status': {},
                'storage_usage': {},
                'quota_violations': [],
                'cleanup_recommendations': []
            }
            
            # Job statistics by status
            status_counts = db.session.query(
                CompressionJob.status,
                db.func.count(CompressionJob.id)
            ).group_by(CompressionJob.status).all()
            
            for status, count in status_counts:
                stats['jobs_by_status'][status] = count
            
            # Storage usage by user tier
            users = User.query.all()
            tier_usage = {'free': [], 'premium': [], 'pro': []}
            
            for user in users:
                user_tier = self._get_user_tier(user.id)
                usage = self.file_manager.get_user_storage_usage(user.id)
                quota = self.STORAGE_QUOTAS.get(user_tier, self.STORAGE_QUOTAS['free'])
                
                usage_info = {
                    'user_id': user.id,
                    'usage_mb': usage['total_size_mb'],
                    'quota_mb': quota,
                    'usage_percentage': (usage['total_size_mb'] / quota) * 100 if quota > 0 else 0
                }
                
                tier_usage[user_tier].append(usage_info)
                
                # Check for quota violations
                if usage['total_size_mb'] > quota:
                    stats['quota_violations'].append(usage_info)
            
            stats['storage_usage'] = tier_usage
            
            # Generate cleanup recommendations
            stats['cleanup_recommendations'] = self._generate_cleanup_recommendations(stats)
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cleanup statistics: {str(e)}")
            return {'error': str(e)}
    
    def _get_expired_jobs(self) -> List[CompressionJob]:
        """Get expired jobs based on default retention period"""
        expired_jobs = []
        
        try:
            # Use default retention period for all jobs
            cutoff_time = datetime.utcnow() - timedelta(hours=self.DEFAULT_RETENTION_PERIOD)
            
            # Get expired jobs
            expired_jobs = CompressionJob.query.filter(
                CompressionJob.created_at < cutoff_time
            ).all()
            
            logger.debug(f"Found {len(expired_jobs)} expired jobs")
            return expired_jobs
            
        except Exception as e:
            logger.error(f"Error getting expired jobs: {str(e)}")
            return []
    
    def _cleanup_job_files_secure(self, job: CompressionJob) -> float:
        """
        Securely clean up files associated with a job using FileManager
        
        Args:
            job: CompressionJob instance
            
        Returns:
            Space freed in MB
        """
        space_freed_mb = 0
        
        try:
            file_paths = []
            
            if job.input_path and os.path.exists(job.input_path):
                file_paths.append(job.input_path)
            
            if job.result_path and os.path.exists(job.result_path):
                file_paths.append(job.result_path)
            
            for file_path in file_paths:
                try:
                    file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
                    
                    # Use FileManager for secure deletion without user_id reference
                    if self.file_manager.delete_file(file_path):
                        space_freed_mb += file_size_mb
                        logger.debug(f"Deleted job file: {file_path}")
                    
                except Exception as e:
                    logger.warning(f"Could not delete job file {file_path}: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error cleaning up job files for job {job.id}: {str(e)}")
        
        return space_freed_mb
    
    def _file_has_job_record(self, file_path: str, user_id: int) -> bool:
        """Check if a file has a corresponding job record"""
        try:
            filename = os.path.basename(file_path)
            
            # Check if file is referenced in any job
            job_with_file = CompressionJob.query.filter(
                CompressionJob.user_id == user_id,
                db.or_(
                    CompressionJob.input_path.like(f'%{filename}'),
                    CompressionJob.result_path.like(f'%{filename}')
                )
            ).first()
            
            return job_with_file is not None
            
        except Exception as e:
            logger.error(f"Error checking job record for file {file_path}: {str(e)}")
            return True  # Assume it has a record to be safe
    
    def _get_user_tier(self, user_id: int) -> str:
        """Get user's subscription tier"""
        try:
            subscription = Subscription.query.filter_by(
                user_id=user_id,
                status='active'
            ).first()
            
            if subscription and subscription.plan:
                return subscription.plan.name.lower()
            
            return 'free'
            
        except Exception as e:
            logger.error(f"Error getting user tier for user {user_id}: {str(e)}")
            return 'free'
    
    def _cleanup_user_files_to_quota(self, user_id: int, quota_mb: float) -> float:
        """
        Clean up user files until under quota, starting with oldest files
        
        Args:
            user_id: User ID
            quota_mb: Storage quota in MB
            
        Returns:
            Space freed in MB
        """
        space_freed_mb = 0
        
        try:
            # Get user files sorted by age (oldest first)
            user_files = self.file_manager.list_user_files(user_id, 'all')
            user_files.sort(key=lambda x: x.get('created_at', datetime.max))
            
            current_usage = self.file_manager.get_user_storage_usage(user_id)
            
            for file_info in user_files:
                if current_usage['total_size_mb'] <= quota_mb:
                    break  # Under quota now
                
                file_path = file_info['file_path']
                file_size_mb = file_info['file_size'] / (1024 * 1024)
                
                if self.file_manager.delete_file(file_path, user_id):
                    space_freed_mb += file_size_mb
                    current_usage['total_size_mb'] -= file_size_mb
                    logger.debug(f"Deleted file for quota enforcement: {file_path}")
            
        except Exception as e:
            logger.error(f"Error cleaning up user files to quota for user {user_id}: {str(e)}")
        
        return space_freed_mb
    
    def _generate_cleanup_recommendations(self, stats: Dict[str, Any]) -> List[str]:
        """Generate cleanup recommendations based on statistics"""
        recommendations = []
        
        try:
            # Check for high storage usage
            for tier, users in stats['storage_usage'].items():
                high_usage_users = [u for u in users if u['usage_percentage'] > 80]
                if high_usage_users:
                    recommendations.append(
                        f"{len(high_usage_users)} {tier} users are using >80% of their storage quota"
                    )
            
            # Check for quota violations
            if stats['quota_violations']:
                recommendations.append(
                    f"{len(stats['quota_violations'])} users are exceeding their storage quota"
                )
            
            # Check for failed jobs
            failed_jobs = stats['jobs_by_status'].get('failed', 0)
            if failed_jobs > 10:
                recommendations.append(
                    f"{failed_jobs} failed jobs could be cleaned up to free space"
                )
            
            # Check for old completed jobs
            completed_jobs = stats['jobs_by_status'].get('completed', 0)
            if completed_jobs > 100:
                recommendations.append(
                    f"Consider running cleanup on {completed_jobs} completed jobs"
                )
            
        except Exception as e:
            logger.error(f"Error generating cleanup recommendations: {str(e)}")
        
        return recommendations