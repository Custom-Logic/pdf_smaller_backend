


we need to learn why the following does not work. 


        from src.tasks.tasks import convert_pdf_task
        task_id = enqueue_task(
            convert_pdf_task,
            job_id,
            file_data,
            format,
            options,
            file.filename,
            tracking['client_job_id'],
            tracking['client_session_id']
        )




        from src.tasks.tasks import conversion_preview_task
        task_id = enqueue_task(
            conversion_preview_task,
            job_id,
            file_data,
            format,
            options,
            tracking['client_job_id'],
            tracking['client_session_id']
        )



        from src.tasks.tasks import ocr_process_task
        task_id = enqueue_task(
            ocr_process_task,
            job_id,
            file_data,
            options,
            file.filename,
            tracking['client_job_id'],
            tracking['client_session_id']
        )


        from src.tasks.tasks import ocr_preview_task
        task_id = enqueue_task(
            ocr_preview_task,
            job_id,
            file_data,
            options,
            tracking['client_job_id'],
            tracking['client_session_id']
        )




    always returns the error that task cannot be scheduled to be specific here is a sample error
    from the front end. 


    684-e3c230ee52ce868b.js:1 Failed to convert WELCOME.pdf: Error: Failed to convert PDF: Job creation failed: API error: 400 Bad Request - {
      "errors": 500,
      "message": "Failed to create conversion job: cannot import name 'convert_pdf_task' from 'src.queues.task_queue' (/root/app/pdf_smaller_backend/src/queues/task_queue.py)",
      "status": "error"
    }

