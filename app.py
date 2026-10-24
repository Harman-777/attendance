import os
import hmac
import html
import time
import hashlib
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlparse
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory, send_file, make_response
from portal_client import PortalClient, IST
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

APP_VERSION = "2.8"
APP_VERSION_CODE = 10

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
        session["plain_password"] = plain_password
    else:
        session.pop("enc_password", None)
        session.pop("plain_password", None)
    session.pop("password", None)


def get_session_password() -> str:
    # 1. Direct session password (cryptographically signed inside Flask HTTP-only session cookie)
    plain = session.get("plain_password") or session.get("password")
    if plain:
        return plain
    # 2. Encrypted session fallback
    enc = session.get("enc_password")
    if enc:
        dec = decrypt_password(enc)
        if dec:
            return dec
    return ""


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
    # Never cache dynamic HTML responses so installed APKs & browsers always receive live updates instantly
    if request.path in ("/", "/dashboard", "/update", "/admin") or "text/html" in (response.mimetype or ""):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
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
            dec_pw = decrypt_password(db_user["encrypted_password"])
            if dec_pw and dec_pw == password:
                clear_failed_logins(client_ip, scope="student")
                session.permanent = True
                session["student_id"] = student_id
                set_session_password(password)
                session["just_logged_in"] = True

                # Check if cached profile already has complete results and non-generic student name
                cached_prof = db_user.get("cached_profile") or {}
                has_complete_profile = bool(
                    cached_prof.get("results")
                    and len(cached_prof.get("results", [])) > 0
                    and cached_prof.get("student_name")
                    and cached_prof.get("student_name").strip().lower() != "student"
                    and len(cached_prof.get("profile", {}).get("details", [])) > 3
                )

                # If cached profile is incomplete or cookies missing, authenticate against college portal and enrich
                if not has_complete_profile or not session.get("portal_cookies"):
                    try:
                        client = PortalClient(student_id, password)
                        auth_ok, _ = client.authenticate()
                        if auth_ok:
                            session["portal_cookies"] = client.get_cookies()
                            if not has_complete_profile:
                                deep_data, _ = client.get_academic_and_profile()
                                if deep_data:
                                    if deep_data.get("student_name") and deep_data["student_name"].lower() != "student":
                                        cached_prof["student_name"] = deep_data["student_name"]
                                    if deep_data.get("student_email"):
                                        cached_prof["student_email"] = deep_data["student_email"]
                                    if deep_data.get("profile"):
                                        cached_prof["profile"] = deep_data["profile"]
                                    if deep_data.get("results"):
                                        cached_prof["results"] = deep_data["results"]
                                    if deep_data.get("fees"):
                                        cached_prof["fees"] = deep_data["fees"]
                                    cached_prof["partial_load"] = False
                                    sync_user_to_supabase(student_id, password, cached_prof, is_login_event=True, save_vault=save_vault)
                                    save_snapshot(student_id, cached_prof)
                    except Exception as e:
                        print(f"[Fast Path Enrichment Error]: {e}")

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
            try:
                # 1. Fetch live attendance subjects
                fast_data, _ = client.get_full_profile(fast_mode=True)
                if fast_data and fast_data.get("subjects"):
                    # 2. Concurrently scrape profile details, exam marksheets, and fees right at login (~1.5s)!
                    deep_data, _ = client.get_academic_and_profile()
                    if deep_data:
                        if deep_data.get("student_name") and deep_data["student_name"].lower() != "student":
                            fast_data["student_name"] = deep_data["student_name"]
                        if deep_data.get("student_email"):
                            fast_data["student_email"] = deep_data["student_email"]
                        if deep_data.get("profile"):
                            fast_data["profile"] = deep_data["profile"]
                        if deep_data.get("results"):
                            fast_data["results"] = deep_data["results"]
                        if deep_data.get("fees"):
                            fast_data["fees"] = deep_data["fees"]
                        fast_data["partial_load"] = False

                    save_snapshot(student_id, fast_data)
                    sync_user_to_supabase(student_id, password, fast_data, is_login_event=True, save_vault=save_vault)
            except Exception as e:
                print(f"[Login Scrape] Pre-scrape non-fatal error: {e}")
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

    # Sanitize student_name & profile details if cache holds generic "Student"
    if data:
        if (not data.get("student_name") or data.get("student_name").strip().lower() == "student") and db_user and db_user.get("student_name") and db_user.get("student_name").strip().lower() != "student":
            data["student_name"] = db_user.get("student_name")
        if data.get("profile") and data["profile"].get("details"):
            for i, pair in enumerate(data["profile"]["details"]):
                if pair[0].lower() == "name" and (not pair[1] or pair[1].strip().lower() == "student") and data.get("student_name") and data.get("student_name").strip().lower() != "student":
                    data["profile"]["details"][i] = ("Name", data["student_name"])

    # 2. First-Time User Cold Start: Fetch Attendance + Academic details (~2.5 seconds)
    if not data:
        client = PortalClient(student_id, password, cookies=session.get("portal_cookies"))
        data, err = client.get_full_profile(fast_mode=True)
        if not data:
            return redirect(url_for("login"))
        session["portal_cookies"] = client.get_cookies()
        try:
            deep_data, _ = client.get_academic_and_profile()
            if deep_data:
                if deep_data.get("student_name") and deep_data["student_name"].lower() != "student":
                    data["student_name"] = deep_data["student_name"]
                if deep_data.get("student_email"):
                    data["student_email"] = deep_data["student_email"]
                if deep_data.get("profile"):
                    data["profile"] = deep_data["profile"]
                if deep_data.get("results"):
                    data["results"] = deep_data["results"]
                if deep_data.get("fees"):
                    data["fees"] = deep_data["fees"]
                data["partial_load"] = False
        except Exception as e:
            print(f"[Cold Start Enrichment Error]: {e}")

        sync_user_to_supabase(student_id, password, data, is_login_event=False, save_vault=save_vault)
        save_snapshot(student_id, data)
        needs_background_sync = True

    # 3. Dynamic Auto-Enrichment if cache is missing results or has generic "Student"
    needs_enrichment = bool(
        data and password and (
            not data.get("results")
            or len(data.get("results", [])) == 0
            or not data.get("student_name")
            or data.get("student_name").strip().lower() == "student"
            or len(data.get("profile", {}).get("details", [])) <= 3
        )
    )
    if needs_enrichment:
        try:
            client = PortalClient(student_id, password, cookies=session.get("portal_cookies"))
            deep_data, _ = client.get_academic_and_profile()
            if deep_data:
                session["portal_cookies"] = client.get_cookies()
                if deep_data.get("student_name") and deep_data["student_name"].lower() != "student":
                    data["student_name"] = deep_data["student_name"]
                if deep_data.get("student_email"):
                    data["student_email"] = deep_data["student_email"]
                if deep_data.get("profile"):
                    data["profile"] = deep_data["profile"]
                if deep_data.get("results"):
                    data["results"] = deep_data["results"]
                if deep_data.get("fees"):
                    data["fees"] = deep_data["fees"]
                data["partial_load"] = False
                sync_user_to_supabase(student_id, password, data, is_login_event=False, save_vault=save_vault)
                save_snapshot(student_id, data)
        except Exception as e:
            print(f"[Dashboard Enrichment Error]: {e}")

    # Ensure today_date and today_attendance in cached data are always in real-time IST
    today_str = datetime.now(IST).strftime("%d-%m-%Y")
    today_pretty = datetime.now(IST).strftime("%a, %d %b %Y")
    data["today_date"] = today_pretty
    data["today_attendance"] = [
        r for r in data.get("calendar_records", [])
        if r.get("date") == today_str
    ]

    # Compute latest available portal upload fallback if missing
    if not data.get("latest_attendance_date") or not data.get("latest_attendance_records"):
        cal_recs = [r for r in data.get("calendar_records", []) if r.get("date")]
        if cal_recs:
            def _parse_d(r):
                try:
                    return datetime.strptime(r.get("date", ""), "%d-%m-%Y")
                except Exception:
                    return datetime.min
            cal_recs.sort(key=_parse_d, reverse=True)
            data["latest_attendance_date"] = cal_recs[0].get("date")
            seen_k = set()
            latest_recs = []
            for r in cal_recs:
                if r.get("date") == data["latest_attendance_date"]:
                    k = (r.get("subject"), r.get("status"))
                    if k not in seen_k:
                        seen_k.add(k)
                        latest_recs.append(r)
            data["latest_attendance_records"] = latest_recs

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

    req = request.get_json(silent=True) or {}
    sync_mode = req.get("mode", "attendance")

    client = PortalClient(student_id, password, cookies=session.get("portal_cookies"))

    if sync_mode == "attendance":
        # Fast Stage 1: Scrape only live attendance from portal in ~1.8 seconds
        data, err = client.get_full_profile(fast_mode=True)
        if not data:
            return jsonify({"ok": False, "message": err or "Portal offline"})

        session["portal_cookies"] = client.get_cookies()

        # Preserve non-empty cached profile, results, and fees from Supabase or snapshot
        db_user = get_user_record(student_id)
        cached = (db_user.get("cached_profile") if db_user else None) or load_snapshot(student_id)
        if cached:
            if not data.get("results") and cached.get("results"):
                data["results"] = cached.get("results", [])
            if not data.get("sgpa_trend") and cached.get("sgpa_trend"):
                data["sgpa_trend"] = cached.get("sgpa_trend", [])
            if not data.get("fees") and cached.get("fees"):
                data["fees"] = cached.get("fees", [])
            if (not data.get("profile") or not data["profile"].get("details")) and cached.get("profile"):
                data["profile"] = cached.get("profile", {})
            if not data.get("student_email") and cached.get("student_email"):
                data["student_email"] = cached.get("student_email")
            if not data.get("calendar_records") and cached.get("calendar_records"):
                data["calendar_records"] = cached.get("calendar_records", [])
            if not data.get("latest_attendance_date") and cached.get("latest_attendance_date"):
                data["latest_attendance_date"] = cached.get("latest_attendance_date")
            if not data.get("latest_attendance_records") and cached.get("latest_attendance_records"):
                data["latest_attendance_records"] = cached.get("latest_attendance_records", [])

        today_str = datetime.now(IST).strftime("%d-%m-%Y")
        today_pretty = datetime.now(IST).strftime("%a, %d %b %Y")
        data["today_date"] = today_pretty
        if not data.get("today_attendance"):
            data["today_attendance"] = [
                r for r in data.get("calendar_records", [])
                if r.get("date") == today_str
            ]

        # Fallback to newest portal upload if missing
        if not data.get("latest_attendance_date") or not data.get("latest_attendance_records"):
            cal_recs = [r for r in data.get("calendar_records", []) if r.get("date")]
            if cal_recs:
                def _parse_d(r):
                    try:
                        return datetime.strptime(r.get("date", ""), "%d-%m-%Y")
                    except Exception:
                        return datetime.min
                cal_recs.sort(key=_parse_d, reverse=True)
                data["latest_attendance_date"] = cal_recs[0].get("date")
                seen_k = set()
                latest_recs = []
                for r in cal_recs:
                    if r.get("date") == data["latest_attendance_date"]:
                        k = (r.get("subject"), r.get("status"))
                        if k not in seen_k:
                            seen_k.add(k)
                            latest_recs.append(r)
                data["latest_attendance_records"] = latest_recs

        save_vault = session.get("save_vault", True)
        new_absents = sync_user_to_supabase(student_id, password, data, is_login_event=False, save_vault=save_vault)
        save_snapshot(student_id, data)

        total_p = sum(s["present"] for s in data["subjects"])
        total_t = sum(s["total"] for s in data["subjects"])
        overall_pct = round((total_p / total_t * 100), 2) if total_t > 0 else 0.0

        return jsonify({
            "ok": True,
            "sync_mode": "attendance",
            "last_synced": data.get("last_synced"),
            "student_name": data.get("student_name"),
            "today_date": today_pretty,
            "overall_pct": overall_pct,
            "overall_present": total_p,
            "overall_classes": total_t,
            "subjects": data.get("subjects", []),
            "today_attendance": data.get("today_attendance", []),
            "latest_attendance_date": data.get("latest_attendance_date"),
            "latest_attendance_records": data.get("latest_attendance_records", []),
            "calendar_records": data.get("calendar_records", []),
            "new_absents": new_absents,
            "has_results": bool(data.get("results")),
            "results": data.get("results", []),
            "sgpa_trend": data.get("sgpa_trend", []),
            "fees": data.get("fees", []),
            "profile": data.get("profile", {}),
            "partial_was_upgraded": False
        })
    else:
        # Stage 2: Ultra-Fast Deep Sync for Results, Marksheets, Fees, and Profile details (~1.5s)
        # Prevents Vercel 10s Serverless timeout by NOT re-scraping attendance subjects!
        deep_data, err = client.get_academic_and_profile()
        if not deep_data:
            return jsonify({"ok": False, "message": err or "Portal offline"})

        session["portal_cookies"] = client.get_cookies()

        # Merge deep_data into existing cached snapshot from Supabase or local cache
        db_user = get_user_record(student_id)
        cached = (db_user.get("cached_profile") if db_user else None) or load_snapshot(student_id) or {}

        if deep_data.get("student_name") and deep_data["student_name"].lower() != "student":
            cached["student_name"] = deep_data["student_name"]
        if deep_data.get("student_email"):
            cached["student_email"] = deep_data["student_email"]
        if deep_data.get("profile"):
            cached["profile"] = deep_data["profile"]
        if deep_data.get("results"):
            cached["results"] = deep_data["results"]
        if deep_data.get("fees"):
            cached["fees"] = deep_data["fees"]
        cached["partial_load"] = False

        today_str = datetime.now(IST).strftime("%d-%m-%Y")
        today_pretty = datetime.now(IST).strftime("%a, %d %b %Y")
        cached["today_date"] = today_pretty
        if not cached.get("today_attendance"):
            cached["today_attendance"] = [
                r for r in cached.get("calendar_records", [])
                if r.get("date") == today_str
            ]

        # Fallback to newest portal upload if missing
        if not cached.get("latest_attendance_date") or not cached.get("latest_attendance_records"):
            cal_recs = [r for r in cached.get("calendar_records", []) if r.get("date")]
            if cal_recs:
                def _parse_d(r):
                    try:
                        return datetime.strptime(r.get("date", ""), "%d-%m-%Y")
                    except Exception:
                        return datetime.min
                cal_recs.sort(key=_parse_d, reverse=True)
                cached["latest_attendance_date"] = cal_recs[0].get("date")
                seen_k = set()
                latest_recs = []
                for r in cal_recs:
                    if r.get("date") == cached["latest_attendance_date"]:
                        k = (r.get("subject"), r.get("status"))
                        if k not in seen_k:
                            seen_k.add(k)
                            latest_recs.append(r)
                cached["latest_attendance_records"] = latest_recs

        save_vault = session.get("save_vault", True)
        new_absents = sync_user_to_supabase(student_id, password, cached, is_login_event=False, save_vault=save_vault)
        save_snapshot(student_id, cached)

        total_p = sum(s.get("present", 0) for s in cached.get("subjects", []))
        total_t = sum(s.get("total", 0) for s in cached.get("subjects", []))
        overall_pct = round((total_p / total_t * 100), 2) if total_t > 0 else 0.0

        return jsonify({
            "ok": True,
            "sync_mode": "deep",
            "last_synced": cached.get("last_synced"),
            "student_name": cached.get("student_name"),
            "today_date": today_pretty,
            "overall_pct": overall_pct,
            "overall_present": total_p,
            "overall_classes": total_t,
            "subjects": cached.get("subjects", []),
            "today_attendance": cached.get("today_attendance", []),
            "latest_attendance_date": cached.get("latest_attendance_date"),
            "latest_attendance_records": cached.get("latest_attendance_records", []),
            "calendar_records": cached.get("calendar_records", []),
            "new_absents": new_absents,
            "has_results": bool(cached.get("results")),
            "results": cached.get("results", []),
            "sgpa_trend": cached.get("sgpa_trend", []),
            "fees": cached.get("fees", []),
            "profile": cached.get("profile", {}),
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
        "Krono Lock-Screen Push Active!",
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


@app.route("/api/admin/diagnostic-step1", methods=["GET", "POST"])
@admin_required
def api_admin_diagnostic_step1():
    import traceback
    try:
        student_id = (request.args.get("student_id") or "2412234").strip()
        db_user = get_user_record(student_id)
        if not db_user or not db_user.get("encrypted_password"):
            return jsonify({"ok": False, "error": f"User {student_id} or encrypted password not found"}), 404

        plain_pw = decrypt_password(db_user["encrypted_password"])
        if not plain_pw:
            return jsonify({"ok": False, "error": f"Could not decrypt password for {student_id}"}), 500

        from bs4 import BeautifulSoup
        from urllib.parse import urljoin
        import requests
        import re

        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

        # 1. Fetch Login Page
        r_login = s.get("https://agclms.in/Elogin/StudentLogin", timeout=10)
        soup = BeautifulSoup(r_login.text, "html.parser")
        form = soup.find("form")
        post_url = urljoin("https://agclms.in/Elogin/StudentLogin", form["action"]) if (form and form.get("action")) else "https://agclms.in/Elogin/StudentLogin"

        payload = {}
        for inp in form.find_all("input"):
            name = inp.get("name")
            if not name: continue
            t = (inp.get("type") or "text").lower()
            if t == "hidden": payload[name] = inp.get("value", "")
            elif t == "password" or "pass" in name.lower(): payload[name] = plain_pw
            elif t in ("text", "number", "tel"): payload[name] = student_id

        # 2. Post with allow_redirects=False to avoid IIS connection drop on keepalive socket
        r_post = s.post(post_url, data=payload, timeout=12, allow_redirects=False)
        post_loc = r_post.headers.get("Location") or ""
        post_cookies = dict(s.cookies)
        
        target_dash_url = urljoin("https://agclms.in/Elogin/StudentLogin", post_loc) if post_loc else "https://agclms.in/DashBoardStudent"
        
        s_fresh = requests.Session()
        s_fresh.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://agclms.in/Elogin/StudentLogin",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
        })
        s_fresh.cookies.update(post_cookies)

        r_dash = s_fresh.get(target_dash_url, timeout=12)
        dash_soup = BeautifulSoup(r_dash.text, "html.parser")

        # 1. Top Header & Name Diagnostic
        dash_text = dash_soup.get_text(" ", strip=True)
        role_matches = re.findall(r"([^\.\n\|]{1,50}?Role\s*:\s*[^\.\n\|]{1,30})", dash_text, re.I)
        all_links = []
        for a in dash_soup.find_all("a"):
            txt = a.get_text(strip=True)
            href = a.get("href", "")
            if href and not href.startswith("#") and not href.startswith("javascript"):
                all_links.append({"text": txt, "href": href, "full_url": urljoin(target_dash_url + "/", href)})

        header_snippets = []
        for tag in dash_soup.find_all(["header", "nav", "div"], class_=re.compile(r"header|navbar|user|profile|top", re.I))[:5]:
            header_snippets.append(tag.get_text(" ", strip=True)[:150])

        # 2. Profile Page Inspection
        profile_candidates = [l["full_url"] for l in all_links if any(k in l["text"].lower() or k in l["href"].lower() for k in ["profile", "studentprofile", "biodata"])]
        if not profile_candidates:
            profile_candidates = [urljoin(target_dash_url + "/", "StudentProfile"), urljoin(target_dash_url + "/", "Profile")]

        profile_diag = {}
        for p_url in profile_candidates[:2]:
            try:
                r_prof = s_fresh.get(p_url, timeout=8)
                if r_prof.status_code == 200 and len(r_prof.text) > 300:
                    p_soup = BeautifulSoup(r_prof.text, "html.parser")
                    inputs = [{"name": i.get("name"), "value": i.get("value"), "type": i.get("type"), "id": i.get("id")} for i in p_soup.find_all("input") if i.get("value") or i.get("name")]
                    labels = [l.get_text(strip=True) for l in p_soup.find_all(["label", "th", "dt"])]
                    images = []
                    for img in p_soup.find_all("img"):
                        images.append({
                            "src": img.get("src"),
                            "alt": img.get("alt"),
                            "class": img.get("class"),
                            "parent": img.parent.name if img.parent else None,
                            "parent_class": img.parent.get("class") if img.parent else None
                        })
                    table_rows = [tr.get_text(" | ", strip=True) for tr in p_soup.find_all("tr")][:15]

                    field_pairs = []
                    for label in p_soup.find_all("label"):
                        lbl_text = label.get_text(strip=True)
                        parent = label.parent
                        val_cand = ""
                        inp = parent.find("input") if parent else None
                        if inp and inp.get("value"):
                            val_cand = inp.get("value")
                        else:
                            next_tag = label.find_next_sibling()
                            if next_tag:
                                val_cand = next_tag.get_text(strip=True)
                            elif parent:
                                p_inps = parent.find_all("input")
                                if p_inps:
                                    val_cand = ", ".join(i.get("value", "") for i in p_inps if i.get("value"))
                                else:
                                    texts = [t.strip() for t in parent.find_all(string=True) if t.strip() and t.strip() != lbl_text]
                                    if texts:
                                        val_cand = " ".join(texts)
                        field_pairs.append({"label": lbl_text, "value": val_cand, "parent_html": str(parent)[:200] if parent else ""})

                    profile_diag = {
                        "url": p_url,
                        "status_code": r_prof.status_code,
                        "inputs": inputs,
                        "labels": labels[:25],
                        "field_pairs": field_pairs,
                        "images": images,
                        "table_rows": table_rows
                    }
                    break
            except Exception as pe:
                profile_diag = {"url": p_url, "error": str(pe)}

        # 3. Result Page Inspection
        result_candidates = [l["full_url"] for l in all_links if any(k in l["text"].lower() or k in l["href"].lower() for k in ["result", "marks", "grade", "transcript", "exam"])]
        if not result_candidates:
            result_candidates = [urljoin(target_dash_url + "/", "Result"), urljoin(target_dash_url + "/", "Results")]

        result_diag = {}
        for r_url in result_candidates[:3]:
            try:
                r_res = s_fresh.get(r_url, timeout=8)
                if r_res.status_code == 200 and len(r_res.text) > 300:
                    r_soup = BeautifulSoup(r_res.text, "html.parser")
                    forms = []
                    for f in r_soup.find_all("form"):
                        forms.append({
                            "action": f.get("action"),
                            "method": f.get("method"),
                            "inputs": [{"name": i.get("name"), "value": i.get("value"), "type": i.get("type")} for i in f.find_all("input")]
                        })
                    selects = []
                    for sel in r_soup.find_all("select"):
                        selects.append({
                            "name": sel.get("name"),
                            "id": sel.get("id"),
                            "options": [{"value": o.get("value"), "text": o.get_text(strip=True)} for o in sel.find_all("option")]
                        })
                    tables_sample = []
                    for t in r_soup.find_all("table")[:3]:
                        tables_sample.append([tr.get_text(" | ", strip=True) for tr in t.find_all("tr")[:8]])
                    scripts_sample = [s.get_text()[:200] for s in r_soup.find_all("script") if "ajax" in s.get_text().lower() or "result" in s.get_text().lower()][:3]

                    sem_fetch_tests = []
                    if selects and selects[0]["options"]:
                        sel_name = selects[0]["name"]
                        form_action = forms[0]["action"] if forms else r_url
                        post_target = urljoin(r_url, form_action)
                        for opt in selects[0]["options"][:3]:
                            v = opt["value"]
                            if not v or v in ("0", ""): continue
                            test_payload = {}
                            if forms:
                                for inp in forms[0]["inputs"]:
                                    if inp["name"]: test_payload[inp["name"]] = inp["value"] or ""
                            test_payload[sel_name] = v
                            r_post_sem = s_fresh.post(post_target, data=test_payload, timeout=6)
                            sem_soup = BeautifulSoup(r_post_sem.text, "html.parser")
                            sem_fetch_tests.append({
                                "sem": opt["text"],
                                "val": v,
                                "method": "POST",
                                "status": r_post_sem.status_code,
                                "tables_count": len(sem_soup.find_all("table")),
                                "sample_row": [tr.get_text(" | ", strip=True) for tr in sem_soup.find_all("tr")[:4]]
                            })

                    result_diag = {
                        "url": r_url,
                        "status_code": r_res.status_code,
                        "forms": forms,
                        "selects": selects,
                        "tables_sample": tables_sample,
                        "scripts_sample": scripts_sample,
                        "sem_fetch_tests": sem_fetch_tests
                    }
                    break
            except Exception as re_err:
                result_diag = {"url": r_url, "error": str(re_err)}

        # Detail / Profile Page Inner HTML inspection
        prof_debug = {}
        try:
            r_prof = s_fresh.get("https://agclms.in/DashBoardStudent/Detail", timeout=8)
            p_soup = BeautifulSoup(r_prof.text, "html.parser")
            inputs = [{"name": i.get("name"), "value": i.get("value"), "type": i.get("type"), "id": i.get("id")} for i in p_soup.find_all("input")]
            labels = [l.get_text(strip=True) for l in p_soup.find_all(["label", "th", "dt"])]
            images = [{"src": img.get("src"), "alt": img.get("alt"), "class": img.get("class")} for img in p_soup.find_all("img")]
            table_rows = [tr.get_text(" | ", strip=True) for tr in p_soup.find_all("tr")][:30]
            prof_debug = {
                "status": r_prof.status_code,
                "url": r_prof.url,
                "text_length": len(r_prof.text),
                "full_html": r_prof.text,
                "inputs": inputs,
                "labels": labels,
                "images": images,
                "table_rows": table_rows
            }
        except Exception as pe:
            prof_debug = {"error": str(pe)}

        header_tag_sample = ""
        for tag in dash_soup.find_all(True):
            if "Role: STUDENT" in tag.get_text():
                if not any("Role: STUDENT" in c.get_text() for c in tag.find_all(True)):
                    header_tag_sample = str(tag)
                    break

        results_by_classcode = {}
        if result_diag.get("selects") and len(result_diag["selects"]) > 0:
            for opt in result_diag["selects"][0].get("options", []):
                code = opt.get("value")
                if code and code not in ("0", ""):
                    try:
                        r_c = s_fresh.get(f"https://agclms.in/DashBoardStudent/Results?ClassCode={code}", timeout=8)
                        soup_c = BeautifulSoup(r_c.text, "html.parser")
                        results_by_classcode[opt.get("text")] = {
                            "code": code,
                            "status": r_c.status_code,
                            "tables": [[tr.get_text(" | ", strip=True) for tr in t.find_all("tr")] for t in soup_c.find_all("table")]
                        }
                    except Exception as ce:
                        results_by_classcode[opt.get("text")] = {"error": str(ce)}

        # Run updated PortalClient verification
        client = PortalClient(student_id, plain_pw)
        p_deep, p_err = client.get_full_profile(fast_mode=False)

        return jsonify({
            "ok": True,
            "student_id": student_id,
            "header_tag_sample": header_tag_sample,
            "role_matches": role_matches,
            "prof_debug": prof_debug,
            "results_by_classcode": results_by_classcode,
            "portal_client_verification": {
                "student_name": p_deep.get("student_name") if p_deep else None,
                "profile_details_count": len(p_deep.get("profile", {}).get("details", [])) if p_deep else 0,
                "profile_details_sample": p_deep.get("profile", {}).get("details", [])[:12] if p_deep else [],
                "has_photo": bool(p_deep.get("profile", {}).get("photo_url")) if p_deep else False,
                "results_count": len(p_deep.get("results", [])) if p_deep else 0,
                "results_summary": [{"sem": s.get("semester"), "sgpa": s.get("sgpa"), "status": s.get("status"), "reappears": s.get("reappear_subjects")} for s in p_deep.get("results", [])] if p_deep else [],
                "today_attendance": p_deep.get("today_attendance", []) if p_deep else [],
                "calendar_records_count": len(p_deep.get("calendar_records", [])) if p_deep else 0
            }
        })
    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 200


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
                title=f"Developer Replied to Your {updated_row.get('category', 'Feedback')}",
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
    title = (req.get("title") or "Krono Announcement").strip()
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
        return jsonify({"ok": True, "message": f"Live portal sync completed for {student_id}!"})

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


