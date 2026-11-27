"""Acadix application factory."""
from flask import Flask

from acadix.config import Settings


def create_app(test_config=None):
    app = Flask(__name__, template_folder="../templates")
    app.config.update(Settings.from_env())
    if test_config:
        app.config.update(test_config)

    from acadix.models import init_db
    from acadix.routes import health_bp, main_bp, share_bp, stats_bp

    init_db(app)
    app.register_blueprint(main_bp)
    app.register_blueprint(share_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(stats_bp)

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
        return response

    return app
