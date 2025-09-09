from flask import Blueprint, jsonify, send_file, current_app
from src.models.job import Job, JobStatus
from src.utils.response_helpers import error_response, success_response
import os

jobs_bp = Blueprint('jobs', __name__)

# ----------------------------  status  ----------------------------
@jobs_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    job = Job.query.filter_by(job_id=job_id).first()
    if not job:
        return error_response(message="Job not found", status_code=404)

    data = {
        "job_id":   job.job_id,
        "status":   job.status.value,
        "task_type": job.task_type,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }
    if job.status == JobStatus.COMPLETED and job.result:
        data["result"] = job.result
        if job.result.get("output_path") and os.path.exists(job.result["output_path"]):
            data["download_url"] = f"/api/jobs/{job_id}/download"
            data["download_available"] = True
        else:
            data["download_available"] = False
    elif job.status == JobStatus.FAILED and job.error:
        data["error"] = job.error
    return success_response(message="Job status retrieved", data=data, status_code=200)



# ----------------------------  download  ----------------------------
@jobs_bp.route('/jobs/<job_id>/download', methods=['GET'])
def download_job_result(job_id):
    job = Job.query.filter_by(job_id=job_id).first()
    if not job:
        return error_response("Job not found", 404)
    if job.status != JobStatus.COMPLETED:
        return error_response("Job not completed yet", 400)
    if not job.result or "output_path" not in job.result:
        return error_response("No result file available", 404)

    path = job.result["output_path"]
    if not os.path.exists(path):
        return error_response("Result file not found on disk", 404)

    fname = job.result.get("original_filename", "result")
    mime  = job.result.get("mime_type", "application/octet-stream")

    return send_file(
        path,
        as_attachment=True,
        download_name=fname,
        mimetype=mime
    )