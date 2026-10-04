import asyncio
from types import SimpleNamespace
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database import Base
from backend.models import School, CrawlJob
from backend import worker
from backend.registry import import_schools

@pytest.fixture
def store(monkeypatch,tmp_path):
    engine = create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine,expire_on_commit=False)
    monkeypatch.setattr(worker,'engine',engine)
    monkeypatch.setattr(worker,'SessionLocal',factory)
    monkeypatch.setenv('CRAWLER_STATE_DIR',str(tmp_path))
    with factory() as db:
        db.add(School(id='real',name='校',short_name='校',city='臺北市',website='https://school.edu.tw',domains=['school.edu.tw'],crawl_enabled=True))
        db.commit()
    return factory

def test_schedule_no_duplicates(store):
    assert worker.enqueue_due() == 1
    assert worker.enqueue_due() == 0

def test_opt_out_rechecked(store,monkeypatch):
    worker.enqueue_due()
    with store() as db:
        db.get(School,'real').crawl_enabled = False
        db.commit()
    async def forbidden(*args,**kwargs):
        pytest.fail('opted out school fetched')
    monkeypatch.setattr(worker,'run_school',forbidden)
    assert asyncio.run(worker.run_once())
    with store() as db:
        assert db.scalar(select(CrawlJob)).status == 'cancelled'

def test_blocked_crawl_no_success(store,monkeypatch):
    worker.enqueue_due()
    async def blocked(*args,**kwargs):
        assert kwargs['commit_state'] is False
        return SimpleNamespace(documents=[],extractions=[],pages_checked=1,errors=[{'url':'https://school.edu.tw','message':'robots disallows'}])
    monkeypatch.setattr(worker,'run_school',blocked)
    monkeypatch.setattr(worker,'acknowledge_result',lambda *args: None)
    asyncio.run(worker.run_once())
    with store() as db:
        assert db.get(School,'real').last_success_at is None
        assert db.scalar(select(CrawlJob)).status == 'failed'

def test_demo_cannot_be_reused(store):
    with store() as db:
        db.get(School,'real').demo = True
        db.commit()
        with pytest.raises(ValueError,match='Demo school IDs'):
            import_schools(db,[{'id':'real','website':'https://school.edu.tw','domains':['school.edu.tw']}])


def test_live_worker_lease_blocks_second_process_and_stale_jobs_recover(store):
    from datetime import timedelta
    from backend.models import WorkerState, now
    worker.enqueue_due()
    assert worker.acquire_lease('one')
    assert not worker.acquire_lease('two')
    with store() as db:
        db.scalar(select(CrawlJob)).status='running'
        db.get(WorkerState,'crawler').lease_until=now()-timedelta(seconds=1)
        db.commit()
    assert worker.acquire_lease('two')
    with store() as db:
        assert db.scalar(select(CrawlJob)).status=='queued'
        assert db.get(WorkerState,'crawler').owner=='two'


def test_worker_keeps_parsed_document_with_pending_review(store,monkeypatch):
    from backend.models import CrawlDocument, ExamVersion
    from crawler.pipeline import CrawlResult
    worker.enqueue_due()
    async def parsed(*args,**kwargs):
        await kwargs['on_progress'](0)
        return CrawlResult(documents=[{'url':'https://school.edu.tw/exam.pdf','title':'段考','content_hash':'parsed','source_type':'document','text':'原始段考文字','pages':[{'page':2,'text':'原始段考文字'}]}],extractions=[{'source_url':'https://school.edu.tw/exam.pdf','academic_year':115,'semester':1,'number':1,'grade':11,'confidence':.65,'subjects':[{'name':'數學A','scope':'1-1～2-2','page_number':2}]}],pages_checked=1)
    monkeypatch.setattr(worker,'run_school',parsed)
    monkeypatch.setattr(worker,'acknowledge_result',lambda *args:None)
    asyncio.run(worker.run_once())
    with store() as db:
        doc=db.scalar(select(CrawlDocument))
        assert doc.text=='原始段考文字' and doc.pages[0]['page']==2
        assert doc.extraction_status=='review'
        assert db.scalar(select(ExamVersion)).status=='review'
        assert db.scalar(select(CrawlJob)).status=='completed'


def test_cancelled_running_job_stops_before_next_fetch(store,monkeypatch):
    worker.enqueue_due()
    async def interrupted(*args,**kwargs):
        with store() as db:
            db.scalar(select(CrawlJob)).status='cancelled';db.commit()
        await kwargs['on_progress'](1)
        pytest.fail('Cancellation must abort the crawl')
    monkeypatch.setattr(worker,'run_school',interrupted)
    monkeypatch.setattr(worker,'acknowledge_result',lambda *args:pytest.fail('Cancelled crawl must not acknowledge'))
    asyncio.run(worker.run_once())
    with store() as db:
        assert db.scalar(select(CrawlJob)).status=='cancelled'
        assert db.get(School,'real').last_success_at is None


def test_database_url_accepts_provider_postgres_scheme(monkeypatch):
    from backend import database
    captured=[]
    monkeypatch.setattr(database,'create_engine',lambda url,**kwargs:captured.append(url))
    database.make_engine('postgresql://user:encoded%40password@localhost/db')
    database.make_engine('postgres://user:encoded%40password@localhost/db')
    assert captured==['postgresql+psycopg://user:encoded%40password@localhost/db']*2
