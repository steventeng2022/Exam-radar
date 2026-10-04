from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def now():
    return datetime.now(timezone.utc)

class School(Base):
    __tablename__ = "schools"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    short_name: Mapped[str] = mapped_column(String)
    type: Mapped[str] = mapped_column(String, default="high_school")
    city: Mapped[str] = mapped_column(String)
    district: Mapped[str] = mapped_column(String, default="")
    website: Mapped[str] = mapped_column(String)
    domains: Mapped[list] = mapped_column(JSON, default=list)
    crawl_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    crawler_status: Mapped[str] = mapped_column(String, default="idle")
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    demo: Mapped[bool] = mapped_column(Boolean, default=False)

class Source(Base):
    __tablename__ = "sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"))
    url: Mapped[str] = mapped_column(Text)
    file_url: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String, index=True)
    source_type: Mapped[str] = mapped_column(String)
    page_number: Mapped[int | None] = mapped_column(Integer)
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    demo: Mapped[bool] = mapped_column(Boolean, default=False)

class Exam(Base):
    __tablename__ = "exams"
    __table_args__ = (UniqueConstraint("school_id", "academic_year", "semester", "number", "grade", name="exam_identity"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"))
    academic_year: Mapped[int] = mapped_column(Integer)
    semester: Mapped[int] = mapped_column(Integer)
    number: Mapped[int] = mapped_column(Integer)
    grade: Mapped[int] = mapped_column(Integer)
    type: Mapped[str] = mapped_column(String, default="段考")
    versions: Mapped[list["ExamVersion"]] = relationship(back_populates="exam", cascade="all, delete-orphan", order_by="ExamVersion.version")

class ExamVersion(Base):
    __tablename__ = "exam_versions"
    __table_args__ = (UniqueConstraint("exam_id", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    exam_id: Mapped[int] = mapped_column(ForeignKey("exams.id"))
    version: Mapped[int] = mapped_column(Integer)
    start_date: Mapped[str | None] = mapped_column(String)
    end_date: Mapped[str | None] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String, default="review")
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    content_hash: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    exam: Mapped[Exam] = relationship(back_populates="versions")
    subjects: Mapped[list["ExamSubject"]] = relationship(cascade="all, delete-orphan")
    source: Mapped[Source] = relationship()

class ExamSubject(Base):
    __tablename__ = "exam_subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("exam_versions.id"))
    name: Mapped[str] = mapped_column(String)
    scope: Mapped[str] = mapped_column(Text)
    evidence: Mapped[str | None] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)

class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"))
    status: Mapped[str] = mapped_column(String, default="queued", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pages_checked: Mapped[int] = mapped_column(Integer, default=0)
    documents: Mapped[int] = mapped_column(Integer, default=0)
    new_exams: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)

class CrawlPage(Base):
    __tablename__ = "crawl_pages"
    __table_args__ = (UniqueConstraint("school_id", "url"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[str] = mapped_column(ForeignKey("schools.id"))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_jobs.id"))
    url: Mapped[str] = mapped_column(Text)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="queued")
    content_hash: Mapped[str | None] = mapped_column(String)
    etag: Mapped[str | None] = mapped_column(String)
    last_modified: Mapped[str | None] = mapped_column(String)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

class CrawlError(Base):
    __tablename__ = "crawl_errors"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("crawl_jobs.id"))
    url: Mapped[str] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
