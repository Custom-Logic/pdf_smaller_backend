import os
from flask import Blueprint, send_file
from src.models.job import Job, JobStatus
from src.utils.response_helpers import error_response, success_response
from pathlib import Path
jobs_bp = Blueprint('jobs', __name__)

# ----------------------------  status  ----------------------------
@jobs_bp.route('/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    job = Job.query.filter_by(job_id=job_id).first()
    if not job:
        return error_response(message="Job not found", status_code=404)

    data = {
        "job_id":   job.job_id,
        "status":   job.status,
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