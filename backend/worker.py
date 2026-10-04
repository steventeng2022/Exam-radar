"""One leased crawler process, durable jobs, heartbeat, cancellation and recovery."""
import asyncio
import logging
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .database import Base, engine, SessionLocal
from .models import School, CrawlJob, Source, CrawlError, CrawlDocument, WorkerState, now
from .services import ingest_exam, audit
from .workflows import LEASE_SECONDS, utc, enqueue_school
from crawler.pipeline import School as CrawlSchool, run_school, acknowledge_result
from crawler.scheduler import next_crawl_at

log = logging.getLogger('examradar.worker')

class JobCancelled(Exception):
    pass


def acquire_lease(owner):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        state = db.scalar(select(WorkerState).where(WorkerState.id == 'crawler').with_for_update())
        if state and state.owner != owner and utc(state.lease_until) > now():
            return False
        if state is None:
            state = WorkerState(id='crawler', owner=owner, lease_until=now())
            db.add(state)
        state.owner = owner
        state.heartbeat_at = now()
        state.lease_until = now() + timedelta(seconds=LEASE_SECONDS)
        state.current_job_id = None
        # Recover only after owning the global lease, never while another process runs.
        for job in db.scalars(select(CrawlJob).where(CrawlJob.status == 'running')):
            job.status = 'queued'
            audit(db, 'crawl', job.id, 'recover', {'status':'running'}, {'status':'queued'})
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return False
        return True


def refresh_lease(owner, *, current_job=None, set_job=False):
    with SessionLocal() as db:
        state = db.scalar(select(WorkerState).where(WorkerState.id == 'crawler').with_for_update())
        if not state or state.owner != owner:
            raise JobCancelled('Worker lease lost')
        state.heartbeat_at = now()
        state.lease_until = now() + timedelta(seconds=LEASE_SECONDS)
        if set_job:
            state.current_job_id = current_job
        db.commit()


def check_lease(db, owner):
    if owner:
        state = db.scalar(select(WorkerState).where(WorkerState.id=='crawler').with_for_update().execution_options(populate_existing=True))
        if not state or state.owner != owner or utc(state.lease_until) <= now():
            raise JobCancelled('Worker lease lost')


def bounded_pages(pages):
    budget = 200000
    output = []
    truncated = False
    for page in pages[:100]:
        text = page['text'][:budget]
        output.append({**page, 'text':text})
        budget -= len(text)
        if len(text) < len(page['text']): truncated = True
        if budget <= 0:
            truncated = True
            break
    return output, truncated


