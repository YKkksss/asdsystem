from config.celery import app


@app.task(name="borrowing.dispatch_due_borrow_reminders")
def dispatch_due_borrow_reminders_task() -> None:
    from apps.borrowing.services import dispatch_due_borrow_reminders

    dispatch_due_borrow_reminders()
