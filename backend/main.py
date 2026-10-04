import os
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, text
from sqlalchemy.orm import Session
from .database import Base, engine, get_db, SessionLocal
from .models import School, Exam, ExamVersion, ExamSubject, CrawlJob, CrawlDocument, Source, AuditLog, now
from .query import published_query, page_rows, academic_year_now
from .services import revision, snapshot, validate_exam, audit
from .schemas import ReviewEdit, DecisionInput, SchoolBatch, SchoolSettings
from .workflows import enqueue_school, job_dict, summary

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    if os.getenv('DEMO_MODE', 'false').lower() == 'true':
        from .seed import seed_demo
        with SessionLocal() as db:
            seed_demo(db)
    yield

app = FastAPI(title='Exam Radar', version='1.1.0', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[s.strip() for s in os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(',') if s.strip()], allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type'])
bearer = HTTPBearer(auto_error=False)

def admin(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    token = os.getenv('ADMIN_TOKEN')
    if not token:
        raise HTTPException(503, 'Admin API disabled: configure ADMIN_TOKEN')
    if not credentials or not secrets.compare_digest(credentials.credentials, token):
        raise HTTPException(401, 'Invalid admin token', headers={'WWW-Authenticate': 'Bearer'})

def school_dict(s):
    return {key: getattr(s, key) for key in ('id','name','short_name','type','city','district','website','domains','crawl_enabled','crawler_status','last_crawled_at','last_success_at','demo')}

def source_dict(s):
    return {key: getattr(s,key) for key in ('id','url','file_url','title','source_type','page_number','demo','fetched_at','content_hash')}

def version_dict(v):
    return {'id':v.id,'version':v.version,'status':v.status,'start_date':v.start_date,'end_date':v.end_date,'confidence':v.confidence,'created_at':v.created_at,'revision':revision(v),'subjects':[{'name':s.name,'scope':s.scope,'evidence':s.evidence,'page_number':s.page_number} for s in v.subjects],'source':source_dict(v.source)}

def serialized_exam(e,v,s,versions=None):
    details = version_dict(v)
    return {'id':e.id,'school_id':s.id,'school_name':s.name,'school_short_name':s.short_name,'city':s.city,'academic_year':e.academic_year,'semester':e.semester,'number':e.number,'grade':e.grade,'type':e.type,'start_date':v.start_date,'end_date':v.end_date,'confidence':v.confidence,'status':v.status,'updated_at':v.created_at,'subjects':details['subjects'],'sources':[details['source']],'versions':versions if versions is not None else [details],'demo':s.demo or v.source.demo}

def exam_dict(db,e,include_private=False):
    versions = [v for v in e.versions if include_private or v.status in ('approved','warning')]
    return serialized_exam(e,versions[-1],db.get(School,e.school_id),[version_dict(v) for v in versions]) if versions else None

def exam_page(db,limit=24,offset=0,**filters):
    rows,total=page_rows(db,published_query(**filters),limit,offset)
    items=[serialized_exam(e,v,s) for e,v,s in rows]
    return {'items':items,'total':total,'offset':offset,'limit':limit,'demo':any(i['demo'] for i in items)}

@app.get('/api/health')
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text('SELECT 1'))
    except Exception:
        raise HTTPException(503,'Database unavailable')
    return {'status':'ok','service':'exam-radar','version':'1.1.0'}

@app.get('/api/schools')
def schools(q: str='',city: str|None=None,db: Session=Depends(get_db)):
    statement=select(School).order_by(School.name)
    if q: statement=statement.where((School.name.contains(q,autoescape=True)) | (School.short_name.contains(q,autoescape=True)))
    if city: statement=statement.where(School.city==city)
    items=[school_dict(s) for s in db.scalars(statement)]
    return {'items':items,'total':len(items)}

@app.get('/api/schools/{school_id}')
def school(school_id: str,db: Session=Depends(get_db)):
    s=db.get(School,school_id)
    if not s: raise HTTPException(404,'School not found')
    return school_dict(s)

@app.get('/api/exams')
def exams(q: str=Query('',max_length=200),city: str|None=None,school_id: str|None=None,grade: int|None=Query(None,ge=7,le=12),academic_year: int|None=Query(None,ge=100),semester: int|None=Query(None,ge=1,le=2),number: int|None=Query(None,ge=1,le=3),subject: str|None=None,limit: int=Query(24,ge=1,le=200),offset: int=Query(0,ge=0),db: Session=Depends(get_db)):
    return exam_page(db,limit,offset,q=q,city=city,school_id=school_id,grade=grade,academic_year=academic_year,semester=semester,number=number,subject=subject)

@app.get('/api/exams/{exam_id}')
def exam(exam_id: int,db: Session=Depends(get_db)):
    e=db.get(Exam,exam_id)
    d=exam_dict(db,e) if e else None
    if not d: raise HTTPException(404,'Exam not found')
    return d

@app.get('/api/schools/{school_id}/exams')
def school_exams(school_id: str,limit: int=Query(24,ge=1,le=200),offset: int=Query(0,ge=0),db: Session=Depends(get_db)):
    if not db.get(School,school_id): raise HTTPException(404,'School not found')
    return exam_page(db,limit,offset,school_id=school_id)

@app.get('/api/filters')
def filters(db: Session=Depends(get_db)):
    query=published_query()
    cities=list(db.scalars(query.with_only_columns(School.city,maintain_column_froms=True).distinct()))
    grades=list(db.scalars(query.with_only_columns(Exam.grade,maintain_column_froms=True).distinct()))
    years=list(db.scalars(query.with_only_columns(Exam.academic_year,maintain_column_froms=True).distinct()))
    subjects=list(db.scalars(query.join(ExamSubject,ExamSubject.version_id==ExamVersion.id).with_only_columns(ExamSubject.name,maintain_column_froms=True).distinct()))
    count=db.scalar(select(func.count()).select_from(query.subquery())) or 0
    school_count=db.scalar(query.with_only_columns(func.count(func.distinct(Exam.school_id)),maintain_column_froms=True)) or 0
    return {'cities':sorted(cities),'grades':sorted(grades),'academic_years':sorted(years,reverse=True),'subjects':sorted(subjects),'statistics':{'schools':school_count,'exams':count},'current_academic_year':academic_year_now()}

@app.get('/api/subjects')
def subjects(db: Session=Depends(get_db)):
    return {'items':filters(db)['subjects']}

@app.get('/api/compare')
def compare(subject: str='數學A',grade: int=Query(11,ge=7,le=12),academic_year: int|None=None,semester: int=Query(1,ge=1,le=2),number: int=Query(1,ge=1,le=3),city: str|None=None,q: str='',limit: int=Query(24,ge=1,le=200),offset: int=Query(0,ge=0),db: Session=Depends(get_db)):
    data=exam_page(db,limit,offset,q=q,city=city,subject=subject,grade=grade,academic_year=academic_year if academic_year is not None else academic_year_now(),semester=semester,number=number)
    return {**data,'subject':subject}

@app.post('/api/admin/crawl/{school_id}',dependencies=[Depends(admin)],status_code=202)
def enqueue(school_id: str,db: Session=Depends(get_db)):
    try: job=enqueue_school(db,school_id)
    except LookupError as exc: raise HTTPException(404,str(exc))
    except ValueError as exc: raise HTTPException(409,str(exc))
    db.commit()
    return {'id':job.id,'status':job.status}

@app.get('/api/admin/summary',dependencies=[Depends(admin)])
def admin_summary(db: Session=Depends(get_db)):
    return summary(db)

@app.get('/api/admin/crawls',dependencies=[Depends(admin)])
def crawls(status: str|None=None,limit: int=Query(20,ge=1,le=200),offset: int=Query(0,ge=0),db: Session=Depends(get_db)):
    statement=select(CrawlJob)
    if status: statement=statement.where(CrawlJob.status==status)
    total=db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    jobs=db.scalars(statement.order_by(CrawlJob.id.desc()).limit(limit).offset(offset))
    return {'items':[job_dict(db,j) for j in jobs],'total':total}

@app.post('/api/admin/crawls/{job_id}/{action}',dependencies=[Depends(admin)])
def change_job(job_id: int,action: str,db: Session=Depends(get_db)):
    job=db.scalar(select(CrawlJob).where(CrawlJob.id==job_id).with_for_update())
    if not job: raise HTTPException(404,'Job not found')
    if action=='cancel':
        if job.status not in ('queued','running'): raise HTTPException(409,'Job is already finished')
        before={'status':job.status}
        job.status='cancelled';job.completed_at=now();job.error='Cancelled by administrator'
        audit(db,'crawl',job.id,'cancel',before,{'status':'cancelled'})
        db.commit()
        return {'id':job.id,'status':job.status}
    if action=='retry':
        if job.status not in ('failed','warning','cancelled'): raise HTTPException(409,'Only unsuccessful jobs can be retried')
        try: new_job=enqueue_school(db,job.school_id,'retry')
        except ValueError as exc: raise HTTPException(409,str(exc))
        db.commit()
        return {'id':new_job.id,'status':new_job.status}
    raise HTTPException(404,'Unknown action')

@app.post('/api/admin/schools/import',dependencies=[Depends(admin)])
def import_registry(body: SchoolBatch,db: Session=Depends(get_db)):
    from .registry import import_schools
    try: count=import_schools(db,[s.model_dump() for s in body.schools],commit=False)
    except ValueError as exc: raise HTTPException(422,str(exc))
    db.commit()
    return {'imported':count}

@app.post('/api/admin/schools/{school_id}/settings',dependencies=[Depends(admin)])
def school_settings(school_id: str,body: SchoolSettings,db: Session=Depends(get_db)):
    s=db.scalar(select(School).where(School.id==school_id).with_for_update())
    if not s: raise HTTPException(404,'School not found')
    if s.demo and body.crawl_enabled: raise HTTPException(409,'Demo school crawling disabled')
    before={'crawl_enabled':s.crawl_enabled};s.crawl_enabled=body.crawl_enabled
    if not body.crawl_enabled:
        for job in db.scalars(select(CrawlJob).where(CrawlJob.school_id==s.id,CrawlJob.status.in_(['queued','running']))):
            job.status='cancelled';job.completed_at=now();job.error='School crawling disabled'
    audit(db,'school',s.id,'settings',before,body.model_dump())
    db.commit()
    return school_dict(s)

@app.get('/api/admin/review',dependencies=[Depends(admin)])
def review(limit: int=Query(20,ge=1,le=200),offset: int=Query(0,ge=0),db: Session=Depends(get_db)):
    statement=select(ExamVersion).where(ExamVersion.status=='review')
    total=db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    items=[{'id':v.id,'exam':exam_dict(db,v.exam,True),'version':version_dict(v)} for v in db.scalars(statement.order_by(ExamVersion.created_at,ExamVersion.id).limit(limit).offset(offset))]
    return {'items':items,'total':total}

@app.post('/api/admin/review/{version_id}/edit',dependencies=[Depends(admin)])
def edit_review(version_id: int,body: ReviewEdit,db: Session=Depends(get_db)):
    v=db.scalar(select(ExamVersion).where(ExamVersion.id==version_id).with_for_update())
    if not v: raise HTTPException(404,'Version not found')
    if v.status!='review' or revision(v)!=body.expected_revision: raise HTTPException(409,'Review changed; reload before editing')
    e=v.exam
    data={'academic_year':e.academic_year,'semester':e.semester,'number':e.number,'grade':e.grade,'start_date':body.start_date.isoformat() if body.start_date else None,'end_date':body.end_date.isoformat() if body.end_date else None,'subjects':[s.model_dump() for s in body.subjects]}
    try: validate_exam(data)
    except ValueError as exc: raise HTTPException(422,str(exc))
    before=snapshot(v);old={s.name:s for s in v.subjects}
    replacements=[ExamSubject(name=s.name,scope=s.scope,page_number=s.page_number,evidence=old[s.name].evidence if s.name in old else None) for s in body.subjects]
    v.start_date=data['start_date'];v.end_date=data['end_date'];v.subjects=replacements
    db.flush()
    audit(db,'review',v.id,'edit',before,{**snapshot(v),'reason':body.reason})
    db.commit()
    return version_dict(v)

@app.post('/api/admin/review/{version_id}/{action}',dependencies=[Depends(admin)])
def review_action(version_id: int,action: str,body: DecisionInput|None=None,db: Session=Depends(get_db)):
    if action not in ('approve','reject'): raise HTTPException(404,'Unknown action')
    v=db.scalar(select(ExamVersion).where(ExamVersion.id==version_id).with_for_update())
    if not v: raise HTTPException(404,'Version not found')
    if v.status!='review' or body and body.expected_revision and revision(v)!=body.expected_revision: raise HTTPException(409,'Review changed; reload before deciding')
    before=snapshot(v);v.status='approved' if action=='approve' else 'rejected'
    document=db.scalar(select(CrawlDocument).where(CrawlDocument.source_id==v.source_id))
    if document:
        pending=db.scalar(select(func.count()).select_from(ExamVersion).where(ExamVersion.source_id==v.source_id,ExamVersion.status=='review'))
        published=db.scalar(select(func.count()).select_from(ExamVersion).where(ExamVersion.source_id==v.source_id,ExamVersion.status.in_(['approved','warning'])))
        document.extraction_status='review' if pending else 'published' if published else 'rejected'
    audit(db,'review',v.id,action,before,{**snapshot(v),'reason':body.reason if body else ''})
    db.commit()
    return {'id':v.id,'status':v.status}

@app.get('/api/admin/audit',dependencies=[Depends(admin)])
def audit_logs(limit: int=Query(20,ge=1,le=100),offset: int=Query(0,ge=0),db: Session=Depends(get_db)):
    rows=db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit).offset(offset))
    return {'items':[{k:getattr(row,k) for k in ('id','entity','entity_id','action','before','after','created_at')} for row in rows],'total':db.scalar(select(func.count()).select_from(AuditLog))}

