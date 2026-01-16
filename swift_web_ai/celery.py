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
    # "run-initiate-all-awr-email": {
    #     "task": "awr_compliance.tasks.initiate_all_awr_emails",
    #     "schedule": crontab(minute="*/3"),
    # },
    # "run-initiate-all-gdpr-email": {
    #     "task": "ai_gdpr.tasks.initiate_all_gdpr_emails",
    #     "schedule": crontab(minute="*/3"),
    # },
    # Run from 4 PM (16:00) to 11 PM (23:00)
    "run-initiate-all-interview-evening": {
        "task": "interview.tasks.ai_phone.initiate_all_interview",
        "schedule": crontab(
            minute="*/5",
            hour="16-23",
            day_of_week="0-6"
        ),
    },
    # Run from 12 AM (00:00) to 9 AM (09:00)
    "run-initiate-all-interview-morning": {
        "task": "interview.tasks.ai_phone.initiate_all_interview",
        "schedule": crontab(
            minute="*/5",
            hour="0-9",
            day_of_week="0-6"
        ),
    },
    # "format-cvs-every-3-minutes": {
    #     "task": "cv_formatter.tasks.initiate_all_cv_formatting",
    #     "schedule": crontab(minute="*/3"),
    # },
    # "run-initiate-all-sms-interview-every-3-min": {
    #     "task": "interview.tasks.ai_sms.initiate_all_sms_interviews",
    #     "schedule": crontab(minute="*/5"),
    # },
    # "initiate-whatsapp-interviews": {
    #     "task": "interview.tasks.ai_whatsapp.initiate_all_whatsapp_interviews",
    #     "schedule": crontab(minute="*/3"),
    # },
    # "run-initiate-all-candidate-skill-search": {
    #     "task": "ai_skill_search.tasks.initiate_ai_skill_search",
    #     "schedule": crontab(minute="*/5"),
    # },
    # "run-initiate-all-client-lead-generation": {
    #     "task": "ai_lead_generation.tasks.initiate_ai_lead_generation_for_all_organizations",
    #     "schedule": crontab(minute="*/5"),
    # }
    # "run-initiate-all-client-lead-generation-part-2": {
    #     "task": "ai_lead_generation.tasks.lead_generation_2.initiate_marketing_automation_for_all_organizations",
    #     "schedule": crontab(minute="*/5"),
    # },
    # 'check-scheduled-whatsapp-campaigns': {
    #     'task': 'whatsapp_campaign.tasks.check_scheduled_campaigns',
    #     'schedule': crontab(minute='*/5'),
    # },
}
