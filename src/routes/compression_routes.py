import subprocess
import os
import logging
from flask import Blueprint, request, send_file, jsonify, g
from flask_jwt_extended import jwt_required, get_jwt_identity, verify_jwt_in_request
from flask_cors import CORS
from src.services.compression_service import CompressionService
from src.services.subscription_service import SubscriptionService
from src.utils.security_utils import validate_file, validate_request_headers, log_security_event
from src.utils.rate_limiter import compression_rate_limit
from src.utils.validation import validate_request_payload

logger = logging.getLogger(__name__)

compression_bp = Blueprint('compression', __name__)
CORS(compression_bp, resources={r"/compress": {"origins": ["https://www.pdfsmaller.site"]}})

# Initialize compression service lazily
compression_service = None

def get_compression_service():
    global compression_service
    if compression_service is None:
        compression_service = CompressionService(os.environ.get('UPLOAD_FOLDER', '/tmp/pdf_uploads'))
    return compression_service

@compression_bp.before_request
def before_request():
    """Security checks before processing requests"""
    # Validate request headers for security threats
    header_validation = validate_request_headers()
    if not header_validation['valid']:
        log_security_event('blocked_request', {
            'reason': 'header_validation_failed',
            'warnings': header_validation['warnings']
        }, 'WARNING')
        return jsonify({
            'error': {
                'code': 'REQUEST_BLOCKED',
                'message': 'Request blocked due to security concerns'
            }
        }), 403
    
    # Set user tier for rate limiting
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            permission_status = SubscriptionService.check_compression_permission(user_id)
            g.current_user_id = user_id
            g.current_user_tier = permission_status.get('plan_name', 'free')
        else:
            g.current_user_tier = 'anonymous'
    except:
        g.current_user_tier = 'anonymous'

@compression_bp.route('/compress', methods=['POST'])
@compression_rate_limit
def compress_pdf():
    """Endpoint for PDF compression with user authentication and usage tracking"""
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

    # Check for user authentication (optional for backward compatibility)
    user_id = None
    try:
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
    except:
        pass  # Continue without user context for unauthenticated requests

    # If user is authenticated, check permissions and usage limits
    if user_id:
        # Calculate file size in MB
        file.seek(0, 2)  # Seek to end
        file_size_bytes = file.tell()
        file.seek(0)  # Reset to beginning
        file_size_mb = file_size_bytes / (1024 * 1024)
        
        # Check user permissions
        permission_check = get_compression_service().check_user_permissions(user_id, file_size_mb)
        if not permission_check['allowed']:
            return jsonify({
                'error': permission_check['reason'],
                'usage_info': permission_check['details']
            }), 403

    try:
        # Process the file with user context
        output_path = get_compression_service().process_upload(
            file, compression_level, image_quality, user_id
        )
        
        # Return the compressed file
        return send_file(
            output_path,
            as_attachment=True,
            download_name=f"compressed_{file.filename}",
            mimetype='application/pdf'
        )
        
    except Exception as e:
        logger.error(f"Error processing file: {str(e)}")
        return jsonify({'error': f'Failed to compress PDF: {str(e)}'}), 500

@compression_bp.route('/info', methods=['POST'])
def get_pdf_info():
    """Get information about a PDF file"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    # Validate file
    validation_error = validate_file(file)
    if validation_error:
        return jsonify({'error': validation_error}), 400
    
    try:
        # Save file temporarily
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            file.save(tmp.name)
            
            # Use pdfinfo to get information
            result = subprocess.run(
                ['pdfinfo', tmp.name],
                capture_output=True, text=True
            )
            
            # Parse pdfinfo output
            info = {}
            for line in result.stdout.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    info[key.strip()] = value.strip()
            
            # Clean up
            os.unlink(tmp.name)
            
            return jsonify(info)
            
    except Exception as e:
        logger.error(f"Error getting PDF info: {str(e)}")
        return jsonify({'error': f'Failed to get PDF information: {str(e)}'}), 500

@compression_bp.route('/jobs', methods=['GET'])
@jwt_required()
def get_compression_jobs():
    """Get user's compression job history"""
    user_id = get_jwt_identity()
    
    try:
        limit = request.args.get('limit', 10, type=int)
        limit = min(max(1, limit), 50)  # Limit between 1 and 50
        
        jobs = get_compression_service().get_user_compression_jobs(user_id, limit)
        
        return jsonify({
            'jobs': jobs,
            'total': len(jobs)
        })
        
    except Exception as e:
        logger.error(f"Error getting compression jobs for user {user_id}: {str(e)}")
        return jsonify({'error': 'Failed to retrieve compression jobs'}), 500

