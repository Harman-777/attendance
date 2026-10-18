import os
import hmac
import html
import time
import hashlib
from datetime import timedelta
from functools import wraps
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, send_file, make_response
from portal_client import PortalClient
from notifier import (
    save_snapshot,
    load_snapshot,
    detect_new_absents,
    send_absent_email,
    send_web_push,
    VAPID_PUBLIC_KEY
)
from db_client import (
    sync_user_to_supabase,
    log_login_activity,
    record_login_event,
    get_user_record,
    save_push_or_email_prefs,
    set_vault_password,
    encrypt_password,
    decrypt_password,
    is_valid_student_id,
    submit_feedback,
    get_user_feedback,
    get_admin_dashboard_data,
    admin_update_feedback,
    admin_manage_user,
    create_admin_broadcast,
    get_user_announcements,
    admin_delete_feedback
)

base_dir = os.path.dirname(os.path.abspath(__file__))
possible_template_dirs = [
    os.path.join(os.getcwd(), "templates"),
    os.path.join(base_dir, "templates"),
    os.path.join(base_dir, "..", "templates"),
]
template_dir = next((d for d in possible_template_dirs if os.path.isdir(d)), os.path.join(base_dir, "templates"))

possible_static_dirs = [
    os.path.join(os.getcwd(), "static"),
    os.path.join(base_dir, "static"),
    os.path.join(base_dir, "..", "static"),
]
static_dir = next((d for d in possible_static_dirs if os.path.isdir(d)), os.path.join(base_dir, "static"))

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)

# 1. Deterministic Serverless Secret Key (Prevents cold-start invalidation on Vercel without predictable fallbacks)
secret_key = os.environ.get("SECRET_KEY", "").strip()
if not secret_key:
    enc_k = os.environ.get("ENCRYPTION_KEY", "").strip()
    sup_k = os.environ.get("SUPABASE_KEY", "").strip()
    seed = (enc_k + sup_k).encode("utf-8")
    secret_key = hashlib.sha256(seed).hexdigest()
app.secret_key = secret_key

# 2. Harden Session Cookies against XSS, Hijacking & CSRF
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("VERCEL")),
    PERMANENT_SESSION_LIFETIME=timedelta(days=90)
)


# 3. Encrypted Session Password Helpers (Prevents plaintext passwords in base64 cookies)
def set_session_password(plain_password: str):
    if plain_password:
        session["enc_password"] = encrypt_password(plain_password)
    else:
        session.pop("enc_password", None)
    session.pop("password", None)


def get_session_password() -> str:
    enc = session.get("enc_password")
    if enc:
        plain = decrypt_password(enc)
        if plain:
            return plain
    return session.get("password", "") or ""


# 4. Unspoofable Client IP Extraction on Vercel
def get_trusted_client_ip() -> str:
    # x-vercel-forwarded-for is set by Vercel's edge network and cannot be spoofed by incoming clients
    vercel_ip = request.headers.get("x-vercel-forwarded-for")
    if vercel_ip:
        return vercel_ip.split(",")[0].strip()
    return (request.remote_addr or "127.0.0.1").split(",")[0].strip()


# 5. Brute-Force Rate Limiter (Tracks failed logins per IP with optional scope)
_FAILED_LOGINS = {}  # { key: [timestamp1, timestamp2, ...] }


def _rate_limit_key(ip: str, scope: str = "") -> str:
    return f"{scope}:{ip}" if scope else ip


def is_ip_rate_limited(ip: str, max_attempts: int = 5, window_sec: int = 600, scope: str = "") -> bool:
    key = _rate_limit_key(ip, scope)
    now = time.time()
    attempts = [t for t in _FAILED_LOGINS.get(key, []) if now - t < window_sec]
    _FAILED_LOGINS[key] = attempts
    return len(attempts) >= max_attempts


def record_failed_login(ip: str, scope: str = ""):
    key = _rate_limit_key(ip, scope)
    now = time.time()
    _FAILED_LOGINS.setdefault(key, []).append(now)


def clear_failed_logins(ip: str, scope: str = ""):
    if scope:
        _FAILED_LOGINS.pop(_rate_limit_key(ip, scope), None)
    else:
        _FAILED_LOGINS.pop(ip, None)
        for s in ["admin", "student"]:
            _FAILED_LOGINS.pop(f"{s}:{ip}", None)


