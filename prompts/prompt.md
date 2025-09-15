

## Fixes for pdf_suite services.


### Conversion Service Fix

{
  `newText`: `@pdf_suite_bp.route('/convert', methods=['POST'])
def convert_pdf():
    \"\"\"Convert PDF to specified format - returns job ID\"\"\"
    try:
        target_format = request.form.get('format', 'txt').lower()
        # Validate format
        if target_format not in ServiceRegistry.get_conversion_service().supported_formats:
            return error_response(message=f\"Unsupported format: {target_format}\", status_code=400)

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
                return error_response(message=\"Invalid options format\", status_code=400)

        job_id = request.form.get('job_id', str(uuid.uuid4()))

        # Read file data
        file_data = file.read()

        # CREATE JOB FIRST - this is the fix!
        from src.jobs.job_manager import JobStatusManager
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type='convert',
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

            logger.info(f\"Conversion job {job_id} enqueued (format: {target_format}, task_id: {task.id})\")

            return success_response(message=\"Conversion job queued successfully\", data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value,
                'format': target_format
            }, status_code=202)
        except Exception as task_error:
             logger.error(f\"Failed to enqueue conversion task {job_id}: {str(task_error)}\")
             JobStatusManager.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=f\"Task enqueueing failed: {str(task_error)}\"
             )
             return error_response(message='Failed to queue conversion job', status_code=500)

    except Exception as e:
        logger.error(f\"PDF conversion job creation failed: {str(e)}\")
        return error_response(message=f\"Failed to create conversion job: {str(e)}\", status_code=500)`,
  `oldText`: `@pdf_suite_bp.route('/convert', methods=['POST'])
def convert_pdf():
    \"\"\"Convert PDF to specified format - returns job ID\"\"\"
    try:
        target_format = request.form.get('format', 'txt').lower()
        # Validate format
        if target_format not in ServiceRegistry.get_conversion_service().supported_formats:
            return error_response(message=f\"Unsupported format: {target_format}\", status_code=400)

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
                return error_response(message=\"Invalid options format\", status_code=400)

        job_id = request.form.get('job_id', str(uuid.uuid4()))


        # Read file data
        file_data = file.read()

        # Enqueue conversion task using .delay() pattern
        try:
            task = convert_pdf_task.delay(
                job_id,
                file_data,
                target_format,
                options,
                file.filename,
            )

            logger.info(f\"Conversion job {job_id} enqueued (format: {target_format}, task_id: {task.id})\")

            return success_response(message=\"Conversion job queued successfully\", data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value,
                'format': target_format
            }, status_code=202)
        except Exception as task_error:
             logger.error(f\"Failed to enqueue conversion task {job_id}: {str(task_error)}\")
             return error_response(message='Failed to queue conversion job', status_code=500)

    except Exception as e:
        logger.error(f\"PDF conversion job creation failed: {str(e)}\")
        return error_response(message=f\"Failed to create conversion job: {str(e)}\", status_code=500)`,
  `pathInProject`: `src/routes/pdf_suite.py`
}


### Convert Preview

Request

{
  `newText`: `@pdf_suite_bp.route('/convert/preview', methods=['POST'])
def get_conversion_preview():
    \"\"\"Get conversion preview and estimates - returns job ID\"\"\"
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
                return error_response(message=\"Invalid options format\", status_code=400)

        job_id = request.form.get('job_id', str(uuid.uuid4()))

        file_data = file.read()

        # CREATE JOB FIRST - this is the fix!
        from src.jobs.job_manager import JobStatusManager
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type='conversion_preview',
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

            logger.info(f\"Conversion preview job {job_id} enqueued (task_id: {task.id})\")

            return success_response(message=\"Conversion preview job queued successfully\", data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value
            }, status_code=202)
        except Exception as task_error:
            logger.error(f\"Failed to enqueue conversion preview task {job_id}: {str(task_error)}\")
            JobStatusManager.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=f\"Task enqueueing failed: {str(task_error)}\"
            )
            return error_response(message='Failed to queue conversion preview job', status_code=500)

    except Exception as e:
        logger.error(f\"Conversion preview job creation failed: {str(e)}\")
        return error_response(message=f\"Failed to create preview job: {str(e)}\", status_code=500)`,
  `oldText`: `@pdf_suite_bp.route('/convert/preview', methods=['POST'])
def get_conversion_preview():
    \"\"\"Get conversion preview and estimates - returns job ID\"\"\"
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
                return error_response(message=\"Invalid options format\", status_code=400)

        job_id = request.form.get('job_id', str(uuid.uuid4()))


        file_data = file.read()

        # Enqueue conversion preview task using .delay() pattern
        task = conversion_preview_task.delay(
            job_id,
            file_data,
            format,
            options,

        )

        logger.info(f\"Conversion preview job {job_id} enqueued (task_id: {task.id})\")

        return success_response(message=\"Conversion preview job queued successfully\", data={
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value
        }, status_code=202)

    except Exception as e:
        logger.error(f\"Conversion preview job creation failed: {str(e)}\")
        return error_response(message=f\"Failed to create preview job: {str(e)}\", status_code=500)`,
  `pathInProject`: `src/routes/pdf_suite.py`
}


