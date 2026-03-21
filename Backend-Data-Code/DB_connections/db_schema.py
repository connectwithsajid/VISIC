# models.py
from sqlalchemy import (
    Column, Integer, String, Text, Date, DateTime, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func

Base = declarative_base()

class CouncilFile(Base):
    __tablename__ = "council_files"
    id = Column(Integer, primary_key=True, index=True)
    cf_number = Column(String(32), nullable=False, unique=True)  # e.g., "21-0043"
    title = Column(Text)
    start_date = Column(String(64))
    last_changed_date = Column(String(64))
    end_date = Column(String(64))
    reference_numbers = Column(Text)
    council_district = Column(String(64))
    council_member_mover = Column(String(128))
    second_council_member = Column(String(128))
    mover_seconder_comment = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # relationships
    activities = relationship("FileActivity", cascade="all, delete-orphan", back_populates="council_file")
    attachments = relationship("Attachment", cascade="all, delete-orphan", back_populates="council_file")


class FileActivity(Base):
    __tablename__ = "file_activities"
    id = Column(Integer, primary_key=True, index=True)
    council_file_id = Column(Integer, ForeignKey("council_files.id", ondelete="CASCADE"), nullable=False, index=True)
    activity_date = Column(String(64))   # keep as string to preserve formatting like MM/DD/YYYY
    activity_text = Column(Text)
    extra = Column(Text)

    council_file = relationship("CouncilFile", back_populates="activities")

    # avoid duplicate identical rows for same file
    __table_args__ = (
        UniqueConstraint('council_file_id', 'activity_date', 'activity_text', name='uq_activity_per_file'),
    )


class Attachment(Base):
    __tablename__ = "attachments"
    id = Column(Integer, primary_key=True, index=True)
    council_file_id = Column(Integer, ForeignKey("council_files.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text)
    url = Column(Text)

    council_file = relationship("CouncilFile", back_populates="attachments")

    __table_args__ = (
        UniqueConstraint('council_file_id', 'url', name='uq_attachment_per_file'),
    )