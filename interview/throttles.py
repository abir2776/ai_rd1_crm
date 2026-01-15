from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone
from rest_framework.throttling import BaseThrottle


class CallRequestIPThrottle(BaseThrottle):
    MAX_CALLS = 2
    WINDOW_HOURS = 12

    def allow_request(self, request, view):
        ip = self.get_ip(request)
        if not ip:
            return True

        cache_key = f"call_request_ip:{ip}"
        now = timezone.now()

        timestamps = cache.get(cache_key, [])
        valid_after = now - timedelta(hours=self.WINDOW_HOURS)
        timestamps = [ts for ts in timestamps if ts > valid_after]

        if len(timestamps) >= self.MAX_CALLS:
            return False

        timestamps.append(now)
        cache.set(cache_key, timestamps, timeout=self.WINDOW_HOURS * 3600)
        return True

    def wait(self):
        return None

    def get_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            return x_forwarded_for.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR")