async def run_once(owner=None):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        check_lease(db, owner)
        job = db.scalar(select(CrawlJob).where(CrawlJob.status=='queued').order_by(CrawlJob.id).with_for_update(skip_locked=True).limit(1))
        if not job: return False
        school = db.get(School, job.school_id)
        if school.demo or not school.crawl_enabled:
            job.status='cancelled';job.completed_at=now();db.commit();return True
        job.status='running';job.started_at=now();school.last_crawled_at=now();school.crawler_status='running'
        db.commit()
        job_id, school_id = job.id, school.id
        crawl_school = CrawlSchool(id=school.id,name=school.name,website=school.website,domains=school.domains)
        state_path = None
        try:
            if owner: refresh_lease(owner,current_job=job_id,set_job=True)
            path = Path(os.getenv('CRAWLER_STATE_DIR','./data/frontier'))
            path.mkdir(parents=True,exist_ok=True)
            state_path = str(path / 'frontier.sqlite3')
            async def progress(pages_checked):
                with SessionLocal() as progress_db:
                    check_lease(progress_db, owner)
                    live_job=progress_db.get(CrawlJob,job_id)
                    live_school=progress_db.get(School,school_id)
                    if live_job.status != 'running' or not live_school.crawl_enabled:
                        raise JobCancelled('Crawl cancelled or school paused')
                    live_job.pages_checked=pages_checked
                    progress_db.commit()
            result = await run_school(crawl_school,state_path=state_path,commit_state=False,on_progress=progress,max_pages=int(os.getenv('CRAWLER_MAX_PAGES','40')))
            db.refresh(job);db.refresh(school);check_lease(db,owner)
            if job.status != 'running' or not school.crawl_enabled:
                raise JobCancelled('Crawl cancelled or school paused')
            sources, documents = {}, {}
            for doc in result.documents:
                source=db.scalar(select(Source).where(Source.school_id==school.id,Source.url==doc['url'],Source.content_hash==doc['content_hash']))
                if not source:
                    source=Source(school_id=school.id,url=doc['url'],file_url=doc['url'] if doc['source_type']!='html' else None,title=doc['title'],content_hash=doc['content_hash'],source_type=doc['source_type'])
                    db.add(source);db.flush()
                sources[doc['url']]=source
                document=db.scalar(select(CrawlDocument).where(CrawlDocument.source_id==source.id))
                if not document:
                    pages,truncated=bounded_pages(doc['pages'])
                    document=CrawlDocument(school_id=school.id,source_id=source.id,text=doc['text'],pages=pages,truncated=truncated,extraction_status='needs_manual')
                    db.add(document)
                documents[doc['url']]=document
            added=0
            validation_errors=[]
            for extraction in result.extractions:
                source=sources.get(extraction['source_url'])
                if not source: raise ValueError('Extraction has no matching source')
                try:
                    with db.begin_nested():
                        version,created=ingest_exam(db,school,source,extraction)
                        added += int(created)
                        documents[extraction['source_url']].extraction_status='review' if version.status=='review' else 'published' if version.status in ('approved','warning') else 'rejected'
                except ValueError as exc:
                    validation_errors.append({'url':extraction['source_url'],'message':str(exc)[:500]})
            for error in result.errors + validation_errors:
                db.add(CrawlError(job_id=job.id,url=error['url'],message=error['message']))
            successes = result.pages_checked - len(result.errors)
            job.pages_checked=result.pages_checked;job.documents=len(result.documents);job.new_exams=added
            job.status='failed' if successes <= 0 and result.errors else 'warning' if result.errors or validation_errors else 'completed'
            job.error='All checked pages failed' if job.status=='failed' else None
            job.completed_at=now();school.crawler_status=job.status
            if successes > 0: school.last_success_at=now()
            db.commit()
            # Database success precedes frontier acknowledgement; retry is idempotent.
            acknowledge_result(state_path,school.id,result)
            log.info('crawl job=%s status=%s pages=%s docs=%s',job.id,job.status,job.pages_checked,job.documents)
        except JobCancelled as exc:
            db.rollback()
            lease = db.get(WorkerState,'crawler') if owner else None
            if owner and (not lease or lease.owner != owner):
                return True
            job=db.get(CrawlJob,job_id)
            job.status='cancelled';job.completed_at=now();job.error=str(exc)
            db.get(School,school_id).crawler_status='idle'
            db.commit()
        except Exception as exc:
            db.rollback()
            job=db.get(CrawlJob,job_id)
            job.status='failed';job.error=str(exc)[:2000];job.completed_at=now()
            db.get(School,school_id).crawler_status='failed'
            db.commit()
            log.exception('crawl job=%s failed',job_id)
        finally:
            if owner:
                try: refresh_lease(owner,set_job=True)
                except JobCancelled: pass
        return True


def enqueue_due():
    current=now()
    with SessionLocal() as db:
        active=set(db.scalars(select(CrawlJob.school_id).where(CrawlJob.status.in_(['queued','running']))))
        count=0
        for school in db.scalars(select(School).where(School.crawl_enabled==True,School.demo==False)):
            if school.id in active: continue
            recent=db.scalar(select(Source.id).where(Source.school_id==school.id,Source.fetched_at>=current-timedelta(days=7)).limit(1))
            failures=0
            for status in db.scalars(select(CrawlJob.status).where(CrawlJob.school_id==school.id,CrawlJob.status.in_(['completed','warning','failed'])).order_by(CrawlJob.id.desc()).limit(4)):
                if status!='failed': break
                failures+=1
            last=utc(school.last_crawled_at)
            due=next_crawl_at(recent_exam=bool(recent),consecutive_failures=failures,now=last) if last else current
            if due <= current:
                enqueue_school(db,school.id,'schedule');count+=1
        db.commit()
        return count


async def heartbeat(owner):
    while True:
        refresh_lease(owner)
        await asyncio.sleep(15)


async def loop(once=False):
    owner=uuid.uuid4().hex
    if not acquire_lease(owner):
        raise SystemExit('Another crawler owns the live lease; run only one worker replica')
    task=asyncio.create_task(heartbeat(owner))
    try:
        if once:
            await run_once(owner)
            return
        last_schedule=0.0
        while True:
            if task.done(): task.result()
            clock=asyncio.get_running_loop().time()
            if clock-last_schedule>=60:
                enqueue_due();last_schedule=clock
            if not await run_once(owner): await asyncio.sleep(5)
    finally:
        task.cancel()
        await asyncio.gather(task,return_exceptions=True)
        with SessionLocal() as db:
            state=db.get(WorkerState,'crawler')
            if state and state.owner==owner:
                state.lease_until=now();state.current_job_id=None;db.commit()

if __name__=='__main__':
    import sys
    logging.basicConfig(level=logging.INFO)
    asyncio.run(loop(once='once' in sys.argv))
