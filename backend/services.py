"""Validate dates, source identity and revisions before every write."""
import hashlib
import json
from datetime import date
from urllib.parse import urlparse
from sqlalchemy import select
from .models import Exam, ExamVersion, ExamSubject, School, Source, AuditLog


def validate_exam(data):
    year, semester, number, grade = (int(data[k]) for k in ('academic_year', 'semester', 'number', 'grade'))
    if not 100 <= year <= date.today().year - 1911 + 1 or semester not in (1, 2) or number not in (1, 2, 3) or grade not in range(7, 13):
        raise ValueError('Invalid academic year, semester, exam number or grade')
    start, end = data.get('start_date'), data.get('end_date')
    for value in (start, end):
        if value and not date(year + 1911, 8, 1) <= date.fromisoformat(value) <= date(year + 1912, 7, 31):
            raise ValueError('Exam date does not match academic year')
    if end and (not start or date.fromisoformat(end) < date.fromisoformat(start)):
        raise ValueError('Invalid exam date range')
    subjects = data.get('subjects', [])
    if not subjects or len(subjects) > 40 or any(not s.get('name', '').strip() or not s.get('scope', '').strip() or len(s['name']) > 50 or len(s['scope']) > 2000 for s in subjects):
        raise ValueError('Subjects and scopes required (maximum 40 subjects)')
    names = [s['name'].strip().casefold() for s in subjects]
    if len(set(names)) != len(names):
        raise ValueError('Duplicate subject names require manual correction')


def snapshot(version):
    return {'status': version.status, 'start_date': version.start_date, 'end_date': version.end_date, 'confidence': version.confidence, 'content_hash': version.content_hash, 'subjects': [{'name': s.name, 'scope': s.scope, 'evidence': s.evidence, 'page_number': s.page_number} for s in version.subjects]}


def revision(version):
    return hashlib.sha256(json.dumps(snapshot(version), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def audit(db, entity, entity_id, action, before=None, after=None):
    db.add(AuditLog(entity=entity, entity_id=str(entity_id), action=action, before=before, after=after))


def ingest_exam(db, school: School, source: Source, data: dict):
    parsed = urlparse(source.url)
    host = (parsed.hostname or '').lower()
    if source.school_id != school.id:
        raise ValueError('Source school mismatch')
    if not (school.demo and source.demo):
        if source.demo or parsed.scheme not in ('http', 'https') or parsed.username or parsed.password or not any(host == domain or host.endswith('.' + domain) for domain in school.domains):
            raise ValueError("Source must belong to the school's official domains")
    validate_exam(data)
    year, semester, number, grade = (int(data[k]) for k in ('academic_year', 'semester', 'number', 'grade'))
    confidence = float(data['confidence'])
    if not 0 <= confidence <= 1:
        raise ValueError('Invalid confidence')
    exam = db.scalar(select(Exam).where(Exam.school_id == school.id, Exam.academic_year == year, Exam.semester == semester, Exam.number == number, Exam.grade == grade))
    if not exam:
        exam = Exam(school_id=school.id, academic_year=year, semester=semester, number=number, grade=grade)
        db.add(exam)
        db.flush()
    existing = next((v for v in exam.versions if v.content_hash == source.content_hash), None)
    if existing:
        return existing, False
    status = 'approved' if confidence >= .95 else 'warning' if confidence >= .75 else 'review' if confidence >= .5 else 'rejected'
    if data.get('review_required') and confidence >= .5:
        status = 'review'
    version = ExamVersion(exam_id=exam.id, version=max((v.version for v in exam.versions), default=0) + 1, start_date=data.get('start_date'), end_date=data.get('end_date'), confidence=confidence, status=status, source_id=source.id, content_hash=source.content_hash)
    version.subjects = [ExamSubject(name=s['name'].strip(), scope=s['scope'].strip(), evidence=s.get('evidence'), page_number=s.get('page_number')) for s in data['subjects']]
    db.add(version)
    db.flush()
    db.expire(exam, ['versions'])
    return version, True
