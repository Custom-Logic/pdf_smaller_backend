# Import all tasks for Celery autodiscovery
from .tasks import (
    compress_task,
    bulk_compress_task,
    convert_pdf_task,
    conversion_preview_task,
    ocr_process_task,
    ocr_preview_task,
    ai_summarize_task,
    ai_translate_task,
    extract_text_task,
    cleanup_expired_jobs,
    get_task_status,
    extract_invoice_task,
    merge_pdfs_task,
    split_pdf_task,
    cleanup_temp_files_task,
    health_check_task,
    extract_bank_statement_task
)

__all__ = [
    'compress_task',
    'bulk_compress_task',
    'convert_pdf_task',
    'conversion_preview_task',
    'ocr_process_task',
    'ocr_preview_task',
    'ai_summarize_task',
    'ai_translate_task',
    'extract_text_task',
    'cleanup_expired_jobs',
    'get_task_status',
    'extract_invoice_task',
    'merge_pdfs_task',
    'split_pdf_task',
    'cleanup_temp_files_task',
    'health_check_task',
    'extract_bank_statement_task'
]