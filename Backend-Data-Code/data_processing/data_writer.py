# data_processing/data_writer.py

from datetime import date
import re
import json
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from dateutil import parser as dateparser

from DB_connections.db_connection import SessionLocal
from DB_connections.db_schema import (
    CouncilMember,
    Project,
    ProjectAddress,
    ProjectMover,
    Vote,
    FileActivity,
    FileActivityURL,
    OnlineDocument,
    GraphType,
    ProjectGraph,
)

ALLOWED_PROJECT_STATUS = {"planned", "in-progress", "completed"}
ALLOWED_MOVE_ROLES = {"primary", "secondary", "other"}


# -----------------
STREET_SUFFIXES = (
    "Street", "St", "Avenue", "Ave", "Boulevard", "Blvd", "Road", "Rd",
    "Drive", "Dr", "Place", "Pl", "Way", "Court", "Ct", "Lane", "Ln",
    "Highway", "Hwy", "Park", "Square", "Sq", "Terrace", "Ter", "Circle", "Cir"
)

DIRECTIONS = r"(?:N|North|S|South|E|East|W|West|NE|NW|SE|SW)?"

ADDRESS_RE = re.compile(
    rf"\b\d+\s+{DIRECTIONS}\s*[A-Za-z0-9'\- ]+?\s+(?:{'|'.join(STREET_SUFFIXES)})\b",
    re.IGNORECASE,
)

ADDRESS_RANGE_RE = re.compile(
    rf"\b\d+\s*(?:and|&|to|-)\s*\d+\s+{DIRECTIONS}\s*[A-Za-z0-9'\- ]+?\s+(?:{'|'.join(STREET_SUFFIXES)})\b",
    re.IGNORECASE,
)

PAREN_RE = re.compile(r"\(([^()]*)\)")

PLACE_HINTS = (
    "park", "square", "plaza", "hall", "room", "center", "centre",
    "station", "memorial", "historic park", "community center", "library",
    "village", "heights", "manor", "apartments", "school", "building",
)

TOPIC_HINTS = (
    "fund", "lease", "waiver", "transfer", "signage", "signs", "moratorium",
    "illegal dumping", "housing", "project", "equipment", "improvements",
    "repairs", "services", "programs", "study", "assessment", "staffing",
    "deployment", "installation", "closure", "seminar", "luncheon",
    "ordinance", "reinstatement", "amendment", "agreement", "tefra",
    "operation", "operations", "repair", "safety",
)


def to_json_list(value):
    return json.dumps(value or [], ensure_ascii=False)


def looks_like_address(text):
    text = normalize(text)
    return bool(ADDRESS_RANGE_RE.search(text) or ADDRESS_RE.search(text))


def extract_address_candidates(title):
    title = normalize(title)
    candidates = []

    for inside in PAREN_RE.findall(title):
        inside = normalize(inside)
        if looks_like_address(inside):
            candidates.append(inside)

    segments = [normalize(x) for x in title.split("/") if normalize(x)]
    for seg in segments:
        if looks_like_address(seg):
            candidates.append(seg)

    seen = set()
    deduped = []
    for c in candidates:
        key = c.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    return deduped


def looks_like_place(text):
    t = normalize(text).lower()
    return any(hint in t for hint in PLACE_HINTS)


def looks_like_topic(text):
    t = normalize(text).lower()
    return any(hint in t for hint in TOPIC_HINTS)


def parse_project_title(title):
    title = normalize(title)
    segments = [normalize(x) for x in title.split("/") if normalize(x)]
    addresses = extract_address_candidates(title)

    places = []
    topics = []

    for seg in segments:
        if seg in addresses:
            continue
        if looks_like_place(seg):
            places.append(seg)
        else:
            topics.append(seg)

    return {
        "project_title": title,
        "address": addresses[0] if addresses else None,
        "addresses": addresses,
        "places": places,
        "topics": topics,
        "segments": segments,
    }
# --------------
def normalize(value):
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def parse_date_safe(value):
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    try:
        return dateparser.parse(str(value)).date()
    except Exception:
        return None


def make_key(value):
    return normalize(value).lower()


def get_or_create_council_member(session, member_data):
    first_name = normalize(member_data.get("first_name"))
    last_name = normalize(member_data.get("last_name"))

    district_raw = member_data.get("cd") or member_data.get("district") or 0
    try:
        district = int(district_raw)
    except Exception:
        district = 0

    member = session.execute(
        select(CouncilMember).where(
            CouncilMember.first_name == first_name,
            CouncilMember.last_name == last_name,
            # CouncilMember.district == district,
        )
    ).scalar_one_or_none()

    if member is None:
        member = CouncilMember(
            # name=normalize(member_data.get("name")),  # ❌ old
            first_name=first_name or "Unknown",
            last_name=last_name or "",
            district=district,
            impact_summary=normalize(member_data.get("impact_summary")),
            website=normalize(member_data.get("website")),
            phone_number=normalize(member_data.get("phone_number")),
            about=normalize(member_data.get("about")),
            profile_pic=normalize(member_data.get("profile_pic")),
        )
        session.add(member)
        session.flush()

    return member

