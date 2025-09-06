"""
Extended Features Routes - Job-Oriented Architecture
Handles conversion, OCR, AI, and cloud integration endpoints
Returns job IDs for async processing
"""

from flask import Blueprint, request, jsonify, send_file
from werkzeug.utils import secure_filename
import os
import tempfile
import json
from datetime import datetime
import logging
import uuid
from enum import Enum

# Import services
from ..services.conversion_service import ConversionService
from ..services.ocr_service import OCRService
from ..services.ai_service import AIService
from ..services.cloud_integration_service import CloudIntegrationService
from flask_cors import CORS

# Import utilities
from ..utils.file_validator import validate_file_type, validate_file_size
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

# ============================================================================
# JOB MANAGEMENT ROUTES
# ============================================================================

@extended_features_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    """Get job status and result if completed"""
    try:
        from src.models.job import Job, JobStatus as JS
        
        job = Job.query.filter_by(id=job_id).first()
        
        if not job:
            return error_response("Job not found", 404)
        
        response_data = {
            'job_id': job.id,
            'status': job.status.value,
            'task_type': job.task_type,
            'client_job_id': job.client_job_id,
            'created_at': job.created_at.isoformat(),
            'updated_at': job.updated_at.isoformat()
        }
        
        if job.status == JS.COMPLETED and job.result:
            response_data['result'] = job.result
            if job.result.get('output_path'):
                response_data['download_url'] = f"/api/extended/jobs/{job_id}/download"
        
        elif job.status == JS.FAILED and job.error:
            response_data['error'] = job.error
        
        return success_response("Job status retrieved", response_data)
        
    except Exception as e:
        logger.error(f"Error getting job status {job_id}: {str(e)}")
        return error_response("Failed to retrieve job status", 500)

