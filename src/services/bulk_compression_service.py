"""
Bulk compression service for handling multiple PDF files
"""
import os
import uuid
import zipfile
import tempfile
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from werkzeug.datastructures import FileStorage

from src.models import CompressionJob, User
from src.models.base import db
from src.services.compression_service import CompressionService
from src.services.subscription_service import SubscriptionService
from src.utils.file_utils import (
    secure_filename, ensure_directory_exists, get_file_size,
    validate_file_type, get_unique_filename, delete_file_safely
)


logger = logging.getLogger(__name__)


class BulkCompressionService:
    """Service for handling bulk PDF compression operations"""
    
    MAX_FILES_FREE = 1  # Free users can only process single files
    MAX_FILES_PREMIUM = 50  # Premium users can process up to 50 files
    MAX_FILES_PRO = 100  # Pro users can process up to 100 files
    
    ALLOWED_EXTENSIONS = {'pdf'}
    MAX_FILE_SIZE_MB = 50  # Maximum individual file size
    
    def __init__(self, upload_folder: str):
        self.upload_folder = upload_folder
        self.compression_service = CompressionService(upload_folder)
        ensure_directory_exists(upload_folder)
    
    def validate_bulk_request(self, user_id: int, files: List[FileStorage]) -> Dict[str, Any]:
        """
        Validate a bulk compression request
        
        Args:
            user_id: ID of the user making the request
            files: List of uploaded files
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Get user subscription info
            subscription = SubscriptionService.get_user_subscription(user_id)
            if subscription and subscription.is_active():
                user_tier = subscription.plan.name
            else:
                user_tier = 'free'
            
            # Check if user can perform bulk operations
            if user_tier == 'free':
                return {
                    'valid': False,
                    'error': 'Bulk compression requires a premium subscription',
                    'error_code': 'PREMIUM_REQUIRED',
                    'max_files': self.MAX_FILES_FREE
                }
            
            # Determine file limits based on user tier
            max_files = self._get_max_files_for_tier(user_tier)
            
            # Validate file count
            if len(files) > max_files:
                return {
                    'valid': False,
                    'error': f'Too many files. Maximum allowed: {max_files}',
                    'error_code': 'TOO_MANY_FILES',
                    'max_files': max_files
                }
            
            if len(files) == 0:
                return {
                    'valid': False,
                    'error': 'No files provided',
                    'error_code': 'NO_FILES'
                }
            
            # Validate each file
            validation_errors = []
            total_size_mb = 0
            
            for i, file in enumerate(files):
                file_validation = self._validate_single_file(file, i)
                if not file_validation['valid']:
                    validation_errors.append(file_validation)
                else:
                    total_size_mb += file_validation['size_mb']
            
            # Check total size limits
            max_total_size = self._get_max_total_size_for_tier(user_tier)
            if total_size_mb > max_total_size:
                validation_errors.append({
                    'valid': False,
                    'error': f'Total file size ({total_size_mb:.1f}MB) exceeds limit ({max_total_size}MB)',
                    'error_code': 'TOTAL_SIZE_EXCEEDED'
                })
            
            # Check user's remaining quota
            usage_check = SubscriptionService.check_compression_permission(user_id)
            if not usage_check['can_compress']:
                return {
                    'valid': False,
                    'error': usage_check['reason'],
                    'error_code': 'QUOTA_EXCEEDED',
                    'usage_info': usage_check
                }
            
            if validation_errors:
                return {
                    'valid': False,
                    'error': 'File validation failed',
                    'error_code': 'VALIDATION_FAILED',
                    'validation_errors': validation_errors,
                    'total_size_mb': total_size_mb
                }
            
            return {
                'valid': True,
                'file_count': len(files),
                'total_size_mb': total_size_mb,
                'user_tier': user_tier,
                'max_files': max_files
            }
            
        except Exception as e:
            logger.error(f"Error validating bulk request: {str(e)}")
            return {
                'valid': False,
                'error': 'System error during validation',
                'error_code': 'SYSTEM_ERROR'
            }
    
    def _validate_single_file(self, file: FileStorage, index: int) -> Dict[str, Any]:
        """Validate a single file in the bulk request"""
        try:
            if not file or not file.filename:
                return {
                    'valid': False,
                    'error': f'File {index + 1}: No file provided',
                    'error_code': 'NO_FILE',
                    'index': index
                }
            
            # Validate file extension
            if not validate_file_type(file.filename, self.ALLOWED_EXTENSIONS):
                return {
                    'valid': False,
                    'error': f'File {index + 1}: Invalid file type. Only PDF files are allowed',
                    'error_code': 'INVALID_TYPE',
                    'filename': file.filename,
                    'index': index
                }
            
            # Check file size
            file.seek(0, 2)  # Seek to end
            size_bytes = file.tell()
            file.seek(0)  # Reset to beginning
            
            size_mb = size_bytes / (1024 * 1024)
            
            if size_mb > self.MAX_FILE_SIZE_MB:
                return {
                    'valid': False,
                    'error': f'File {index + 1}: File too large ({size_mb:.1f}MB). Maximum: {self.MAX_FILE_SIZE_MB}MB',
                    'error_code': 'FILE_TOO_LARGE',
                    'filename': file.filename,
                    'size_mb': size_mb,
                    'index': index
                }
            
            if size_bytes == 0:
                return {
                    'valid': False,
                    'error': f'File {index + 1}: Empty file',
                    'error_code': 'EMPTY_FILE',
                    'filename': file.filename,
                    'index': index
                }
            
            # Validate file content (basic PDF header check)
            file_content = file.read(1024)  # Read first 1KB
            file.seek(0)  # Reset
            
            if not file_content.startswith(b'%PDF-'):
                return {
                    'valid': False,
                    'error': f'File {index + 1}: Invalid PDF file format',
                    'error_code': 'INVALID_PDF',
                    'filename': file.filename,
                    'index': index
                }
            
            return {
                'valid': True,
                'filename': file.filename,
                'size_mb': size_mb,
                'size_bytes': size_bytes,
                'index': index
            }
            
        except Exception as e:
            logger.error(f"Error validating file {index}: {str(e)}")
            return {
                'valid': False,
                'error': f'File {index + 1}: Error reading file',
                'error_code': 'READ_ERROR',
                'index': index
            }
    
    def create_bulk_job(self, user_id: int, files: List[FileStorage], 
                       compression_settings: Dict[str, Any]) -> CompressionJob:
        """
        Create a bulk compression job
        
        Args:
            user_id: ID of the user
            files: List of uploaded files
            compression_settings: Compression settings to apply
            
        Returns:
            Created CompressionJob instance
        """
        try:
            # Generate unique job identifier
            job_id = str(uuid.uuid4())
            
            # Create job record
            job = CompressionJob(
                user_id=user_id,
                job_type='bulk',
                original_filename=f"bulk_job_{len(files)}_files",
                settings=compression_settings
            )
            job.file_count = len(files)
            
            db.session.add(job)
            db.session.flush()  # Get the job ID
            
            # Create job directory
            job_dir = os.path.join(self.upload_folder, f"bulk_job_{job.id}")
            ensure_directory_exists(job_dir)
            
            # Save uploaded files
            input_files = []
            total_size = 0
            
            for i, file in enumerate(files):
                secure_name = secure_filename(file.filename)
                unique_name = get_unique_filename(job_dir, f"input_{i:03d}_{secure_name}")
                file_path = os.path.join(job_dir, unique_name)
                
                file.save(file_path)
                file_size = get_file_size(file_path)
                total_size += file_size
                
                input_files.append({
                    'original_name': file.filename,
                    'saved_name': unique_name,
                    'path': file_path,
                    'size': file_size
                })
            
            # Update job with file information
            job.input_path = job_dir
            job.original_size_bytes = total_size
            
            # Store file list in job settings
            job_settings = job.get_settings()
            job_settings['input_files'] = input_files
            job_settings['job_directory'] = job_dir
            job.set_settings(job_settings)
            
            db.session.commit()
            
            logger.info(f"Created bulk compression job {job.id} with {len(files)} files for user {user_id}")
            return job
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating bulk job: {str(e)}")
            raise
    
    def process_bulk_job_async(self, job_id: int) -> str:
        """
        Queue a bulk compression job for asynchronous processing
        
        Args:
            job_id: ID of the compression job
            
        Returns:
            Celery task ID
        """
        try:
            from src.tasks.compression_tasks import process_bulk_compression
            
            # Queue the task
            task = process_bulk_compression.delay(job_id)
            
            # Update job with task ID
            job = CompressionJob.query.get(job_id)
            if job:
                job.task_id = task.id
                db.session.commit()
            
            logger.info(f"Queued bulk compression job {job_id} with task ID {task.id}")
            return task.id
            
        except Exception as e:
            logger.error(f"Error queuing bulk job {job_id}: {str(e)}")
            raise
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get the status of a Celery task
        
        Args:
            task_id: Celery task ID
            
        Returns:
            Task status information
        """
        try:
            from src.celery_app import celery_app
            
            result = celery_app.AsyncResult(task_id)
            
            if result.state == 'PENDING':
                return {
                    'state': result.state,
                    'status': 'Task is waiting to be processed',
                    'progress': 0
                }
            elif result.state == 'PROGRESS':
                return {
                    'state': result.state,
                    'current': result.info.get('current', 0),
                    'total': result.info.get('total', 1),
                    'progress': result.info.get('progress', 0),
                    'status': result.info.get('status', 'Processing...')
                }
            elif result.state == 'SUCCESS':
                return {
                    'state': result.state,
                    'result': result.result,
                    'status': 'Task completed successfully',
                    'progress': 100
                }
            elif result.state == 'FAILURE':
                return {
                    'state': result.state,
                    'error': str(result.info),
                    'status': 'Task failed',
                    'progress': 0
                }
            else:
                return {
                    'state': result.state,
                    'status': f'Task state: {result.state}',
                    'progress': 0
                }
                
        except Exception as e:
            logger.error(f"Error getting task status for {task_id}: {str(e)}")
            return {
                'state': 'ERROR',
                'error': str(e),
                'status': 'Error retrieving task status',
                'progress': 0
            }

    def process_bulk_job_sync(self, job_id: int) -> Dict[str, Any]:
        """
        Process a bulk compression job synchronously (for testing/small batches)
        
        Args:
            job_id: ID of the compression job
            
        Returns:
            Processing results
        """
        try:
            job = CompressionJob.query.get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            if job.job_type != 'bulk':
                raise ValueError(f"Job {job_id} is not a bulk job")
            
            # Mark job as processing
            job.mark_as_processing()
            db.session.commit()
            
            # Get job settings and files
            settings = job.get_settings()
            input_files = settings.get('input_files', [])
            job_dir = settings.get('job_directory')
            
            if not job_dir or not os.path.exists(job_dir):
                raise ValueError("Job directory not found")
            
            # Process each file
            processed_files = []
            total_compressed_size = 0
            errors = []
            
            for i, file_info in enumerate(input_files):
                try:
                    result = self._process_single_file_in_batch(
                        file_info, job_dir, settings, i
                    )
                    processed_files.append(result)
                    total_compressed_size += result['compressed_size']
                    
                    # Update progress
                    job.completed_count = i + 1
                    db.session.commit()
                    
                except Exception as e:
                    error_info = {
                        'file': file_info['original_name'],
                        'error': str(e),
                        'index': i
                    }
                    errors.append(error_info)
                    logger.error(f"Error processing file {file_info['original_name']}: {str(e)}")
            
            # Create result archive if any files were processed
            result_path = None
            if processed_files:
                result_path = self._create_result_archive(job_dir, processed_files, job.id)
            
            # Update job with final results
            job.compressed_size_bytes = total_compressed_size
            job.result_path = result_path
            job.calculate_compression_ratio()
            
            if errors and not processed_files:
                # All files failed
                job.mark_as_failed(f"All files failed to process. Errors: {len(errors)}")
            elif errors:
                # Some files failed
                job.mark_as_completed()
                job.error_message = f"Completed with {len(errors)} errors"
            else:
                # All files succeeded
                job.mark_as_completed()
            
            db.session.commit()
            
            # Increment usage counter for successful compressions
            if processed_files:
                SubscriptionService.increment_usage(job.user_id, len(processed_files))
            
            return {
                'success': True,
                'job_id': job_id,
                'processed_count': len(processed_files),
                'error_count': len(errors),
                'errors': errors,
                'result_path': result_path,
                'total_compressed_size': total_compressed_size
            }
            
        except Exception as e:
            # Mark job as failed
            if 'job' in locals():
                job.mark_as_failed(str(e))
                db.session.commit()
            
            logger.error(f"Error processing bulk job {job_id}: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'job_id': job_id
            }
    
    def _process_single_file_in_batch(self, file_info: Dict[str, Any], 
                                    job_dir: str, settings: Dict[str, Any], 
                                    index: int) -> Dict[str, Any]:
        """Process a single file within a bulk job"""
        input_path = file_info['path']
        output_filename = f"compressed_{index:03d}_{file_info['saved_name']}"
        output_path = os.path.join(job_dir, output_filename)
        
        # Extract compression settings
        compression_level = settings.get('compression_level', 'medium')
        image_quality = settings.get('image_quality', 80)
        
        # Perform compression
        self.compression_service.compress_pdf(
            input_path, output_path, compression_level, image_quality
        )
        
        # Get compressed file size
        compressed_size = get_file_size(output_path)
        
        return {
            'original_name': file_info['original_name'],
            'original_size': file_info['size'],
            'compressed_size': compressed_size,
            'compression_ratio': ((file_info['size'] - compressed_size) / file_info['size']) * 100,
            'output_path': output_path,
            'output_filename': output_filename
        }
    
    def _create_result_archive(self, job_dir: str, processed_files: List[Dict[str, Any]], 
                             job_id: int) -> str:
        """Create a ZIP archive containing all compressed files"""
        archive_filename = f"compressed_files_job_{job_id}.zip"
        archive_path = os.path.join(job_dir, archive_filename)
        
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_info in processed_files:
                if os.path.exists(file_info['output_path']):
                    # Use original filename for the archive
                    archive_name = f"compressed_{file_info['original_name']}"
                    zipf.write(file_info['output_path'], archive_name)
        
        return archive_path
    
    def get_job_progress(self, job_id: int) -> Dict[str, Any]:
        """
        Get progress information for a bulk job
        
        Args:
            job_id: ID of the compression job
            
        Returns:
            Progress information
        """
        try:
            job = CompressionJob.query.get(job_id)
            if not job:
                return {
                    'found': False,
                    'error': 'Job not found'
                }
            
            progress_data = {
                'found': True,
                'job_id': job_id,
                'status': job.status,
                'job_type': job.job_type,
                'file_count': job.file_count,
                'completed_count': job.completed_count,
                'progress_percentage': job.get_progress_percentage(),
                'created_at': job.created_at.isoformat(),
                'started_at': job.started_at.isoformat() if job.started_at else None,
                'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                'is_completed': job.is_completed(),
                'is_successful': job.is_successful(),
                'error_message': job.error_message
            }
            
            # Add result information if completed
            if job.is_completed() and job.is_successful():
                progress_data.update({
                    'original_size_bytes': job.original_size_bytes,
                    'compressed_size_bytes': job.compressed_size_bytes,
                    'compression_ratio': job.compression_ratio,
                    'result_available': bool(job.result_path and os.path.exists(job.result_path))
                })
            
            return progress_data
            
        except Exception as e:
            logger.error(f"Error getting job progress for {job_id}: {str(e)}")
            return {
                'found': False,
                'error': 'System error retrieving job progress'
            }
    
    def get_result_file_path(self, job_id: int, user_id: int) -> Optional[str]:
        """
        Get the result file path for a completed bulk job
        
        Args:
            job_id: ID of the compression job
            user_id: ID of the user (for authorization)
            
        Returns:
            Path to result file or None if not available
        """
        try:
            job = CompressionJob.query.filter_by(id=job_id, user_id=user_id).first()
            
            if not job:
                logger.warning(f"Job {job_id} not found for user {user_id}")
                return None
            
            if not job.is_completed() or not job.is_successful():
                logger.warning(f"Job {job_id} is not completed successfully")
                return None
            
            if not job.result_path or not os.path.exists(job.result_path):
                logger.warning(f"Result file not found for job {job_id}")
                return None
            
            return job.result_path
            
        except Exception as e:
            logger.error(f"Error getting result file for job {job_id}: {str(e)}")
            return None
    
    def cleanup_job_files(self, job_id: int) -> bool:
        """
        Clean up all files associated with a bulk job
        
        Args:
            job_id: ID of the compression job
            
        Returns:
            True if cleanup was successful
        """
        try:
            job = CompressionJob.query.get(job_id)
            if not job:
                return False
            
            settings = job.get_settings()
            job_dir = settings.get('job_directory')
            
            if job_dir and os.path.exists(job_dir):
                import shutil
                shutil.rmtree(job_dir)
                logger.info(f"Cleaned up job directory for job {job_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up job {job_id}: {str(e)}")
            return False
    
    def _get_max_files_for_tier(self, tier: str) -> int:
        """Get maximum number of files allowed for user tier"""
        tier_limits = {
            'free': self.MAX_FILES_FREE,
            'premium': self.MAX_FILES_PREMIUM,
            'pro': self.MAX_FILES_PRO
        }
        return tier_limits.get(tier, self.MAX_FILES_FREE)
    
    def _get_max_total_size_for_tier(self, tier: str) -> float:
        """Get maximum total file size in MB for user tier"""
        tier_limits = {
            'free': 10.0,  # 10MB total for free users
            'premium': 500.0,  # 500MB total for premium users
            'pro': 1000.0  # 1GB total for pro users
        }
        return tier_limits.get(tier, 10.0)
    
    def get_user_bulk_jobs(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent bulk compression jobs for a user
        
        Args:
            user_id: ID of the user
            limit: Maximum number of jobs to return
            
        Returns:
            List of job information dictionaries
        """
        try:
            jobs = CompressionJob.query.filter_by(
                user_id=user_id, 
                job_type='bulk'
            ).order_by(
                CompressionJob.created_at.desc()
            ).limit(limit).all()
            
            return [job.to_dict() for job in jobs]
            
        except Exception as e:
            logger.error(f"Error getting bulk jobs for user {user_id}: {str(e)}")
            return []