# 6. Global CSRF Origin Protection on POST Requests
@app.before_request
def csrf_origin_protect():
    if request.method == "POST":
        origin = request.headers.get("Origin") or request.headers.get("Referer")
        if origin:
            parsed = urlparse(origin)
            if parsed.netloc and parsed.netloc != request.host:
                return jsonify({"ok": False, "message": "CSRF Origin mismatch blocked."}), 403


# 7. Inject Production Security Headers on Every Response
@app.after_request
def apply_security_headers(response):
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    client_ip = get_trusted_client_ip()

    # 1. 1-Click Persistent Login: If user is already authenticated, jump straight to dashboard
    if request.method == "GET":
        if session.get("student_id") and get_session_password():
            return redirect(url_for("dashboard"))

    if request.method == "POST":
        if is_ip_rate_limited(client_ip, max_attempts=10, window_sec=600, scope="student"):
            return render_template(
                "login.html",
                error="Too many failed attempts. Your IP is locked out for 10 minutes."
            ), 429

        student_id = request.form.get("student_id", "").strip()
        password = request.form.get("password", "").strip()
        save_vault = request.form.get("save_vault", "1") != "0"
        session["save_vault"] = save_vault

        if not is_valid_student_id(student_id):
            return render_template("login.html", error="Invalid Student ID format.")

        # 1. Fast Path (0.4s Instant Login): If user enabled Cloud Vault in Supabase, verify instantly!
        db_user = get_user_record(student_id)
        if db_user and db_user.get("encrypted_password") and db_user.get("cached_profile"):
            if decrypt_password(db_user["encrypted_password"]) == password:
                clear_failed_logins(client_ip, scope="student")
                session.permanent = True
                session["student_id"] = student_id
                set_session_password(password)
                session["just_logged_in"] = True
                return redirect(url_for("dashboard"))

        # 2. Standard Path: Authenticate against college portal and save cookies to avoid double login
        client = PortalClient(student_id, password)
        success, err = client.authenticate()

        if not success:
            record_failed_login(client_ip, scope="student")
            cached = (db_user.get("cached_profile") if db_user else None) or load_snapshot(student_id)
            if cached and "Portal unreachable" in (err or ""):
                clear_failed_logins(client_ip, scope="student")
                session.permanent = True
                session["student_id"] = student_id
                set_session_password(password)
                session["just_logged_in"] = True
                return redirect(url_for("dashboard"))
            error = err
        else:
            clear_failed_logins(client_ip, scope="student")
            session.permanent = True
            session["student_id"] = student_id
            set_session_password(password)
            session["portal_cookies"] = client.get_cookies()
            session["just_logged_in"] = True
            return redirect(url_for("dashboard"))

    return render_template("login.html", error=error)


@app.route("/dashboard")
def dashboard():
    student_id = session.get("student_id")
    password = get_session_password()
    if not student_id or not password:
        return redirect(url_for("login"))

    is_login_event = session.pop("just_logged_in", False)
    db_user = get_user_record(student_id)
    save_vault = session.get("save_vault", True)

    # Cloud Password Vault: Automatically encrypt & save password if enabled (default ON)
    if save_vault and password:
        if not db_user or not db_user.get("encrypted_password"):
            set_vault_password(student_id, plain_password=password, enable=True)
            db_user = get_user_record(student_id)

    vault_enabled = bool(db_user and db_user.get("encrypted_password"))

    data = None
    needs_background_sync = False

    # 1. Instant 0.4s Load if we have a cached snapshot in Supabase or local cache
    if db_user and db_user.get("cached_profile") and db_user["cached_profile"].get("subjects"):
        data = db_user["cached_profile"]
        needs_background_sync = True
    else:
        local_cache = load_snapshot(student_id)
        if local_cache and local_cache.get("subjects"):
            data = local_cache
            needs_background_sync = True

    # 2. First-Time User Cold Start: Fetch ONLY Attendance first (~2 seconds)
    if not data:
        client = PortalClient(student_id, password, cookies=session.get("portal_cookies"))
        data, err = client.get_full_profile(fast_mode=True)
        if not data:
            return redirect(url_for("login"))
        session["portal_cookies"] = client.get_cookies()
        sync_user_to_supabase(student_id, password, data, is_login_event=False, save_vault=save_vault)
        save_snapshot(student_id, data)
        needs_background_sync = True

    if is_login_event:
        ua = request.headers.get("User-Agent", "")
        ip = get_trusted_client_ip()
        record_login_event(student_id, (data.get("student_name") if data else "Student") or "Student", ua, ip)

    total_present = sum(s["present"] for s in data["subjects"])
    total_classes = sum(s["total"] for s in data["subjects"])
    overall_pct = (total_present / total_classes * 100) if total_classes > 0 else 0

    danger_subjects = [
        s for s in data["subjects"]
        if s.get("danger_level") in ("critical", "warning")
    ]

    user_feedback = get_user_feedback(student_id)
    admin_announcements = get_user_announcements(student_id)

    return render_template(
        "dashboard.html",
        data=data,
        new_absents=[],
        vault_enabled=vault_enabled,
        needs_background_sync=needs_background_sync,
        danger_subjects=danger_subjects,
        overall_present=total_present,
        overall_classes=total_classes,
        overall_pct=round(overall_pct, 2),
        user_feedback=user_feedback,
        admin_announcements=admin_announcements
    )


