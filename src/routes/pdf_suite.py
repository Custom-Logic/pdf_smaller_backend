"""
PDF Suite Routes - Job-Oriented Architecture
Handles conversion, OCR, AI, and cloud integration endpoints
Returns job IDs for async processing
"""

import json
import logging
import uuid
from datetime import datetime

from celery import Task
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
# CORS(pdf_suite_bp, resources={r"/api": {"origins": ["https://www.pdfsmaller.site"]}})

# Services are now managed through ServiceRegistry
# No need for global service instances


# Configure logging
logger = logging.getLogger(__name__)

# Note: File validation logic moved to src.utils.security_utils for centralization
def create_job_id() -> str:
    return str(uuid.uuid4())
# ============================================================================
# CONVERSION ROUTES (Job-Oriented)
# ============================================================================

@pdf_suite_bp.route('/convert', methods=['POST'])
def convert_pdf():
    """Convert PDF to specified format - returns job ID"""
    try:
        target_format = request.form.get('format', 'txt').lower()
        # Validate format
        if target_format not in ServiceRegistry.get_conversion_service().supported_formats:
            return error_response(message=f"Unsupported format: {target_format}", status_code=400)

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

        job_id = request.form.get('job_id', create_job_id())

        # Read file data
        file_data = file.read()

        # CREATE JOB FIRST - this is the fix!        
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type=TaskType.CONVERT.value,
            input_data={
                'target_format': target_format,
                'options': options,
                'file_size': len(file_data),
                'original_filename': file.filename
            }
        )
        
        if not job:
            return error_response(message='Failed to create conversion job', status_code=500)

        # Enqueue conversion task using .delay() pattern
        try:
            task = convert_pdf_task.delay(
                job_id,
                file_data,
                target_format,
                options,
                file.filename,
            )

            logger.info(f"Conversion job {job_id} enqueued (format: {target_format}, task_id: {task.id})")

            return success_response(message="Conversion job queued successfully", data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value,
                'format': target_format
            }, status_code=202)
        except Exception as task_error:
             logger.error(f"Failed to enqueue conversion task {job_id}: {str(task_error)}")
             JobStatusManager.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=f"Task enqueueing failed: {str(task_error)}"
             )
             return error_response(message='Failed to queue conversion job', status_code=500)

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

        format = request.form.get('format', 'docx')
        options = {}

        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response(message="Invalid options format", status_code=400)

        job_id = request.form.get('job_id', create_job_id())

        file_data = file.read()

        # CREATE JOB FIRST - this is the fix!
        
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type=TaskType.CONVERSION_PREVIEW.value,
            input_data={
                'target_format': format,
                'options': options,
                'file_size': len(file_data),
                'original_filename': file.filename
            }
        )
        
        if not job:
            return error_response(message='Failed to create conversion preview job', status_code=500)

        # Enqueue conversion preview task using .delay() pattern
        try:
            task = conversion_preview_task.delay(
                job_id,
                file_data,
                format,
                options,
            )

            logger.info(f"Conversion preview job {job_id} enqueued (task_id: {task.id})")

            return success_response(message="Conversion preview job queued successfully", data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value
            }, status_code=202)
        except Exception as task_error:
            logger.error(f"Failed to enqueue conversion preview task {job_id}: {str(task_error)}")
            JobStatusManager.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=f"Task enqueueing failed: {str(task_error)}"
            )
            return error_response(message='Failed to queue conversion preview job', status_code=500)

    except Exception as e:
        logger.error(f"Conversion preview job creation failed: {str(e)}")
        return error_response(message=f"Failed to create preview job: {str(e)}", status_code=500)

# ============================================================================
# OCR ROUTES (Job-Oriented)
# ============================================================================

