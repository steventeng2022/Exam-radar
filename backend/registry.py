"""Atomic registry import shared by CLI and the admin API."""
import argparse
import json
from pydantic import ValidationError
from .database import Base, engine, SessionLocal
from .models import School
from .schemas import SchoolInput
from .seed import seed_demo
from .services import audit


def import_schools(db, items, *, commit=True):
    # Validate the whole batch before changing any existing row.
    parsed = []
    for item in items:
        old = db.get(School, item.get('id'))
        if old and old.demo:
            raise ValueError('Demo school IDs cannot be reused: initialize a clean real database')
        merged = {k: getattr(old, k) for k in SchoolInput.model_fields} if old else {}
        merged.update(item)
        parsed.append(SchoolInput.model_validate(merged))
    if len({s.id for s in parsed}) != len(parsed):
        raise ValueError('Duplicate school IDs in import')
    for item in parsed:
        school = db.get(School, item.id)
        before = {k: getattr(school, k) for k in SchoolInput.model_fields} if school else None
        if not school:
            school = School(id=item.id)
            db.add(school)
        for key, value in item.model_dump().items():
            setattr(school, key, value)
        school.demo = False
        audit(db, 'school', school.id, 'import', before, item.model_dump())
    if commit:
        db.commit()
    return len(parsed)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['initialize'])
    parser.add_argument('--demo', action='store_true')
    parser.add_argument('--import-json')
    args = parser.parse_args()
    if args.demo and args.import_json:
        parser.error('Use demo or real registry separately')
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if args.demo:
            seed_demo(db)
        if args.import_json:
            with open(args.import_json, encoding='utf-8') as source:
                import_schools(db, json.load(source))

if __name__ == '__main__':
    main()