@app.route("/api/background-sync", methods=["POST"])
def api_background_sync():
    student_id = session.get("student_id")
    password = get_session_password()
    if not student_id or not password:
        return jsonify({"ok": False, "message": "Not logged in."}), 401

    client = PortalClient(student_id, password, cookies=session.get("portal_cookies"))
    data, err = client.get_full_profile(fast_mode=False)
    if not data:
        return jsonify({"ok": False, "message": err or "Portal offline"})

    session["portal_cookies"] = client.get_cookies()
    save_vault = session.get("save_vault", True)
    new_absents = sync_user_to_supabase(student_id, password, data, is_login_event=False, save_vault=save_vault)
    save_snapshot(student_id, data)

    total_p = sum(s["present"] for s in data["subjects"])
    total_t = sum(s["total"] for s in data["subjects"])
    overall_pct = round((total_p / total_t * 100), 2) if total_t > 0 else 0.0

    return jsonify({
        "ok": True,
        "last_synced": data.get("last_synced"),
        "student_name": data.get("student_name"),
        "overall_pct": overall_pct,
        "overall_present": total_p,
        "overall_classes": total_t,
        "subjects": data.get("subjects", []),
        "today_attendance": data.get("today_attendance", []),
        "calendar_records": data.get("calendar_records", []),
        "new_absents": new_absents,
        "partial_was_upgraded": True
    })


@app.route("/api/toggle-vault", methods=["POST"])
def api_toggle_vault():
    student_id = session.get("student_id")
    password = get_session_password()
    if not student_id or not password:
        return jsonify({"ok": False, "message": "Not logged in."}), 401

    req = request.get_json() or {}
    enable = bool(req.get("enable", True))
    ok, msg, enc_str = set_vault_password(student_id, plain_password=password, enable=enable)
    return jsonify({
        "ok": ok,
        "vault_enabled": bool(enc_str),
        "message": msg
    })


@app.route("/api/change-password", methods=["POST"])
def api_change_password():
    student_id = session.get("student_id")
    password = get_session_password()
    if not student_id or not password:
        return jsonify({"ok": False, "message": "Not logged in."}), 401

    req = request.get_json() or {}
    old_pw = req.get("old_password", "").strip()
    new_pw = req.get("new_password", "").strip()
    conf_pw = req.get("confirm_password", "").strip()

    if not old_pw or not new_pw or new_pw != conf_pw:
        return jsonify({"ok": False, "message": "New passwords do not match or are empty."})

    client = PortalClient(student_id, password, cookies=session.get("portal_cookies"))
    ok, msg = client.change_password(old_pw, new_pw, conf_pw)
    if ok:
        set_session_password(new_pw)
    return jsonify({"ok": ok, "message": msg})


@app.route("/api/save-subscription", methods=["POST"])
def api_save_subscription():
    student_id = session.get("student_id")
    if not student_id:
        return jsonify({"ok": False, "message": "Not logged in."}), 401

    req = request.get_json() or {}
    email = req.get("email")
    push_sub = req.get("subscription")
    ok = save_push_or_email_prefs(student_id, email=email, push_sub=push_sub, auto_sync=True)
    return jsonify({
        "ok": ok,
        "message": "Saved to Supabase! Background auto-sync & alerts are now active." if ok else "Could not save to Supabase."
    })