@pdf_suite_bp.route('/ocr', methods=['POST'])
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

        job_id = request.form.get('job_id', create_job_id())

        file_data = file.read()

        # CREATE JOB FIRST - this is the fix!

        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type=TaskType.OCR.value,
            input_data={
                'options': options,
                'file_size': len(file_data),
                'original_filename': file.filename
            }
        )
        
        if not job:
            return error_response(message='Failed to create OCR job', status_code=500)

        # Enqueue OCR task using .delay() pattern
        try:
            task = ocr_process_task.delay(
                job_id=job_id,
                file_data=file_data,
                options=options,
                original_filename=file.filename)

            logger.info(f"OCR job {job_id} enqueued (task_id: {task.id})")

            return success_response(message="OCR job queued successfully", data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value
            }, status_code=202)
        except Exception as task_error:
            logger.error(f"Failed to enqueue OCR task {job_id}: {str(task_error)}")
            JobStatusManager.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=f"Task enqueueing failed: {str(task_error)}"
            )
            return error_response(message='Failed to queue OCR job', status_code=500)

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

        options = {}
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response(message="Invalid options format", status_code=400)

        job_id = request.form.get('job_id', create_job_id())

        file_data = file.read()

        # CREATE JOB FIRST - this is the fix!
        
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type=TaskType.OCV_PREVIEW.value,
            input_data={
                'options': options,
                'file_size': len(file_data),
                'original_filename': file.filename
            }
        )
        
        if not job:
            return error_response(message='Failed to create OCR preview job', status_code=500)

        # Enqueue OCR preview task using .delay() pattern
        try:
            task = ocr_preview_task.delay(
                job_id,
                file_data,
                options,
            )

            logger.info(f"OCR preview job {job_id} enqueued (task_id: {task.id})")

            return success_response(message="OCR preview job queued successfully", data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value
            }, status_code=202)
        except Exception as task_error:
            logger.error(f"Failed to enqueue OCR preview task {job_id}: {str(task_error)}")
            JobStatusManager.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=f"Task enqueueing failed: {str(task_error)}"
            )
            return error_response(message='Failed to queue OCR preview job', status_code=500)

    except Exception as e:
        logger.error(f"OCR preview job creation failed: {str(e)}")
        return error_response(message=f"Failed to create OCR preview job: {str(e)}", status_code=500)

# ============================================================================
# AI ROUTES (Job-Oriented)
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

        # CREATE JOB FIRST - this is the fix!
        
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type=TaskType.AI_SUMMARIZE.value,
            input_data={
                'text_length': len(text),
                'options': options
            }
        )
        
        if not job:
            return error_response(message='Failed to create summarization job', status_code=500)

        # Enqueue AI summarization task using .delay() pattern
        try:
            task = ai_summarize_task.delay(
                job_id,
                text,
                options,
            )

            logger.info(f"AI summarization job {job_id} enqueued (task_id: {task.id})")

            return success_response(message="Summarization job queued successfully", data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value
            }, status_code=202)
        except Exception as task_error:
            logger.error(f"Failed to enqueue AI summarization task {job_id}: {str(task_error)}")
            JobStatusManager.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=f"Task enqueueing failed: {str(task_error)}"
            )
            return error_response(message='Failed to queue summarization job', status_code=500)

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
        job_id = request.form.get('job_id', create_job_id())

        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type=TaskType.AI_TRANSLATE.value,
            input_data={
                'text_length': len(text),
                'options': options
            }
        )


        # Enqueue AI translation task using .delay() pattern
        task = ai_translate_task.delay(
            job_id,
            text,
            target_language,
            options
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

@pdf_suite_bp.route('/ai/extract-text', methods=['POST'])
def extract_text():
    """Extract text content from PDF - returns job ID"""
    try:
        file, error = get_file_and_validate('ai')
        if error:
            return error

        job_id = request.form.get('job_id', create_job_id())

        file_data = file.read()

        # CREATE JOB FIRST - this is the fix!

        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type=TaskType.AI_EXTRACT_TEXT.value,
            input_data={
                'file_size': len(file_data),
                'original_filename': file.filename
            }
        )
        
        if not job:
            return error_response(message='Failed to create text extraction job', status_code=500)

        # Enqueue text extraction task using .delay() pattern
        try:
            task = extract_text_task.delay(
                job_id,
                file_data,
                file.filename,
            )

            logger.info(f"Text extraction job {job_id} enqueued (task_id: {task.id})")

            return success_response(message="Text extraction job queued successfully", data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value
            }, status_code=202)
        except Exception as task_error:
            logger.error(f"Failed to enqueue text extraction task {job_id}: {str(task_error)}")
            JobStatusManager.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=f"Task enqueueing failed: {str(task_error)}"
            )
            return error_response(message='Failed to queue text extraction job', status_code=500)

    except Exception as e:
        logger.error(f"Text extraction job creation failed: {str(e)}")
        return error_response(message=f"Failed to create text extraction job: {str(e)}", status_code=500)

