"""
PDF Suite Routes - Job-Oriented Architecture
Handles conversion, OCR, AI, and cloud integration endpoints
Returns job IDs for async processing
"""

import json
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from flask import Blueprint, request

from src.models import JobStatus, TaskType
from src.services.service_registry import ServiceRegistry
from src.utils.response_helpers import success_response, error_response
from src.utils.security_utils import get_file_and_validate
from src.tasks.tasks import (
    convert_pdf_task,
    conversion_preview_task,
    ocr_process_task,
    ocr_preview_task,
    ai_summarize_task,
    ai_translate_task,
    extract_text_task,
    extract_invoice_task,
    extract_bank_statement_task
)
from src.jobs import JobStatusManager

# Initialize blueprint
pdf_suite_bp = Blueprint('pdf_suite', __name__)
logger = logging.getLogger(__name__)

def create_job_id() -> str:
    """Generate a unique job ID."""
    return str(uuid.uuid4())

def _parse_options_from_request() -> Tuple[Dict[str, Any], Optional[str]]:
    """Parse options from request form data."""
    options = {}
    error = None
    
    if 'options' in request.form:
        try:
            options = json.loads(request.form['options'])
        except json.JSONDecodeError:
            error = "Invalid options format"
    
    return options, error

def _create_and_enqueue_job(
    job_id: str,
    task_type: TaskType,
    input_data: Dict[str, Any],
    task_function,
    task_args: tuple,
    task_kwargs: Dict[str, Any]
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Create job and enqueue task with proper error handling."""
    try:
        # Create job first
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type=task_type.value,
            input_data=input_data
        )
        
        if not job:
            return None, 'Failed to create job'

        # Enqueue task
        task = task_function.delay(*task_args, **task_kwargs)

        logger.info(f"{task_type.name} job {job_id} enqueued (task_id: {task.id})")

        return {
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value
        }, None

    except Exception as e:
        logger.error(f"Failed to enqueue {task_type.name} task {job_id}: {str(e)}")
        JobStatusManager.update_job_status(
            job_id=job_id,
            status=JobStatus.FAILED,
            error_message=f"Task enqueueing failed: {str(e)}"
        )
        return None, f'Failed to queue {task_type.name.lower()} job'

# ============================================================================
# CONVERSION ROUTES
# ============================================================================

@pdf_suite_bp.route('/convert', methods=['POST'])
def convert_pdf():
    """Convert PDF to specified format - returns job ID"""
    try:
        target_format = request.form.get('format', 'txt').lower()
        
        # Validate format
        conversion_service = ServiceRegistry.get_conversion_service()
        if target_format not in conversion_service.supported_formats:
            return error_response(message=f"Unsupported format: {target_format}", status_code=400)

        # Get and validate file
        file, error = get_file_and_validate('conversion')
        if error:
            return error

        # Get conversion options
        options, error = _parse_options_from_request()
        if error:
            return error_response(message=error, status_code=400)

        job_id = request.form.get('job_id', create_job_id())
        file_data = file.read()

        # Create and enqueue job
        result, error_msg = _create_and_enqueue_job(
            job_id=job_id,
            task_type=TaskType.CONVERT,
            input_data={
                'target_format': target_format,
                'options': options,
                'file_size': len(file_data),
                'original_filename': file.filename
            },
            task_function=convert_pdf_task,
            task_args=(job_id, file_data, target_format, options, file.filename),
            task_kwargs={}
        )

        if error_msg:
            return error_response(message=error_msg, status_code=500)

        return success_response(
            message="Conversion job queued successfully",
            data={**result, 'format': target_format},
            status_code=202
        )

    except Exception as e:
        logger.error(f"PDF conversion job creation failed: {str(e)}")
        return error_response(message=f"Failed to create conversion job: {str(e)}", status_code=500)

@pdf_suite_bp.route('/convert/preview', methods=['POST'])
def get_conversion_preview():
    """Get conversion preview and estimates - returns job ID"""
    try:
        file, error = get_file_and_validate('conversion')
        if error:
            return error

        target_format = request.form.get('format', 'docx')
        options, error = _parse_options_from_request()
        if error:
            return error_response(message=error, status_code=400)

        job_id = request.form.get('job_id', create_job_id())
        file_data = file.read()

        # Create and enqueue job
        result, error_msg = _create_and_enqueue_job(
            job_id=job_id,
            task_type=TaskType.CONVERSION_PREVIEW,
            input_data={
                'target_format': target_format,
                'options': options,
                'file_size': len(file_data),
                'original_filename': file.filename
            },
            task_function=conversion_preview_task,
            task_args=(job_id, file_data, target_format, options),
            task_kwargs={}
        )

        if error_msg:
            return error_response(message=error_msg, status_code=500)

        return success_response(
            message="Conversion preview job queued successfully",
            data=result,
            status_code=202
        )

    except Exception as e:
        logger.error(f"Conversion preview job creation failed: {str(e)}")
        return error_response(message=f"Failed to create preview job: {str(e)}", status_code=500)

# ============================================================================
# OCR ROUTES
# ============================================================================

@pdf_suite_bp.route('/ocr', methods=['POST'])
def process_ocr():
    """Process OCR on uploaded file - returns job ID"""
    try:
        file, error = get_file_and_validate('ocr')
        if error:
            return error

        options, error = _parse_options_from_request()
        if error:
            return error_response(message=error, status_code=400)

        job_id = request.form.get('job_id', create_job_id())
        file_data = file.read()

        # Create and enqueue job
        result, error_msg = _create_and_enqueue_job(
            job_id=job_id,
            task_type=TaskType.OCR,
            input_data={
                'options': options,
                'file_size': len(file_data),
                'original_filename': file.filename
            },
            task_function=ocr_process_task,
            task_args=(job_id, file_data, options, file.filename),
            task_kwargs={}
        )

        if error_msg:
            return error_response(message=error_msg, status_code=500)

        return success_response(
            message="OCR job queued successfully",
            data=result,
            status_code=202
        )

    except Exception as e:
        logger.error(f"OCR job creation failed: {str(e)}")
        return error_response(message=f"Failed to create OCR job: {str(e)}", status_code=500)

@pdf_suite_bp.route('/ocr/preview', methods=['POST'])
def get_ocr_preview():
    """Get OCR preview and estimates - returns job ID"""
    try:
        file, error = get_file_and_validate('ocr')
        if error:
            return error

        options, error = _parse_options_from_request()
        if error:
            return error_response(message=error, status_code=400)

        job_id = request.form.get('job_id', create_job_id())
        file_data = file.read()

        # Create and enqueue job
        result, error_msg = _create_and_enqueue_job(
            job_id=job_id,
            task_type=TaskType.OCR_PREVIEW,
            input_data={
                'options': options,
                'file_size': len(file_data),
                'original_filename': file.filename
            },
            task_function=ocr_preview_task,
            task_args=(job_id, file_data, options),
            task_kwargs={}
        )

        if error_msg:
            return error_response(message=error_msg, status_code=500)

        return success_response(
            message="OCR preview job queued successfully",
            data=result,
            status_code=202
        )

    except Exception as e:
        logger.error(f"OCR preview job creation failed: {str(e)}")
        return error_response(message=f"Failed to create OCR preview job: {str(e)}", status_code=500)

# ============================================================================
# AI ROUTES
# ============================================================================

@pdf_suite_bp.route('/ai/summarize', methods=['POST'])
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
        job_id = data.get('job_id', create_job_id())

        # Create and enqueue job
        result, error_msg = _create_and_enqueue_job(
            job_id=job_id,
            task_type=TaskType.AI_SUMMARIZE,
            input_data={
                'text_length': len(text),
                'options': options
            },
            task_function=ai_summarize_task,
            task_args=(job_id, text, options),
            task_kwargs={}
        )

        if error_msg:
            return error_response(message=error_msg, status_code=500)

        return success_response(
            message="Summarization job queued successfully",
            data=result,
            status_code=202
        )

    except Exception as e:
        logger.error(f"AI summarization job creation failed: {str(e)}")
        return error_response(message=f"Failed to create summarization job: {str(e)}", status_code=500)

@pdf_suite_bp.route('/ai/translate', methods=['POST'])
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
        job_id = data.get('job_id', create_job_id())

        # Create and enqueue job
        result, error_msg = _create_and_enqueue_job(
            job_id=job_id,
            task_type=TaskType.AI_TRANSLATE,
            input_data={
                'target_language': target_language,
                'text_length': len(text),
                'options': options
            },
            task_function=ai_translate_task,
            task_args=(job_id, text, target_language, options),
            task_kwargs={}
        )

        if error_msg:
            return error_response(message=error_msg, status_code=500)

        return success_response(
            message="Translation job queued successfully",
            data=result,
            status_code=202
        )

    except Exception as e:
        logger.error(f"AI translation job creation failed: {str(e)}")
        return error_response(message=f"Failed to create translation job: {str(e)}", status_code=500)

# ============================================================================
# TEXT EXTRACTION ROUTES
# ============================================================================

@pdf_suite_bp.route('/ai/extract-text', methods=['POST'])
def extract_text():
    """Extract text content from PDF - returns job ID"""
    try:
        file, error = get_file_and_validate('ai')
        if error:
            return error

        job_id = request.form.get('job_id', create_job_id())
        file_data = file.read()

        # Create and enqueue job
        result, error_msg = _create_and_enqueue_job(
            job_id=job_id,
            task_type=TaskType.AI_EXTRACT_TEXT,
            input_data={
                'file_size': len(file_data),
                'original_filename': file.filename
            },
            task_function=extract_text_task,
            task_args=(job_id, file_data, file.filename),
            task_kwargs={}
        )

        if error_msg:
            return error_response(message=error_msg, status_code=500)

        return success_response(
            message="Text extraction job queued successfully",
            data=result,
            status_code=202
        )

    except Exception as e:
        logger.error(f"Text extraction job creation failed: {str(e)}")
        return error_response(message=f"Failed to create text extraction job: {str(e)}", status_code=500)

# ============================================================================
# INVOICE EXTRACTION ROUTES
# ============================================================================

@pdf_suite_bp.route('/ai/extract-invoice', methods=['POST'])
def extract_invoice():
    """Extract invoice data from PDF - returns job ID"""
    try:
        file, error = get_file_and_validate('extraction')
        if error:
            return error

        options, error = _parse_options_from_request()
        if error:
            return error_response(message=error, status_code=400)

        job_id = request.form.get('job_id', create_job_id())
        file_data = file.read()

        # Create job first
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type=TaskType.AI_INVOICE_EXTRACTION.value,
            input_data={
                'file_size': len(file_data),
                'original_filename': file.filename,
                'options': options
            }
        )
        
        if not job:
            return error_response(message='Failed to create invoice extraction job', status_code=500)

        # Save file temporarily
        file_service = ServiceRegistry.get_file_management_service()
        file_path = file_service.save_file(file, job_id)

        # Enqueue invoice extraction task
        task = extract_invoice_task.delay(job_id, file_path, options)

        logger.info(f"Invoice extraction job {job_id} enqueued (task_id: {task.id})")

        return success_response(
            message="Invoice extraction job queued successfully",
            data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value
            },
            status_code=202
        )

    except Exception as e:
        logger.error(f"Invoice extraction job creation failed: {str(e)}")
        return error_response(message=f"Failed to create invoice extraction job: {str(e)}", status_code=500)

@pdf_suite_bp.route('/ai/invoice-capabilities', methods=['GET'])
def get_invoice_capabilities():
    """Get invoice extraction capabilities"""
    try:
        capabilities = ServiceRegistry.get_invoice_extraction_service().get_extraction_capabilities()
        return success_response(
            message="Invoice extraction capabilities retrieved successfully",
            data=capabilities
        )
    except Exception as e:
        logger.error(f"Invoice capabilities retrieval failed: {str(e)}")
        return error_response(message=f"Invoice capabilities retrieval failed: {str(e)}", status_code=500)

# ============================================================================
# BANK STATEMENT EXTRACTION ROUTES
# ============================================================================

@pdf_suite_bp.route('/ai/extract-bank-statement', methods=['POST'])
def extract_bank_statement():
    """Extract bank statement data from PDF - returns job ID"""
    try:
        file, error = get_file_and_validate('extraction')
        if error:
            return error

        options, error = _parse_options_from_request()
        if error:
            return error_response(message=error, status_code=400)

        job_id = request.form.get('job_id', create_job_id())
        file_data = file.read()

        # Create job first
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type=TaskType.AI_BANK_STATEMENT_EXTRACTION.value,
            input_data={
                'file_size': len(file_data),
                'original_filename': file.filename,
                'options': options
            }
        )
        
        if not job:
            return error_response(message='Failed to create bank statement extraction job', status_code=500)

        # Save file temporarily
        file_service = ServiceRegistry.get_file_management_service()
        file_path = file_service.save_file(file, job_id)

        # Enqueue bank statement extraction task
        task = extract_bank_statement_task.delay(job_id, file_path, options)

        logger.info(f"Bank statement extraction job {job_id} enqueued (task_id: {task.id})")

        return success_response(
            message="Bank statement extraction job queued successfully",
            data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value
            },
            status_code=202
        )

    except Exception as e:
        logger.error(f"Bank statement extraction job creation failed: {str(e)}")
        return error_response(message=f"Failed to create bank statement extraction job: {str(e)}", status_code=500)

@pdf_suite_bp.route('/ai/bank-statement-capabilities', methods=['GET'])
def get_bank_statement_capabilities():
    """Get bank statement extraction capabilities"""
    try:
        capabilities = ServiceRegistry.get_bank_statement_extraction_service().get_extraction_capabilities()
        return success_response(
            message="Bank statement extraction capabilities retrieved successfully",
            data=capabilities
        )
    except Exception as e:
        logger.error(f"Bank statement capabilities retrieval failed: {str(e)}")
        return error_response(message=f"Bank statement capabilities retrieval failed: {str(e)}", status_code=500)

# ============================================================================
# HEALTH CHECK AND STATUS ROUTES
# ============================================================================

@pdf_suite_bp.route('/extended-features/status', methods=['GET'])
def get_extended_features_status():
    """Get status of all extended features"""
    try:
        # Check Redis availability
        redis_available = False
        try:
            from src.celery_app import get_celery_app
            celery_app = get_celery_app()
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
            'extraction': {
                'available': True,
                'supported_formats': ['pdf'],
                'max_file_size': '25MB',
                'async_processing': True,
                'features': ['invoice_extraction', 'bank_statement_extraction']
            },
            'queue': {
                'redis_available': redis_available,
                'job_processing': True
            },
            'timestamp': datetime.utcnow().isoformat()
        }

        return success_response(
            message="Extended features status retrieved successfully",
            data=status
        )

    except Exception as e:
        logger.error(f"Status retrieval failed: {str(e)}")
        return error_response(message=f"Status retrieval failed: {str(e)}", status_code=500)

@pdf_suite_bp.route('/extended-features/capabilities', methods=['GET'])
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
            'extraction': {
                'name': 'Document Data Extraction',
                'description': 'Extract structured data from invoices and bank statements using AI',
                'features': ['invoice_data_extraction', 'bank_statement_extraction', 'structured_output', 'export_formats'],
                'options': {
                    'export_format': 'string (json|csv|excel|none)',
                    'export_filename': 'string (optional custom filename)',
                    'include_confidence': 'boolean (include AI confidence scores)',
                    'validate_data': 'boolean (perform data validation)'
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

        return success_response(
            message="Extended features capabilities retrieved successfully",
            data=capabilities
        )

    except Exception as e:
        logger.error(f"Capabilities retrieval failed: {str(e)}")
        return error_response(message=f"Capabilities retrieval failed: {str(e)}", status_code=500)