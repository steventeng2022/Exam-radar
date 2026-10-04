"""Validated, deduplicated writes shared by crawler and API."""
from datetime import date
from urllib.parse import urlparse
from sqlalchemy import select
from .models import Exam, ExamVersion, ExamSubject, School, Source

def ingest_exam(db, school: School, source: Source, data: dict):
    host = (urlparse(source.url).hostname or "").lower()
    if not source.demo and not any(host == domain or host.endswith('.' + domain) for domain in school.domains):
        raise ValueError("Source must belong to the school's official domains")
    year, semester, number, grade = (int(data[k]) for k in ("academic_year", "semester", "number", "grade"))
    if not 100 <= year <= date.today().year - 1911 + 1 or semester not in (1, 2) or number not in (1, 2, 3) or grade not in range(7, 13):
        raise ValueError("Invalid academic year, semester, exam number or grade")
    start, end = data.get("start_date"), data.get("end_date")
    if start:
        parsed_start = date.fromisoformat(start)
        if parsed_start.year not in (year + 1911, year + 1912):
            raise ValueError("Exam date does not match academic year")
    if end and (not start or date.fromisoformat(end) < date.fromisoformat(start)):
        raise ValueError("Invalid exam date range")
    confidence = float(data["confidence"])
    if not 0 <= confidence <= 1:
        raise ValueError("Invalid confidence")
    subjects = data.get("subjects", [])
    if not subjects or any(not s.get("name") or not s.get("scope") for s in subjects):
        raise ValueError("Subjects and scopes required")
    exam = db.scalar(select(Exam).where(Exam.school_id == school.id, Exam.academic_year == year, Exam.semester == semester, Exam.number == number, Exam.grade == grade))
    if not exam:
        exam = Exam(school_id=school.id, academic_year=year, semester=semester, number=number, grade=grade)
        db.add(exam)
        db.flush()
    existing = next((v for v in exam.versions if v.content_hash == source.content_hash), None)
    if existing:
        return existing, False
    status = "approved" if confidence >= .95 else "warning" if confidence >= .75 else "review" if confidence >= .5 else "rejected"
    version = ExamVersion(exam_id=exam.id, version=max((v.version for v in exam.versions), default=0) + 1, start_date=start, end_date=end, confidence=confidence, status=status, source_id=source.id, content_hash=source.content_hash)
    version.subjects = [ExamSubject(name=s["name"], scope=s["scope"], evidence=s.get("evidence"), page_number=s.get("page_number")) for s in subjects]
    db.add(version)
    db.flush()
    db.expire(exam, ["versions"])
    return version, True