@compression_bp.route('/jobs/<int:job_id>', methods=['GET'])
@jwt_required()
def get_compression_job(job_id):
    """Get specific compression job details"""
    user_id = get_jwt_identity()
    
    try:
        from src.models import CompressionJob
        job = CompressionJob.query.filter_by(id=job_id, user_id=user_id).first()
        
        if not job:
            return jsonify({'error': 'Compression job not found'}), 404
        
        return jsonify(job.to_dict())
        
    except Exception as e:
        logger.error(f"Error getting compression job {job_id} for user {user_id}: {str(e)}")
        return jsonify({'error': 'Failed to retrieve compression job'}), 500

@compression_bp.route('/usage', methods=['GET'])
@jwt_required()
def get_usage_info():
    """Get user's current usage statistics and limits"""
    user_id = get_jwt_identity()
    
    try:
        usage_stats = SubscriptionService.get_usage_statistics(user_id)
        permission_status = SubscriptionService.check_compression_permission(user_id)
        
        return jsonify({
            'usage': usage_stats,
            'permissions': permission_status,
            'can_compress': permission_status['can_compress']
        })
        
    except Exception as e:
        logger.error(f"Error getting usage info for user {user_id}: {str(e)}")
        return jsonify({'error': 'Failed to retrieve usage information'}), 500

