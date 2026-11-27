"""SQLAlchemy Core schema and persistence operations."""
import json
import secrets
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, MetaData, String, Table, Text, create_engine, func, select, text, update

metadata = MetaData()
roadmaps = Table(
    "roadmaps",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("topic", String(80), nullable=False, index=True),
    Column("level", String(16), nullable=False),
    Column("roadmap", Text, nullable=False),
    Column("courses", Text, nullable=False, default="[]"),
    Column("kind", String(12), nullable=False, default="cache", index=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def init_db(app):
    url = app.config.get("DATABASE_URL")
    if not url:
        app.extensions["acadix_engine"] = None
        return
    try:
        engine = create_engine(url, pool_pre_ping=True, pool_recycle=300)
        metadata.create_all(engine)
        app.extensions["acadix_engine"] = engine
        app.extensions.pop("acadix_db_error", None)
    except Exception as exc:
        app.extensions["acadix_engine"] = None
        app.extensions["acadix_db_error"] = type(exc).__name__


def get_engine():
    from flask import current_app

    return current_app.extensions.get("acadix_engine")


def check_database():
    engine = get_engine()
    if engine is None:
        return False
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return True


def get_cached_from_db(topic, level):
    engine = get_engine()
    if engine is None:
        return None
    statement = (
        select(roadmaps.c.roadmap)
        .where(
            roadmaps.c.topic == topic.strip().lower(),
            roadmaps.c.level == level,
            roadmaps.c.kind == "cache",
        )
        .order_by(roadmaps.c.created_at.desc())
        .limit(1)
    )
    with engine.connect() as connection:
        return connection.execute(statement).scalar_one_or_none()


def set_cached_in_db(topic, level, data):
    engine = get_engine()
    if engine is None:
        return
    normalized = topic.strip().lower()
    cache_id = "cache-" + __import__("hashlib").sha256(
        f"{normalized}|{level}".encode()
    ).hexdigest()[:24]
    now = datetime.now(timezone.utc)
    with engine.begin() as connection:
        exists = connection.execute(
            select(roadmaps.c.id).where(roadmaps.c.id == cache_id)
        ).first()
        values = {
            "topic": normalized,
            "level": level,
            "roadmap": data,
            "courses": "[]",
            "kind": "cache",
            "created_at": now,
        }
        if exists:
            connection.execute(update(roadmaps).where(roadmaps.c.id == cache_id).values(**values))
        else:
            connection.execute(roadmaps.insert().values(id=cache_id, **values))


def create_shared_roadmap(topic, level, roadmap, courses):
    engine = get_engine()
    if engine is None:
        return None
    share_id = secrets.token_urlsafe(9)
    values = {
        "id": share_id,
        "topic": topic,
        "level": level,
        "roadmap": roadmap,
        "courses": json.dumps(courses, ensure_ascii=False),
        "kind": "share",
        "created_at": datetime.now(timezone.utc),
    }
    with engine.begin() as connection:
        connection.execute(roadmaps.insert().values(**values))
    return share_id


def get_shared_roadmap(share_id):
    engine = get_engine()
    if engine is None:
        return None
    statement = select(roadmaps).where(
        roadmaps.c.id == share_id,
        roadmaps.c.kind == "share",
    )
    with engine.connect() as connection:
        row = connection.execute(statement).mappings().first()
    if not row:
        return None
    try:
        courses = json.loads(row["courses"])
    except (TypeError, json.JSONDecodeError):
        courses = []
    return {
        "topic": row["topic"],
        "level": row["level"],
        "roadmap": row["roadmap"],
        "courses": courses if isinstance(courses, list) else [],
    }


def get_topic_stats(limit=20):
    engine = get_engine()
    if engine is None:
        return None
    statement = (
        select(roadmaps.c.topic, func.count().label("count"))
        .where(roadmaps.c.kind.in_(["cache", "share"]))
        .group_by(roadmaps.c.topic)
        .order_by(func.count().desc())
        .limit(limit)
    )
    with engine.connect() as connection:
        return [{"topic": row.topic, "count": row.count} for row in connection.execute(statement)]
