"""Scheduling policy used by workers; per-school jobs stay independently resumable."""
from datetime import datetime,timedelta,timezone

def next_crawl_at(*,recent_exam=False,consecutive_failures=0,now=None):
    now=now or datetime.now(timezone.utc)
    hours=6 if recent_exam else 24
    hours=min(168,hours*2**min(consecutive_failures,4))
    return now+timedelta(hours=hours)
