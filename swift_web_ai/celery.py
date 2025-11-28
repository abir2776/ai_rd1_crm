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
    # "run-initiate-all-interview-every-5-min": {
    #     "task": "interview.tasks.ai_phone.initiate_all_interview",
    #     "schedule": crontab(minute="*/3"),
    # },
    # "format-cvs-every-3-minutes": {
    #     "task": "cv_formatter.tasks.initiate_all_cv_formatting",
    #     "schedule": crontab(minute="*/3"),
    # },
    # "run-initiate-all-sms-interview-every-3-min": {
    #     "task": "interview.tasks.ai_sms.initiate_all_sms_interviews",
    #     "schedule": crontab(minute="*/3"),
    # },
    "initiate-whatsapp-interviews": {
        "task": "interview.tasks.ai_whatsapp.initiate_all_whatsapp_interviews",
        "schedule": crontab(minute="*/3"),
    },
}
