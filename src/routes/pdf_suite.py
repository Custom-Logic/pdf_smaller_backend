"""
PDF Suite Routes – Job-oriented architecture
Handles conversion, OCR, AI, and cloud integration endpoints.
Returns job IDs for async processing.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from flask import Blueprint, request, current_app
from werkzeug.exceptions import UnsupportedMediaType, RequestEntityTooLarge

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
    extract_bank_statement_task,
)
from src.jobs import JobStatusManager

pdf_suite_bp = Blueprint("pdf_suite", __name__)
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #
MAX_JSON_OPTIONS_SIZE = 64 * 1024          # 64 kB
MAX_TEXT_PAYLOAD      = 100 * 1024         # 100 kB
MAX_FILE_SIZE         = 100 * 1024 * 1024  # 100 MB

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _validate_job_id(jid: Optional[str]) -> str:
    """Return a safe job-id (uuid4 if none or invalid)."""
    if not jid:
        return str(uuid.uuid4())
    try:
        uuid.UUID(jid)
        return jid
    except ValueError:
        return str(uuid.uuid4())

def _load_json_options() -> Tuple[Dict[str, Any], Optional[str]]:
    """Load options from form field with size guard."""
    options: Dict[str, Any] = {}
    error: Optional[str] = None
    raw = request.form.get("options")
    if raw:
        if len(raw.encode("utf-8")) > MAX_JSON_OPTIONS_SIZE:
            return {}, "Options payload too large"
        try:
            options = json.loads(raw)
            if not isinstance(options, dict):
                return {}, "Options must be a JSON object"
        except json.JSONDecodeError:
            error = "Invalid JSON in options"
    return options, error

def _get_safe_service(getter_name: str):
    """Return a service or raise a RuntimeError if missing."""
    try:
        svc = getattr(ServiceRegistry, getter_name)()
        if svc is None:
            raise RuntimeError(f"Service {getter_name} not registered")
        return svc
    except Exception as exc:
        logger.exception("Service lookup failed")
        raise RuntimeError(f"Service unavailable: {exc}") from exc

def _enqueue_job(
    *,
    job_id: str,
    task_type: TaskType,
    input_data: Dict[str, Any],
    task_func,
    task_args: Tuple[Any, ...],
    task_kwargs: Dict[str, Any],
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Create job record and enqueue Celery task with unified error handling."""
    try:
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type=task_type.value,
            input_data=input_data,
        )
        if not job:
            return {}, "Failed to create job record"

        task = task_func.delay(*task_args, **task_kwargs)
        logger.info("%s job %s enqueued (task_id: %s)", task_type.name, job_id, task.id)
        return {"job_id": job_id, "task_id": task.id, "status": JobStatus.PENDING.value}, None

    except Exception as exc:
        logger.error("Enqueue %s job %s failed: %s", task_type.name, job_id, exc)
        JobStatusManager.update_job_status(
            job_id=job_id,
            status=JobStatus.FAILED,
            error_message=f"Enqueue failed: {exc}",
        )
        return {}, f"Failed to queue {task_type.name.lower()} job"

# --------------------------------------------------------------------------- #
# Generic request guards
# --------------------------------------------------------------------------- #
@pdf_suite_bp.before_request
def _content_length_guard():
    """Reject oversized requests before they hit handlers."""
    cl = request.content_length or 0
    if cl > MAX_FILE_SIZE:
        raise RequestEntityTooLarge()