### OCR Service


Request

{
  `newText`: `@pdf_suite_bp.route('/ocr', methods=['POST'])
def process_ocr():
    \"\"\"Process OCR on uploaded file - returns job ID\"\"\"
    try:
        file, error = get_file_and_validate('ocr')
        if error:
            return error

        options = {}
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response(message=\"Invalid options format\", status_code=400)

        job_id = request.form.get('job_id', str(uuid.uuid4()))

        file_data = file.read()

        # CREATE JOB FIRST - this is the fix!
        from src.jobs.job_manager import JobStatusManager
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type='ocr',
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

            logger.info(f\"OCR job {job_id} enqueued (task_id: {task.id})\")

            return success_response(message=\"OCR job queued successfully\", data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value
            }, status_code=202)
        except Exception as task_error:
            logger.error(f\"Failed to enqueue OCR task {job_id}: {str(task_error)}\")
            JobStatusManager.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=f\"Task enqueueing failed: {str(task_error)}\"
            )
            return error_response(message='Failed to queue OCR job', status_code=500)

    except Exception as e:
        logger.error(f\"OCR job creation failed: {str(e)}\")
        return error_response(message=f\"Failed to create OCR job: {str(e)}\", status_code=500)`,
  `oldText`: `@pdf_suite_bp.route('/ocr', methods=['POST'])
def process_ocr():
    \"\"\"Process OCR on uploaded file - returns job ID\"\"\"
    try:
        file, error = get_file_and_validate('ocr')
        if error:
            return error

        options = {}
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response(message=\"Invalid options format\", status_code=400)


        job_id = request.form.get('job_id', str(uuid.uuid4()))

        file_data = file.read()

        # Enqueue OCR task using .delay() pattern
        task = ocr_process_task.delay(
            job_id=job_id,
            file_data=file_data,
            options=options,
            original_filename=file.filename)

        logger.info(f\"OCR job {job_id} enqueued (task_id: {task.id})\")

        return success_response(message=\"OCR job queued successfully\", data={
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value
        }, status_code=202)

    except Exception as e:
        logger.error(f\"OCR job creation failed: {str(e)}\")
        return error_response(message=f\"Failed to create OCR job: {str(e)}\", status_code=500)`,
  `pathInProject`: `src/routes/pdf_suite.py`
}


### OCR Preview


Request

{
  `newText`: `@pdf_suite_bp.route('/ocr/preview', methods=['POST'])
def get_ocr_preview():
    \"\"\"Get OCR preview and estimates - returns job ID\"\"\"
    try:
        file, error = get_file_and_validate('ocr')
        if error:
            return error

        options = {}
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response(message=\"Invalid options format\", status_code=400)

        job_id = request.form.get('job_id', str(uuid.uuid4()))

        file_data = file.read()

        # CREATE JOB FIRST - this is the fix!
        from src.jobs.job_manager import JobStatusManager
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type='ocr_preview',
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

            logger.info(f\"OCR preview job {job_id} enqueued (task_id: {task.id})\")

            return success_response(message=\"OCR preview job queued successfully\", data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value
            }, status_code=202)
        except Exception as task_error:
            logger.error(f\"Failed to enqueue OCR preview task {job_id}: {str(task_error)}\")
            JobStatusManager.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=f\"Task enqueueing failed: {str(task_error)}\"
            )
            return error_response(message='Failed to queue OCR preview job', status_code=500)

    except Exception as e:
        logger.error(f\"OCR preview job creation failed: {str(e)}\")
        return error_response(message=f\"Failed to create OCR preview job: {str(e)}\", status_code=500)`,
  `oldText`: `@pdf_suite_bp.route('/ocr/preview', methods=['POST'])
def get_ocr_preview():
    \"\"\"Get OCR preview and estimates - returns job ID\"\"\"
    try:
        file, error = get_file_and_validate('ocr')
        if error:
            return error

        options = {}
        if 'options' in request.form:
            try:
                options = json.loads(request.form['options'])
            except json.JSONDecodeError:
                return error_response(message=\"Invalid options format\", status_code=400)

        job_id = request.form.get('job_id', str(uuid.uuid4()))


        file_data = file.read()

        # Enqueue OCR preview task using .delay() pattern
        task = ocr_preview_task.delay(
            job_id,
            file_data,
            options,

        )

        logger.info(f\"OCR preview job {job_id} enqueued (task_id: {task.id})\")

        return success_response(message=\"OCR preview job queued successfully\", data={
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value
        }, status_code=202)

    except Exception as e:
        logger.error(f\"OCR preview job creation failed: {str(e)}\")
        return error_response(message=f\"Failed to create OCR preview job: {str(e)}\", status_code=500)`,
  `pathInProject`: `src/routes/pdf_suite.py`
}


