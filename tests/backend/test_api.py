import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database import Base, get_db
from backend.main import app
from backend.models import School, Source, ExamVersion
from backend.seed import seed_demo
from backend.services import ingest_exam

@pytest.fixture
def setup(monkeypatch):
    engine = create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine,expire_on_commit=False)
    with factory() as db:
        seed_demo(db)
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    monkeypatch.setenv('ADMIN_TOKEN','test-token')
    client = TestClient(app)
    yield client,factory
    app.dependency_overrides.clear()


def test_search_and_provenance(setup):
    client,_ = setup
    response = client.get('/api/exams',params={'q':'育成','grade':11})
    assert response.status_code == 200
    data = response.json()
    assert data['total'] == 1
    assert data['demo'] is True
    assert data['items'][0]['sources'][0]['content_hash']
    assert client.get('/api/compare').json()['total'] == 5


def test_admin_gate_and_demo_crawl(setup):
    client,_ = setup
    assert client.get('/api/admin/review').status_code == 401
    assert client.post('/api/admin/crawl/yucheng',headers={'Authorization':'Bearer test-token'}).status_code == 409


def test_version_dedup_review_and_no_private_leak(setup):
    client,factory = setup
    with factory() as db:
        school = db.get(School,'yucheng')
        source = Source(school_id=school.id,url=school.website,title='revision demo',content_hash='new-version',source_type='demo',demo=True)
        db.add(source)
        db.flush()
        data = {'academic_year':115,'semester':1,'number':1,'grade':11,'confidence':.65,'subjects':[{'name':'數學A','scope':'1-1～3-1'}]}
        version,created = ingest_exam(db,school,source,data)
        assert created
        duplicate,created = ingest_exam(db,school,source,data)
        assert not created and duplicate.id == version.id
        version_id = version.id
        exam_id = version.exam_id
        db.commit()
    public = client.get(f'/api/exams/{exam_id}').json()
    assert len(public['versions']) == 1
    headers = {'Authorization':'Bearer test-token'}
    assert client.post(f'/api/admin/review/{version_id}/approve',headers=headers).status_code == 200
    assert len(client.get(f'/api/exams/{exam_id}').json()['versions']) == 2
    assert client.post(f'/api/admin/review/{version_id}/reject',headers=headers).status_code == 409


def test_reject_invalid_origin_and_dates(setup):
    _,factory = setup
    with factory() as db:
        school = db.get(School,'yucheng')
        source = Source(school_id=school.id,url='https://evil.example/x',title='x',content_hash='x',source_type='html')
        db.add(source)
        db.flush()
        data = {'academic_year':115,'semester':1,'number':1,'grade':11,'confidence':.9,'subjects':[{'name':'數學','scope':'1'}]}
        with pytest.raises(ValueError,match='official domains'):
            ingest_exam(db,school,source,data)
        source.url = school.website
        data['start_date'] = '2020-10-13'
        with pytest.raises(ValueError,match='academic year'):
            ingest_exam(db,school,source,data)
