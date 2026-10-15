import os
from datetime import datetime, timezone
import requests
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Automatically load .env.local on local machine (Vercel uses its own Env Vars)
load_dotenv(".env.local")
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")


def _get_fernet():
    if not ENCRYPTION_KEY:
        return None
    try:
        return Fernet(ENCRYPTION_KEY.encode("utf-8"))
    except Exception as e:
        print("Fernet initialization error:", e)
        return None


def encrypt_password(plain_password: str) -> str:
    f = _get_fernet()
    if not f or not plain_password:
        return ""
    return f.encrypt(plain_password.encode("utf-8")).decode("utf-8")


def decrypt_password(encrypted_password: str) -> str:
    f = _get_fernet()
    if not f or not encrypted_password:
        return ""
    try:
        return f.decrypt(encrypted_password.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def _headers(prefer=None):
    h = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def is_db_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_KEY)


def get_user_record(student_id: str):
    """Fetches a single student's row from portal_users."""
    if not is_db_configured():
        return None
    try:
        url = f"{SUPABASE_URL}/rest/v1/portal_users?student_id=eq.{student_id}&select=*"
        res = requests.get(url, headers=_headers(), timeout=8)
        if res.status_code == 200:
            rows = res.json()
            return rows[0] if rows else None
    except Exception as e:
        print("Supabase get_user_record error:", e)
    return None


def sync_user_to_supabase(student_id: str, plain_password: str, data: dict, is_login_event: bool = False):
    """
    Compares live attendance with Supabase known_absents to detect new absents,
    then upserts the student's profile, encrypted password, and snapshot to portal_users.
    """
    if not is_db_configured() or not data:
        return []

    existing = get_user_record(student_id)
    old_absents = set(existing.get("known_absents") or []) if existing else set()
    login_count = (existing.get("login_count") or 0) + (1 if is_login_event else 0) if existing else 1

    # Build current absent keys ("DD-MM-YYYY|Subject Name") and detect newly added absents
    current_absent_keys = []
    new_absents = []
    for r in data.get("calendar_records", []):
        if r.get("status") == "ABSENT":
            key = f"{r.get('date')}|{r.get('subject')}"
            current_absent_keys.append(key)
            if existing and key not in old_absents:
                new_absents.append(r)

    total_p = sum(s.get("present", 0) for s in data.get("subjects", []))
    total_t = sum(s.get("total", 0) for s in data.get("subjects", []))
    overall_pct = round((total_p / total_t * 100), 2) if total_t > 0 else 0.0

    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "student_id": str(student_id),
        "student_name": data.get("student_name", "Student"),
        "encrypted_password": encrypt_password(plain_password),
        "email": data.get("student_email") or (existing.get("email") if existing else ""),
        "incharge": data.get("incharge", ""),
        "overall_pct": overall_pct,
        "known_absents": current_absent_keys,
        "cached_profile": data,
        "login_count": max(login_count, 1),
        "last_synced_at": now_iso
    }

    if is_login_event or not existing:
        payload["last_login_at"] = now_iso

    try:
        url = f"{SUPABASE_URL}/rest/v1/portal_users"
        requests.post(
            url,
            headers=_headers("resolution=merge-duplicates,return=minimal"),
            json=payload,
            timeout=10
        )
    except Exception as e:
        print("Supabase sync_user_to_supabase error:", e)

    return new_absents


def log_login_activity(student_id: str, student_name: str, user_agent: str, ip_address: str):
    """Inserts an audit entry into login_logs whenever a student signs in."""
    if not is_db_configured():
        return
    try:
        url = f"{SUPABASE_URL}/rest/v1/login_logs"
        payload = {
            "student_id": str(student_id),
            "student_name": student_name or "Student",
            "user_agent": (user_agent or "")[:250],
            "ip_address": (ip_address or "")[:64]
        }
        requests.post(url, headers=_headers("return=minimal"), json=payload, timeout=6)
    except Exception as e:
        print("Supabase log_login_activity error:", e)


def save_push_or_email_prefs(student_id: str, email: str = None, push_sub: dict = None, auto_sync: bool = True):
    """Updates a student's notification email or Web Push subscription in Supabase."""
    if not is_db_configured() or not student_id:
        return False
    update_data = {"auto_sync_enabled": auto_sync}
    if email is not None:
        update_data["email"] = email
    if push_sub is not None:
        update_data["push_subscription"] = push_sub

    try:
        url = f"{SUPABASE_URL}/rest/v1/portal_users?student_id=eq.{student_id}"
        res = requests.patch(url, headers=_headers("return=minimal"), json=update_data, timeout=8)
        return res.status_code in (200, 204)
    except Exception as e:
        print("Supabase save_push_or_email_prefs error:", e)
        return False


def get_all_auto_sync_users():
    """Used by the background worker to pull all students who have auto-sync enabled."""
    if not is_db_configured():
        return []
    try:
        url = f"{SUPABASE_URL}/rest/v1/portal_users?auto_sync_enabled=eq.true&select=*"
        res = requests.get(url, headers=_headers(), timeout=12)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print("Supabase get_all_auto_sync_users error:", e)
    return []