@app.route("/api/send-alert", methods=["POST"])
def api_send_alert():
    req = request.get_json() or {}
    to_email = req.get("email", "").strip()
    smtp_user = req.get("smtp_user", "").strip()
    smtp_pass = req.get("smtp_pass", "").strip()
    student_id = session.get("student_id")

    if student_id and to_email:
        save_push_or_email_prefs(student_id, email=to_email, auto_sync=True)

    cached = load_snapshot(student_id) if student_id else None
    if not cached and student_id:
        db_user = get_user_record(student_id)
        if db_user:
            cached = db_user.get("cached_profile")

    if not cached:
        return jsonify({"ok": False, "message": "No attendance snapshot found."})

    absents = [r for r in cached.get("calendar_records", []) if r.get("status") == "ABSENT"][-3:]
    if not absents:
        absents = [{"subject": "Sample Test Subject", "date": cached.get("today_date", "Today"), "status": "ABSENT"}]

    ok, msg = send_absent_email(to_email, cached.get("student_name", "Student"), absents, smtp_user, smtp_pass)
    return jsonify({"ok": ok, "message": msg})


@app.route("/sw.js")
def service_worker():
    return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")


@app.route("/api/vapid-public-key")
def api_vapid_public_key():
    return jsonify({"publicKey": VAPID_PUBLIC_KEY})


@app.route("/api/test-push", methods=["POST"])
def api_test_push():
    student_id = session.get("student_id")
    if not student_id:
        return jsonify({"ok": False, "message": "Not logged in."}), 401

    req = request.get_json() or {}
    sub = req.get("subscription")
    if not sub:
        return jsonify({"ok": False, "message": "No push subscription provided."})

    save_push_or_email_prefs(student_id, push_sub=sub, auto_sync=True)
    ok, msg = send_web_push(
        sub,
        "⚡ Ultra Portal Lock-Screen Push Active!",
        "Your device is now linked to Supabase. Any new ABSENT mark will alert you automatically!"
    )
    return jsonify({"ok": ok, "message": msg})


# ==================== USER FEEDBACK ENDPOINT ====================

@app.route("/api/submit-feedback", methods=["POST"])
def api_submit_feedback():
    student_id = session.get("student_id")
    if not student_id:
        return jsonify({"ok": False, "message": "Not logged in."}), 401

    req = request.get_json() or {}
    category = html.escape((req.get("category") or "Suggestion").strip())
    rating = req.get("rating", 5)
    message = html.escape((req.get("message") or "").strip())

    if len(message) < 5:
        return jsonify({"ok": False, "message": "Please enter at least 5 characters."})

    db_user = get_user_record(student_id)
    student_name = (db_user.get("student_name") if db_user else None) or "User"

    ok, msg = submit_feedback(student_id, student_name, category, rating, message)
    return jsonify({"ok": ok, "message": msg})


# ==================== DEDICATED ADMIN PORTAL ====================

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "master_harman").strip()
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "").strip()


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("is_ultra_admin"):
            return redirect(url_for("admin_login"))
        session.permanent = True
        return f(*args, **kwargs)
    return decorated


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("is_ultra_admin"):
        return redirect(url_for("admin_dashboard"))

    error = None
    client_ip = get_trusted_client_ip()

    if request.method == "POST":
        if is_ip_rate_limited(client_ip, max_attempts=5, window_sec=600, scope="admin"):
            return render_template(
                "admin_login.html",
                error="Too many failed attempts. Your IP is locked out for 10 minutes."
            ), 429

        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not ADMIN_PASSWORD:
            error = "ADMIN_PASSWORD is not set in environment variables."
        elif hmac.compare_digest(username, ADMIN_USERNAME) and hmac.compare_digest(password, ADMIN_PASSWORD):
            clear_failed_logins(client_ip, scope="admin")
            session.permanent = True
            session["is_ultra_admin"] = True
            return redirect(url_for("admin_dashboard"))
        else:
            record_failed_login(client_ip, scope="admin")
            time.sleep(1.2)  # Throttle automated scripts across serverless cold starts
            error = "Invalid Administrator Credentials."

    return render_template("admin_login.html", error=error)


def get_admin_dashboard_context():
    admin_data = get_admin_dashboard_data()
    users = admin_data["users"]
    feedback = admin_data["feedback"]
    logs = admin_data["logs"]

    stats = {
        "total_users": len(users),
        "vault_users": sum(1 for u in users if u.get("encrypted_password")),
        "push_users": sum(1 for u in users if u.get("push_subscription")),
        "pending_feedback": sum(1 for f in feedback if f.get("status") == "Pending" and f.get("category") != "ADMIN_BROADCAST"),
        "total_logins": sum((u.get("login_count") or 1) for u in users)
    }
    return {"users": users, "feedback": feedback, "logs": logs, "stats": stats}


