"""Flask blueprints for the public, sharing, health, and admin endpoints."""
import hmac
import json
import re
import secrets
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    make_response,
    render_template,
    request,
    session,
    stream_with_context,
)

from acadix.ai.client import all_models_busy, generate_roadmap, stream_roadmap
from acadix.ai.validate import validate_stage
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



def _sse(event, payload):
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"


def _stream_courses(topic):
    try:
        return search_learning_links(topic)
    except Exception:
        current_app.logger.exception("Learning link search failed during streaming")
        return []


def _stages_to_markdown(stages):
    summary = stages[1].get("summary") or "خارطة طريق تعليمية مخصصة لهذا المجال."
    lines = ["## الملخص التنفيذي", f"- {summary}"]
    for number in range(1, 5):
        stage = stages[number]
        lines.extend(
            [
                "",
                f"## المرحلة {number}: {stage['name']}",
                stage.get("description", ""),
            ]
        )
        lines.extend(f"- [ ] {task}" for task in stage["tasks"])
    return "\n".join(lines)


@main_bp.post("/generate/stream")
def generate_stream():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Invalid request body"), 400

    topic = data.get("topic")
    level = data.get("level", "مبتدئ")
    if not isinstance(topic, str) or not topic.strip() or len(topic) > 80:
        return jsonify(error="Invalid topic"), 400
    topic = topic.strip()
    if level not in LEVELS:
        return jsonify(error="Invalid level"), 400

    cached = get_cached(topic, level)
    if not cached:
        ip = request.remote_addr or "unknown"
        if too_many(ip):
            return jsonify(error="وصلت إلى حد الخرائط الجديدة هذه الساعة."), 429

    @stream_with_context
    def generate_events():
        if cached:
            yield _sse(
                "complete",
                {"roadmap": cached, "topic": topic, "level": level,
                 "courses": _stream_courses(topic)},
            )
            return

        stages = {}
        buffer = ""

        def accept_line(line):
            try:
                item = json.loads(line)
            except (TypeError, ValueError):
                return None
            if not validate_stage(item) or item["stage"] in stages:
                return None
            stages[item["stage"]] = item
            return item

        try:
            for delta in stream_roadmap(topic, level):
                buffer += delta
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    item = accept_line(line.strip())
                    if item:
                        yield _sse("stage", item)
            if buffer.strip():
                item = accept_line(buffer.strip())
                if item:
                    yield _sse("stage", item)
        except Exception:
            current_app.logger.exception("Roadmap streaming failed")

        if len(stages) == 4:
            roadmap = _stages_to_markdown(stages)
            set_cached(topic, level, roadmap)
            courses = _stream_courses(topic)
            yield _sse(
                "complete",
                {"roadmap": roadmap, "topic": topic, "level": level, "courses": courses},
            )
            return

        # Discard partial stages in the client before switching to the legacy response.
        try:
            roadmap = generate_roadmap(topic, level)
        except Exception:
            current_app.logger.exception("Legacy roadmap fallback failed")
            roadmap = None
        if roadmap:
            set_cached(topic, level, roadmap)
            yield _sse(
                "fallback",
                {"roadmap": roadmap, "topic": topic, "level": level,
                 "courses": _stream_courses(topic)},
            )
        else:
            yield _sse("error", {"message": "تعذّر توليد الخارطة الآن. حاول مجدداً."})

    response = Response(generate_events(), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


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
        if len(link) > 2048:
            return jsonify(error="Invalid course URL"), 400
        try:
            parsed = urlsplit(link)
        except ValueError:
            return jsonify(error="Invalid course URL"), 400
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
