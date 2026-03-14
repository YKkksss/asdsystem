from config.celery import app


@app.task(name="digitization.process_file_process_job")
def process_file_process_job_task(job_id: int) -> None:
    from apps.digitization.services import process_file_process_job

    process_file_process_job(job_id)