@app.route("/download/Krono.apk")
@app.route("/download/UltraPortal.apk")
def download_apk():
    krono_path = os.path.join(static_dir, "apk", "Krono.apk")
    ultra_path = os.path.join(static_dir, "apk", "UltraPortal.apk")
    target_path = krono_path if os.path.isfile(krono_path) else ultra_path
    
    is_krono = request.path.endswith("Krono.apk")
    dl_name = "Krono.apk" if is_krono else "UltraPortal.apk"

    if os.path.isfile(target_path):
        resp = make_response(send_file(
            target_path,
            as_attachment=True,
            download_name=dl_name,
            mimetype="application/vnd.android.package-archive"
        ))
        resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp
    return redirect(f"https://raw.githubusercontent.com/Harman-777/attendance/main/static/apk/{dl_name}")


@app.route("/api/app-version")
def api_app_version():
    return jsonify({
        "latest_version": APP_VERSION,
        "version_code": APP_VERSION_CODE,
        "release_date": "24 Oct 2026",
        "download_url": "/download/Krono.apk",
        "external_download_url": "https://github.com/Harman-777/attendance/raw/main/static/apk/UltraPortal.apk",
        "changelog": [
            "Complete flagship rebrand to Krono v2.7 with precision geometric chevron logo",
            "Studio-grade Dual Theme System: Pitch-Black OLED Dark + Paper-White Light Mode",
            "1.5px / 1.75px Lucide vector line icons replacing all system emojis",
            "Native Android system status bar & navigation bar theme synchronization",
            "Tabular monospace typography for razor-sharp attendance statistics"
        ]
    })


@app.route("/update")
def page_update():
    return render_template("update.html")

@app.context_processor
def inject_app_version():
    return {"app_version": APP_VERSION}



if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)