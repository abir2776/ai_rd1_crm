from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "swift_web_ai.settings")

app = Celery("swift_web_ai")

app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")


# -------------------------------
#     Celery Beat SCHEDULE
# -------------------------------
app.conf.beat_schedule = {
    "run-initiate-all-interview-every-5-min": {
        "task": "interview.tasks.initiate_all_interview",
        "schedule": crontab(minute="*/1"),
        "args": (),
    },
}