@extended_features_bp.route('/jobs/<job_id>/download', methods=['GET'])
def download_job_result(job_id):
    """Download the result file for a completed job"""
    try:
        from src.models.job import Job, JobStatus
        
        job = Job.query.filter_by(id=job_id).first()
        
        if not job:
            return error_response("Job not found", 404)
        
        if job.status != JobStatus.COMPLETED:
            return error_response("Job not completed yet", 400)
        
        if not job.result or 'output_path' not in job.result:
            return error_response("No result file available", 404)
        
        output_path = job.result['output_path']
        
        if not os.path.exists(output_path):
            return error_response("Result file not found", 404)
        
        # Generate download filename
        original_filename = job.result.get('original_filename', 'result')
        download_filename = f"{job.task_type}_{original_filename}"
        
        # Set appropriate mimetype based on task type
        mimetype = job.result.get('mime_type', 'application/octet-stream')
        
        return send_file(
            output_path,
            as_attachment=True,
            download_name=download_filename,
            mimetype=mimetype
        )
        
    except Exception as e:
        logger.error(f"Error downloading job result {job_id}: {str(e)}")
        return error_response("Failed to download result file", 500)

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
            return error_response(f"Unsupported format: {format}", 400)
        
        # Check if file was uploaded
        if 'file' not in request.files:
            return error_response("No file provided", 400)
        
        file = request.files['file']
        if file.filename == '':
            return error_response("No file selected", 400)
        
        # Validate file
        if not allowed_file(file.filename, 'conversion'):
            return error_response("Invalid file type. Only PDF files are supported.", 400)
        
        if file.content_length and file.content_length > MAX_FILE_SIZES['conversion']:
            return error_response("File too large. Maximum size is 100MB.", 400)
        
        # Get conversion options
        options = {}
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response("Invalid options format", 400)
        
        # Get client-provided tracking IDs
        client_job_id = request.form.get('client_job_id')
        client_session_id = request.form.get('client_session_id')
        
        # Read file data
        file_data = file.read()
        original_filename = file.filename
        
        # Create job and enqueue for processing
        job_id = str(uuid.uuid4())
        
        # Enqueue conversion task
        from src.queues.task_queue import task_queue, convert_pdf_task
        task_queue.enqueue(
            convert_pdf_task,
            job_id,
            file_data,
            format,
            options,
            original_filename,
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        
        logger.info(f"Conversion job {job_id} enqueued (format: {format}, client_job_id: {client_job_id})")
        
        return success_response("Conversion job queued successfully", {
            'job_id': job_id,
            'status': JobStatus.PENDING.value,
            'format': format,
            'message': 'Conversion job queued for processing'
        }), 202
        
    except Exception as e:
        logger.error(f"PDF conversion job creation failed: {str(e)}")
        return error_response(f"Failed to create conversion job: {str(e)}", 500)

@extended_features_bp.route('/convert/preview', methods=['POST'])
def get_conversion_preview():
    """Get conversion preview and estimates - returns job ID"""
    try:
        if 'file' not in request.files:
            return error_response("No file provided", 400)
        
        file = request.files['file']
        format = request.form.get('format', 'docx')
        options = {}
        
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response("Invalid options format", 400)
        
        # Get client-provided tracking IDs
        client_job_id = request.form.get('client_job_id')
        client_session_id = request.form.get('client_session_id')
        
        # Read file data
        file_data = file.read()
        
        # Create job and enqueue for processing
        job_id = str(uuid.uuid4())
        
        # Enqueue preview task
        from src.queues.task_queue import task_queue, conversion_preview_task
        task_queue.enqueue(
            conversion_preview_task,
            job_id,
            file_data,
            format,
            options,
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        
        logger.info(f"Conversion preview job {job_id} enqueued (client_job_id: {client_job_id})")
        
        return success_response("Conversion preview job queued successfully", {
            'job_id': job_id,
            'status': JobStatus.PENDING.value,
            'message': 'Conversion preview job queued for processing'
        }), 202
        
    except Exception as e:
        logger.error(f"Conversion preview job creation failed: {str(e)}")
        return error_response(f"Failed to create preview job: {str(e)}", 500)

# ============================================================================
# OCR ROUTES (Job-Oriented)
# ============================================================================

@extended_features_bp.route('/ocr/process', methods=['POST'])
def process_ocr():
    """Process OCR on uploaded file - returns job ID"""
    try:
        if 'file' not in request.files:
            return error_response("No file provided", 400)
        
        file = request.files['file']
        if file.filename == '':
            return error_response("No file selected", 400)
        
        # Validate file
        if not allowed_file(file.filename, 'ocr'):
            return error_response("Invalid file type for OCR processing.", 400)
        
        if file.content_length and file.content_length > MAX_FILE_SIZES['ocr']:
            return error_response("File too large. Maximum size is 50MB.", 400)
        
        # Get OCR options
        options = {}
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response("Invalid options format", 400)
        
        # Get client-provided tracking IDs
        client_job_id = request.form.get('client_job_id')
        client_session_id = request.form.get('client_session_id')
        
        # Read file data
        file_data = file.read()
        original_filename = file.filename
        
        # Create job and enqueue for processing
        job_id = str(uuid.uuid4())
        
        # Enqueue OCR task
        from src.queues.task_queue import task_queue, ocr_process_task
        task_queue.enqueue(
            ocr_process_task,
            job_id,
            file_data,
            options,
            original_filename,
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        
        logger.info(f"OCR job {job_id} enqueued (client_job_id: {client_job_id})")
        
        return success_response("OCR job queued successfully", {
            'job_id': job_id,
            'status': JobStatus.PENDING.value,
            'message': 'OCR job queued for processing'
        }), 202
        
    except Exception as e:
        logger.error(f"OCR job creation failed: {str(e)}")
        return error_response(f"Failed to create OCR job: {str(e)}", 500)

@extended_features_bp.route('/ocr/preview', methods=['POST'])
def get_ocr_preview():
    """Get OCR preview and estimates - returns job ID"""
    try:
        if 'file' not in request.files:
            return error_response("No file provided", 400)
        
        file = request.files['file']
        options = {}
        
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response("Invalid options format", 400)
        
        # Get client-provided tracking IDs
        client_job_id = request.form.get('client_job_id')
        client_session_id = request.form.get('client_session_id')
        
        # Read file data
        file_data = file.read()
        
        # Create job and enqueue for processing
        job_id = str(uuid.uuid4())
        
        # Enqueue OCR preview task
        from src.queues.task_queue import task_queue, ocr_preview_task
        task_queue.enqueue(
            ocr_preview_task,
            job_id,
            file_data,
            options,
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        
        logger.info(f"OCR preview job {job_id} enqueued (client_job_id: {client_job_id})")
        
        return success_response("OCR preview job queued successfully", {
            'job_id': job_id,
            'status': JobStatus.PENDING.value,
            'message': 'OCR preview job queued for processing'
        }), 202
        
    except Exception as e:
        logger.error(f"OCR preview job creation failed: {str(e)}")
        return error_response(f"Failed to create OCR preview job: {str(e)}", 500)

# ============================================================================
# AI ROUTES (Job-Oriented)
# ============================================================================

@extended_features_bp.route('/ai/summarize', methods=['POST'])
def summarize_pdf():
    """Summarize PDF content using AI - returns job ID"""
    try:
        # Get text content from request
        data = request.get_json()
        if not data or 'text' not in data:
            return error_response("No text content provided", 400)
        
        text = data['text']
        options = data.get('options', {})
        
        # Validate text length
        if len(text) > 100000:  # 100KB limit
            return error_response("Text too long. Maximum length is 100KB.", 400)
        
        # Get client-provided tracking IDs
        client_job_id = data.get('client_job_id')
        client_session_id = data.get('client_session_id')
        
        # Create job and enqueue for processing
        job_id = str(uuid.uuid4())
        
        # Enqueue summarization task
        from src.queues.task_queue import task_queue, ai_summarize_task
        task_queue.enqueue(
            ai_summarize_task,
            job_id,
            text,
            options,
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        
        logger.info(f"AI summarization job {job_id} enqueued (client_job_id: {client_job_id})")
        
        return success_response("Summarization job queued successfully", {
            'job_id': job_id,
            'status': JobStatus.PENDING.value,
            'message': 'AI summarization job queued for processing'
        }), 202
        
    except Exception as e:
        logger.error(f"AI summarization job creation failed: {str(e)}")
        return error_response(f"Failed to create summarization job: {str(e)}", 500)

@extended_features_bp.route('/ai/translate', methods=['POST'])
def translate_text():
    """Translate text using AI - returns job ID"""
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return error_response("No text content provided", 400)
        
        text = data['text']
        target_language = data.get('target_language', 'en')
        options = data.get('options', {})
        
        # Validate text length
        if len(text) > 100000:  # 100KB limit
            return error_response("Text too long. Maximum length is 100KB.", 400)
        
        # Get client-provided tracking IDs
        client_job_id = data.get('client_job_id')
        client_session_id = data.get('client_session_id')
        
        # Create job and enqueue for processing
        job_id = str(uuid.uuid4())
        
        # Enqueue translation task
        from src.queues.task_queue import task_queue, ai_translate_task
        task_queue.enqueue(
            ai_translate_task,
            job_id,
            text,
            target_language,
            options,
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        
        logger.info(f"AI translation job {job_id} enqueued (client_job_id: {client_job_id})")
        
        return success_response("Translation job queued successfully", {
            'job_id': job_id,
            'status': JobStatus.PENDING.value,
            'message': 'AI translation job queued for processing'
        }), 202
        
    except Exception as e:
        logger.error(f"AI translation job creation failed: {str(e)}")
        return error_response(f"Failed to create translation job: {str(e)}", 500)

# ============================================================================
# TEXT EXTRACTION ROUTES (Job-Oriented)
# ============================================================================

@extended_features_bp.route('/extract/text', methods=['POST'])
def extract_text():
    """Extract text content from PDF - returns job ID"""
    try:
        if 'file' not in request.files:
            return error_response("No file provided", 400)
        
        file = request.files['file']
        if file.filename == '':
            return error_response("No file selected", 400)
        
        # Validate file
        if not allowed_file(file.filename, 'ai'):
            return error_response("Invalid file type. Only PDF files are supported.", 400)
        
        if file.content_length and file.content_length > MAX_FILE_SIZES['ai']:
            return error_response("File too large. Maximum size is 25MB.", 400)
        
        # Get client-provided tracking IDs
        client_job_id = request.form.get('client_job_id')
        client_session_id = request.form.get('client_session_id')
        
        # Read file data
        file_data = file.read()
        original_filename = file.filename
        
        # Create job and enqueue for processing
        job_id = str(uuid.uuid4())
        
        # Enqueue text extraction task
        from src.queues.task_queue import task_queue, extract_text_task
        task_queue.enqueue(
            extract_text_task,
            job_id,
            file_data,
            original_filename,
            client_job_id=client_job_id,
            client_session_id=client_session_id
        )
        
        logger.info(f"Text extraction job {job_id} enqueued (client_job_id: {client_job_id})")
        
        return success_response("Text extraction job queued successfully", {
            'job_id': job_id,
            'status': JobStatus.PENDING.value,
            'message': 'Text extraction job queued for processing'
        }), 202
        
    except Exception as e:
        logger.error(f"Text extraction job creation failed: {str(e)}")
        return error_response(f"Failed to create text extraction job: {str(e)}", 500)

# ============================================================================
# CLOUD INTEGRATION ROUTES (Synchronous - no job creation needed)
# ============================================================================

# Cloud routes remain synchronous since they're typically fast operations
# that don't require background processing

@extended_features_bp.route('/cloud/<provider>/token', methods=['POST'])
def exchange_cloud_token(provider):
    """Exchange authorization code for access token"""
    try:
        data = request.get_json()
        if not data or 'code' not in data:
            return error_response("No authorization code provided", 400)
        
        code = data['code']
        redirect_uri = data.get('redirect_uri')
        
        # Exchange code for token
        result = cloud_service.exchange_code_for_token(provider, code, redirect_uri)
        return success_response("Token exchange successful", result)
        
    except Exception as e:
        logger.error(f"Cloud token exchange failed: {str(e)}")
        return error_response(f"Token exchange failed: {str(e)}", 500)

@extended_features_bp.route('/cloud/<provider>/validate', methods=['GET'])
def validate_cloud_token(provider):
    """Validate cloud provider access token"""
    try:
        # Get token from authorization header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return error_response("No valid authorization header", 401)
        
        token = auth_header.split(' ')[1]
        
        # Validate token
        is_valid = cloud_service.validate_token(provider, token)
        
        if is_valid:
            return success_response("Token is valid", {'valid': True})
        else:
            return error_response("Token is invalid", 401)
            
    except Exception as e:
        logger.error(f"Cloud token validation failed: {str(e)}")
        return error_response(f"Token validation failed: {str(e)}", 500)

# ============================================================================
# HEALTH CHECK AND STATUS ROUTES
# ============================================================================

@extended_features_bp.route('/extended-features/status', methods=['GET'])
def get_extended_features_status():
    """Get status of all extended features"""
    try:
        # Check if required services are available
        redis_available = False
        try:
            from src.queues.task_queue import redis_conn
            redis_available = redis_conn.ping()
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
        
        return success_response("Extended features status retrieved successfully", status)
        
    except Exception as e:
        logger.error(f"Status retrieval failed: {str(e)}")
        return error_response(f"Status retrieval failed: {str(e)}", 500)

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
        
        return success_response("Extended features capabilities retrieved successfully", capabilities)
        
    except Exception as e:
        logger.error(f"Capabilities retrieval failed: {str(e)}")
        return error_response(f"Capabilities retrieval failed: {str(e)}", 500)