import logging
import os
import uuid
from datetime import datetime
from enum import Enum

from flask import Blueprint, request, jsonify

from src.models import db, Job
from src.utils.security_utils import validate_file
from src.utils.response_helpers import success_response, error_response

logger = logging.getLogger(__name__)

compression_bp = Blueprint('compression', __name__)
# CORS(compression_bp, resources={r"/api": {"origins": ["https://www.pdfsmaller.site"]}})


class JobStatus(Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'

# Updated tasks.py - Ensure proper error handling

@compression_bp.route('/compress', methods=['POST'])
def compress_pdf():
    """Endpoint for PDF compression - returns job ID immediately"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return error_response(message='No file provided', error_code='NO_FILE', status_code=400)

        file = request.files['file']
        
        # Validate file
        validation_error = validate_file(file)
        if validation_error:
            return  error_response(message='Invalid file', errors={'file': [validation_error]}, status_code=400)

        # Get compression parameters
        compression_level = request.form.get('compressionLevel', 'medium')
        try:
            image_quality = int(request.form.get('imageQuality', 80))
        except (ValueError, TypeError):
            image_quality = 80
        image_quality = max(10, min(image_quality, 100))

        # Get client-provided tracking IDs
        job_id = request.form.get('job_id', str(uuid.uuid4()))
        # Read file data
        file_data = file.read()
        # Create job and enqueue for processing
        compression_settings = {
            'compression_level': compression_level,
            'image_quality': image_quality
        }
        job = Job(
            job_id=job_id,
            task_type='compress',
            input_data={
                'compression_settings': compression_settings,
                'file_size': len(file_data),
                'original_filename': file.filename
            }
            
        )
        db.session.add(job)
        db.session.commit()
        # Enqueue compression task (async processing)
        try:
            from src.tasks.tasks import compress_task
            compress_task.delay(job_id, file_data, compression_settings, file.filename)
            logger.info(f"Compression job {job_id} enqueued (job_id: {job_id})")
            
            data = {
                'success': True,
                'job_id': job_id,
                'status': JobStatus.PENDING.value,
                'message': 'Compression job queued successfully'
            }
            return success_response(data=data, message='Compression job created', status_code=202)
        except Exception as task_error:
            logger.error(f"Failed to enqueue compression task {job_id}: {str(task_error)}")
            # Update job status to failed
            job.status = JobStatus.FAILED.value
            job.error_message = f"Task enqueueing failed: {str(task_error)}"
            db.session.commit()
            return error_response(message='Failed to queue compression job', status_code=500)
        
    except Exception as e:
        logger.error(f"Error creating compression job: {str(e)}")
        return error_response(message='Failed to create compression job', status_code=500)

@compression_bp.route('/bulk', methods=['POST'])
def bulk_compress():
    """Endpoint for bulk PDF compression - returns job ID immediately"""
    try:
        # Check if files were uploaded
        if 'files' not in request.files:
            return error_response(message='No files provided', error_code='NO_FILES', status_code=400)

        files = request.files.getlist('files')
        
        if not files or len(files) == 0:
            return error_response(message='No files provided', error_code='NO_FILES', status_code=400)

        # Get compression settings
        compression_level = request.form.get('compressionLevel', 'medium')
        try:
            image_quality = int(request.form.get('imageQuality', 80))
        except (ValueError, TypeError):
            image_quality = 80
        image_quality = max(10, min(image_quality, 100))
        
        compression_settings = {
            'compression_level': compression_level,
            'image_quality': image_quality
        }
        
        # Get client-provided tracking IDs
        job_id = request.form.get('job_id', str(uuid.uuid4()))

        # Read all files
        file_data_list = []
        original_filenames = []
        
        for file in files:
            validation_error = validate_file(file)
            if validation_error:
                continue  # Skip invalid files
            file_data_list.append(file.read())
            original_filenames.append(file.filename)
        
        if not file_data_list:
            return error_response(message='No valid files provided', error_code='NO_VALID_FILES', status_code=400)

        # Enqueue bulk compression task
        from src.tasks.tasks import bulk_compress_task
        bulk_compress_task.delay(
            job_id=job_id,
            file_data_list=file_data_list,
            filenames=original_filenames,
            settings=compression_settings,
        )
        
        logger.info(f"Bulk compression job {job_id} enqueued (job_id: {job_id})")

        data = {
            'success': True,
            'job_id': job_id,
            'status': JobStatus.PENDING.value,
            'file_count': len(file_data_list),
            'message': f'Bulk compression job created with {len(file_data_list)} files'
        }
        return success_response(message='Bulk compression job created', data=data, status_code=202)
        
    except Exception as e:
        logger.error(f"Error creating bulk compression job: {str(e)}")
        return jsonify({
            'error': 'Failed to create bulk compression job',
            'error_code': 'SYSTEM_ERROR'
        }), 500

@compression_bp.route('/health', methods=['GET'])
def compression_health_check():
    """Health check for compression service"""
    try:
        # Check if required tools are available
        import subprocess
        
        # Check pdfinfo
        try:
            subprocess.run(['pdfinfo', '--version'], capture_output=True, timeout=5)
            pdfinfo_available = True
        except:
            pdfinfo_available = False
        
        # Check Ghostscript
        try:
            subprocess.run(['gs', '--version'], capture_output=True, timeout=5)
            ghostscript_available = True
        except:
            ghostscript_available = False
        
        # Check Redis connection (for job queue)
        redis_available = False
        try:
            from src.celery_app import get_celery_app
            celery_app = get_celery_app()
            redis_available = celery_app.control.ping(timeout=1.0) is not None
        except:
            pass
        
        return jsonify({
            'success': True,
            'status': 'healthy',
            'services': {
                'pdfinfo': pdfinfo_available,
                'ghostscript': ghostscript_available,
                'redis_queue': redis_available,
                'compression_service': True
            },
            'timestamp': datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

# Remove user-specific endpoints since backend is now user-agnostic
# The following endpoints are removed:
# - /jobs (GET) - user job history
# - /jobs/<int:job_id> (GET) - specific user job
# - /bulk/jobs (GET) - user bulk jobs
# These are now handled by the frontend using the generic job status endpoint