@compression_bp.route('/bulk', methods=['POST'])
@jwt_required()
@limiter.limit(get_user_rate_limit)
def bulk_compress():
    """Endpoint for bulk PDF compression with premium user validation"""
    user_id = get_jwt_identity()
    
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
        
        # Initialize bulk compression service
        from src.services.bulk_compression_service import BulkCompressionService
        bulk_service = BulkCompressionService(os.environ.get('UPLOAD_FOLDER', '/tmp/pdf_uploads'))
        
        # Validate bulk request
        validation_result = bulk_service.validate_bulk_request(user_id, files)
        
        if not validation_result['valid']:
            return jsonify({
                'error': validation_result['error'],
                'error_code': validation_result.get('error_code', 'VALIDATION_FAILED'),
                'details': {
                    'max_files': validation_result.get('max_files'),
                    'validation_errors': validation_result.get('validation_errors'),
                    'usage_info': validation_result.get('usage_info')
                }
            }), 400
        
        # Create bulk compression job
        job = bulk_service.create_bulk_job(user_id, files, compression_settings)
        
        # Queue job for asynchronous processing
        task_id = bulk_service.process_bulk_job_async(job.id)
        
        logger.info(f"Created bulk compression job {job.id} for user {user_id} with {len(files)} files")
        
        return jsonify({
            'success': True,
            'job_id': job.id,
            'task_id': task_id,
            'file_count': len(files),
            'total_size_mb': validation_result['total_size_mb'],
            'status': 'queued',
            'message': f'Bulk compression job created with {len(files)} files'
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating bulk compression job for user {user_id}: {str(e)}")
        return jsonify({
            'error': 'Failed to create bulk compression job',
            'error_code': 'SYSTEM_ERROR'
        }), 500

@compression_bp.route('/bulk/jobs/<int:job_id>/status', methods=['GET'])
@jwt_required()
def get_bulk_job_status(job_id):
    """Get status of a bulk compression job"""
    user_id = get_jwt_identity()
    
    try:
        from src.services.bulk_compression_service import BulkCompressionService
        bulk_service = BulkCompressionService(os.environ.get('UPLOAD_FOLDER', '/tmp/pdf_uploads'))
        
        # Get job progress
        progress = bulk_service.get_job_progress(job_id)
        
        if not progress['found']:
            return jsonify({
                'error': 'Job not found',
                'error_code': 'JOB_NOT_FOUND'
            }), 404
        
        # Verify job belongs to user
        from src.models import CompressionJob
        job = CompressionJob.query.filter_by(id=job_id, user_id=user_id).first()
        
        if not job:
            return jsonify({
                'error': 'Job not found or access denied',
                'error_code': 'ACCESS_DENIED'
            }), 404
        
        # Get Celery task status if job is processing
        task_status = None
        if job.task_id and job.status == 'processing':
            task_status = bulk_service.get_task_status(job.task_id)
        
        response_data = {
            'job_id': job_id,
            'status': progress['status'],
            'job_type': progress['job_type'],
            'file_count': progress['file_count'],
            'completed_count': progress['completed_count'],
            'progress_percentage': progress['progress_percentage'],
            'created_at': progress['created_at'],
            'started_at': progress['started_at'],
            'completed_at': progress['completed_at'],
            'is_completed': progress['is_completed'],
            'is_successful': progress['is_successful'],
            'error_message': progress['error_message']
        }
        
        # Add result information if completed successfully
        if progress['is_completed'] and progress['is_successful']:
            response_data.update({
                'original_size_bytes': progress.get('original_size_bytes'),
                'compressed_size_bytes': progress.get('compressed_size_bytes'),
                'compression_ratio': progress.get('compression_ratio'),
                'result_available': progress.get('result_available', False)
            })
        
        # Add task status if available
        if task_status:
            response_data['task_status'] = task_status
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"Error getting bulk job status {job_id} for user {user_id}: {str(e)}")
        return jsonify({
            'error': 'Failed to retrieve job status',
            'error_code': 'SYSTEM_ERROR'
        }), 500

@compression_bp.route('/bulk/jobs/<int:job_id>/download', methods=['GET'])
@jwt_required()
def download_bulk_result(job_id):
    """Download the result ZIP archive for a completed bulk compression job"""
    user_id = get_jwt_identity()
    
    try:
        from src.services.bulk_compression_service import BulkCompressionService
        bulk_service = BulkCompressionService(os.environ.get('UPLOAD_FOLDER', '/tmp/pdf_uploads'))
        
        # Get result file path (includes user authorization check)
        result_path = bulk_service.get_result_file_path(job_id, user_id)
        
        if not result_path:
            return jsonify({
                'error': 'Result file not found or not available',
                'error_code': 'RESULT_NOT_AVAILABLE'
            }), 404
        
        # Verify file exists
        if not os.path.exists(result_path):
            logger.error(f"Result file missing for job {job_id}: {result_path}")
            return jsonify({
                'error': 'Result file not found on server',
                'error_code': 'FILE_MISSING'
            }), 404
        
        # Get job details for filename
        from src.models import CompressionJob
        job = CompressionJob.query.filter_by(id=job_id, user_id=user_id).first()
        
        if not job:
            return jsonify({
                'error': 'Job not found',
                'error_code': 'JOB_NOT_FOUND'
            }), 404
        
        # Generate download filename
        download_filename = f"compressed_files_job_{job_id}_{job.file_count}_files.zip"
        
        logger.info(f"User {user_id} downloading bulk result for job {job_id}")
        
        return send_file(
            result_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        logger.error(f"Error downloading bulk result {job_id} for user {user_id}: {str(e)}")
        return jsonify({
            'error': 'Failed to download result file',
            'error_code': 'SYSTEM_ERROR'
        }), 500

@compression_bp.route('/bulk/jobs', methods=['GET'])
@jwt_required()
def get_bulk_jobs():
    """Get user's bulk compression job history"""
    user_id = get_jwt_identity()
    
    try:
        limit = request.args.get('limit', 10, type=int)
        limit = min(max(1, limit), 50)  # Limit between 1 and 50
        
        from src.services.bulk_compression_service import BulkCompressionService
        bulk_service = BulkCompressionService(os.environ.get('UPLOAD_FOLDER', '/tmp/pdf_uploads'))
        
        jobs = bulk_service.get_user_bulk_jobs(user_id, limit)
        
        return jsonify({
            'jobs': jobs,
            'total': len(jobs)
        })
        
    except Exception as e:
        logger.error(f"Error getting bulk jobs for user {user_id}: {str(e)}")
        return jsonify({
            'error': 'Failed to retrieve bulk jobs',
            'error_code': 'SYSTEM_ERROR'
        }), 500