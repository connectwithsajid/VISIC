from sqlalchemy import (
    Column,
    String,
    Integer,
    Date,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class CouncilMember(Base):
    __tablename__ = "council_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    district = Column(Integer, nullable=False)
    impact_summary = Column(String, nullable=True)
    website = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    about = Column(String, nullable=True)
    profile_pic = Column(String, nullable=True)

    project_movers = relationship("ProjectMover", back_populates="council_member")
    votes = relationship("Vote", back_populates="council_member")


class Project(Base):
    __tablename__ = "projects"

    # id = Column(Integer, primary_key=True, autoincrement=True)
    id = Column(String, primary_key=True, nullable=False)  # VARCHAR
    name = Column(String, nullable=False)
    status = Column(String, nullable=False)
    about = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    meeting_date = Column(Date, nullable=True)
    meeting_type = Column(String, nullable=True)
    vote_action = Column(String, nullable=True)
    vote_given = Column(String, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('planned', 'in-progress', 'completed')",
            name="ck_projects_status",
        ),
    )

    file_activities = relationship("FileActivity", back_populates="project", cascade="all, delete-orphan")
    file_activity_urls = relationship("FileActivityURL", back_populates="project", cascade="all, delete-orphan")
    online_documents = relationship("OnlineDocument", back_populates="project", cascade="all, delete-orphan")
    project_movers = relationship("ProjectMover", back_populates="project", cascade="all, delete-orphan")
    votes = relationship("Vote", back_populates="project", cascade="all, delete-orphan")
    project_graphs = relationship("ProjectGraph", back_populates="project", cascade="all, delete-orphan")


class ProjectMover(Base):
    __tablename__ = "project_movers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    council_member_id = Column(Integer, ForeignKey("council_members.id", ondelete="CASCADE"), nullable=False)
    role = Column(String, nullable=False)

    __table_args__ = (
        UniqueConstraint("project_id", "council_member_id", "role", name="uq_project_mover"),
        CheckConstraint(
            "role IN ('primary', 'secondary', 'other')",
            name="ck_project_movers_role",
        ),
    )

    project = relationship("Project", back_populates="project_movers")
    council_member = relationship("CouncilMember", back_populates="project_movers")


class Vote(Base):
    __tablename__ = "votes"

    council_member_id = Column(Integer, ForeignKey("council_members.id", ondelete="CASCADE"), primary_key=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    vote = Column(String, nullable=True)

    council_member = relationship("CouncilMember", back_populates="votes")
    project = relationship("Project", back_populates="votes")


class FileActivity(Base):
    __tablename__ = "file_activities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    activity_date = Column(Date, nullable=True)
    activity_text = Column(String, nullable=True)

    project = relationship("Project", back_populates="file_activities")
    urls = relationship("FileActivityURL", back_populates="file_activity", cascade="all, delete-orphan")


class FileActivityURL(Base):
    __tablename__ = "file_activities_url"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    url = Column(String, nullable=False)
    file_activity_id = Column(Integer, ForeignKey("file_activities.id", ondelete="CASCADE"), nullable=False)

    project = relationship("Project", back_populates="file_activity_urls")
    file_activity = relationship("FileActivity", back_populates="urls")


class OnlineDocument(Base):
    __tablename__ = "online_documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    url = Column(String, nullable=False)
    title = Column(String, nullable=False)
    date = Column(Date, nullable=False)

    project = relationship("Project", back_populates="online_documents")


class GraphType(Base):
    __tablename__ = "graph_types"

    id = Column(Integer, primary_key=True, autoincrement=True)
    label = Column(String, nullable=True)
    description = Column(String, nullable=True)

    projects = relationship("ProjectGraph", back_populates="graph_type", cascade="all, delete-orphan")


class ProjectGraph(Base):
    __tablename__ = "project_graphs"

    project_id = Column(String, ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    graph_id = Column(Integer, ForeignKey("graph_types.id", ondelete="CASCADE"), primary_key=True)

    project = relationship("Project", back_populates="project_graphs")
    graph_type = relationship("GraphType", back_populates="projects")