"""Flask blueprints for the public, sharing, health, and admin endpoints."""
import hmac
import re
import secrets
from urllib.parse import urlsplit

from flask import Blueprint, current_app, jsonify, make_response, render_template, request, session

from acadix.ai.client import all_models_busy, generate_roadmap
from acadix.cache import get_cached, set_cached
from acadix.models import check_database, create_shared_roadmap, get_shared_roadmap, get_topic_stats
from acadix.rate_limit import too_many
from acadix.search import search_learning_links

main_bp = Blueprint("main", __name__)
share_bp = Blueprint("share", __name__)
health_bp = Blueprint("health", __name__)
stats_bp = Blueprint("stats", __name__)

LEVELS = ("مبتدئ", "متوسط", "متقدم")
_SHARE_ID = re.compile(r"^[A-Za-z0-9_-]{12}$")


@main_bp.route("/", methods=["GET", "POST"])
def home():
    searched = False
    courses = []
    roadmap = ""
    topic = ""
    level = "مبتدئ"
    notice = ""
    session.setdefault("csrf_token", secrets.token_urlsafe(32))
    try:
        if request.method == "POST":
            topic = (request.form.get("topic") or "").strip()[:80]
            level = request.form.get("level", "مبتدئ")
            if level not in LEVELS:
                level = "مبتدئ"
            if topic:
                searched = True
                roadmap = get_cached(topic, level)
                if not roadmap:
                    ip = request.remote_addr or "unknown"
                    if too_many(ip):
                        notice = "وصلت إلى حد الخرائط الجديدة هذه الساعة. جرّب موضوعاً من الوسوم الشائعة أو عد لاحقاً."
                    else:
                        roadmap = generate_roadmap(topic, level)
                        if roadmap:
                            set_cached(topic, level, roadmap)
                        elif all_models_busy():
                            notice = "الخدمة مشغولة الآن بسبب كثرة الطلبات. جرّب بعد دقائق."
                if roadmap:
                    courses = search_learning_links(topic)
    except Exception:
        current_app.logger.exception("Home request failed")
        roadmap = ""
        searched = True

    payload = {
        "searched": searched,
        "topic": topic,
        "level": level,
        "roadmap": roadmap or "",
        "courses": courses,
        "notice": notice,
        "csrf_token": session["csrf_token"],
        "share_enabled": bool(current_app.config.get("DATABASE_URL")),
    }
    return render_template("index.html", payload=payload)


@share_bp.post("/share")
def create_share():
    if not request.is_json:
        return jsonify(error="Content-Type must be application/json"), 415

    supplied_token = request.headers.get("X-CSRF-Token", "")
    expected_token = session.get("csrf_token", "")
    if not expected_token or not hmac.compare_digest(supplied_token, expected_token):
        return jsonify(error="Invalid CSRF token"), 403

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Invalid request body"), 400

    topic = data.get("topic")
    level = data.get("level")
    roadmap = data.get("roadmap")
    courses = data.get("courses", [])
    if not isinstance(topic, str) or not topic.strip() or len(topic) > 80:
        return jsonify(error="Invalid topic"), 400
    if level not in LEVELS:
        return jsonify(error="Invalid level"), 400
    if not isinstance(roadmap, str) or not roadmap.strip() or len(roadmap) > 40000:
        return jsonify(error="Invalid roadmap"), 400
    if not isinstance(courses, list) or len(courses) > 12:
        return jsonify(error="Invalid courses"), 400

    safe_courses = []
    for course in courses:
        if not isinstance(course, dict):
            return jsonify(error="Invalid course entry"), 400
        title, platform, link = course.get("title"), course.get("platform"), course.get("link")
        if not all(isinstance(value, str) for value in (title, platform, link)):
            return jsonify(error="Invalid course entry"), 400
        parsed = urlsplit(link)
        if (
            parsed.scheme not in {"https", "http"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
        ):
            return jsonify(error="Invalid course URL"), 400
        safe_courses.append(
            {"title": title[:300], "platform": platform[:100], "link": link[:2048]}
        )

    try:
        share_id = create_shared_roadmap(topic.strip(), level, roadmap, safe_courses)
    except Exception:
        current_app.logger.exception("Share persistence failed")
        return jsonify(error="Sharing is temporarily unavailable"), 503
    if not share_id:
        return jsonify(error="Sharing requires DATABASE_URL"), 503
    return jsonify(id=share_id, url=f"/r/{share_id}"), 201


@share_bp.get("/r/<share_id>")
def shared_roadmap(share_id):
    if not _SHARE_ID.fullmatch(share_id):
        return make_response("Not found", 404)
    try:
        data = get_shared_roadmap(share_id)
    except Exception:
        current_app.logger.exception("Shared roadmap lookup failed")
        return make_response("Sharing is temporarily unavailable", 503)
    if not data:
        return make_response("Not found", 404)
    session.setdefault("csrf_token", secrets.token_urlsafe(32))
    payload = {
        "searched": True,
        **data,
        "notice": "",
        "csrf_token": session["csrf_token"],
        "share_enabled": bool(current_app.config.get("DATABASE_URL")),
    }
    return render_template("index.html", payload=payload)


@health_bp.get("/health")
def health():
    if current_app.config.get("DATABASE_URL"):
        try:
            if not check_database():
                return "database unavailable", 503
        except Exception:
            current_app.logger.exception("Database health check failed")
            return "database unavailable", 503
    return "ok"


@stats_bp.get("/stats")
def stats():
    configured_token = current_app.config.get("ADMIN_TOKEN", "")
    if not configured_token:
        return make_response("Not found", 404)
    supplied = request.headers.get("Authorization", "")
    if supplied.startswith("Bearer "):
        supplied = supplied[7:]
    else:
        supplied = request.args.get("token", "")
    if not supplied or not hmac.compare_digest(supplied, configured_token):
        return make_response("Unauthorized", 401)
    try:
        topics = get_topic_stats()
    except Exception:
        current_app.logger.exception("Stats query failed")
        return jsonify(error="Statistics are temporarily unavailable"), 503
    if topics is None:
        return jsonify(error="Statistics require DATABASE_URL"), 503
    return jsonify(topics=topics)
