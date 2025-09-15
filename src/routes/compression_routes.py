import logging

import uuid
from datetime import datetime, timezone


from flask import Blueprint, request, jsonify

from src.models import db, Job, JobStatus
from src.utils.security_utils import validate_file
from src.utils.response_helpers import success_response, error_response
from src.jobs.job_manager import JobStatusManager
from src.tasks.tasks import compress_task, bulk_compress_task

logger = logging.getLogger(__name__)

compression_bp = Blueprint('compression', __name__)
# CORS(compression_bp, resources={r"/api": {"origins": ["https://www.pdfsmaller.site"]}})

# Updated tasks.py - Ensure proper error handling

# Fix for compression_routes.py - create job BEFORE enqueueing task

@compression_bp.route('/compress', methods=['POST'])
def compress_pdf():
    """Endpoint for PDF compression - returns job ID immediately"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return error_response(message='No file provided', error_code='NO_FILE', status_code=400)

        file = request.files['file']

        # Validate file
        validation_error = validate_file(file, 'compression')
        if validation_error:
            return error_response(message=validation_error, status_code=400)

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

        # Create compression settings
        compression_settings = {
            'compression_level': compression_level,
            'image_quality': image_quality
        }

        # CREATE JOB FIRST - this is the fix!
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type='compress',
            input_data={
                'compression_settings': compression_settings,
                'file_size': len(file_data),
                'original_filename': file.filename
            }
        )

        if not job:
            return error_response(message='Failed to create job', status_code=500)

        # Now enqueue compression task (async processing)
        try:
            compress_task.delay(job_id, file_data, compression_settings, file.filename)
            logger.info(f"Compression job {job_id} enqueued")

            data = {
                'success': True,
                'job_id': job_id,
                'status': JobStatus.PENDING.value,
                'message': 'Compression job queued successfully'
            }
            return success_response(data=data, message='Compression job created', status_code=202)

        except Exception as task_error:
            logger.error(f"Failed to enqueue compression task {job_id}: {str(task_error)}")
            JobStatusManager.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=f"Task enqueueing failed: {str(task_error)}"
            )
            return error_response(message='Failed to queue compression job', status_code=500)

    except Exception as e:
        logger.error(f"Error creating compression job: {str(e)}")
        return error_response(message='Failed to create compression job', status_code=500)


# Fix for bulk compression route in compression_routes.py

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
            validation_error = validate_file(file, 'compression')
            if validation_error:
                continue  # Skip invalid files
            file_data_list.append(file.read())
            original_filenames.append(file.filename)

        if not file_data_list:
            return error_response(message='No valid files provided', error_code='NO_VALID_FILES', status_code=400)

        # CREATE JOB FIRST - this is the fix!
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type='bulk_compress',
            input_data={
                'settings': compression_settings,
                'file_count': len(file_data_list),
                'total_size': sum(len(d) for d in file_data_list),
                'filenames': original_filenames
            }
        )

        if not job:
            return error_response(message='Failed to create bulk job', status_code=500)

        # Enqueue bulk compression task
        try:
            bulk_compress_task.delay(
                job_id=job_id,
                file_data_list=file_data_list,
                filenames=original_filenames,
                settings=compression_settings,
            )

            logger.info(f"Bulk compression job {job_id} enqueued")

            data = {
                'success': True,
                'job_id': job_id,
                'status': JobStatus.PENDING.value,
                'file_count': len(file_data_list),
                'message': f'Bulk compression job created with {len(file_data_list)} files'
            }
            return success_response(message='Bulk compression job created', data=data, status_code=202)

        except Exception as task_error:
            logger.error(f"Failed to enqueue bulk compression task {job_id}: {str(task_error)}")
            JobStatusManager.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=f"Task enqueueing failed: {str(task_error)}"
            )
            return error_response(message='Failed to queue bulk compression job', status_code=500)

    except Exception as e:
        logger.error(f"Error creating bulk compression job: {str(e)}")
        return error_response(message='Failed to create bulk compression job', error_code='SYSTEM_ERROR',
                              status_code=500)

@compression_bp.route('/health', methods=['GET'])
def compression_health_check():
    """Comprehensive health check endpoint with monitoring data"""
    try:
        import os
        from flask import current_app
        
        # Check database connectivity
        db.session.execute('SELECT 1')
        
        # Check file system access
        upload_dir = os.path.join(current_app.config.get('UPLOAD_FOLDER', '/tmp'), 'health_check')
        os.makedirs(upload_dir, exist_ok=True)
        test_file = os.path.join(upload_dir, 'health_test.txt')
        with open(test_file, 'w') as f:
            f.write('health check')
        os.remove(test_file)
        
        # Check if required tools are available
        import subprocess
        pdfinfo_available = False
        ghostscript_available = False
        
        try:
            subprocess.run(['pdfinfo', '--version'], capture_output=True, timeout=5)
            pdfinfo_available = True
        except:
            pass
        
        try:
            subprocess.run(['gs', '--version'], capture_output=True, timeout=5)
            ghostscript_available = True
        except:
            pass
        
        # Check Redis connection
        redis_status = 'connected'
        try:
            from src.celery_app import get_celery_app
            celery_app = get_celery_app()
            redis_available = celery_app.control.ping(timeout=1.0) is not None
            if not redis_available:
                redis_status = 'disconnected'
        except:
            redis_status = 'disconnected'
        
        # Get system metrics
        import psutil
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        return success_response(
            message='Compression service is healthy',
            data={
                'service': 'compression',
                'status': 'healthy',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'system': {
                    'memory_usage_percent': memory.percent,
                    'disk_usage_percent': disk.percent,
                    'cpu_count': psutil.cpu_count(),
                    'load_average': psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
                },
                'dependencies': {
                    'database': 'connected',
                    'filesystem': 'accessible',
                    'pdfinfo': pdfinfo_available,
                    'ghostscript': ghostscript_available,
                    'redis': redis_status
                },
                'version': '1.0.0'
            }
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return error_response(
            message='Health check failed',
            error_code='HEALTH_CHECK_FAILED',
            details={'error': str(e)},
            status_code=503
        )
