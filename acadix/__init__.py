"""Acadix application factory."""
from flask import Flask, request

from acadix.config import Settings


def create_app(test_config=None):
    app = Flask(__name__, template_folder="../templates")
    app.config.update(Settings.from_env())
    if test_config:
        app.config.update(test_config)

    # Import account tables before create_all so new tables are created alongside existing data.
    from acadix import accounts  # noqa: F401
    from acadix.accounts import get_user_by_id
    from acadix.auth import auth_bp, init_auth
    from acadix.models import init_db
    from acadix.routes import health_bp, main_bp, share_bp, stats_bp

    init_db(app)
    init_auth(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(share_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(stats_bp)

    @app.context_processor
    def inject_current_user():
        return {"current_user": get_user_by_id(session_user_id())}

    def session_user_id():
        from flask import session
        return session.get("user_id")

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; connect-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'self'; "
            "frame-ancestors 'none'; form-action 'self'",
        )
        if request.is_secure:
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    return app
