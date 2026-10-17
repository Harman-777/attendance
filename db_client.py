import os
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
    if not is_db_configured() or not student_id:
        return None
    try:
        url = f"{SUPABASE_URL}/rest/v1/portal_users?student_id=eq.{student_id}&select=*"
        res = requests.get(url, headers=_headers(), timeout=6)
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
    if not is_db_configured() or not student_id:
        return False, "Supabase is not configured.", ""

    enc_val = encrypt_password(plain_password) if (enable and plain_password) else None
    update_data = {
        "encrypted_password": enc_val,
        "auto_sync_enabled": bool(enc_val)
    }

    try:
        url = f"{SUPABASE_URL}/rest/v1/portal_users?student_id=eq.{student_id}"
        res = requests.patch(url, headers=_headers("return=minimal"), json=update_data, timeout=8)
        if res.status_code in (200, 204):
            if enc_val:
                preview = enc_val[:16] + "..." + enc_val[-6:]
                return True, f"Password encrypted & saved to Supabase Vault ({preview})!", enc_val
            return True, "Password removed from Supabase Vault (set to EMPTY).", ""
        return False, f"Supabase error ({res.status_code}): {res.text}", ""
    except Exception as e:
        return False, f"Database connection error: {str(e)}", ""


def sync_user_to_supabase(student_id: str, plain_password: str, data: dict, is_login_event: bool = False):
    """
    Upserts the student's profile and attendance snapshot.
    Preserves existing encrypted_password if the user already opted into the Vault;
    otherwise leaves encrypted_password empty until they click the Encrypt button.
    """
    if not is_db_configured() or not data:
        return []

    existing = get_user_record(student_id)
    old_absents = set(existing.get("known_absents") or []) if existing else set()
    login_count = (existing.get("login_count") or 0) + (1 if is_login_event else 0) if existing else 1

    # Preserve incomplete fields if this was a fast attendance-only load
    if existing and existing.get("cached_profile") and data.get("partial_load"):
        old_cache = existing["cached_profile"]
        if not data.get("results") and old_cache.get("results"):
            data["results"] = old_cache["results"]
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

    # Only keep encrypted_password if user previously enabled the Vault
    existing_enc = existing.get("encrypted_password") if existing else None
    vault_pw = encrypt_password(plain_password) if (existing_enc and plain_password) else existing_enc

    now_iso = datetime.now(timezone.utc).isoformat()
    payload = {
        "student_id": str(student_id),
        "student_name": data.get("student_name", "Student"),
        "encrypted_password": vault_pw,
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


def save_push_or_email_prefs(student_id: str, email: str = None, push_sub: dict = None, auto_sync: bool = True):
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