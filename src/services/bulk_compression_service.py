"""
Bulk compression service - Job-Oriented Architecture
Handles multiple file compression without user awareness
"""

import logging
import os
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional

from werkzeug.datastructures import FileStorage

from src.models.base import db
from src.models.job import Job, JobStatus
from src.services.compression_service import CompressionService
from src.utils.file_utils import (
    secure_filename, ensure_directory_exists, get_file_size,
    validate_file_type, get_unique_filename, delete_file_safely
)

logger = logging.getLogger(__name__)

class BulkCompressionService:
    """Service for handling bulk PDF compression operations - Job-Oriented"""
    
    # Configuration constants
    MAX_FILES = 100  # Maximum files per bulk job
    MAX_FILE_SIZE_MB = 50  # Maximum individual file size
    MAX_TOTAL_SIZE_MB = 1000  # Maximum total size per bulk job
    ALLOWED_EXTENSIONS = {'pdf'}

    def __init__(self, upload_folder: str):
        self.upload_folder = upload_folder
        self.compression_service = CompressionService(upload_folder)
        ensure_directory_exists(upload_folder)
    
    def validate_bulk_request(self, files: List[FileStorage]) -> Dict[str, Any]:
        """
        Validate a bulk compression request (user-agnostic)
        
        Args:
            files: List of uploaded files
            
        Returns:
            Dictionary with validation results
        """
        try:
            # Validate file count
            if len(files) > self.MAX_FILES:
                return {
                    'valid': False,
                    'error': f'Too many files. Maximum allowed: {self.MAX_FILES}',
                    'error_code': 'TOO_MANY_FILES',
                    'max_files': self.MAX_FILES
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
            if total_size_mb > self.MAX_TOTAL_SIZE_MB:
                validation_errors.append({
                    'valid': False,
                    'error': f'Total file size ({total_size_mb:.1f}MB) exceeds limit ({self.MAX_TOTAL_SIZE_MB}MB)',
                    'error_code': 'TOTAL_SIZE_EXCEEDED'
                })
            
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
                'max_files': self.MAX_FILES
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
    
    def create_bulk_job(self, file_data_list: List[bytes], filenames: List[str], 
                       compression_settings: Dict[str, Any], client_job_id: str = None) -> Job:
        """
        Create a bulk compression job (user-agnostic)
        
        Args:
            file_data_list: List of file data as bytes
            filenames: List of original filenames
            compression_settings: Compression settings to apply
            client_job_id: Client-provided job ID for tracking
            
        Returns:
            Created Job instance
        """
        # Generate unique job identifier
        job_id = str(uuid.uuid4())
        # Create job directory
        # noinspection PyTypeChecker
        job_dir: Path = os.path.join(self.upload_folder, f"bulk_job_{job_id}")
        ensure_directory_exists(job_dir)
        try:
            # Save uploaded files
            input_files = []
            total_size = 0
            for i, (file_data, filename) in enumerate(zip(file_data_list, filenames)):
                secure_name = secure_filename(filename)
                # noinspection PyTypeChecker
                unique_name = get_unique_filename(job_dir, f"input_{i:03d}_{secure_name}")
                file_path = os.path.join(job_dir, unique_name)

                # Write file data to disk
                with open(file_path, 'wb') as f:
                    f.write(file_data)

                file_size = get_file_size(file_path)
                total_size += file_size

                input_files.append({
                    'original_name': filename,
                    'saved_name': unique_name,
                    'path': file_path,
                    'size': file_size
                })

            # Create job record
            job = Job(
                id=job_id,
                task_type='bulk_compress',
                input_data={
                    'compression_settings': compression_settings,
                    'file_count': len(file_data_list),
                    'total_size': total_size,
                    'input_files': input_files,
                    'job_directory': job_dir
                },
                client_job_id=client_job_id
            )

            db.session.add(job)
            db.session.commit()

            logger.info(f"Created bulk compression job {job_id} with {len(file_data_list)} files")
            return job

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating bulk job: {str(e)}")
            # Clean up any created files
            try:
                if job_dir and 'job_dir' in locals() and os.path.exists(job_dir):
                    import shutil
                    shutil.rmtree(job_dir)
            except:
                pass
            raise
    
    def process_bulk_job(self, job_id: str) -> Dict[str, Any]:
        """
        Process a bulk compression job synchronously
        
        Args:
            job_id: ID of the job
            
        Returns:
            Processing results
        """
        try:
            job = Job.query.get(job_id)
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            if job.task_type != 'bulk_compress':
                raise ValueError(f"Job {job_id} is not a bulk compression job")
            
            # Update job status
            job.status = JobStatus.PROCESSING
            db.session.commit()
            
            # Get job data
            input_data = job.input_data
            input_files = input_data.get('input_files', [])
            compression_settings = input_data.get('compression_settings', {})
            job_dir = input_data.get('job_directory')
            
            if not job_dir or not os.path.exists(job_dir):
                raise ValueError("Job directory not found")
            
            # Process each file
            processed_files = []
            total_compressed_size = 0
            errors = []
            
            for i, file_info in enumerate(input_files):
                try:
                    result = self._process_single_file_in_batch(
                        file_info, job_dir, compression_settings, i
                    )
                    processed_files.append(result)
                    total_compressed_size += result['compressed_size']
                    
                    # Update progress in job metadata
                    progress_data = job.result or {}
                    progress_data['processed_count'] = i + 1
                    progress_data['total_count'] = len(input_files)
                    job.result = progress_data
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
                result_path = self.create_result_archive(job_dir, processed_files, job_id)
            
            # Update job with final results
            job.result = {
                'processed_files': len(processed_files),
                'total_files': len(input_files),
                'errors': errors,
                'result_path': result_path,
                'total_compressed_size': total_compressed_size,
                'processed_files_info': processed_files
            }
            
            if errors and not processed_files:
                job.status = JobStatus.FAILED
                job.error = f"All files failed: {len(errors)} errors"
            elif errors:
                job.status = JobStatus.COMPLETED
                job.result['warning'] = f"Completed with {len(errors)} errors"
            else:
                job.status = JobStatus.COMPLETED
            
            db.session.commit()
            
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
            # Update job status on error
            if 'job' in locals():
                job.status = JobStatus.FAILED
                job.error = str(e)
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
    
    @staticmethod
    def create_result_archive(job_dir: str, processed_files: List[Dict[str, Any]],
                              job_id: str) -> str:
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
    
    @staticmethod
    def get_job_progress(job_id: str) -> Dict[str, Any]:
        """
        Get progress information for a bulk job
        
        Args:
            job_id: ID of the job
            
        Returns:
            Progress information
        """
        try:
            job = Job.query.get(job_id)
            if not job:
                return {
                    'found': False,
                    'error': 'Job not found'
                }
            
            progress_data = {
                'found': True,
                'job_id': job_id,
                'status': job.status.value,
                'task_type': job.task_type,
                'created_at': job.created_at.isoformat(),
                'updated_at': job.updated_at.isoformat(),
                'client_job_id': job.client_job_id
            }
            
            # Add file count information if available
            if job.input_data:
                progress_data['file_count'] = job.input_data.get('file_count', 0)
                progress_data['total_size'] = job.input_data.get('total_size', 0)
            
            # Add progress information if processing
            if job.status == JobStatus.PROCESSING and job.result:
                progress_data.update({
                    'processed_count': job.result.get('processed_count', 0),
                    'total_count': job.result.get('total_count', 0),
                    'progress_percentage': int((job.result.get('processed_count', 0) / 
                                              job.result.get('total_count', 1)) * 100)
                })
            
            # Add result information if completed
            if job.status == JobStatus.COMPLETED and job.result:
                progress_data.update({
                    'processed_files': job.result.get('processed_files', 0),
                    'error_count': len(job.result.get('errors', [])),
                    'result_available': bool(job.result.get('result_path')),
                    'total_compressed_size': job.result.get('total_compressed_size', 0)
                })
            
            # Add error information if failed
            if job.status == JobStatus.FAILED:
                progress_data['error'] = job.error
            
            return progress_data
            
        except Exception as e:
            logger.error(f"Error getting job progress for {job_id}: {str(e)}")
            return {
                'found': False,
                'error': 'System error retrieving job progress'
            }
    
    @staticmethod
    def get_result_file_path(job_id: str) -> Optional[str]:
        """
        Get the result file path for a completed bulk job
        
        Args:
            job_id: ID of the job
            
        Returns:
            Path to result file or None if not available
        """
        try:
            job = Job.query.get(job_id)
            
            if not job:
                logger.warning(f"Job {job_id} not found")
                return None
            
            if job.status != JobStatus.COMPLETED:
                logger.warning(f"Job {job_id} is not completed")
                return None
            
            if not job.result or 'result_path' not in job.result:
                logger.warning(f"Result file not found in job {job_id} data")
                return None
            
            result_path = job.result['result_path']
            if not os.path.exists(result_path):
                logger.warning(f"Result file not found on disk: {result_path}")
                return None
            
            return result_path
            
        except Exception as e:
            logger.error(f"Error getting result file for job {job_id}: {str(e)}")
            return None
    
    def cleanup_job_files(self, job_id: str) -> bool:
        """
        Clean up all files associated with a bulk job
        
        Args:
            job_id: ID of the job
            
        Returns:
            True if cleanup was successful
        """
        try:
            job = Job.query.get(job_id)
            if not job:
                return False
            
            # Get job directory from input data
            job_dir = None
            if job.input_data and 'job_directory' in job.input_data:
                job_dir = job.input_data['job_directory']
            
            # Clean up result files from result data
            if job.result and 'result_path' in job.result:
                result_path = job.result['result_path']
                if os.path.exists(result_path):
                    delete_file_safely(result_path)
            
            # Clean up processed files
            if job.result and 'processed_files_info' in job.result:
                for file_info in job.result['processed_files_info']:
                    if 'output_path' in file_info and os.path.exists(file_info['output_path']):
                        delete_file_safely(file_info['output_path'])
            
            # Clean up input files and directory
            if job_dir and os.path.exists(job_dir):
                import shutil
                shutil.rmtree(job_dir)
                logger.info(f"Cleaned up job directory for job {job_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error cleaning up job {job_id}: {str(e)}")
            return False
    
    def process_bulk_files_direct(self, file_data_list: List[bytes], filenames: List[str],
                                compression_settings: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process bulk files directly without creating a job record
        (For small batches or testing)
        
        Args:
            file_data_list: List of file data as bytes
            filenames: List of original filenames
            compression_settings: Compression settings
            
        Returns:
            Processing results
        """
        try:
            # Create temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                # Save files to temp directory
                input_files = []
                for i, (file_data, filename) in enumerate(zip(file_data_list, filenames)):
                    file_path = os.path.join(temp_dir, f"input_{i:03d}_{secure_filename(filename)}")
                    with open(file_path, 'wb') as f:
                        f.write(file_data)
                    
                    input_files.append({
                        'original_name': filename,
                        'path': file_path,
                        'size': len(file_data)
                    })
                
                # Process files
                processed_files = []
                errors = []
                total_compressed_size = 0
                
                for i, file_info in enumerate(input_files):
                    try:
                        result = self._process_single_file_in_batch(
                            file_info, temp_dir, compression_settings, i
                        )
                        processed_files.append(result)
                        total_compressed_size += result['compressed_size']
                    except Exception as e:
                        errors.append({
                            'file': file_info['original_name'],
                            'error': str(e),
                            'index': i
                        })
                
                # Create result archive in memory
                result_zip_data = None
                if processed_files:
                    result_zip_data = self._create_result_archive_in_memory(processed_files)
                
                return {
                    'success': True,
                    'processed_count': len(processed_files),
                    'error_count': len(errors),
                    'errors': errors,
                    'total_compressed_size': total_compressed_size,
                    'result_zip_data': result_zip_data,
                    'processed_files': processed_files
                }
                
        except Exception as e:
            logger.error(f"Error in direct bulk processing: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def _create_result_archive_in_memory(self, processed_files: List[Dict[str, Any]]) -> bytes:
        """Create a ZIP archive in memory"""
        import io
        
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_info in processed_files:
                if os.path.exists(file_info['output_path']):
                    archive_name = f"compressed_{file_info['original_name']}"
                    zipf.write(file_info['output_path'], archive_name)
        
        zip_buffer.seek(0)
        return zip_buffer.getvalue()