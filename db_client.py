import os
import re
import base64
import hashlib
from datetime import datetime, timezone
import requests
from cryptography.fernet import Fernet
from dotenv import load_dotenv

load_dotenv(".env.local")
load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().strip('"').strip("'").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "").strip().strip('"').strip("'")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "").strip().strip('"').strip("'")

VALID_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,25}$")


def is_valid_student_id(student_id: str) -> bool:
    if not student_id or not isinstance(student_id, str):
        return False
    return bool(VALID_ID_RE.match(student_id.strip()))


def _get_fernet():
    """
    Initializes Fernet AES encryption. If ENCRYPTION_KEY has formatting issues
    or wrong padding, automatically normalizes it via SHA-256 so it never fails.
    """
    raw_secret = ENCRYPTION_KEY or os.environ.get("SECRET_KEY", "ultra_attendance_secret_key_pro")
    try:
        return Fernet(raw_secret.encode("utf-8"))
    except Exception:
        derived_key = base64.urlsafe_b64encode(hashlib.sha256(raw_secret.encode("utf-8")).digest())
        return Fernet(derived_key)


def encrypt_password(plain_password: str) -> str:
    if not plain_password:
        return ""
    f = _get_fernet()
    return f.encrypt(plain_password.encode("utf-8")).decode("utf-8")


def decrypt_password(encrypted_password: str) -> str:
    if not encrypted_password:
        return ""
    f = _get_fernet()
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
    if not is_db_configured() or not is_valid_student_id(student_id):
        return None
    try:
        url = f"{SUPABASE_URL}/rest/v1/portal_users"
        params = {"student_id": f"eq.{student_id}", "select": "*"}
        res = requests.get(url, headers=_headers(), params=params, timeout=6)
        if res.status_code == 200:
            rows = res.json()
            return rows[0] if rows else None
    except Exception as e:
        print("Supabase get_user_record error:", e)
    return None


def set_vault_password(student_id: str, plain_password: str = None, enable: bool = True):
    """
    Called when the user clicks the Encrypt Password button in the UI.
    Encrypts and saves the password to Supabase, or wipes it back to NULL if disabled.
    """
    if not is_db_configured() or not is_valid_student_id(student_id):
        return False, "Invalid student ID or database not configured.", ""

    enc_val = encrypt_password(plain_password) if (enable and plain_password) else None
    update_data = {
        "encrypted_password": enc_val,
        "auto_sync_enabled": bool(enc_val)
    }

    try:
        url = f"{SUPABASE_URL}/rest/v1/portal_users"
        params = {"student_id": f"eq.{student_id}"}
        res = requests.patch(url, headers=_headers("return=minimal"), params=params, json=update_data, timeout=8)
        if res.status_code in (200, 204):
            if enc_val:
                preview = enc_val[:16] + "..." + enc_val[-6:]
                return True, f"Password encrypted & saved to Supabase Vault ({preview})!", enc_val
            return True, "Password removed from Supabase Vault (set to EMPTY).", ""
        return False, f"Supabase error ({res.status_code}): {res.text}", ""
    except Exception as e:
        return False, f"Database connection error: {str(e)}", ""


def sync_user_to_supabase(student_id: str, plain_password: str, data: dict, is_login_event: bool = False, save_vault: bool = True):
    """
    Upserts the student's profile and attendance snapshot.
    Encrypts password by default into Supabase Cloud Password Vault so background auto-sync
    and Admin sync work seamlessly.
    """
    if not is_db_configured() or not data or not is_valid_student_id(student_id):
        return []

    existing = get_user_record(student_id)
    old_absents = set(existing.get("known_absents") or []) if existing else set()
    login_count = (existing.get("login_count") or 0) + (1 if is_login_event else 0) if existing else 1

    # Preserve non-empty results, sgpa_trend, fees, profile, calendar_records, and subjects from previous cache
    if existing and existing.get("cached_profile"):
        old_cache = existing["cached_profile"]
        if not data.get("calendar_records") and old_cache.get("calendar_records"):
            data["calendar_records"] = old_cache["calendar_records"]
        if not data.get("subjects") and old_cache.get("subjects"):
            data["subjects"] = old_cache["subjects"]
        if not data.get("today_attendance") and old_cache.get("today_attendance"):
            data["today_attendance"] = old_cache["today_attendance"]
        if not data.get("latest_attendance_date") and old_cache.get("latest_attendance_date"):
            data["latest_attendance_date"] = old_cache["latest_attendance_date"]
        if not data.get("latest_attendance_records") and old_cache.get("latest_attendance_records"):
            data["latest_attendance_records"] = old_cache["latest_attendance_records"]
        if not data.get("results") and old_cache.get("results"):
            data["results"] = old_cache["results"]
        if not data.get("sgpa_trend") and old_cache.get("sgpa_trend"):
            data["sgpa_trend"] = old_cache["sgpa_trend"]
        if not data.get("fees") and old_cache.get("fees"):
            data["fees"] = old_cache["fees"]
        if (not data.get("profile") or not data["profile"].get("details")) and old_cache.get("profile"):
            data["profile"] = old_cache["profile"]

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

    # Encrypt password into Cloud Vault by default unless opted out
    if save_vault and plain_password:
        vault_pw = encrypt_password(plain_password)
    elif existing and existing.get("encrypted_password"):
        vault_pw = existing.get("encrypted_password")
    else:
        vault_pw = None

    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "student_id": str(student_id),
        "student_name": data.get("student_name", "Student"),
        "encrypted_password": vault_pw,
        "auto_sync_enabled": bool(vault_pw),
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
            timeout=8
        )
    except Exception as e:
        print("Supabase sync_user_to_supabase error:", e)

    return new_absents