@app.route("/admin")
@admin_required
def admin_dashboard():
    ctx = get_admin_dashboard_context()
    return render_template("admin.html", **ctx)


@app.route("/admin/view/<student_id>")
@admin_required
def admin_view_student(student_id):
    student_id = (student_id or "").strip()
    if not is_valid_student_id(student_id):
        ctx = get_admin_dashboard_context()
        return render_template(
            "admin.html",
            error=f"Invalid student ID format: {html.escape(student_id)}",
            **ctx
        )

    db_user = get_user_record(student_id)

    # Optional: Live force sync if admin requests fresh scrape via ?live=1
    if request.args.get("live") == "1" and db_user and db_user.get("encrypted_password"):
        plain_pw = decrypt_password(db_user["encrypted_password"])
        if plain_pw:
            client = PortalClient(student_id, plain_pw)
            fresh_data, _ = client.get_full_profile(fast_mode=False)
            if fresh_data:
                sync_user_to_supabase(student_id, plain_pw, fresh_data, is_login_event=False)
                save_snapshot(student_id, fresh_data)
                db_user = get_user_record(student_id)

    data = (db_user.get("cached_profile") if db_user else None) or load_snapshot(student_id)
    cached_prof_details = data.get("profile", {}).get("details", []) if data else []
    if (not data or not data.get("subjects") or len(cached_prof_details) < 4) and db_user and db_user.get("encrypted_password"):
        plain_pw = decrypt_password(db_user["encrypted_password"])
        if plain_pw:
            client = PortalClient(student_id, plain_pw)
            fresh_data, _ = client.get_full_profile(fast_mode=False)
            if fresh_data:
                data = fresh_data
                sync_user_to_supabase(student_id, plain_pw, data, is_login_event=False)
                save_snapshot(student_id, data)

    if not data or not data.get("subjects"):
        ctx = get_admin_dashboard_context()
        return render_template(
            "admin.html",
            error=f"No synced attendance records found for student {student_id}.",
            **ctx
        )

    total_present = sum(s.get("present", 0) for s in data["subjects"])
    total_classes = sum(s.get("total", 0) for s in data["subjects"])
    overall_pct = (total_present / total_classes * 100) if total_classes > 0 else 0

    danger_subjects = [
        s for s in data["subjects"]
        if s.get("danger_level") in ("critical", "warning")
    ]

    user_feedback = get_user_feedback(student_id)
    admin_announcements = get_user_announcements(student_id)
    vault_enabled = bool(db_user and db_user.get("encrypted_password"))

    return render_template(
        "dashboard.html",
        data=data,
        new_absents=[],
        vault_enabled=vault_enabled,
        needs_background_sync=False,
        danger_subjects=danger_subjects,
        overall_present=total_present,
        overall_classes=total_classes,
        overall_pct=round(overall_pct, 2),
        user_feedback=user_feedback,
        admin_announcements=admin_announcements,
        is_admin_view=True,
        viewed_student_id=student_id
    )


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_ultra_admin", None)
    return redirect(url_for("admin_login"))


@app.route("/api/admin/reply-feedback", methods=["POST"])
@admin_required
def api_admin_reply_feedback():
    req = request.get_json() or {}
    fb_id = req.get("id")
    status = req.get("status", "Reviewed")
    reply = (req.get("admin_reply") or "").strip()

    ok, updated_row = admin_update_feedback(fb_id, status, reply)
    if ok and updated_row and reply:
        target_id = updated_row.get("student_id")
        u_rec = get_user_record(target_id)
        if u_rec and u_rec.get("push_subscription"):
            send_web_push(
                u_rec["push_subscription"],
                title=f"💬 Developer Replied to Your {updated_row.get('category', 'Feedback')}",
                body=reply[:120],
                url="/dashboard"
            )
    return jsonify({"ok": ok, "message": "Reply saved & user notified!" if ok else "Failed to update feedback."})


@app.route("/api/admin/delete-feedback", methods=["POST"])
@admin_required
def api_admin_delete_feedback():
    req = request.get_json() or {}
    fb_id = req.get("id")
    ok = admin_delete_feedback(fb_id)
    return jsonify({"ok": ok, "message": "Deleted!" if ok else "Could not delete."})


