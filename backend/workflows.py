"""Shared job lifecycle and admin state. Tokens are never persisted."""
from datetime import timedelta, timezone
from sqlalchemy import select, func
from .models import School, CrawlJob, CrawlError, WorkerState, ExamVersion, now
from .services import audit

LEASE_SECONDS = 180

def utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def enqueue_school(db, school_id, action='enqueue'):
    school = db.scalar(select(School).where(School.id == school_id).with_for_update())
    if not school:
        raise LookupError('School not found')
    if school.demo or not school.crawl_enabled:
        raise ValueError('School crawling disabled; demo data is never crawled')
    existing = db.scalar(select(CrawlJob).where(CrawlJob.school_id == school_id, CrawlJob.status.in_(['queued', 'running'])))
    if existing:
        return existing
    job = CrawlJob(school_id=school_id)
    db.add(job)
    db.flush()
    audit(db, 'crawl', job.id, action, after={'school_id': school_id, 'status': 'queued'})
    return job


def job_dict(db, job):
    data = {k: getattr(job, k) for k in ('id', 'school_id', 'status', 'created_at', 'started_at', 'completed_at', 'pages_checked', 'documents', 'new_exams', 'error')}
    school = db.get(School, job.school_id)
    data['school_name'] = school.name if school else job.school_id
    data['errors'] = [{'url': e.url, 'message': e.message} for e in db.scalars(select(CrawlError).where(CrawlError.job_id == job.id).order_by(CrawlError.id).limit(10))]
    return data


def worker_info(db):
    state = db.get(WorkerState, 'crawler')
    if not state:
        return {'online': False, 'heartbeat_at': None, 'current_job_id': None}
    return {'online': utc(state.lease_until) > now() and (now() - utc(state.heartbeat_at)).total_seconds() < LEASE_SECONDS, 'heartbeat_at': state.heartbeat_at, 'current_job_id': state.current_job_id}


def summary(db):
    counts = dict(db.execute(select(CrawlJob.status, func.count()).group_by(CrawlJob.status)).all())
    return {'schools': db.scalar(select(func.count()).select_from(School)), 'enabled_schools': db.scalar(select(func.count()).select_from(School).where(School.crawl_enabled == True, School.demo == False)), 'needs_review': db.scalar(select(func.count()).select_from(ExamVersion).where(ExamVersion.status == 'review')), 'jobs': counts, 'worker': worker_info(db)}