def get_or_create_graph_type(session, graph_data):
    label = normalize(graph_data.get("label"))
    graph_type = session.execute(
        select(GraphType).where(GraphType.label == label)
    ).scalar_one_or_none()

    if graph_type is None:
        graph_type = GraphType(
            label=label,
            description=normalize(graph_data.get("description")),
        )
        session.add(graph_type)
        session.flush()

    return graph_type


def dedupe_activities_keep_first(incoming_activities):
    seen = set()
    deduped = []

    for act in incoming_activities or []:
        activity_date = normalize(act.get("date"))
        activity_text = normalize(act.get("activity") or act.get("activity_text"))
        key = (activity_date, activity_text)

        if key in seen:
            print("Skipped duplicate in JSON:", key)
            continue

        seen.add(key)
        deduped.append({
            "date": activity_date,
            "activity": activity_text,
            "doc_url": normalize(act.get("doc_url")),
            "doc_title": normalize(act.get("doc_title")),
            "doc_date": normalize(act.get("doc_date")),
            "icon_src": normalize(act.get("icon_src")),
            "showtip_id": normalize(act.get("showtip_id")),
        })

    return deduped


def dedupe_documents_keep_first(incoming_documents):
    seen = set()
    deduped = []

    for doc in incoming_documents or []:
        url = normalize(doc.get("url"))
        title = normalize(doc.get("title") or doc.get("text"))
        doc_date = normalize(doc.get("date"))

        if not url:
            continue

        if url in seen:
            print("Skipped duplicate document in JSON:", url)
            continue

        seen.add(url)
        deduped.append({
            "url": url,
            "title": title,
            "date": doc_date,
        })

    return deduped


