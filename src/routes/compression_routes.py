import os
import logging
import uuid
from flask import Blueprint, request, send_file, jsonify, g
from flask_cors import CORS
from src.services.compression_service import CompressionService
from src.utils.security_utils import validate_file
from src.utils.validation import validate_request_payload
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

compression_bp = Blueprint('compression', __name__)
CORS(compression_bp, resources={r"/api": {"origins": ["https://www.pdfsmaller.site"]}})

# Initialize compression service lazily
compression_service = None

def get_compression_service():
    global compression_service
    if compression_service is None:
        compression_service = CompressionService(os.environ.get('UPLOAD_FOLDER', '/tmp/pdf_uploads'))
    return compression_service

class JobStatus(Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'


# Updated routes.py - Fixed download endpoint
@compression_bp.route('/jobs/<job_id>/download', methods=['GET'])
def download_job_result(job_id):
    """Download the result file for a completed job"""
    try:
        from src.models.job import Job, JobStatus
        
        job = Job.query.filter_by(id=job_id).first()
        
        if not job:
            logger.error(f"Job {job_id} not found")
            return jsonify({'error': 'Job not found'}), 404
        
        if job.status != JobStatus.COMPLETED:
            logger.warning(f"Job {job_id} not completed, status: {job.status.value}")
            return jsonify({
                'error': 'Job not completed yet',
                'status': job.status.value
            }), 400
        
        if not job.result or 'output_path' not in job.result:
            logger.error(f"Job {job_id} has no result or output_path")
            return jsonify({'error': 'No result file available'}), 404
        
        output_path = job.result['output_path']
        
        if not os.path.exists(output_path):
            logger.error(f"Result file not found at {output_path} for job {job_id}")
            return jsonify({'error': 'Result file not found'}), 404
        
        # Verify file is readable and not empty
        try:
            file_size = os.path.getsize(output_path)
            if file_size == 0:
                logger.error(f"Result file is empty for job {job_id}")
                return jsonify({'error': 'Result file is empty'}), 404
        except OSError as e:
            logger.error(f"Cannot access result file for job {job_id}: {e}")
            return jsonify({'error': 'Cannot access result file'}), 404
        
        # Generate download filename
        original_filename = job.result.get('original_filename', 'document.pdf')
        # Ensure filename is safe
        safe_filename = secure_filename(original_filename)
        download_filename = f"compressed_{safe_filename}"
        
        return send_file(
            output_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Error downloading job result {job_id}: {str(e)}")
        return jsonify({'error': f'Failed to download result file: {str(e)}'}), 500

# Fixed job status endpoint
@compression_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get job status and result if completed"""
    try:
        from src.models import Job, JobStatus as JS
        
        # Validate job_id format
        if not job_id or len(job_id.strip()) == 0:
            return jsonify({'error': 'Invalid job ID'}), 400
        
        job = Job.query.filter_by(id=job_id.strip()).first()
        logger.debug(f"Looking up job status for job_id {job_id}")

        if not job:
            logger.debug(f"Job with id {job_id} was not found")
            return jsonify({'error': 'Job not found'}), 404
        
        response_data = {
            'job_id': job.id,
            'status': job.status.value,
            'task_type': job.task_type,
            'client_job_id': job.client_job_id,
            'created_at': job.created_at.isoformat(),
            'updated_at': job.updated_at.isoformat()
        }
        
        logger.debug(f"Job status found: {response_data}")        

        if job.status == JS.COMPLETED and job.result:
            response_data['result'] = job.result
            
            # Verify download availability
            if job.result.get('output_path') and os.path.exists(job.result['output_path']):
                response_data['download_url'] = f"/api/jobs/{job_id}/download"
                response_data['download_available'] = True
            else:
                logger.warning(f"Job {job_id} completed but output file not found")
                response_data['download_available'] = False
        
        elif job.status == JS.FAILED and job.error:
            response_data['error'] = job.error
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error getting job status {job_id}: {str(e)}")
        return jsonify({'error': f'Failed to retrieve job status: {str(e)}'}), 500

# Updated tasks.py - Ensure proper error handling

@compression_bp.route('/compress', methods=['POST'])
def compress_pdf():
    """Endpoint for PDF compression - returns job ID immediately"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        
        # Validate file
        validation_error = validate_file(file)
        if validation_error:
            return jsonify({'error': validation_error}), 400
        
        # Get compression parameters
        compression_level = request.form.get('compressionLevel', 'medium')
        try:
            image_quality = int(request.form.get('imageQuality', 80))
        except (ValueError, TypeError):
            image_quality = 80
        image_quality = max(10, min(image_quality, 100))

        # Get client-provided tracking IDs
        client_job_id = request.form.get('client_job_id')
        client_session_id = request.form.get('client_session_id')

        # Read file data
        file_data = file.read()
        
        # Create job and enqueue for processing
        job_id = str(uuid.uuid4())
        
        # Enqueue compression task (async processing)
        from src.tasks.tasks import compress_task
        compress_task.delay(
            job_id,
            file_data,
            {
                'compression_level': compression_level,
                'image_quality': image_quality
            },
            original_filename=file.filename,
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        
        logger.info(f"Compression job {job_id} enqueued (client_job_id: {client_job_id})")
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'status': JobStatus.PENDING.value,
            'message': 'Compression job queued successfully'
        }), 202
        
    except Exception as e:
        logger.error(f"Error creating compression job: {str(e)}")
        return jsonify({'error': f'Failed to create compression job: {str(e)}'}), 500

@compression_bp.route('/bulk', methods=['POST'])
def bulk_compress():
    """Endpoint for bulk PDF compression - returns job ID immediately"""
    try:
        # Check if files were uploaded
        if 'files' not in request.files:
            return jsonify({
                'error': 'No files provided',
                'error_code': 'NO_FILES'
            }), 400
        
        files = request.files.getlist('files')
        
        if not files or len(files) == 0:
            return jsonify({
                'error': 'No files provided',
                'error_code': 'NO_FILES'
            }), 400
        
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
        client_job_id = request.form.get('client_job_id')
        client_session_id = request.form.get('client_session_id')
        
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
            return jsonify({'error': 'No valid files provided'}), 400
        
        # Create job and enqueue for processing
        job_id = str(uuid.uuid4())
        
        # Enqueue bulk compression task
        from src.tasks.tasks import bulk_compress_task
        bulk_compress_task.delay(
            job_id,
            file_data_list,
            original_filenames,
            compression_settings,
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        
        logger.info(f"Bulk compression job {job_id} enqueued (client_job_id: {client_job_id})")
        
        return jsonify({
            'success': True,
            'job_id': job_id,
            'status': JobStatus.PENDING.value,
            'file_count': len(file_data_list),
            'message': f'Bulk compression job created with {len(file_data_list)} files'
        }), 202
        
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
            from src.celery_app import celery_app
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