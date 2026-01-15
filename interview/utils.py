import pytz

MAX_CALLS = 2
WINDOW_HOURS = 12


def local_to_utc(local_dt, timezone):
    tz = pytz.timezone(timezone)
    local_dt = tz.localize(local_dt)
    return local_dt.astimezone(pytz.UTC)