def save_project_record(project_id: str, data: dict):
    session = SessionLocal()

    try:
        project_id = normalize(
            project_id
            or data.get("project_id")
            or data.get("id")
            or data.get("cf_number")
        )

        if not project_id:
            raise ValueError("project_id is required")

        # -------------------------
        # Find or create Project
        # -------------------------
        project = session.execute(
            select(Project).where(Project.id == project_id)
        ).scalar_one_or_none()

        if project is None:
            project = Project(
                id=project_id,
                name=normalize(data.get("name") or data.get("title") or project_id),
                status="planned",
                about=normalize(data.get("about")),
                start_date=parse_date_safe(data.get("start_date")),
                end_date=parse_date_safe(data.get("end_date")),
                meeting_date=None,
                meeting_type="",
                vote_action="",
                vote_given="",
            )
            session.add(project)
            session.flush()

        # Update project fields
        project.name = normalize(data.get("name") or data.get("title") or project.name)
        project.about = normalize(data.get("about"))

        if data.get("status"):
            status = normalize(data.get("status")).lower()
            if status in ALLOWED_PROJECT_STATUS:
                project.status = status

        if data.get("start_date"):
            project.start_date = parse_date_safe(data.get("start_date"))

        if data.get("end_date"):
            project.end_date = parse_date_safe(data.get("end_date"))

       
        # -------------------------
        # Address info
        # -------------------------
        raw_title = normalize(data.get("title") or data.get("name") or project.name or project_id)
        title_info = parse_project_title(raw_title)

        existing_title = session.execute(
            select(ProjectAddress).where(ProjectAddress.project_id == project.id)
        ).scalar_one_or_none()

        if existing_title is None:
            session.add(
                ProjectAddress(
                    project_id=project.id,
                    project_title=title_info["project_title"],
                    address=title_info["address"],
                    addresses=to_json_list(title_info["addresses"]),
                    places=to_json_list(title_info["places"]),
                    topics=to_json_list(title_info["topics"]),
                    segments=to_json_list(title_info["segments"]),
                )
            )
        else:
            existing_title.project_title = title_info["project_title"]
            existing_title.address = title_info["address"]
            existing_title.addresses = to_json_list(title_info["addresses"])
            existing_title.places = to_json_list(title_info["places"])
            existing_title.topics = to_json_list(title_info["topics"])
            existing_title.segments = to_json_list(title_info["segments"])

        # -------------------------
        # Vote info
        # -------------------------
        vote_info = data.get("vote_info", {}) or {}
        if vote_info:
            project.meeting_date = parse_date_safe(vote_info.get("Meeting Date"))
            project.meeting_type = normalize(vote_info.get("Meeting Type"))
            project.vote_action = normalize(vote_info.get("Vote Action"))
            project.vote_given = normalize(vote_info.get("Vote Given"))

        # ===============================
        # FILE ACTIVITIES
        # ===============================
        incoming_activities = dedupe_activities_keep_first(data.get("file_activities", []))

        existing_activity_keys = {
            (normalize(row.activity_date), normalize(row.activity_text))
            for row in session.execute(
                select(FileActivity.activity_date, FileActivity.activity_text)
                .where(FileActivity.project_id == project.id)
            ).all()
        }

        existing_activity_urls = {
            normalize(row[0])
            for row in session.execute(
                select(FileActivityURL.url).where(FileActivityURL.project_id == project.id)
            ).all()
        }

        for act in incoming_activities:
            key = (normalize(act["date"]), normalize(act["activity"]))

            if key in existing_activity_keys:
                print("Skipped existing DB record:", key)
                continue

            activity = FileActivity(
                project_id=project.id,
                activity_date=parse_date_safe(act["date"]),
                activity_text=act["activity"],
            )
            session.add(activity)
            session.flush()

            if act.get("doc_url"):
                doc_url = normalize(act["doc_url"])
                if doc_url and doc_url not in existing_activity_urls:
                    session.add(
                        FileActivityURL(
                            project_id=project.id,
                            url=doc_url,
                            file_activity_id=activity.id,
                        )
                    )
                    existing_activity_urls.add(doc_url)

        # ===============================
        # ONLINE DOCUMENTS
        # ===============================
        incoming_documents = data.get("attachments") or data.get("online_documents") or []
        deduped_documents = dedupe_documents_keep_first(incoming_documents)

        for doc in deduped_documents:
            url = normalize(doc["url"])

            existing_doc = session.execute(
                select(OnlineDocument).where(
                    OnlineDocument.project_id == project.id,
                    OnlineDocument.url == url
                )
            ).scalar_one_or_none()

            if existing_doc:
                print("Updating existing document:", url)
                existing_doc.title = normalize(doc["title"])
                existing_doc.date = parse_date_safe(doc["date"]) or project.start_date or date.today()
                continue

            print("Inserting new document:", url)
            session.add(
                OnlineDocument(
                    project_id=project.id,
                    url=url,
                    title=normalize(doc["title"] or url),
                    date=parse_date_safe(doc["date"]) or project.start_date or date.today(),
                )
            )

        
        # ===============================
        # VOTES
        # ===============================
        incoming_votes = data.get("vote_members", []) or []

        existing_vote_keys = {
            (normalize(row.council_member_id), normalize(row.project_id))
            for row in session.execute(
                select(Vote.council_member_id, Vote.project_id)
                .where(Vote.project_id == project.id)
            ).all()
        }

        for vote_item in incoming_votes:
            member = get_or_create_council_member(session, vote_item)

            vote_key = (member.id, project.id)
            if vote_key in existing_vote_keys:
                print("Skipped existing DB vote:", vote_key)
                continue

            session.add(
                Vote(
                    council_member_id=member.id,
                    project_id=project.id,
                    vote=normalize(vote_item.get("vote")),
                )
            )
            existing_vote_keys.add(vote_key)

        # ===============================
        # PROJECT MOVERS
        # ===============================
        incoming_movers = data.get("project_movers", []) or []

        existing_mover_keys = {
            (normalize(row.project_id), normalize(row.council_member_id), normalize(row.role))
            for row in session.execute(
                select(ProjectMover.project_id, ProjectMover.council_member_id, ProjectMover.role)
                .where(ProjectMover.project_id == project.id)
            ).all()
        }

        for mover in incoming_movers:
            role = normalize(mover.get("role") or "other").lower()
            if role not in ALLOWED_MOVE_ROLES:
                role = "other"

            member = get_or_create_council_member(session, mover)

            mover_key = (project.id, member.id, role)
            if mover_key in existing_mover_keys:
                print("Skipped existing DB mover:", mover_key)
                continue

            session.add(
                ProjectMover(
                    project_id=project.id,
                    council_member_id=member.id,
                    role=role,
                )
            )
            existing_mover_keys.add(mover_key)

        # ===============================
        # GRAPH TYPES / PROJECT GRAPHS
        # ===============================
        incoming_graph_types = data.get("graph_types", []) or []

        existing_project_graph_keys = {
            (normalize(row.project_id), normalize(row.graph_id))
            for row in session.execute(
                select(ProjectGraph.project_id, ProjectGraph.graph_id)
                .where(ProjectGraph.project_id == project.id)
            ).all()
        }

        for graph_data in incoming_graph_types:
            graph_type = get_or_create_graph_type(session, graph_data)

            graph_key = (project.id, graph_type.id)
            if graph_key in existing_project_graph_keys:
                print("Skipped existing DB graph relation:", graph_key)
                continue

            session.add(
                ProjectGraph(
                    project_id=project.id,
                    graph_id=graph_type.id,
                )
            )
            existing_project_graph_keys.add(graph_key)

        session.commit()

        return {
            "project_id": project.id,
            "status": "ok",
        }

    except IntegrityError as e:
        session.rollback()
        print("IntegrityError:", e)
        raise

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


def save_council_file(cf_number: str, data: dict):
    return save_project_record(cf_number, data)