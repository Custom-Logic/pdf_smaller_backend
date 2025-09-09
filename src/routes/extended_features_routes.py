"""
Extended Features Routes - Job-Oriented Architecture
Handles conversion, OCR, AI, and cloud integration endpoints
Returns job IDs for async processing
"""

import json
import logging
import os
import uuid
from datetime import datetime
from enum import Enum

from flask import Blueprint, request, send_file, jsonify
from flask_cors import CORS

from ..services.ai_service import AIService
from ..services.cloud_integration_service import CloudIntegrationService
from ..services.conversion_service import ConversionService
from ..services.ocr_service import OCRService
from ..utils.response_helpers import success_response, error_response

# Initialize blueprint
extended_features_bp = Blueprint('extended_features', __name__)
CORS(extended_features_bp, resources={r"/api": {"origins": ["https://www.pdfsmaller.site"]}})

# Initialize services
conversion_service = ConversionService()
ocr_service = OCRService()
ai_service = AIService()
cloud_service = CloudIntegrationService()

# Configure logging
logger = logging.getLogger(__name__)

# Job status enum
class JobStatus(Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'

# File upload configuration
ALLOWED_EXTENSIONS = {
    'conversion': {'pdf'},
    'ocr': {'pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'},
    'ai': {'pdf'}
}

MAX_FILE_SIZES = {
    'conversion': 100 * 1024 * 1024,  # 100MB
    'ocr': 50 * 1024 * 1024,          # 50MB
    'ai': 25 * 1024 * 1024            # 25MB
}

def allowed_file(filename, feature_type):
    """Check if file extension is allowed for the feature"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS.get(feature_type, set())

def get_file_and_validate(feature_type, max_size_mb=None):
    """Helper function to get and validate uploaded file"""
    if 'file' not in request.files:
        return None, error_response(message="No file provided", status_code=400)

    file = request.files['file']
    if file.filename == '':
        return None, error_response(message="No file selected", status_code=400)

    if not allowed_file(file.filename, feature_type):
        allowed = ', '.join(ALLOWED_EXTENSIONS.get(feature_type, set()))
        return None, error_response(message=f"Invalid file type. Allowed: {allowed}", status_code=400)

    max_size = MAX_FILE_SIZES.get(feature_type, 25 * 1024 * 1024)
    if file.content_length and file.content_length > max_size:
        size_mb = max_size // (1024 * 1024)
        return None, error_response(message=f"File too large. Maximum size is {size_mb}MB.", status_code=400)

    return file, None

def get_tracking_ids():
    """Helper function to extract client tracking IDs"""
    return {
        'client_job_id': request.form.get('client_job_id'),
        'client_session_id': request.form.get('client_session_id')
    }

def get_json_tracking_ids():
    """Helper function to extract tracking IDs from JSON"""
    data = request.get_json() or {}
    return {
        'client_job_id': data.get('client_job_id'),
        'client_session_id': data.get('client_session_id')
    }

# ============================================================================
# JOB MANAGEMENT ROUTES
# ============================================================================

@extended_features_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get job status and result if completed"""
    try:
        from src.models.job import Job, JobStatus as JS

        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            return error_response(message="Job not found", status_code=404)

        response_data = {
            'job_id': job.job_id,
            'status': job.status,
            'task_type': job.task_type,
            'session_id': job.session_id,
            'created_at': job.created_at.isoformat() if job.created_at else None,
            'updated_at': job.updated_at.isoformat() if job.updated_at else None
        }

        if job.status == JobStatus.COMPLETED.value and job.result:
            response_data['result'] = job.result
            if job.result.get('output_path'):
                response_data['download_url'] = f"/api/extended/jobs/{job_id}/download"
        elif job.status == JobStatus.FAILED.value and job.error:
            response_data['error'] = job.error

        return success_response(message="Job status retrieved", data=response_data, status_code=202)

    except Exception as e:
        logger.error(f"Error getting job status {job_id}: {str(e)}")
        return error_response("Failed to retrieve job status", 500)

@extended_features_bp.route('/jobs/<job_id>/download', methods=['GET'])
def download_job_result(job_id):
    """Download the result file for a completed job"""
    try:
        from src.models.job import Job, JobStatus

        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            return error_response(message="Job not found", status_code=404)

        if job.status != JobStatus.COMPLETED.value:
            return error_response(message="Job not completed yet", status_code=400)

        if not job.result or 'output_path' not in job.result:
            return error_response(message="No result file available", status_code=404)

        output_path = job.result['output_path']
        if not os.path.exists(output_path):
            return error_response(message="Result file not found", status_code=404)

        # Generate download filename
        original_filename = job.result.get('original_filename', 'result')
        download_filename = f"{job.task_type}_{original_filename}"
        mimetype = job.result.get('mime_type', 'application/octet-stream')

        return send_file(
            output_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype=mimetype
        )

    except Exception as e:
        logger.error(f"Error downloading job result {job_id}: {str(e)}")
        return error_response(message="Failed to download result file", status_code=500)

# ============================================================================
# CONVERSION ROUTES (Job-Oriented)
# ============================================================================

@extended_features_bp.route('/convert/pdf-to-<format>', methods=['POST'])
def convert_pdf(format):
    """Convert PDF to specified format - returns job ID"""
    try:
        # Validate format
        supported_formats = ['docx', 'xlsx', 'txt', 'html']
        if format not in supported_formats:
            return error_response(message=f"Unsupported format: {format}", status_code=400)

        # Get and validate file
        file, error = get_file_and_validate('conversion')
        if error:
            return error

        # Get conversion options
        options = {}
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response(message="Invalid options format", status_code=400)

        # Get tracking IDs
        tracking = get_tracking_ids()

        # Read file data
        file_data = file.read()
        job_id = str(uuid.uuid4())

        # Enqueue conversion task using .delay() pattern
        from src.tasks.tasks import convert_pdf_task
        task = convert_pdf_task.delay(
            job_id,
            file_data,
            format,
            options,
            file.filename,
            tracking['client_job_id'],
            tracking['client_session_id']
        )

        logger.info(f"Conversion job {job_id} enqueued (format: {format}, task_id: {task.id})")

        return success_response(message="Conversion job queued successfully", data={
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value,
            'format': format
        }, status_code=202)

    except Exception as e:
        logger.error(f"PDF conversion job creation failed: {str(e)}")
        return error_response(message=f"Failed to create conversion job: {str(e)}", status_code=500)

@extended_features_bp.route('/convert/preview', methods=['POST'])
def get_conversion_preview():
    """Get conversion preview and estimates - returns job ID"""
    try:
        file, error = get_file_and_validate('conversion')
        if error:
            return error

        format = request.form.get('format', 'docx')
        options = {}

        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response(message="Invalid options format", status_code=400)

        tracking = get_tracking_ids()
        file_data = file.read()
        job_id = str(uuid.uuid4())

        # Enqueue conversion preview task using .delay() pattern
        from src.tasks.tasks import conversion_preview_task
        task = conversion_preview_task.delay(
            job_id,
            file_data,
            format,
            options,
            tracking['client_job_id'],
            tracking['client_session_id']
        )

        logger.info(f"Conversion preview job {job_id} enqueued (task_id: {task.id})")

        return success_response(message="Conversion preview job queued successfully", data={
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value
        }, status_code=202)

    except Exception as e:
        logger.error(f"Conversion preview job creation failed: {str(e)}")
        return error_response(message=f"Failed to create preview job: {str(e)}", status_code=500)

# ============================================================================
# OCR ROUTES (Job-Oriented)
# ============================================================================

@extended_features_bp.route('/ocr/process', methods=['POST'])
def process_ocr():
    """Process OCR on uploaded file - returns job ID"""
    try:
        file, error = get_file_and_validate('ocr')
        if error:
            return error

        options = {}
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response(message="Invalid options format", status_code=400)

        tracking = get_tracking_ids()
        file_data = file.read()
        job_id = str(uuid.uuid4())

        # Enqueue OCR task using .delay() pattern
        from src.tasks.tasks import ocr_process_task
        task = ocr_process_task.delay(
            job_id,
            file_data,
            options,
            file.filename,
            tracking['client_job_id'],
            tracking['client_session_id']
        )

        logger.info(f"OCR job {job_id} enqueued (task_id: {task.id})")

        return success_response(message="OCR job queued successfully", data={
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value
        }, status_code=202)

    except Exception as e:
        logger.error(f"OCR job creation failed: {str(e)}")
        return error_response(message=f"Failed to create OCR job: {str(e)}", status_code=500)

@extended_features_bp.route('/ocr/preview', methods=['POST'])
def get_ocr_preview():
    """Get OCR preview and estimates - returns job ID"""
    try:
        file, error = get_file_and_validate('ocr')
        if error:
            return error

        options = {}
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response(message="Invalid options format", status_code=400)

        tracking = get_tracking_ids()
        file_data = file.read()
        job_id = str(uuid.uuid4())

        # Enqueue OCR preview task using .delay() pattern
        from src.tasks.tasks import ocr_preview_task
        task = ocr_preview_task.delay(
            job_id,
            file_data,
            options,
            tracking['client_job_id'],
            tracking['client_session_id']
        )

        logger.info(f"OCR preview job {job_id} enqueued (task_id: {task.id})")

        return success_response(message="OCR preview job queued successfully", data={
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value
        }, status_code=202)

    except Exception as e:
        logger.error(f"OCR preview job creation failed: {str(e)}")
        return error_response(message=f"Failed to create OCR preview job: {str(e)}", status_code=500)

# ============================================================================
# AI ROUTES (Job-Oriented)
# ============================================================================

@extended_features_bp.route('/ai/summarize', methods=['POST'])
def summarize_pdf():
    """Summarize PDF content using AI - returns job ID"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return error_response(message="No text content provided", status_code=400)

        text = data['text']
        if len(text) > 100000:  # 100KB limit
            return error_response(message="Text too long. Maximum length is 100KB.", status_code=400)

        options = data.get('options', {})
        tracking = get_json_tracking_ids()
        job_id = str(uuid.uuid4())

        # Enqueue AI summarization task using .delay() pattern
        from src.tasks.tasks import ai_summarize_task
        task = ai_summarize_task.delay(
            job_id,
            text,
            options,
            tracking['client_job_id'],
            tracking['client_session_id']
        )

        logger.info(f"AI summarization job {job_id} enqueued (task_id: {task.id})")

        return success_response(message="Summarization job queued successfully", data={
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value
        }, status_code=202)

    except Exception as e:
        logger.error(f"AI summarization job creation failed: {str(e)}")
        return error_response(message=f"Failed to create summarization job: {str(e)}", status_code=500)

@extended_features_bp.route('/ai/translate', methods=['POST'])
def translate_text():
    """Translate text using AI - returns job ID"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return error_response(message="No text content provided", status_code=400)

        text = data['text']
        if len(text) > 100000:  # 100KB limit
            return error_response(message="Text too long. Maximum length is 100KB.", status_code=400)

        target_language = data.get('target_language', 'en')
        options = data.get('options', {})
        tracking = get_json_tracking_ids()
        job_id = str(uuid.uuid4())

        # Enqueue AI translation task using .delay() pattern
        from src.tasks.tasks import ai_translate_task
        task = ai_translate_task.delay(
            job_id,
            text,
            target_language,
            options,
            tracking['client_job_id'],
            tracking['client_session_id']
        )

        logger.info(f"AI translation job {job_id} enqueued (task_id: {task.id})")

        return success_response(message="Translation job queued successfully", data={
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value
        }, status_code=202)

    except Exception as e:
        logger.error(f"AI translation job creation failed: {str(e)}")
        return error_response(message=f"Failed to create translation job: {str(e)}", status_code=500)

# ============================================================================
# TEXT EXTRACTION ROUTES (Job-Oriented)
# ============================================================================

@extended_features_bp.route('/extract/text', methods=['POST'])
def extract_text():
    """Extract text content from PDF - returns job ID"""
    try:
        file, error = get_file_and_validate('ai')
        if error:
            return error

        tracking = get_tracking_ids()
        file_data = file.read()
        job_id = str(uuid.uuid4())

        # Enqueue text extraction task using .delay() pattern
        from src.tasks.tasks import extract_text_task
        task = extract_text_task.delay(
            job_id,
            file_data,
            file.filename,
            tracking['client_job_id'],
            tracking['client_session_id']
        )

        logger.info(f"Text extraction job {job_id} enqueued (task_id: {task.id})")

        return success_response(message="Text extraction job queued successfully", data={
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value
        }, status_code=202)

    except Exception as e:
        logger.error(f"Text extraction job creation failed: {str(e)}")
        return error_response(message=f"Failed to create text extraction job: {str(e)}", status_code=500)

# ============================================================================
# CLOUD INTEGRATION ROUTES (Synchronous)
# ============================================================================

@extended_features_bp.route('/cloud/<provider>/token', methods=['POST'])
def exchange_cloud_token(provider):
    """Exchange authorization code for access token"""
    try:
        data = request.get_json()
        if not data or 'code' not in data:
            return error_response(message="No authorization code provided", status_code=400)

        code = data['code']
        redirect_uri = data.get('redirect_uri')

        result = cloud_service.exchange_code_for_token(provider, code, redirect_uri)
        return success_response(message="Token exchange successful", data=result)

    except Exception as e:
        logger.error(f"Cloud token exchange failed: {str(e)}")
        return error_response(message=f"Token exchange failed: {str(e)}", status_code=500)

@extended_features_bp.route('/cloud/<provider>/validate', methods=['GET'])
def validate_cloud_token(provider):
    """Validate cloud provider access token"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return error_response(message="No valid authorization header", status_code=401)

        token = auth_header.split(' ')[1]
        is_valid = cloud_service.validate_token(provider, token)

        if is_valid:
            return success_response(message="Token is valid", data={'valid': True})
        else:
            return error_response(message="Token is invalid", status_code=401)

    except Exception as e:
        logger.error(f"Cloud token validation failed: {str(e)}")
        return error_response(message=f"Token validation failed: {str(e)}", status_code=500)

# ============================================================================
# HEALTH CHECK AND STATUS ROUTES
# ============================================================================

@extended_features_bp.route('/extended-features/status', methods=['GET'])
def get_extended_features_status():
    """Get status of all extended features"""
    try:
        # Check Redis availability
        redis_available = False
        try:
            from src.celery_app import celery_app
            redis_available = celery_app.control.ping(timeout=1.0) is not None
        except:
            pass

        status = {
            'conversion': {
                'available': True,
                'supported_formats': ['docx', 'xlsx', 'txt', 'html'],
                'max_file_size': '100MB',
                'async_processing': True
            },
            'ocr': {
                'available': True,
                'supported_formats': ['pdf', 'png', 'jpg', 'jpeg', 'tiff', 'bmp'],
                'max_file_size': '50MB',
                'async_processing': True
            },
            'ai': {
                'available': True,
                'supported_formats': ['pdf'],
                'max_file_size': '25MB',
                'async_processing': True
            },
            'cloud': {
                'available': True,
                'supported_providers': ['google_drive', 'dropbox', 'onedrive'],
                'async_processing': False
            },
            'queue': {
                'redis_available': redis_available,
                'job_processing': True
            },
            'timestamp': datetime.utcnow().isoformat()
        }

        return success_response(message="Extended features status retrieved successfully", data=status)

    except Exception as e:
        logger.error(f"Status retrieval failed: {str(e)}")
        return error_response(message=f"Status retrieval failed: {str(e)}", status_code=500)

@extended_features_bp.route('/extended-features/capabilities', methods=['GET'])
def get_extended_features_capabilities():
    """Get detailed capabilities of all extended features"""
    try:
        capabilities = {
            'conversion': {
                'name': 'PDF Conversion',
                'description': 'Convert PDFs to Word, Excel, Text, and HTML formats',
                'features': ['format_conversion', 'layout_preservation', 'table_extraction'],
                'options': {
                    'preserveLayout': 'boolean',
                    'extractTables': 'boolean',
                    'extractImages': 'boolean',
                    'quality': 'string (low|medium|high)'
                },
                'processing_mode': 'async'
            },
            'ocr': {
                'name': 'Optical Character Recognition',
                'description': 'Extract text from scanned PDFs and images',
                'features': ['text_extraction', 'searchable_pdf', 'language_support'],
                'options': {
                    'language': 'string',
                    'quality': 'string (fast|balanced|accurate)',
                    'outputFormat': 'string (searchable_pdf|text|json)'
                },
                'processing_mode': 'async'
            },
            'ai': {
                'name': 'AI-Powered Features',
                'description': 'Summarize and translate PDF content using AI',
                'features': ['summarization', 'translation', 'multiple_languages'],
                'options': {
                    'style': 'string (concise|detailed|academic|casual|professional)',
                    'maxLength': 'string (short|medium|long)',
                    'targetLanguage': 'string (language code)'
                },
                'processing_mode': 'async'
            },
            'cloud': {
                'name': 'Cloud Integration',
                'description': 'Save and load files from cloud storage providers',
                'features': ['file_upload', 'file_download', 'folder_management', 'oauth_authentication'],
                'providers': ['google_drive', 'dropbox', 'onedrive'],
                'processing_mode': 'sync'
            }
        }

        return success_response(message="Extended features capabilities retrieved successfully", data=capabilities)

    except Exception as e:
        logger.error(f"Capabilities retrieval failed: {str(e)}")
        return error_response(message=f"Capabilities retrieval failed: {str(e)}", status_code=500)