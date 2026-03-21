# db_writer.py
from DB_connections.db_connection import SessionLocal
from DB_connections.db_schema import CouncilFile, FileActivity, Attachment
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select


# Only updated 

def normalize(value):
    if value is None:
        return ""
    return " ".join(str(value).split()).strip()


def save_council_file(cf_number: str, data: dict):
    session = SessionLocal()

    try:
        # -------------------------
        # Find or create CouncilFile
        # -------------------------
        stmt = select(CouncilFile).where(CouncilFile.cf_number == cf_number)
        cf = session.execute(stmt).scalars().first()

        if not cf:
            cf = CouncilFile(cf_number=cf_number)
            session.add(cf)
            session.flush()

        # Update scalar fields
        for field in [
            "title", "start_date", "last_changed_date", "end_date",
            "reference_numbers", "council_district", "council_member_mover", 
            "second_council_member", "mover_seconder_comment"
        ]:
            if field in data:
                setattr(cf, field, data.get(field))
        # ===============================
        # HANDLE ACTIVITIES
        # ===============================

        incoming_raw = data.get("file_activities", [])

        # Step 1: Deduplicate incoming JSON
        seen_incoming = set()
        deduped_activities = []

        for act in incoming_raw:
            date = normalize(act.get("date"))
            text = normalize(act.get("activity") or act.get("activity_text"))

            key = (date, text)

            if key in seen_incoming:
                print("Skipped duplicate in JSON:", key)
                continue

            seen_incoming.add(key)
            deduped_activities.append({
                "date": date,
                "text": text,
                "extra": normalize(act.get("extra"))
            })

        # Step 2: Load existing DB records
        existing_rows = session.execute(
            select(FileActivity.activity_date, FileActivity.activity_text)
            .where(FileActivity.council_file_id == cf.id)
        ).all()

        existing_keys = {
            (normalize(row.activity_date), normalize(row.activity_text))
            for row in existing_rows
        }

        # Step 3: Insert only new records
        for act in deduped_activities:
            key = (act["date"], act["text"])

            if key in existing_keys:
                print("Skipped existing DB record:", key)
                continue

            new_activity = FileActivity(
                council_file_id=cf.id,
                activity_date=act["date"],
                activity_text=act["text"],
                extra=act["extra"]
            )

            session.add(new_activity)

        # ===============================
        # HANDLE ATTACHMENTS
        # ===============================

        incoming_attachments = data.get("attachments", [])

        seen_urls = set()
        deduped_attachments = []

        for att in incoming_attachments:
            url = normalize(att.get("url"))
            text = normalize(att.get("text"))

            if not url:
                continue

            if url in seen_urls:
                print("Skipped duplicate attachment in JSON:", url)
                continue

            seen_urls.add(url)
            deduped_attachments.append({
                "url": url,
                "text": text
            })

        existing_urls = {
            row[0]
            for row in session.execute(
                select(Attachment.url)
                .where(Attachment.council_file_id == cf.id)
            ).all()
        }

        for att in deduped_attachments:
            if att["url"] in existing_urls:
                print("Skipped existing DB attachment:", att["url"])
                continue

            session.add(
                Attachment(
                    council_file_id=cf.id,
                    text=att["text"],
                    url=att["url"]
                )
            )

        session.commit()
        return cf.id

    except IntegrityError:
        session.rollback()
        raise

    finally:
        session.close()

# All or Nothing 
# def save_council_file(cf_number: str, data: dict):
    """
    Insert or update a CouncilFile and its related activities & attachments.
    `data` is expected to include:
      - title, date_received_introduced, last_changed_date, expiration_date,
      - reference_numbers, council_district, mover, second, mover_seconder_comment,
      - file_activities: list of {"date","activity","extra"}
      - attachments: list of {"text","url"}
    """
    session = SessionLocal()
    try:
        # Try to find existing record
        stmt = select(CouncilFile).where(CouncilFile.cf_number == cf_number)
        existing = session.execute(stmt).scalar_one_or_none()

        if existing is None:
            cf = CouncilFile(cf_number=cf_number)
            session.add(cf)
            # flush to get cf.id for child relationships
            session.flush()  
        else:
            cf = existing

        # Update scalar fields
        for field in [
            "title", "start_date", "last_changed_date", "end_date",
            "reference_numbers", "council_district", "council_member_mover", 
            "second_council_member", "mover_seconder_comment"
        ]:
            if field in data:
                setattr(cf, field, data.get(field))

        # Replace activities: simple approach -> delete existing and insert new
        # Alternatively you could diff and upsert
        if "file_activities" in data:
            # clear existing
            cf.activities[:] = []
            for act in data.get("file_activities", []):
                fa = FileActivity(
                    activity_date=act.get("date"),
                    activity_text=act.get("activity"),
                    extra=act.get("extra")
                )
                cf.activities.append(fa)

        if "attachments" in data:
            cf.attachments[:] = []
            for att in data.get("attachments", []):
                a = Attachment(text=att.get("text"), url=att.get("url"))
                cf.attachments.append(a)

        session.add(cf)
        session.commit()
        session.refresh(cf)
        return cf.id
    except IntegrityError as e:
        session.rollback()
        raise
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()