# --------------------------------------------------------------------------- #
# CONVERSION
# --------------------------------------------------------------------------- #
@pdf_suite_bp.route("/convert", methods=["POST", "GET"])
def convert_pdf():
    """Convert PDF to target format (txt/docx/xlsx/html)."""
    try:
        target = request.form.get("format", "txt").lower()
        conv_svc = _get_safe_service("get_conversion_service")
        if target not in conv_svc.supported_formats:
            return error_response(f"Unsupported format: {target}", 400)

        file, err = get_file_and_validate("conversion")
        if err:
            return err

        options, err = _load_json_options()
        if err:
            return error_response(err, 400)

        job_id = _validate_job_id(request.form.get("job_id"))
        file_bytes = file.read()  # single read
        if len(file_bytes) > MAX_FILE_SIZE:
            return error_response(message="File too large", status_code413)

        data, err = _enqueue_job(
            job_id=job_id,
            task_type=TaskType.CONVERT,
            input_data={
                "target_format": target,
                "options": options,
                "file_size": len(file_bytes),
                "original_filename": file.filename,
            },
            task_func=convert_pdf_task,
            task_args=(job_id, file_bytes, target, options, file.filename),
            task_kwargs={},
        )
        if err:
            return error_response(err, 500)

        return success_response(message="Conversion job queued", data={**data, "format": target}, status_code=202)
    except Exception as exc:
        logger.exception("convert_pdf failed")
        return error_response(message=f"Job creation failed: {exc}", status_code=500)

@pdf_suite_bp.route("/convert/preview", methods=["POST", "GET"])
def get_conversion_preview():
    """Return conversion estimates."""
    try:
        file, err = get_file_and_validate("conversion")
        if err:
            return err
        target = request.form.get("format", "docx")
        options, err = _load_json_options()
        if err:
            return error_response(err, 400)

        job_id = _validate_job_id(request.form.get("job_id"))
        file_bytes = file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            return error_response("File too large", 413)

        data, err = _enqueue_job(
            job_id=job_id,
            task_type=TaskType.CONVERSION_PREVIEW,
            input_data={
                "target_format": target,
                "options": options,
                "file_size": len(file_bytes),
                "original_filename": file.filename,
            },
            task_func=conversion_preview_task,
            task_args=(job_id, file_bytes, target, options),
            task_kwargs={},
        )
        if err:
            return error_response(err, 500)
        return success_response(message="Preview job queued", data=data, status_code=202)
    except Exception as exc:
        logger.exception("conversion preview failed")
        return error_response(f"Preview job failed: {exc}", 500)

# --------------------------------------------------------------------------- #
# OCR
# --------------------------------------------------------------------------- #
@pdf_suite_bp.route("/ocr", methods=["POST", "GET"])
def process_ocr():
    """Run OCR on scanned file."""
    try:
        file, err = get_file_and_validate("ocr")
        if err:
            return err
        options, err = _load_json_options()
        if err:
            return error_response(err, 400)

        job_id = _validate_job_id(request.form.get("job_id"))
        file_bytes = file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            return error_response("File too large", 413)

        data, err = _enqueue_job(
            job_id=job_id,
            task_type=TaskType.OCR,
            input_data={
                "options": options,
                "file_size": len(file_bytes),
                "original_filename": file.filename,
            },
            task_func=ocr_process_task,
            task_args=(job_id, file_bytes, options, file.filename),
            task_kwargs={},
        )
        if err:
            return error_response(err, 500)
        return success_response(message="OCR job queued", data=data, status_code=202)
    except Exception as exc:
        logger.exception("OCR job failed")
        return error_response(f"OCR job failed: {exc}", 500)

@pdf_suite_bp.route("/ocr/preview", methods=["POST", "GET"])
def get_ocr_preview():
    """OCR preview/estimate."""
    try:
        file, err = get_file_and_validate("ocr")
        if err:
            return err
        options, err = _load_json_options()
        if err:
            return error_response(err, 400)

        job_id = _validate_job_id(request.form.get("job_id"))
        file_bytes = file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            return error_response("File too large", 413)

        data, err = _enqueue_job(
            job_id=job_id,
            task_type=TaskType.OCR_PREVIEW,
            input_data={
                "options": options,
                "file_size": len(file_bytes),
                "original_filename": file.filename,
            },
            task_func=ocr_preview_task,
            task_args=(job_id, file_bytes, options),
            task_kwargs={},
        )
        if err:
            return error_response(err, 500)
        return success_response(message="OCR preview queued", data=data, status_code=202)
    except Exception as exc:
        logger.exception("OCR preview failed")
        return error_response(f"OCR preview failed: {exc}", 500)

