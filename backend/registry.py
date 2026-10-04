"""Initialize tables, optionally seed demos or import an explicit school registry."""
import argparse
import json
from urllib.parse import urlparse
from .database import Base, engine, SessionLocal
from .models import School
from .seed import seed_demo

def import_schools(db, items):
    for item in items:
        host = urlparse(item["website"]).hostname
        domains = item.get("domains", [])
        if urlparse(item["website"]).scheme not in ("https","http") or not host or not domains or any("/" in d or not d.endswith(".edu.tw") for d in domains):
            raise ValueError("Registry requires official .edu.tw domains and HTTP(S) website")
        if not any(host == d or host.endswith('.' + d) for d in domains):
            raise ValueError("Website must match registered domain")
        school = db.get(School,item["id"])
        if school and school.demo:
            raise ValueError("Demo school IDs cannot be reused: initialize a clean real database")
        if not school:
            school = School(id=item["id"])
            db.add(school)
        for field in ("name","short_name","city","district","website","domains","type"):
            if field in item:
                setattr(school,field,item[field])
        school.crawl_enabled = bool(item.get("crawl_enabled",True))
        school.demo = False
    db.commit()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["initialize"])
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--import-json")
    args = parser.parse_args()
    if args.demo and args.import_json:
        parser.error("Use demo or real registry separately")
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        if args.demo:
            seed_demo(db)
        if args.import_json:
            with open(args.import_json, encoding="utf-8") as source:
                import_schools(db,json.load(source))

if __name__ == "__main__":
    main()
