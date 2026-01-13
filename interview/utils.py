from datetime import timedelta

import pytz
from django.utils import timezone

from .models import CallRequest

MAX_CALLS = 2
WINDOW_HOURS = 12


def local_to_utc(local_dt, timezone):
    tz = pytz.timezone(timezone)
    local_dt = tz.localize(local_dt)
    return local_dt.astimezone(pytz.UTC)


def can_place_call(phone: str) -> bool:
    since = timezone.now() - timedelta(hours=WINDOW_HOURS)

    count = CallRequest.objects.filter(phone=phone, created_at__gte=since).count()

    return count < MAX_CALLS