# ============================================================================
# INVOICE EXTRACTION ROUTES (Job-Oriented)
# ============================================================================

@pdf_suite_bp.route('/ai/extract-invoice', methods=['POST'])
def extract_invoice():
    """Extract invoice data from PDF - returns job ID"""
    try:
        file, error = get_file_and_validate('extraction')
        if error:
            return error

        # Get extraction options
        options = {}
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response(message="Invalid options format", status_code=400)

        job_id = request.form.get('job_id', create_job_id())
        

        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type=TaskType.AI_INVOICE_EXTRACTION.value,
            input_data={
                'file_size': len(file_data),
                'original_filename': file.filename,
                'options': options
            }
        )

        # Save file temporarily
        file_service = ServiceRegistry.get_file_management_service()
        file_path = file_service.save_file(file, job_id)

        # Enqueue invoice extraction task using .delay() pattern
        task = extract_invoice_task.delay(
            job_id,
            file_path,
            options
        )

        logger.info(f"Invoice extraction job {job_id} enqueued (task_id: {task.id})")

        return success_response(message="Invoice extraction job queued successfully", data={
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value
        }, status_code=202)

    except Exception as e:
        logger.error(f"Invoice extraction job creation failed: {str(e)}")
        return error_response(message=f"Failed to create invoice extraction job: {str(e)}", status_code=500)


@pdf_suite_bp.route('/ai/invoice-capabilities', methods=['GET'])
def get_invoice_capabilities():
    """Get invoice extraction capabilities"""
    try:
        capabilities = ServiceRegistry.get_invoice_extraction_service().get_extraction_capabilities()
        return success_response(message="Invoice extraction capabilities retrieved successfully", data=capabilities)
    except Exception as e:
        logger.error(f"Invoice capabilities retrieval failed: {str(e)}")
        return error_response(message=f"Invoice capabilities retrieval failed: {str(e)}", status_code=500)


# ============================================================================
# BANK STATEMENT EXTRACTION ROUTES (Job-Oriented)
# ============================================================================

@pdf_suite_bp.route('/ai/extract-bank-statement', methods=['POST'])
def extract_bank_statement():
    """Extract bank statement data from PDF - returns job ID"""
    try:
        file, error = get_file_and_validate('extraction')
        if error:
            return error

        # Get extraction options
        options = {}
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response(message="Invalid options format", status_code=400)

        job_id = request.form.get('job_id', create_job_id())

        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type=TaskType.AI_BANK_STATEMENT_EXTRACTION.value,
            input_data={
                'file_size': len(file_data),
                'original_filename': file.filename,
                'options': options
            }
        )
        
        # Save file temporarily
        file_service = ServiceRegistry.get_file_management_service()
        file_path = file_service.save_file(file, job_id)

        # Enqueue bank statement extraction task using .delay() pattern
        task = extract_bank_statement_task.delay(
            job_id,
            file_path,
            options
        )

        logger.info(f"Bank statement extraction job {job_id} enqueued (task_id: {task.id})")

        return success_response(message="Bank statement extraction job queued successfully", data={
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value
        }, status_code=202)

    except Exception as e:
        logger.error(f"Bank statement extraction job creation failed: {str(e)}")
        return error_response(message=f"Failed to create bank statement extraction job: {str(e)}", status_code=500)


@pdf_suite_bp.route('/ai/bank-statement-capabilities', methods=['GET'])
def get_bank_statement_capabilities():
    """Get bank statement extraction capabilities"""
    try:
        capabilities = ServiceRegistry.get_bank_statement_extraction_service().get_extraction_capabilities()
        return success_response(message="Bank statement extraction capabilities retrieved successfully", data=capabilities)
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

        return success_response(message="Extended features status retrieved successfully", data=status)

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

        return success_response(message="Extended features capabilities retrieved successfully", data=capabilities)

    except Exception as e:
        logger.error(f"Capabilities retrieval failed: {str(e)}")
        return error_response(message=f"Capabilities retrieval failed: {str(e)}", status_code=500)