# --------------------------------------------------------------------------- #
# AI – SUMMARIZE / TRANSLATE
# --------------------------------------------------------------------------- #
def _get_json_from_request() -> Dict[str, Any]:
    """Return parsed JSON or raise UnsupportedMediaType/400."""
    if not request.is_json:
        raise UnsupportedMediaType("Content-Type must be application/json")
    data = request.get_json(silent=True)
    if not data or not isinstance(data, dict):
        raise ValueError("Invalid JSON payload")
    return data

@pdf_suite_bp.route("/ai/summarize", methods=["POST", "GET"])
def summarize_pdf():
    """Summarize text via AI."""
    try:
        data = _get_json_from_request()
        text = data.get("text", "")
        if not text:
            return error_response("No text provided", 400)
        if len(text.encode("utf-8")) > MAX_TEXT_PAYLOAD:
            return error_response("Text too large (limit 100 kB)", 400)

        options = data.get("options", {})
        job_id = _validate_job_id(data.get("job_id"))

        payload, err = _enqueue_job(
            job_id=job_id,
            task_type=TaskType.AI_SUMMARIZE,
            input_data={"text_length": len(text), "options": options},
            task_func=ai_summarize_task,
            task_args=(job_id, text, options),
            task_kwargs={},
        )
        if err:
            return error_response(err, 500)
        return success_response(message="Summarization queued", data=payload, status_code=202)
    except (UnsupportedMediaType, ValueError) as exc:
        return error_response(str(exc), 400)
    except Exception as exc:
        logger.exception("summarize failed")
        return error_response(f"Summarization failed: {exc}", 500)

@pdf_suite_bp.route("/ai/translate", methods=["POST", "GET"])
def translate_text():
    """Translate text via AI."""
    try:
        data = _get_json_from_request()
        text = data.get("text", "")
        if not text:
            return error_response("No text provided", 400)
        if len(text.encode("utf-8")) > MAX_TEXT_PAYLOAD:
            return error_response("Text too large (limit 100 kB)", 400)

        target = data.get("target_language", "en")
        options = data.get("options", {})
        job_id = _validate_job_id(data.get("job_id"))

        payload, err = _enqueue_job(
            job_id=job_id,
            task_type=TaskType.AI_TRANSLATE,
            input_data={
                "target_language": target,
                "text_length": len(text),
                "options": options,
            },
            task_func=ai_translate_task,
            task_args=(job_id, text, target, options),
            task_kwargs={},
        )
        if err:
            return error_response(err, 500)
        return success_response(message="Translation queued", data=payload, status_code=202)
    except (UnsupportedMediaType, ValueError) as exc:
        return error_response(str(exc), 400)
    except Exception as exc:
        logger.exception("translation failed")
        return error_response(f"Translation failed: {exc}", 500)

# --------------------------------------------------------------------------- #
# TEXT / INVOICE / BANK-STATEMENT EXTRACTION
# --------------------------------------------------------------------------- #
@pdf_suite_bp.route("/ai/extract-text", methods=["POST", "GET"])
def extract_text():
    """Extract plain text from PDF."""
    try:
        file, err = get_file_and_validate("ai")
        if err:
            return err
        job_id = _validate_job_id(request.form.get("job_id"))
        file_bytes = file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            return error_response("File too large", 413)

        payload, err = _enqueue_job(
            job_id=job_id,
            task_type=TaskType.AI_EXTRACT_TEXT,
            input_data={
                "file_size": len(file_bytes),
                "original_filename": file.filename,
            },
            task_func=extract_text_task,
            task_args=(job_id, file_bytes, file.filename),
            task_kwargs={},
        )
        if err:
            return error_response(err, 500)
        return success_response(message="Text extraction queued", data=payload, status_code=202)
    except Exception as exc:
        logger.exception("text extraction failed")
        return error_response(f"Text extraction failed: {exc}", 500)

