import os
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_from_directory
from portal_client import PortalClient
from notifier import save_snapshot, load_snapshot, detect_new_absents, send_absent_email, send_web_push, VAPID_PUBLIC_KEY
from db_client import (
    sync_user_to_supabase,
    log_login_activity,
    get_user_record,
    save_push_or_email_prefs
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
app.secret_key = os.environ.get("SECRET_KEY", "ultra_attendance_secret_key_pro")

@app.route("/sw.js")
def service_worker():
    """Serves the Service Worker at the root scope so it can control the whole PWA."""
    return send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")


@app.route("/api/vapid-public-key")
def api_vapid_public_key():
    return jsonify({"publicKey": VAPID_PUBLIC_KEY})


@app.route("/api/test-push", methods=["POST"])
def api_test_push():
    """Saves the browser's PushSubscription to Supabase and fires an instant test push."""
    student_id = session.get("student_id")
    if not student_id:
        return jsonify({"ok": False, "message": "Not logged in."}), 401

    req = request.get_json() or {}
    sub = req.get("subscription")
    if not sub:
        return jsonify({"ok": False, "message": "No push subscription provided."})

    # Save push token permanently in Supabase portal_users table
    save_push_or_email_prefs(student_id, push_sub=sub, auto_sync=True)

    # Fire a live encrypted push from Python to the device
    ok, msg = send_web_push(
        sub,
        "⚡ Ultra Portal Lock-Screen Push Active!",
        "Your device is now linked to Supabase. Any new ABSENT mark will alert you automatically!"
    )
    return jsonify({"ok": ok, "message": msg})


@app.route("/", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        student_id = request.form.get("student_id", "").strip()
        password = request.form.get("password", "").strip()

        client = PortalClient(student_id, password)
        success, err = client.authenticate()

        if not success:
            # Check local snapshot or Supabase cloud snapshot if college portal is down
            cached = load_snapshot(student_id)
            if not cached:
                db_user = get_user_record(student_id)
                if db_user and db_user.get("cached_profile"):
                    cached = db_user["cached_profile"]

            if cached and "Portal unreachable" in (err or ""):
                session["student_id"] = student_id
                session["password"] = password
                session["just_logged_in"] = True
                return redirect(url_for("dashboard"))
            error = err
        else:
            session["student_id"] = student_id
            session["password"] = password
            session["just_logged_in"] = True
            return redirect(url_for("dashboard"))

    return render_template("login.html", error=error)


@app.route("/dashboard")
def dashboard():
    student_id = session.get("student_id")
    password = session.get("password")
    if not student_id or not password:
        return redirect(url_for("login"))

    is_login_event = session.pop("just_logged_in", False)

    client = PortalClient(student_id, password)
    data, err = client.get_full_profile()

    new_absents = []
    if data:
        # 1. Sync to Supabase & detect new absents against persistent cloud state
        db_new_absents = sync_user_to_supabase(student_id, password, data, is_login_event=is_login_event)
        # 2. Also keep local snapshot fallback
        local_new_absents = detect_new_absents(student_id, data)
        new_absents = db_new_absents if db_new_absents else local_new_absents
        save_snapshot(student_id, data)

        if is_login_event:
            ua = request.headers.get("User-Agent", "")
            ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
            log_login_activity(student_id, data.get("student_name", "Student"), ua, ip)
    else:
        # Fallback to Supabase Cloud Snapshot first, then local /tmp cache
        db_user = get_user_record(student_id)
        if db_user and db_user.get("cached_profile"):
            data = db_user["cached_profile"]
            data["is_offline"] = True
        else:
            data = load_snapshot(student_id)
            if data:
                data["is_offline"] = True
            else:
                return redirect(url_for("login"))

    total_present = sum(s["present"] for s in data["subjects"])
    total_classes = sum(s["total"] for s in data["subjects"])
    overall_pct = (total_present / total_classes * 100) if total_classes > 0 else 0

    danger_subjects = [
        s for s in data["subjects"]
        if s.get("danger_level") in ("critical", "warning")
    ]

    return render_template(
        "dashboard.html",
        data=data,
        new_absents=new_absents,
        danger_subjects=danger_subjects,
        overall_present=total_present,
        overall_classes=total_classes,
        overall_pct=round(overall_pct, 2)
    )


@app.route("/api/change-password", methods=["POST"])
def api_change_password():
    student_id = session.get("student_id")
    password = session.get("password")
    if not student_id or not password:
        return jsonify({"ok": False, "message": "Not logged in."}), 401

    req = request.get_json() or {}
    old_pw = req.get("old_password", "").strip()
    new_pw = req.get("new_password", "").strip()
    conf_pw = req.get("confirm_password", "").strip()

    if not old_pw or not new_pw or new_pw != conf_pw:
        return jsonify({"ok": False, "message": "New passwords do not match or are empty."})

    client = PortalClient(student_id, password)
    ok, msg = client.change_password(old_pw, new_pw, conf_pw)
    if ok:
        session["password"] = new_pw
    return jsonify({"ok": ok, "message": msg})


@app.route("/api/save-subscription", methods=["POST"])
def api_save_subscription():
    """Saves Web Push subscription & notification email directly to Supabase."""
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


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)