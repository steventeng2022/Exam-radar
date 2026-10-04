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


def test_database_pagination_filters_and_literal_search(setup):
    client,_=setup
    first=client.get('/api/exams?limit=4&offset=0').json()
    second=client.get('/api/exams?limit=4&offset=4').json()
    assert first['total']==second['total']==15
    assert {e['id'] for e in first['items']}.isdisjoint({e['id'] for e in second['items']})
    meta=client.get('/api/filters').json()
    assert meta['statistics']=={'schools':5,'exams':15}
    assert meta['academic_years']==[115] and '數學A' in meta['subjects']
    assert client.get('/api/exams',params={'q':'%'}).json()['total']==0
    assert client.get('/api/exams?grade=1').status_code==422


def test_edit_review_preserves_source_audit_and_prevents_stale_approval(setup):
    client,factory=setup
    with factory() as db:
        school=db.get(School,'yucheng')
        source=Source(school_id=school.id,url=school.website,title='pending',content_hash='correction-test',source_type='demo',demo=True)
        db.add(source);db.flush()
        v,_=ingest_exam(db,school,source,{'academic_year':115,'semester':1,'number':1,'grade':11,'confidence':.65,'subjects':[{'name':'數學A','scope':'old scope','evidence':'原始擷取文字','page_number':2}]})
        db.commit();version_id=v.id;exam_id=v.exam_id
    headers={'Authorization':'Bearer test-token'}
    record=next(r for r in client.get('/api/admin/review',headers=headers).json()['items'] if r['id']==version_id)
    old_revision=record['version']['revision']
    payload={'expected_revision':old_revision,'start_date':'2026-10-13','end_date':'2026-10-15','subjects':[{'name':'數學A','scope':'1-1～2-3','page_number':2}],'reason':'依原公告第2頁修正'}
    edited=client.post(f'/api/admin/review/{version_id}/edit',headers=headers,json=payload)
    assert edited.status_code==200,edited.text
    assert edited.json()['source']['content_hash']=='correction-test'
    assert edited.json()['subjects'][0]['evidence']=='原始擷取文字'
    assert client.post(f'/api/admin/review/{version_id}/approve',headers=headers,json={'expected_revision':old_revision}).status_code==409
    assert client.post(f'/api/admin/review/{version_id}/approve',headers=headers,json={'expected_revision':edited.json()['revision']}).status_code==200
    public=client.get(f'/api/exams/{exam_id}').json()
    assert len(public['versions'])==2 and public['subjects'][0]['scope']=='1-1～2-3'
    audit_rows=client.get('/api/admin/audit',headers=headers).json()['items']
    edit=next(row for row in audit_rows if row['action']=='edit')
    assert edit['before']['subjects'][0]['scope']=='old scope'
    assert edit['after']['reason']==payload['reason']
    assert client.get('/api/admin/audit').status_code==401


def test_import_pause_cancel_and_retry_lifecycle(setup):
    client,_=setup
    headers={'Authorization':'Bearer test-token'}
    school={'id':'real-test','name':'測試高中','short_name':'測試','city':'臺北市','website':'https://school.edu.tw','domains':['school.edu.tw'],'crawl_enabled':True}
    assert client.post('/api/admin/schools/import',headers=headers,json={'schools':[school]}).status_code==200
    one=client.post('/api/admin/crawl/real-test',headers=headers).json()
    two=client.post('/api/admin/crawl/real-test',headers=headers).json()
    assert one['id']==two['id']
    assert client.post(f"/api/admin/crawls/{one['id']}/cancel",headers=headers).status_code==200
    retry=client.post(f"/api/admin/crawls/{one['id']}/retry",headers=headers)
    assert retry.status_code==200 and retry.json()['id']!=one['id']
    assert client.post('/api/admin/schools/real-test/settings',headers=headers,json={'crawl_enabled':False}).status_code==200
    assert client.post('/api/admin/crawl/real-test',headers=headers).status_code==409
    assert client.post('/api/admin/schools/yucheng/settings',headers=headers,json={'crawl_enabled':True}).status_code==409
    jobs=client.get('/api/admin/crawls',headers=headers).json()['items']
    assert all(j['status']=='cancelled' for j in jobs)
    assert client.get('/api/admin/summary',headers=headers).json()['worker']['online'] is False


def test_validation_rejects_duplicate_subjects_and_out_of_year_end_dates(setup):
    _,factory=setup
    with factory() as db:
        school=db.get(School,'yucheng')
        source=Source(school_id=school.id,url=school.website,title='bad',content_hash='bad-dates',source_type='demo',demo=True)
        db.add(source);db.flush()
        data={'academic_year':115,'semester':1,'number':1,'grade':11,'confidence':.9,'start_date':'2026-10-13','end_date':'2028-10-15','subjects':[{'name':'數學A','scope':'1'}]}
        with pytest.raises(ValueError,match='academic year'): ingest_exam(db,school,source,data)
        data['end_date']=None;data['subjects'].append({'name':'數學A','scope':'2'})
        with pytest.raises(ValueError,match='Duplicate subject'): ingest_exam(db,school,source,data)


def test_only_latest_published_subjects_match_search(setup):
    client,factory=setup
    with factory() as db:
        school=db.get(School,'yucheng')
        source=Source(school_id=school.id,url=school.website,title='new',content_hash='latest-query',source_type='demo',demo=True)
        db.add(source);db.flush()
        ingest_exam(db,school,source,{'academic_year':115,'semester':1,'number':1,'grade':11,'confidence':.99,'subjects':[{'name':'數學A','scope':'最新章節'}]});db.commit()
    assert client.get('/api/exams',params={'q':'育成','grade':11,'subject':'國文'}).json()['total']==0
    assert client.get('/api/exams',params={'q':'最新章節','grade':11}).json()['total']==1