### AI Services


Request

{
  `newText`: `@pdf_suite_bp.route('/ai/extract-text', methods=['POST'])
def extract_text():
    \"\"\"Extract text content from PDF - returns job ID\"\"\"
    try:
        file, error = get_file_and_validate('ai')
        if error:
            return error

        job_id = request.form.get('job_id', str(uuid.uuid4()))

        file_data = file.read()

        # CREATE JOB FIRST - this is the fix!
        from src.jobs.job_manager import JobStatusManager
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type='extract_text',
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

            logger.info(f\"Text extraction job {job_id} enqueued (task_id: {task.id})\")

            return success_response(message=\"Text extraction job queued successfully\", data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value
            }, status_code=202)
        except Exception as task_error:
            logger.error(f\"Failed to enqueue text extraction task {job_id}: {str(task_error)}\")
            JobStatusManager.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=f\"Task enqueueing failed: {str(task_error)}\"
            )
            return error_response(message='Failed to queue text extraction job', status_code=500)

    except Exception as e:
        logger.error(f\"Text extraction job creation failed: {str(e)}\")
        return error_response(message=f\"Failed to create text extraction job: {str(e)}\", status_code=500)`,
  `oldText`: `@pdf_suite_bp.route('/ai/extract-text', methods=['POST'])
def extract_text():
    \"\"\"Extract text content from PDF - returns job ID\"\"\"
    try:
        file, error = get_file_and_validate('ai')
        if error:
            return error

        job_id = request.form.get('job_id', str(uuid.uuid4()))

        file_data = file.read()

        # Enqueue text extraction task using .delay() pattern
        task = extract_text_task.delay(
            job_id,
            file_data,
            file.filename,

        )

        logger.info(f\"Text extraction job {job_id} enqueued (task_id: {task.id})\")

        return success_response(message=\"Text extraction job queued successfully\", data={
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value
        }, status_code=202)

    except Exception as e:
        logger.error(f\"Text extraction job creation failed: {str(e)}\")
        return error_response(message=f\"Failed to create text extraction job: {str(e)}\", status_code=500)`,
  `pathInProject`: `src/routes/pdf_suite.py`
}


### AI Summarize Routes

Request