def log_login_activity(student_id: str, student_name: str, user_agent: str, ip_address: str):
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
        requests.post(url, headers=_headers("return=minimal"), json=payload, timeout=5)
    except Exception as e:
        print("Supabase log_login_activity error:", e)


def record_login_event(student_id: str, student_name: str, user_agent: str, ip_address: str):
    """
    Records a live login event into login_logs AND updates portal_users last_login_at and login_count.
    Ensures the Admin Dashboard accurately reflects real-time logins and totals.
    """
    if not is_db_configured() or not is_valid_student_id(student_id):
        return

    # 1. Insert audit log record
    log_login_activity(student_id, student_name, user_agent, ip_address)

    # 2. Update user's last_login_at and increment login_count in portal_users
    try:
        existing = get_user_record(student_id)
        current_count = (existing.get("login_count") or 1) if existing else 0
        now_iso = datetime.now(timezone.utc).isoformat()

        patch_payload = {
            "last_login_at": now_iso,
            "login_count": current_count + 1
        }
        if student_name and student_name != "Student":
            patch_payload["student_name"] = student_name

        url = f"{SUPABASE_URL}/rest/v1/portal_users"
        params = {"student_id": f"eq.{student_id}"}
        requests.patch(url, headers=_headers("return=minimal"), params=params, json=patch_payload, timeout=6)
    except Exception as e:
        print("Error updating portal_users login timestamp/count:", e)


def save_push_or_email_prefs(student_id: str, email: str = None, push_sub: dict = None, auto_sync: bool = True):
    if not is_db_configured() or not is_valid_student_id(student_id):
        return False
    update_data = {"auto_sync_enabled": auto_sync}
    if email is not None:
        update_data["email"] = email
    if push_sub is not None:
        update_data["push_subscription"] = push_sub

    try:
        url = f"{SUPABASE_URL}/rest/v1/portal_users"
        params = {"student_id": f"eq.{student_id}"}
        res = requests.patch(url, headers=_headers("return=minimal"), params=params, json=update_data, timeout=8)
        return res.status_code in (200, 204)
    except Exception as e:
        print("Supabase save_push_or_email_prefs error:", e)
        return False


def get_all_auto_sync_users():
    if not is_db_configured():
        return []
    try:
        url = f"{SUPABASE_URL}/rest/v1/portal_users"
        params = {"auto_sync_enabled": "eq.true", "select": "*"}
        res = requests.get(url, headers=_headers(), params=params, timeout=12)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print("Supabase get_all_auto_sync_users error:", e)
    return []

def submit_feedback(student_id: str, student_name: str, category: str, rating: int, message: str):
    """Saves a user's feedback or suggestion into app_feedback."""
    if not is_db_configured() or not is_valid_student_id(student_id) or not message:
        return False, "Database not configured or invalid student ID/empty message."

    payload = {
        "student_id": str(student_id),
        "student_name": student_name or "User",
        "category": (category or "Suggestion")[:50],
        "rating": max(1, min(5, int(rating or 5))),
        "message": message.strip()[:1000],
        "status": "Pending"
    }
    try:
        url = f"{SUPABASE_URL}/rest/v1/app_feedback"
        res = requests.post(url, headers=_headers("return=minimal"), json=payload, timeout=8)
        if res.status_code in (200, 201, 204):
            return True, "Thank you! Your feedback has been sent directly to the developer."
        return False, f"Failed to submit ({res.status_code})."
    except Exception as e:
        return False, f"Error submitting feedback: {str(e)}"


def get_user_feedback(student_id: str):
    """Fetches a specific user's submitted feedback and any developer replies."""
    if not is_db_configured() or not is_valid_student_id(student_id):
        return []
    try:
        url = f"{SUPABASE_URL}/rest/v1/app_feedback"
        params = {
            "student_id": f"eq.{student_id}",
            "category": "neq.ADMIN_BROADCAST",
            "select": "*",
            "order": "created_at.desc",
            "limit": "15"
        }
        res = requests.get(url, headers=_headers(), params=params, timeout=6)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print("Supabase get_user_feedback error:", e)
    return []


