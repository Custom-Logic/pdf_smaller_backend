import os
import logging
from flask import Blueprint, send_file
from src.models.job import Job, JobStatus
from src.utils.response_helpers import error_response, success_response
from pathlib import Path
jobs_bp = Blueprint('jobs', __name__)
logger = logging.getLogger(__name__)
# ----------------------------  status  ----------------------------
@jobs_bp.route('/jobs/<job_id>', methods=['GET', 'POST'])
def get_job_status(job_id):
    """Get job status by ID"""
    try:
        job = Job.query.filter_by(job_id=job_id).first()
        if not job:
            return error_response(
                message='Job not found',
                error_code='JOB_NOT_FOUND',
                status_code=404
            )
        
        # Add monitoring metrics
        job_data = job.to_dict()
        job_data['monitoring'] = {
            'created_at_iso': job.created_at.isoformat() if job.created_at else None,
            'updated_at_iso': job.updated_at.isoformat() if job.updated_at else None,
            'processing_duration_seconds': (job.updated_at - job.created_at).total_seconds() if job.updated_at and job.created_at else None
        }
        
        return success_response(
            message='Job status retrieved successfully',
            data=job_data
        )
    except Exception as e:
        logger.error(f"Error retrieving job status: {str(e)}", extra={'job_id': job_id})
        return error_response(
            message='Failed to retrieve job status',
            error_code='JOB_STATUS_ERROR',
            status_code=500
        )



# ----------------------------  download  ----------------------------
@jobs_bp.route('/jobs/<job_id>/download', methods=['GET','POST'])
def download_job_result(job_id):
    job = Job.query.filter_by(job_id=job_id).first()
    if not job:
        return error_response(message="Job not found", status_code=404)
    if not job.is_completed():
        return error_response(message="Job not completed yet", status_code=400)
    if not job.result or "output_path" not in job.result:
        return error_response(message="No result file available", status_code=404)
    # This is running in UBuntu should the path be like this.
    # ./uploads/dev/results/compressed_a55865f3-935f-4dc1-83af-fd78ca4b4730_COR14.1A.pdf"
    #  or should it be a complete path. hint when its like this even though the file exist it is not sending the file
    raw_path = job.result["output_path"]
    path = (Path.cwd() / raw_path).resolve()
    if not path.is_file():
        return error_response(message="Result file not found on disk", status_code=404)

    fname = job.result.get("original_filename", "result")
    mime  = job.result.get("mime_type", "application/octet-stream")
    # return error_response(message=f"DEBUG : MIME: {mime} FNAME : {fname} - {path}", status_code=404)
    return send_file(
        str(path),
        as_attachment=True,
        download_name=fname,
        mimetype=mime
    )