@app.route("/api/admin/broadcast-push", methods=["POST"])
@admin_required
def api_admin_broadcast_push():
    req = request.get_json() or {}
    target = (req.get("target") or "all").strip()
    title = (req.get("title") or "⚡ Ultra Portal Announcement").strip()
    body = (req.get("body") or "").strip()

    if not body:
        return jsonify({"ok": False, "message": "Notification body cannot be empty."})

    # 1. Save in-app announcement so users see it inside their dashboard
    create_admin_broadcast(target, title, body)

    # 2. Also fire OS/Browser Web Push to all subscribed devices
    admin_data = get_admin_dashboard_data()
    sent_count = 0
    for u in admin_data["users"]:
        if target != "all" and u.get("student_id") != target:
            continue
        sub = u.get("push_subscription")
        if sub:
            ok, _ = send_web_push(sub, title=title, body=body, url="/dashboard")
            if ok:
                sent_count += 1

    return jsonify({
        "ok": True,
        "message": f"Saved to Dashboards & pushed to {sent_count} lock-screen device(s)!"
    })


@app.route("/api/admin/user-action", methods=["POST"])
@admin_required
def api_admin_user_action():
    req = request.get_json() or {}
    student_id = (req.get("student_id") or "").strip()
    action = (req.get("action") or "").strip()

    if not is_valid_student_id(student_id):
        return jsonify({"ok": False, "message": "Invalid student ID."}), 400

    if action == "force_sync":
        u = get_user_record(student_id)
        if not u or not u.get("encrypted_password"):
            return jsonify({"ok": False, "message": "User does not have an encrypted password in Vault."})
        plain_pw = decrypt_password(u["encrypted_password"])
        if not plain_pw:
            return jsonify({
                "ok": False,
                "message": "Could not decrypt Vault password (key changed). Click 'Wipe Vault' and re-save it."
            })
        client = PortalClient(student_id, plain_pw)
        data, err = client.get_full_profile(fast_mode=False)
        if not data:
            return jsonify({"ok": False, "message": f"Sync failed: {err}"})
        sync_user_to_supabase(student_id, plain_pw, data, is_login_event=False)
        return jsonify({"ok": True, "message": f"✔ Live portal sync completed for {student_id}!"})

    ok, msg = admin_manage_user(student_id, action)
    return jsonify({"ok": ok, "message": msg})


@app.route("/logout")
def logout():
    for key in ["student_id", "password", "enc_password", "portal_cookies", "just_logged_in", "save_vault"]:
        session.pop(key, None)
    return redirect(url_for("login"))


@app.route("/.well-known/assetlinks.json")
def assetlinks():
    # Android Digital Asset Links standard for WebAPK / Trusted Web Activity verification
    # Package: in.agclms.ultraportal
    assetlinks_data = [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": "in.agclms.ultraportal",
                "sha256_cert_fingerprints": [
                    "FC:85:E3:2F:2F:FF:15:1C:CE:71:07:7F:D4:E5:FA:75:3E:17:03:2C:D8:38:77:87:68:68:79:23:50:AC:20:0A",
                    "FA:C6:17:45:DC:09:03:78:6F:B9:ED:E6:2A:96:2B:39:9F:73:48:F0:BB:6F:89:9B:83:32:66:75:91:03:3B:9C"
                ]
            }
        }
    ]
    return jsonify(assetlinks_data)


@app.route("/download/UltraPortal.apk")
def download_apk():
    apk_path = os.path.join(static_dir, "apk", "UltraPortal.apk")
    if os.path.isfile(apk_path):
        resp = make_response(send_file(
            apk_path,
            as_attachment=True,
            download_name="UltraPortal.apk",
            mimetype="application/vnd.android.package-archive"
        ))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
    return redirect("https://github.com/Harman-777/attendance/releases/latest/download/UltraPortal.apk")


@app.route("/api/app-version")
def api_app_version():
    return jsonify({
        "latest_version": "2.2",
        "version_code": 4,
        "release_date": "18 Oct 2026",
        "download_url": "/download/UltraPortal.apk",
        "changelog": [
            "Native Android DownloadListener & 1-Click Update system",
            "Universal PWA WebAPK installability with service worker fetch handler",
            "Direct WhatsApp mobile app integration (bypasses browser)",
            "Native Android Share Sheet drawer with direct APK download link",
            "Full 15-field official student profile sync for all students"
        ]
    })


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)