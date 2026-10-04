from sqlalchemy import select
from .models import School, Source
from .services import ingest_exam

SCHOOLS = [
    ("yucheng", "臺北市立育成高級中學", "育成高中", "南港區", "https://www.yucsh.tp.edu.tw", "www.yucsh.tp.edu.tw"),
    ("chenggong", "臺北市立成功高級中學", "成功高中", "中正區", "https://www.cksh.tp.edu.tw", "www.cksh.tp.edu.tw"),
    ("jianguo", "臺北市立建國高級中學", "建國中學", "中正區", "https://www.ck.tp.edu.tw", "www.ck.tp.edu.tw"),
    ("hsnu", "國立臺灣師範大學附屬高級中學", "師大附中", "大安區", "https://www.hs.ntnu.edu.tw", "www.hs.ntnu.edu.tw"),
    ("songshan", "臺北市立松山高級中學", "松山高中", "信義區", "https://www.sssh.tp.edu.tw", "www.sssh.tp.edu.tw"),
]

def seed_demo(db):
    if db.scalar(select(School.id).limit(1)):
        return
    for i, (sid, name, short, district, website, domain) in enumerate(SCHOOLS):
        school = School(id=sid, name=name, short_name=short, city="臺北市", district=district, website=website, domains=[domain], demo=True, crawl_enabled=False)
        db.add(school)
        db.flush()
        source = Source(school_id=sid, url=website, title="示範資料・115學年度第一次段考範圍（非學校公告）", content_hash=f"demo-{sid}-1", source_type="demo", demo=True)
        db.add(source)
        db.flush()
        for grade in (10, 11, 12):
            ingest_exam(db, school, source, {"academic_year":115,"semester":1,"number":1,"grade":grade,"start_date":f"2026-10-{13+i:02d}","end_date":f"2026-10-{15+i:02d}","confidence":.97,"subjects":[{"name":"國文","scope":"第1課～第4課"},{"name":"英文","scope":"Lesson 1–3"},{"name":"數學A" if grade > 10 else "數學","scope":f"1-1～2-{[2,1,3,2,1][i]}"},{"name":"物理","scope":"第1章～第2章"},{"name":"化學","scope":"第1章～第2章"}]})
    db.commit()
