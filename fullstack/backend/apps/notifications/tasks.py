from config.celery import app


@app.task(name="notifications.send_email_task")
def send_email_task(email_task_id: int) -> None:
    from apps.notifications.services import process_email_task

    process_email_task(email_task_id)