# --------------- invoice --------------- #
@pdf_suite_bp.route("/ai/extract-invoice", methods=["POST", "GET"])
def extract_invoice():
    """Extract structured invoice data."""
    try:
        file, err = get_file_and_validate("extraction")
        if err:
            return err
        options, err = _load_json_options()
        if err:
            return error_response(err, 400)

        job_id = _validate_job_id(request.form.get("job_id"))
        file_bytes = file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            return error_response("File too large", 413)

        # persist file
        file_svc = _get_safe_service("get_file_management_service")
        file_path = file_svc.save_file(file, job_id)

        payload, err = _enqueue_job(
            job_id=job_id,
            task_type=TaskType.AI_INVOICE_EXTRACTION,
            input_data={
                "file_size": len(file_bytes),
                "original_filename": file.filename,
                "options": options,
            },
            task_func=extract_invoice_task,
            task_args=(job_id, file_path, options),
            task_kwargs={},
        )
        if err:
            return error_response(err, 500)
        return success_response(message="Invoice extraction queued", data=payload, status_code=202)
    except Exception as exc:
        logger.exception("invoice extraction failed")
        return error_response(f"Invoice extraction failed: {exc}", 500)

@pdf_suite_bp.route("/ai/invoice-capabilities", methods=["POST", "GET"])
def get_invoice_capabilities():
    """Return invoice extractor capabilities."""
    try:
        svc = _get_safe_service("get_invoice_extraction_service")
        caps = svc.get_extraction_capabilities()
        return success_response(message="Capabilities retrieved", data=caps)
    except Exception as exc:
        logger.exception("invoice capabilities failed")
        return error_response(f"Capabilities failed: {exc}", 500)

# --------------- bank statement --------------- #
@pdf_suite_bp.route("/ai/extract-bank-statement", methods=["POST", "GET"])
def extract_bank_statement():
    """Extract structured bank-statement data."""
    try:
        file, err = get_file_and_validate("extraction")
        if err:
            return err
        options, err = _load_json_options()
        if err:
            return error_response(err, 400)

        job_id = _validate_job_id(request.form.get("job_id"))
        file_bytes = file.read()
        if len(file_bytes) > MAX_FILE_SIZE:
            return error_response("File too large", 413)

        file_svc = _get_safe_service("get_file_management_service")
        file_path = file_svc.save_file(file, job_id)

        payload, err = _enqueue_job(
            job_id=job_id,
            task_type=TaskType.AI_BANK_STATEMENT_EXTRACTION,
            input_data={
                "file_size": len(file_bytes),
                "original_filename": file.filename,
                "options": options,
            },
            task_func=extract_bank_statement_task,
            task_args=(job_id, file_path, options),
            task_kwargs={},
        )
        if err:
            return error_response(err, 500)
        return success_response(message="Bank-statement extraction queued", data=payload, status_code=202)
    except Exception as exc:
        logger.exception("bank-statement extraction failed")
        return error_response(f"Bank-statement extraction failed: {exc}", 500)

@pdf_suite_bp.route("/ai/bank-statement-capabilities", methods=["POST", "GET"])
def get_bank_statement_capabilities():
    """Return bank-statement extractor capabilities."""
    try:
        svc = _get_safe_service("get_bank_statement_extraction_service")
        caps = svc.get_extraction_capabilities()
        return success_response(message="Capabilities retrieved", data=caps, status_code=200)
    except Exception as exc:
        logger.exception("bank-statement capabilities failed")
        return error_response(f"Capabilities failed: {exc}", 500)