def create_admin_broadcast(target_id: str, title: str, body: str):
    """Saves an Admin Broadcast in Supabase so students see it inside their dashboard."""
    if not is_db_configured():
        return False
    try:
        # Use target student_id, or 'ALL' (if foreign key allows) or attach to existing users
        url = f"{SUPABASE_URL}/rest/v1/app_feedback"
        users = get_admin_dashboard_data().get("users", [])
        targets = [u["student_id"] for u in users if target_id == "all" or u["student_id"] == target_id]
        for tid in targets:
            payload = {
                "student_id": str(tid),
                "student_name": "⚡ Admin Announcement",
                "category": "ADMIN_BROADCAST",
                "rating": 5,
                "message": title.strip()[:150],
                "admin_reply": body.strip()[:1000],
                "status": "Unread"
            }
            requests.post(url, headers=_headers("return=minimal"), json=payload, timeout=6)
        return True
    except Exception as e:
        print("Broadcast save error:", e)
        return False


def get_user_announcements(student_id: str):
    """Fetches recent Admin Broadcasts and Developer Replies for the student's top banner."""
    if not is_db_configured() or not is_valid_student_id(student_id):
        return []
    try:
        url = f"{SUPABASE_URL}/rest/v1/app_feedback"
        params = {
            "student_id": f"eq.{student_id}",
            "category": "eq.ADMIN_BROADCAST",
            "select": "*",
            "order": "created_at.desc",
            "limit": "3"
        }
        res = requests.get(url, headers=_headers(), params=params, timeout=6)
        if res.status_code == 200:
            return res.json()
    except Exception:
        pass
    return []


def admin_delete_feedback(feedback_id: int):
    if not is_db_configured():
        return False
    try:
        url = f"{SUPABASE_URL}/rest/v1/app_feedback"
        params = {"id": f"eq.{int(feedback_id)}"}
        res = requests.delete(url, headers=_headers("return=minimal"), params=params, timeout=6)
        return res.status_code in (200, 204)
    except Exception:
        return False


def get_admin_dashboard_data():
    """Fetches all users, feedback tickets, and recent login logs for the Admin Console."""
    data = {"users": [], "feedback": [], "logs": []}
    if not is_db_configured():
        return data

    try:
        u_res = requests.get(
            f"{SUPABASE_URL}/rest/v1/portal_users",
            headers=_headers(),
            params={"select": "*", "order": "last_login_at.desc"},
            timeout=8
        )
        if u_res.status_code == 200:
            data["users"] = u_res.json()

        f_res = requests.get(
            f"{SUPABASE_URL}/rest/v1/app_feedback",
            headers=_headers(),
            params={"select": "*", "order": "created_at.desc"},
            timeout=8
        )
        if f_res.status_code == 200:
            data["feedback"] = f_res.json()

        l_res = requests.get(
            f"{SUPABASE_URL}/rest/v1/login_logs",
            headers=_headers(),
            params={"select": "*", "order": "logged_in_at.desc", "limit": "100"},
            timeout=8
        )
        if l_res.status_code == 200:
            data["logs"] = l_res.json()
    except Exception as e:
        print("Admin data fetch error:", e)

    return data


def admin_update_feedback(feedback_id: int, status: str, admin_reply: str):
    """Updates the status and developer reply on a feedback item and returns the ticket."""
    if not is_db_configured():
        return False, None
    try:
        url = f"{SUPABASE_URL}/rest/v1/app_feedback"
        params = {"id": f"eq.{int(feedback_id)}"}
        payload = {
            "status": status,
            "admin_reply": admin_reply.strip() if admin_reply else None
        }
        res = requests.patch(url, headers=_headers("return=representation"), params=params, json=payload, timeout=8)
        if res.status_code in (200, 204):
            rows = res.json() if res.text else []
            return True, (rows[0] if rows else None)
    except Exception as e:
        print("Admin reply error:", e)
    return False, None


def admin_manage_user(student_id: str, action: str):
    """Allows the Admin to wipe a user's vault, toggle auto-sync, or delete a user row."""
    if not is_db_configured() or not is_valid_student_id(student_id):
        return False, "Invalid student ID."

    url = f"{SUPABASE_URL}/rest/v1/portal_users"
    params = {"student_id": f"eq.{student_id}"}
    try:
        if action == "wipe_vault":
            res = requests.patch(
                url,
                headers=_headers("return=minimal"),
                params=params,
                json={"encrypted_password": None, "auto_sync_enabled": False},
                timeout=8
            )
            return res.status_code in (200, 204), f"Wiped Cloud Vault for {student_id}."
        elif action == "toggle_sync":
            user = get_user_record(student_id)
            new_state = not bool(user.get("auto_sync_enabled")) if user else False
            res = requests.patch(
                url,
                headers=_headers("return=minimal"),
                params=params,
                json={"auto_sync_enabled": new_state},
                timeout=8
            )
            return res.status_code in (200, 204), f"Auto-sync set to {new_state} for {student_id}."
        elif action == "delete_user":
            res = requests.delete(url, headers=_headers("return=minimal"), params=params, timeout=8)
            return res.status_code in (200, 204), f"Deleted user {student_id} from Supabase."
    except Exception as e:
        return False, str(e)
    return False, "Unknown action."    