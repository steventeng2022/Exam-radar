"""Persistent single-worker runner. Use one worker replica for SQLite."""
import asyncio
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from .database import Base, engine, SessionLocal
from .models import School, CrawlJob, Source, CrawlError, now
from .services import ingest_exam
from crawler.pipeline import School as CrawlSchool, run_school, acknowledge_result

async def run_once():
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        # Lock queued job atomically in PostgreSQL; SQLite deployment uses one worker.
        job = db.scalar(select(CrawlJob).where(CrawlJob.status == "queued").order_by(CrawlJob.id).with_for_update(skip_locked=True).limit(1))
        if not job:
            return False
        school = db.get(School, job.school_id)
        if school.demo or not school.crawl_enabled:
            job.status = "cancelled"
            job.completed_at = now()
            db.commit()
            return True
        job.status = "running"
        job.started_at = now()
        school.last_crawled_at = now()
        school.crawler_status = "running"
        db.commit()
        job_id = job.id
        crawl_school = CrawlSchool(id=school.id, name=school.name, website=school.website, domains=school.domains)
        path = Path(os.getenv("CRAWLER_STATE_DIR", "./data/frontier"))
        path.mkdir(parents=True, exist_ok=True)
        state_path = str(path / "frontier.sqlite3")
        try:
            result = await run_school(crawl_school, state_path=state_path, commit_state=False)
            sources = {}
            for doc in result.documents:
                source = db.scalar(select(Source).where(Source.school_id == school.id, Source.url == doc["url"], Source.content_hash == doc["content_hash"]))
                if not source:
                    source = Source(school_id=school.id,url=doc["url"],title=doc["title"],content_hash=doc["content_hash"],source_type=doc["source_type"],page_number=doc.get("page_number"))
                    db.add(source)
                    db.flush()
                sources[doc["url"]] = source
            added = 0
            for extraction in result.extractions:
                source = sources.get(extraction["source_url"])
                if not source:
                    raise ValueError("Extraction has no matching source")
                _, created = ingest_exam(db,school,source,extraction)
                added += int(created)
            for error in result.errors:
                db.add(CrawlError(job_id=job.id,url=error["url"],message=error["message"]))
            job.pages_checked = result.pages_checked
            job.documents = len(result.documents)
            job.new_exams = added
            job.status = "completed" if not result.errors else "warning"
            job.completed_at = now()
            school.crawler_status = job.status
            if not result.errors or result.pages_checked > len(result.errors):
                school.last_success_at = now()
            db.commit()
            acknowledge_result(state_path,school.id,result)
        except Exception as exc:
            db.rollback()
            job = db.get(CrawlJob, job_id)
            school = db.get(School, job.school_id)
            job.status = "failed"
            job.error = str(exc)[:2000]
            job.completed_at = now()
            school.crawler_status = "failed"
            db.commit()
        return True

def enqueue_due():
    current = datetime.now(timezone.utc)
    with SessionLocal() as db:
        active = set(db.scalars(select(CrawlJob.school_id).where(CrawlJob.status.in_(["queued", "running"]))))
        count = 0
        for school in db.scalars(select(School).where(School.crawl_enabled == True, School.demo == False)):
            if school.id in active:
                continue
            recent = db.scalar(select(Source.id).where(Source.school_id == school.id, Source.fetched_at >= current - timedelta(days=7)).limit(1))
            interval = timedelta(hours=6 if recent else 24)
            if school.crawler_status == "failed":
                interval = timedelta(hours=48)
            last = school.last_crawled_at
            if last and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            if not last or current - last >= interval:
                db.add(CrawlJob(school_id=school.id))
                count += 1
        db.commit()
        return count

async def loop():
    # A stopped process leaves running jobs safely requeued for resumption.
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        for job in db.scalars(select(CrawlJob).where(CrawlJob.status == "running")):
            job.status = "queued"
        db.commit()
    last_schedule = 0.0
    while True:
        clock = asyncio.get_running_loop().time()
        if clock - last_schedule >= 60:
            enqueue_due()
            last_schedule = clock
        if not await run_once():
            await asyncio.sleep(5)

if __name__ == "__main__":
    import sys
    asyncio.run(run_once() if "once" in sys.argv else loop())
