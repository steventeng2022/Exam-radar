"""Filter and paginate the latest published version in SQL, not in browser memory."""
from datetime import date
from sqlalchemy import select, func, or_, exists
from sqlalchemy.orm import selectinload, joinedload
from .models import Exam, ExamVersion, ExamSubject, School

PUBLISHED = ("approved", "warning")

def academic_year_now():
    today = date.today()
    return today.year - (1911 if today.month >= 8 else 1912)

def published_query(q="", city=None, school_id=None, grade=None, academic_year=None, semester=None, number=None, subject=None):
    latest = select(ExamVersion.exam_id, func.max(ExamVersion.version).label("latest")).where(ExamVersion.status.in_(PUBLISHED)).group_by(ExamVersion.exam_id).subquery()
    statement = select(Exam, ExamVersion, School).join(latest, latest.c.exam_id == Exam.id).join(ExamVersion, (ExamVersion.exam_id == Exam.id) & (ExamVersion.version == latest.c.latest)).join(School, School.id == Exam.school_id)
    for field, value in (("school_id", school_id), ("grade", grade), ("academic_year", academic_year), ("semester", semester), ("number", number)):
        if value is not None:
            statement = statement.where(getattr(Exam, field) == value)
    if city:
        statement = statement.where(School.city == city)
    if subject:
        statement = statement.where(exists(select(ExamSubject.id).where(ExamSubject.version_id == ExamVersion.id, ExamSubject.name == subject)))
    if q.strip():
        needle = q.strip().casefold()
        statement = statement.where(or_(func.lower(School.name).contains(needle, autoescape=True), func.lower(School.short_name).contains(needle, autoescape=True), func.lower(School.city).contains(needle, autoescape=True), exists(select(ExamSubject.id).where(ExamSubject.version_id == ExamVersion.id, or_(func.lower(ExamSubject.name).contains(needle, autoescape=True), func.lower(ExamSubject.scope).contains(needle, autoescape=True))))))
    return statement

def page_rows(db, statement, limit=24, offset=0):
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.execute(statement.options(joinedload(ExamVersion.source), selectinload(ExamVersion.subjects)).order_by(Exam.academic_year.desc(), Exam.semester.desc(), Exam.number.desc(), School.name, Exam.grade, Exam.id).limit(limit).offset(offset)).all()
    return rows, total
