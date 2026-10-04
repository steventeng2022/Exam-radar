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
        assert db.scalar(select(CrawlJob)).status == 'warning'

def test_demo_cannot_be_reused(store):
    with store() as db:
        db.get(School,'real').demo = True
        db.commit()
        with pytest.raises(ValueError,match='Demo school IDs'):
            import_schools(db,[{'id':'real','website':'https://school.edu.tw','domains':['school.edu.tw']}])