# --------------------------------------------------------------------------- #
# HEALTH / STATUS
# --------------------------------------------------------------------------- #
@pdf_suite_bp.route("/extended-features/status", methods=["POST", "GET"])
def get_extended_features_status():
    """Return overall subsystem health."""
    try:
        # quick redis ping with 1 s timeout
        redis_ok = False
        try:
            from src.celery_app import get_celery_app
            redis_ok = bool(get_celery_app().control.ping(timeout=1))
        except Exception:  # noqa
            pass

        conv_svc = _get_safe_service("get_conversion_service")
        ocr_svc = _get_safe_service("get_ocr_service")

        status = {
            "conversion": {
                "available": True,
                "supported_formats": list(conv_svc.supported_formats),
                "max_file_size": "100MB",
                "async_processing": True,
            },
            "ocr": {
                "available": True,
                "supported_formats": list(ocr_svc.supported_input_formats),
                "max_file_size": "50MB",
                "async_processing": True,
            },
            "ai": {
                "available": True,
                "supported_formats": ["pdf"],
                "max_file_size": "25MB",
                "async_processing": True,
            },
            "extraction": {
                "available": True,
                "supported_formats": ["pdf"],
                "max_file_size": "25MB",
                "async_processing": True,
                "features": ["invoice_extraction", "bank_statement_extraction"],
            },
            "queue": {"redis_available": redis_ok, "job_processing": True},
            "timestamp": datetime.utcnow().isoformat(),
        }
        return success_response(message="Status retrieved", data=status, status_code=200)
    except Exception as exc:
        logger.exception("status endpoint failed")
        return error_response(f"Status failed: {exc}", 500)

@pdf_suite_bp.route("/extended-features/capabilities", methods=["POST", "GET"])
def get_extended_features_capabilities():
    """Return detailed capabilities map."""
    try:
        # Dynamic lists are fetched inside try/except; if service is missing
        # we fall back to static list so the whole endpoint doesn't 500.
        conv_formats = []
        try:
            conv_formats = list(
                _get_safe_service("get_conversion_service").supported_formats
            )
        except Exception:
            conv_formats = ["docx", "xlsx", "txt", "html"]

        caps = {
            "conversion": {
                "name": "PDF Conversion",
                "description": "Convert PDFs to Word, Excel, Text, and HTML formats",
                "features": ["format_conversion", "layout_preservation", "table_extraction"],
                "options": {
                    "preserveLayout": "boolean",
                    "extractTables": "boolean",
                    "extractImages": "boolean",
                    "quality": "string (low|medium|high)",
                },
                "processing_mode": "async",
                "supported_formats": conv_formats,
            },
            "ocr": {
                "name": "Optical Character Recognition",
                "description": "Extract text from scanned PDFs and images",
                "features": ["text_extraction", "searchable_pdf", "language_support"],
                "options": {
                    "language": "string",
                    "quality": "string (fast|balanced|accurate)",
                    "outputFormat": "string (searchable_pdf|text|json)",
                },
                "processing_mode": "async",
            },
            "ai": {
                "name": "AI-Powered Features",
                "description": "Summarize and translate PDF content using AI",
                "features": ["summarization", "translation", "multiple_languages"],
                "options": {
                    "style": "string (concise|detailed|academic|casual|professional)",
                    "maxLength": "string (short|medium|long)",
                    "targetLanguage": "string (language code)",
                },
                "processing_mode": "async",
            },
            "extraction": {
                "name": "Document Data Extraction",
                "description": "Extract structured data from invoices and bank statements",
                "features": [
                    "invoice_data_extraction",
                    "bank_statement_extraction",
                    "structured_output",
                    "export_formats",
                ],
                "options": {
                    "export_format": "string (json|csv|excel|none)",
                    "export_filename": "string (optional custom filename)",
                    "include_confidence": "boolean (include AI confidence scores)",
                    "validate_data": "boolean (perform data validation)",
                },
                "processing_mode": "async",
            },
            "cloud": {
                "name": "Cloud Integration",
                "description": "Save/load files from cloud storage providers",
                "features": ["file_upload", "file_download", "folder_management", "oauth"],
                "providers": ["google_drive", "dropbox", "onedrive"],
                "processing_mode": "sync",
            },
        }
        return success_response(message="Capabilities retrieved", data=caps, status_code=200)
    except Exception as exc:
        logger.exception("capabilities endpoint failed")
        return error_response(f"Capabilities failed: {exc}", 500)