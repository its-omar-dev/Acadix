"""Account persistence tables and helpers for Acadix."""
# ruff: noqa: I001
from datetime import datetime, timezone
import json
import secrets

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    Text,
    UniqueConstraint,
    insert,
    select,
)
from sqlalchemy.exc import IntegrityError

from acadix.models import metadata


users = Table(
    "users",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("email", String(254), nullable=False, unique=True, index=True),
    Column("display_name", String(80), nullable=False),
    Column("password_hash", String(255), nullable=True),
    Column("avatar_url", String(2048), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
)

oauth_accounts = Table(
    "oauth_accounts",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("provider", String(20), nullable=False),
    Column("provider_user_id", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_identity"),
)

user_roadmaps = Table(
    "user_roadmaps",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("user_id", String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("topic", String(80), nullable=False),
    Column("level", String(16), nullable=False),
    Column("roadmap", Text, nullable=False),
    Column("courses", Text, nullable=False, default="[]"),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


def _engine():
    from flask import current_app

    return current_app.extensions.get("acadix_engine")


def _user(row):
    if row is None:
        return None
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "avatar_url": row["avatar_url"],
    }


def get_user_by_id(user_id):
    engine = _engine()
    if engine is None or not user_id:
        return None
    with engine.connect() as connection:
        row = connection.execute(select(users).where(users.c.id == user_id)).mappings().first()
    return _user(row)


def get_user_by_email(email):
    engine = _engine()
    if engine is None:
        return None
    with engine.connect() as connection:
        row = connection.execute(
            select(users).where(users.c.email == email.strip().lower())
        ).mappings().first()
    return _user(row)


def create_password_user(email, display_name, password_hash):
    engine = _engine()
    if engine is None:
        return None
    user_id = secrets.token_urlsafe(18)
    values = {
        "id": user_id,
        "email": email.strip().lower(),
        "display_name": display_name.strip(),
        "password_hash": password_hash,
        "avatar_url": None,
        "created_at": datetime.now(timezone.utc),
    }
    try:
        with engine.begin() as connection:
            connection.execute(insert(users).values(**values))
    except IntegrityError:
        return None
    return get_user_by_id(user_id)


def get_password_hash(email):
    engine = _engine()
    if engine is None:
        return None
    with engine.connect() as connection:
        return connection.execute(
            select(users.c.password_hash).where(users.c.email == email.strip().lower())
        ).scalar_one_or_none()


def get_or_create_oauth_user(provider, provider_user_id, email, display_name, avatar_url=None):
    engine = _engine()
    if engine is None:
        return None
    email = email.strip().lower()
    with engine.begin() as connection:
        linked = connection.execute(
            select(users)
            .join(oauth_accounts, oauth_accounts.c.user_id == users.c.id)
            .where(
                oauth_accounts.c.provider == provider,
                oauth_accounts.c.provider_user_id == str(provider_user_id),
            )
        ).mappings().first()
        if linked:
            return _user(linked)

        existing = connection.execute(
            select(users).where(users.c.email == email)
        ).mappings().first()
        if existing:
            user_id = existing["id"]
        else:
            user_id = secrets.token_urlsafe(18)
            connection.execute(
                insert(users).values(
                    id=user_id,
                    email=email,
                    display_name=(display_name or email.split("@", 1)[0])[:80],
                    password_hash=None,
                    avatar_url=(avatar_url or "")[:2048] or None,
                    created_at=datetime.now(timezone.utc),
                )
            )
        connection.execute(
            insert(oauth_accounts).values(
                id=secrets.token_urlsafe(18),
                user_id=user_id,
                provider=provider,
                provider_user_id=str(provider_user_id),
                created_at=datetime.now(timezone.utc),
            )
        )
    return get_user_by_id(user_id)


def save_user_roadmap(user_id, topic, level, roadmap, courses=None):
    engine = _engine()
    if engine is None or not user_id:
        return None
    roadmap_id = secrets.token_urlsafe(18)
    with engine.begin() as connection:
        connection.execute(
            insert(user_roadmaps).values(
                id=roadmap_id,
                user_id=user_id,
                topic=topic[:80],
                level=level[:16],
                roadmap=roadmap,
                courses=json.dumps(courses or [], ensure_ascii=False),
                created_at=datetime.now(timezone.utc),
            )
        )
    return roadmap_id