{
  `newText`: `@pdf_suite_bp.route('/ai/summarize', methods=['POST'])
def summarize_pdf():
    \"\"\"Summarize PDF content using AI - returns job ID\"\"\"
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return error_response(message=\"No text content provided\", status_code=400)

        text = data['text']
        if len(text) > 100000:  # 100KB limit
            return error_response(message=\"Text too long. Maximum length is 100KB.\", status_code=400)

        options = data.get('options', {})
        job_id = data.get('job_id', str(uuid.uuid4()))

        # CREATE JOB FIRST - this is the fix!
        from src.jobs.job_manager import JobStatusManager
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type='ai_summarize',
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

            logger.info(f\"AI summarization job {job_id} enqueued (task_id: {task.id})\")

            return success_response(message=\"Summarization job queued successfully\", data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value
            }, status_code=202)
        except Exception as task_error:
            logger.error(f\"Failed to enqueue AI summarization task {job_id}: {str(task_error)}\")
            JobStatusManager.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=f\"Task enqueueing failed: {str(task_error)}\"
            )
            return error_response(message='Failed to queue summarization job', status_code=500)

    except Exception as e:
        logger.error(f\"AI summarization job creation failed: {str(e)}\")
        return error_response(message=f\"Failed to create summarization job: {str(e)}\", status_code=500)`,
  `oldText`: `@pdf_suite_bp.route('/ai/summarize', methods=['POST'])
def summarize_pdf():
    \"\"\"Summarize PDF content using AI - returns job ID\"\"\"
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return error_response(message=\"No text content provided\", status_code=400)

        text = data['text']
        if len(text) > 100000:  # 100KB limit
            return error_response(message=\"Text too long. Maximum length is 100KB.\", status_code=400)

        options = data.get('options', {})
        job_id = request.form.get('job_id', str(uuid.uuid4()))



        # Enqueue AI summarization task using .delay() pattern
        task = ai_summarize_task.delay(
            job_id,
            text,
            options,

        )

        logger.info(f\"AI summarization job {job_id} enqueued (task_id: {task.id})\")

        return success_response(message=\"Summarization job queued successfully\", data={
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value
        }, status_code=202)

    except Exception as e:
        logger.error(f\"AI summarization job creation failed: {str(e)}\")
        return error_response(message=f\"Failed to create summarization job: {str(e)}\", status_code=500)`,
  `pathInProject`: `src/routes/pdf_suite.py`
}

### AI Translate Route


Request

{
  `newText`: `@pdf_suite_bp.route('/ai/translate', methods=['POST'])
def translate_text():
    \"\"\"Translate text using AI - returns job ID\"\"\"
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return error_response(message=\"No text content provided\", status_code=400)

        text = data['text']
        if len(text) > 100000:  # 100KB limit
            return error_response(message=\"Text too long. Maximum length is 100KB.\", status_code=400)

        target_language = data.get('target_language', 'en')
        options = data.get('options', {})
        job_id = data.get('job_id', str(uuid.uuid4()))

        # CREATE JOB FIRST - this is the fix!
        from src.jobs.job_manager import JobStatusManager
        job = JobStatusManager.get_or_create_job(
            job_id=job_id,
            task_type='ai_translate',
            input_data={
                'target_language': target_language,
                'text_length': len(text),
                'options': options
            }
        )
        
        if not job:
            return error_response(message='Failed to create translation job', status_code=500)

        # Enqueue AI translation task using .delay() pattern
        try:
            task = ai_translate_task.delay(
                job_id,
                text,
                target_language,
                options
            )

            logger.info(f\"AI translation job {job_id} enqueued (task_id: {task.id})\")

            return success_response(message=\"Translation job queued successfully\", data={
                'job_id': job_id,
                'task_id': task.id,
                'status': JobStatus.PENDING.value
            }, status_code=202)
        except Exception as task_error:
            logger.error(f\"Failed to enqueue AI translation task {job_id}: {str(task_error)}\")
            JobStatusManager.update_job_status(
                job_id=job_id,
                status=JobStatus.FAILED,
                error_message=f\"Task enqueueing failed: {str(task_error)}\"
            )
            return error_response(message='Failed to queue translation job', status_code=500)

    except Exception as e:
        logger.error(f\"AI translation job creation failed: {str(e)}\")
        return error_response(message=f\"Failed to create translation job: {str(e)}\", status_code=500)`,
  `oldText`: `@pdf_suite_bp.route('/ai/translate', methods=['POST'])
def translate_text():
    \"\"\"Translate text using AI - returns job ID\"\"\"
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return error_response(message=\"No text content provided\", status_code=400)

        text = data['text']
        if len(text) > 100000:  # 100KB limit
            return error_response(message=\"Text too long. Maximum length is 100KB.\", status_code=400)

        target_language = data.get('target_language', 'en')
        options = data.get('options', {})
        job_id = request.form.get('job_id', str(uuid.uuid4()))


        # Enqueue AI translation task using .delay() pattern
        task = ai_translate_task.delay(
            job_id,
            text,
            target_language,
            options
        )

        logger.info(f\"AI translation job {job_id} enqueued (task_id: {task.id})\")

        return success_response(message=\"Translation job queued successfully\", data={
            'job_id': job_id,
            'task_id': task.id,
            'status': JobStatus.PENDING.value
        }, status_code=202)

    except Exception as e:
        logger.error(f\"AI translation job creation failed: {str(e)}\")
        return error_response(message=f\"`
}