@app.get('/api/admin/documents',dependencies=[Depends(admin)])
def documents(status: str|None=None,limit: int=Query(20,ge=1,le=100),offset: int=Query(0,ge=0),db: Session=Depends(get_db)):
    statement=select(CrawlDocument,Source,School).join(Source,Source.id==CrawlDocument.source_id).join(School,School.id==CrawlDocument.school_id)
    if status: statement=statement.where(CrawlDocument.extraction_status==status)
    total=db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows=db.execute(statement.order_by(Source.fetched_at.desc()).limit(limit).offset(offset))
    return {'items':[{'id':d.id,'source_id':s.id,'school_name':school.name,'status':d.extraction_status,'source':source_dict(s),'excerpt':d.text[:300],'truncated':d.truncated} for d,s,school in rows],'total':total}

@app.get('/api/admin/sources/{source_id}/document',dependencies=[Depends(admin)])
def source_document(source_id: int,db: Session=Depends(get_db)):
    doc=db.scalar(select(CrawlDocument).where(CrawlDocument.source_id==source_id))
    if not doc: raise HTTPException(404,'Parsed document not available; open the original announcement')
    return {'source':source_dict(db.get(Source,source_id)),'text':doc.text,'pages':doc.pages,'status':doc.extraction_status,'truncated':doc.truncated}
