import os
import subprocess
import tempfile
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from src.utils import secure_filename, cleanup_old_files
from src.models import CompressionJob, User
from src.models.base import db
from src.services.subscription_service import SubscriptionService

logger = logging.getLogger(__name__)


class CompressionService:
    GHOSTSCRIPT_BINARY = "/usr/bin/gs"  # Absolute path to Ghostscript

    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
        Path(self.upload_folder).mkdir(parents=True, exist_ok=True)
        # Verify Ghostscript exists at startup
        if not os.path.exists(self.GHOSTSCRIPT_BINARY):
            raise EnvironmentError(f"Ghostscript binary not found at {self.GHOSTSCRIPT_BINARY}")

    def compress_pdf(self, input_path, output_path, compression_level='medium', image_quality=80):
        """
        Compress PDF using Ghostscript with advanced options
        """
        compression_settings = {
            'low': '/prepress',
            'medium': '/default',
            'high': '/ebook',
            'maximum': '/screen'
        }

        gs_setting = compression_settings.get(compression_level, '/default')

        try:
            command = [
                self.GHOSTSCRIPT_BINARY,
                '-sDEVICE=pdfwrite',
                '-dCompatibilityLevel=1.4',
                f'-dPDFSETTINGS={gs_setting}',
                f'-dColorImageDownsampleType=/Bicubic',
                f'-dColorImageResolution={image_quality}',
                f'-dGrayImageDownsampleType=/Bicubic',
                f'-dGrayImageResolution={image_quality}',
                f'-dMonoImageDownsampleType=/Bicubic',
                f'-dMonoImageResolution={image_quality}',
                '-dEmbedAllFonts=true',
                '-dSubsetFonts=true',
                '-dAutoRotatePages=/None',
                '-dColorConversionStrategy=/sRGB',
                '-dProcessColorModel=/DeviceRGB',
                '-dConvertCMYKImagesToRGB=true',
                '-dDetectDuplicateImages=true',
                '-dDownsampleColorImages=true',
                '-dDownsampleGrayImages=true',
                '-dDownsampleMonoImages=true',
                '-dUseCIEColor=true',
                '-dNOPAUSE',
                '-dQUIET',
                '-dBATCH',
                f'-sOutputFile={output_path}',
                input_path
            ]

            logger.info(f"Executing Ghostscript command: {' '.join(command)}")

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode != 0:
                logger.error(f"Ghostscript error: {result.stderr}")
                raise Exception(f"Ghostscript failed: {result.stderr}")

            if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
                raise Exception("Compression failed: Output file is empty or doesn't exist")

            return True

        except subprocess.TimeoutExpired:
            logger.error("Ghostscript command timed out")
            raise Exception("Compression process timed out")
        except Exception as e:
            logger.error(f"Error during compression: {str(e)}")
            raise

    def process_upload(self, file, compression_level='medium', image_quality=80, user_id=None):
        """
        Process an uploaded file and return the path to the compressed version
        Now includes user context for tracking and permissions
        """
        filename = secure_filename(file.filename)
        input_path = os.path.join(self.upload_folder, f"input_{filename}")
        output_path = os.path.join(self.upload_folder, f"compressed_{filename}")

        # Create compression job for tracking
        compression_job = None
        if user_id:
            compression_job = self._create_compression_job(
                user_id, filename, compression_level, image_quality
            )

        try:
            file.save(input_path)
            
            # Get file size before compression
            original_size = os.path.getsize(input_path)
            
            # Update job status to processing
            if compression_job:
                compression_job.mark_as_processing()
                compression_job.input_path = input_path
                compression_job.original_size_bytes = original_size
                db.session.commit()
            
            # Perform compression
            self.compress_pdf(input_path, output_path, compression_level, image_quality)
            
            # Get compressed file size
            compressed_size = os.path.getsize(output_path)
            
            # Update job with results
            if compression_job:
                compression_job.result_path = output_path
                compression_job.compressed_size_bytes = compressed_size
                compression_job.calculate_compression_ratio()
                compression_job.mark_as_completed()
                db.session.commit()
                
                # Increment user usage counter
                if user_id:
                    SubscriptionService.increment_usage(user_id)
            
            cleanup_old_files(self.upload_folder, max_age_hours=1)
            return output_path
            
        except Exception as e:
            # Mark job as failed if it exists
            if compression_job:
                compression_job.mark_as_failed(str(e))
                db.session.commit()
            
            # Clean up files
            for path in [input_path, output_path]:
                if os.path.exists(path):
                    os.remove(path)
            logger.error(f"Compression service error: {str(e)}")
            raise

    def _create_compression_job(self, user_id: int, filename: str, compression_level: str, image_quality: int) -> CompressionJob:
        """Create a compression job record for tracking"""
        try:
            settings = {
                'compression_level': compression_level,
                'image_quality': image_quality
            }
            
            job = CompressionJob(
                user_id=user_id,
                job_type='single',
                original_filename=filename,
                settings=settings
            )
            
            db.session.add(job)
            db.session.commit()
            
            logger.info(f"Created compression job {job.id} for user {user_id}")
            return job
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating compression job: {str(e)}")
            raise

    def check_user_permissions(self, user_id: int, file_size_mb: float) -> Dict[str, Any]:
        """
        Check if user has permission to compress files
        Returns detailed permission status
        """
        try:
            # Get user's compression permissions
            permission_status = SubscriptionService.check_compression_permission(user_id)
            
            if not permission_status['can_compress']:
                return {
                    'allowed': False,
                    'reason': permission_status['reason'],
                    'details': permission_status
                }
            
            # Check file size limits
            max_file_size = SubscriptionService.get_max_file_size(user_id)
            if file_size_mb > max_file_size:
                return {
                    'allowed': False,
                    'reason': f'File size ({file_size_mb:.1f}MB) exceeds limit ({max_file_size}MB)',
                    'details': permission_status
                }
            
            return {
                'allowed': True,
                'reason': None,
                'details': permission_status
            }
            
        except Exception as e:
            logger.error(f"Error checking user permissions: {str(e)}")
            return {
                'allowed': False,
                'reason': 'System error checking permissions',
                'details': {}
            }

    def get_user_compression_jobs(self, user_id: int, limit: int = 10) -> list:
        """Get recent compression jobs for a user"""
        try:
            jobs = CompressionJob.query.filter_by(user_id=user_id)\
                .order_by(CompressionJob.created_at.desc())\
                .limit(limit)\
                .all()
            
            return [job.to_dict() for job in jobs]
            
        except Exception as e:
            logger.error(f"Error getting compression jobs for user {user_id}: {str(e)}")
            return []