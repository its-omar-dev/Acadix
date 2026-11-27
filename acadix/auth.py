"""Password and OAuth authentication routes for Acadix."""
import hmac
import re

from authlib.integrations.flask_client import OAuth
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from acadix.accounts import (
    create_password_user,
    get_or_create_oauth_user,
    get_password_hash,
    get_user_by_email,
)
from acadix.rate_limit import too_many

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def init_auth(app):
    oauth = OAuth(app)
    app.extensions["oauth"] = oauth
    google_id = app.config.get("GOOGLE_CLIENT_ID")
    google_secret = app.config.get("GOOGLE_CLIENT_SECRET")
    app.config["GOOGLE_OAUTH_ENABLED"] = bool(google_id and google_secret)
    if google_id and google_secret:
        oauth.register(
            name="google",
            client_id=google_id,
            client_secret=google_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )

    github_id = app.config.get("GITHUB_CLIENT_ID")
    github_secret = app.config.get("GITHUB_CLIENT_SECRET")
    app.config["GITHUB_OAUTH_ENABLED"] = bool(github_id and github_secret)
    if github_id and github_secret:
        oauth.register(
            name="github",
            client_id=github_id,
            client_secret=github_secret,
            access_token_url="https://github.com/login/oauth/access_token",
            authorize_url="https://github.com/login/oauth/authorize",
            api_base_url="https://api.github.com/",
            client_kwargs={"scope": "read:user user:email"},
        )


def _csrf_token():
    token = session.get("csrf_token")
    if not token:
        import secrets

        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def _valid_csrf():
    supplied = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    return bool(expected and supplied and hmac.compare_digest(supplied, expected))


def _page(mode, error=None):
    configured = current_app.extensions.get("oauth")
    return render_template(
        "auth.html",
        mode=mode,
        error=error,
        csrf_token=_csrf_token(),
        google_enabled=current_app.config.get("GOOGLE_OAUTH_ENABLED", False),
        github_enabled=current_app.config.get("GITHUB_OAUTH_ENABLED", False),
    )


def _login_user(user):
    session.clear()
    session["user_id"] = user["id"]
    _csrf_token()


@auth_bp.get("/register")
def register_page():
    return _page("register")


@auth_bp.post("/register")
def register():
    if not _valid_csrf():
        return _page("register", "انتهت صلاحية الطلب. حدّث الصفحة وحاول مجدداً."), 400
    ip = request.remote_addr or "unknown"
    if too_many("register:" + ip, limit=5, window=3600):
        return _page("register", "محاولات كثيرة. حاول بعد ساعة."), 429
    email = (request.form.get("email") or "").strip().lower()
    name = (request.form.get("display_name") or "").strip()
    password = request.form.get("password") or ""
    if not _EMAIL.fullmatch(email) or len(email) > 254:
        return _page("register", "أدخل بريداً إلكترونياً صحيحاً."), 400
    if len(name) < 2 or len(name) > 80:
        return _page("register", "الاسم يجب أن يكون بين حرفين و80 حرفاً."), 400
    if len(password) < 10 or len(password) > 128:
        return _page("register", "كلمة المرور يجب أن تكون بين 10 و128 حرفاً."), 400
    if current_app.extensions.get("acadix_engine") is None:
        return _page("register", "قاعدة البيانات غير متاحة حالياً. حاول لاحقاً."), 503
    user = create_password_user(email, name, generate_password_hash(password))
    if not user:
        return _page("register", "هذا البريد مسجّل مسبقاً. جرّب تسجيل الدخول."), 409
    _login_user(user)
    return redirect(url_for("main.home"))


@auth_bp.get("/login")
def login_page():
    return _page("login")


@auth_bp.post("/login")
def login():
    if not _valid_csrf():
        return _page("login", "انتهت صلاحية الطلب. حدّث الصفحة وحاول مجدداً."), 400
    ip = request.remote_addr or "unknown"
    if too_many("login:" + ip, limit=8, window=900):
        return _page("login", "محاولات تسجيل دخول كثيرة. حاول بعد 15 دقيقة."), 429
    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    if current_app.extensions.get("acadix_engine") is None:
        return _page("login", "قاعدة البيانات غير متاحة حالياً. حاول لاحقاً."), 503
    password_hash = get_password_hash(email)
    if not password_hash or not check_password_hash(password_hash, password):
        return _page("login", "البريد الإلكتروني أو كلمة المرور غير صحيحة."), 401
    user = get_user_by_email(email)
    _login_user(user)
    return redirect(url_for("main.home"))


@auth_bp.post("/logout")
def logout():
    if not _valid_csrf():
        return "Invalid CSRF token", 400
    session.clear()
    return redirect(url_for("main.home"))


@auth_bp.get("/google")
def google_login():
    client = current_app.extensions.get("oauth")
    if not client or not current_app.config.get("GOOGLE_OAUTH_ENABLED"):
        return _page("login", "تسجيل Google غير مهيأ بعد. أضف مفاتيح OAuth في إعدادات الاستضافة."), 503
    redirect_uri = url_for("auth.google_callback", _external=True, _scheme="https")
    return client.google.authorize_redirect(redirect_uri)


@auth_bp.get("/google/callback")
def google_callback():
    client = current_app.extensions.get("oauth")
    if not client or not client.google:
        return redirect(url_for("auth.login"))
    try:
        token = client.google.authorize_access_token()
        info = token.get("userinfo") or client.google.get("userinfo").json()
        if not info.get("email_verified") or not info.get("sub") or not info.get("email"):
            flash("تعذّر التحقق من بريد حساب Google.", "error")
            return redirect(url_for("auth.login"))
        user = get_or_create_oauth_user(
            "google", info["sub"], info["email"], info.get("name"), info.get("picture")
        )
        if not user:
            return _page("login", "قاعدة البيانات غير متاحة حالياً."), 503
        _login_user(user)
        return redirect(url_for("main.home"))
    except Exception:
        current_app.logger.exception("Google OAuth callback failed")
        return _page("login", "تعذّر تسجيل الدخول عبر Google. حاول مرة أخرى."), 400


@auth_bp.get("/github")
def github_login():
    client = current_app.extensions.get("oauth")
    if not client or not current_app.config.get("GITHUB_OAUTH_ENABLED"):
        return _page("login", "تسجيل GitHub غير مهيأ بعد. أضف مفاتيح OAuth في إعدادات الاستضافة."), 503
    redirect_uri = url_for("auth.github_callback", _external=True, _scheme="https")
    return client.github.authorize_redirect(redirect_uri)


@auth_bp.get("/github/callback")
def github_callback():
    client = current_app.extensions.get("oauth")
    if not client or not client.github:
        return redirect(url_for("auth.login"))
    try:
        client.github.authorize_access_token()
        profile = client.github.get("user").json()
        email = profile.get("email")
        if not email:
            email_rows = client.github.get("user/emails").json()
            email = next(
                (item.get("email") for item in email_rows
                 if item.get("primary") and item.get("verified")),
                None,
            )
        if not email or not profile.get("id"):
            return _page("login", "يجب أن يكون لحساب GitHub بريد إلكتروني موثّق."), 400
        user = get_or_create_oauth_user(
            "github",
            profile["id"],
            email,
            profile.get("name") or profile.get("login"),
            profile.get("avatar_url"),
        )
        if not user:
            return _page("login", "قاعدة البيانات غير متاحة حالياً."), 503
        _login_user(user)
        return redirect(url_for("main.home"))
    except Exception:
        current_app.logger.exception("GitHub OAuth callback failed")
        return _page("login", "تعذّر تسجيل الدخول عبر GitHub. حاول مرة أخرى."), 400
