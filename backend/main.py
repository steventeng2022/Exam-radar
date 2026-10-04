import os
import secrets
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import Base, engine, get_db, SessionLocal
from .models import School, Exam, ExamVersion, CrawlJob

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    if os.getenv("DEMO_MODE", "false").lower() == "true":
        from .seed import seed_demo
        with SessionLocal() as db:
            seed_demo(db)
    yield

app = FastAPI(title="Exam Radar", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","), allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])
bearer = HTTPBearer(auto_error=False)

def admin(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
    token = os.getenv("ADMIN_TOKEN")
    if not token:
        raise HTTPException(503, "Admin API disabled: configure ADMIN_TOKEN")
    if not credentials or not secrets.compare_digest(credentials.credentials, token):
        raise HTTPException(401, "Invalid admin token", headers={"WWW-Authenticate": "Bearer"})

def school_dict(s):
    return {key: getattr(s, key) for key in ("id", "name", "short_name", "type", "city", "district", "website", "domains", "crawl_enabled", "crawler_status", "last_crawled_at", "last_success_at", "demo")}

def version_dict(v):
    return {"id":v.id,"version":v.version,"status":v.status,"start_date":v.start_date,"end_date":v.end_date,"confidence":v.confidence,"created_at":v.created_at,"subjects":[{"name":s.name,"scope":s.scope,"evidence":s.evidence,"page_number":s.page_number} for s in v.subjects],"source":{"id":v.source.id,"url":v.source.url,"file_url":v.source.file_url,"title":v.source.title,"source_type":v.source.source_type,"page_number":v.source.page_number,"demo":v.source.demo,"fetched_at":v.source.fetched_at,"content_hash":v.source.content_hash}}

def exam_dict(db, e, include_private=False):
    versions = [v for v in e.versions if include_private or v.status in ("approved", "warning")]
    if not versions:
        return None
    v = versions[-1]
    s = db.get(School, e.school_id)
    details = version_dict(v)
    return {"id":e.id,"school_id":s.id,"school_name":s.name,"school_short_name":s.short_name,"city":s.city,"academic_year":e.academic_year,"semester":e.semester,"number":e.number,"grade":e.grade,"type":e.type,"start_date":v.start_date,"end_date":v.end_date,"confidence":v.confidence,"status":v.status,"updated_at":v.created_at,"subjects":details["subjects"],"sources":[details["source"]],"versions":[version_dict(ver) for ver in versions],"demo":s.demo or v.source.demo}

@app.get("/api/health")
def health():
    return {"status":"ok","service":"exam-radar"}

@app.get("/api/schools")
def schools(q: str = "", city: str | None = None, db: Session = Depends(get_db)):
    items = [school_dict(s) for s in db.scalars(select(School).order_by(School.name)) if (not q or q.casefold() in (s.name + s.short_name).casefold()) and (not city or city == s.city)]
    return {"items":items,"total":len(items)}

@app.get("/api/schools/{school_id}")
def school(school_id: str, db: Session = Depends(get_db)):
    s = db.get(School, school_id)
    if not s:
        raise HTTPException(404, "School not found")
    return school_dict(s)

def find_exams(db, q="", city=None, school_id=None, grade=None, academic_year=None, semester=None, number=None, subject=None):
    items = []
    query = select(Exam).order_by(Exam.academic_year.desc(), Exam.id.desc())
    for field, value in (("school_id",school_id),("grade",grade),("academic_year",academic_year),("semester",semester),("number",number)):
        if value is not None:
            query = query.where(getattr(Exam, field) == value)
    for e in db.scalars(query):
        d = exam_dict(db, e)
        if not d or city and d["city"] != city:
            continue
        if subject and not any(subject == s["name"] for s in d["subjects"]):
            continue
        searchable = d["school_name"] + d["school_short_name"] + ''.join(s["name"] + s["scope"] for s in d["subjects"])
        if q and q.casefold() not in searchable.casefold():
            continue
        items.append(d)
    return items

@app.get("/api/exams")
def exams(q: str = "", city: str | None = None, school_id: str | None = None, grade: int | None = None, academic_year: int | None = None, semester: int | None = None, number: int | None = None, subject: str | None = None, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    items = find_exams(db,q,city,school_id,grade,academic_year,semester,number,subject)
    return {"items":items[offset:offset+limit],"total":len(items),"demo":any(i["demo"] for i in items)}

@app.get("/api/exams/{exam_id}")
def exam(exam_id: int, db: Session = Depends(get_db)):
    e = db.get(Exam,exam_id)
    d = exam_dict(db,e) if e else None
    if not d:
        raise HTTPException(404,"Exam not found")
    return d

@app.get("/api/schools/{school_id}/exams")
def school_exams(school_id: str, db: Session = Depends(get_db)):
    items = find_exams(db,school_id=school_id)
    return {"items":items,"total":len(items)}

@app.get("/api/subjects")
def subjects(db: Session = Depends(get_db)):
    return {"items": sorted({s["name"] for e in find_exams(db) for s in e["subjects"]})}

@app.get("/api/compare")
def compare(subject: str = "數學A", grade: int | None = 11, academic_year: int | None = 115, semester: int | None = 1, number: int | None = 1, db: Session = Depends(get_db)):
    items = find_exams(db,grade=grade,academic_year=academic_year,semester=semester,number=number,subject=subject)
    return {"items":items,"total":len(items),"subject":subject,"demo":any(i["demo"] for i in items)}

@app.post("/api/admin/crawl/{school_id}", dependencies=[Depends(admin)], status_code=202)
def enqueue(school_id: str, db: Session = Depends(get_db)):
    s = db.get(School,school_id)
    if not s:
        raise HTTPException(404,"School not found")
    if not s.crawl_enabled or s.demo:
        raise HTTPException(409,"School crawling disabled; demo data is never crawled")
    existing = db.scalar(select(CrawlJob).where(CrawlJob.school_id==school_id,CrawlJob.status.in_(["queued","running"])))
    if existing:
        return {"id":existing.id,"status":existing.status}
    job = CrawlJob(school_id=school_id)
    db.add(job)
    db.commit()
    return {"id":job.id,"status":job.status}

@app.get("/api/admin/crawls", dependencies=[Depends(admin)])
def crawls(db: Session = Depends(get_db)):
    jobs = list(db.scalars(select(CrawlJob).order_by(CrawlJob.id.desc()).limit(200)))
    return {"items":[{k:getattr(j,k) for k in ("id","school_id","status","created_at","started_at","completed_at","pages_checked","documents","new_exams","error")} for j in jobs],"total":len(jobs)}

@app.get("/api/admin/review", dependencies=[Depends(admin)])
def review(db: Session = Depends(get_db)):
    items = [{"id":v.id,"exam":exam_dict(db,v.exam,True),"version":version_dict(v)} for v in db.scalars(select(ExamVersion).where(ExamVersion.status=="review"))]
    return {"items":items,"total":len(items)}

@app.post("/api/admin/review/{version_id}/{action}", dependencies=[Depends(admin)])
def review_action(version_id: int, action: str, db: Session = Depends(get_db)):
    if action not in ("approve","reject"):
        raise HTTPException(404,"Unknown action")
    version = db.get(ExamVersion,version_id)
    if not version:
        raise HTTPException(404,"Version not found")
    if version.status != "review":
        raise HTTPException(409,"Only pending review versions can be decided")
    version.status = "approved" if action == "approve" else "rejected"
    db.commit()
    return {"id":version.id,"status":version.status}
