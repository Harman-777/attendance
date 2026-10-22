import os
import json
import smtplib
import tempfile
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
from pywebpush import webpush, WebPushException
from dotenv import load_dotenv

load_dotenv(".env.local")
load_dotenv()

if os.environ.get("VERCEL"):
    CACHE_DIR = os.path.join(tempfile.gettempdir(), "attendance_cache")
else:
    CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

VAPID_PUBLIC_KEY = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_CLAIMS = {"sub": "mailto:alerts@krono.app"}


def get_cache_path(student_id):
    return os.path.join(CACHE_DIR, f"snapshot_{student_id}.json")


def save_snapshot(student_id, data):
    path = get_cache_path(student_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_snapshot(student_id):
    path = get_cache_path(student_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def detect_new_absents(student_id, new_data):
    old_data = load_snapshot(student_id)
    old_records = set()
    if old_data and "calendar_records" in old_data:
        for r in old_data["calendar_records"]:
            if r.get("status") == "ABSENT":
                old_records.add(f"{r.get('date')}|{r.get('subject')}")

    new_absents = []
    for r in new_data.get("calendar_records", []):
        if r.get("status") == "ABSENT":
            key = f"{r.get('date')}|{r.get('subject')}"
            if old_data and key not in old_records:
                new_absents.append(r)

    return new_absents


def send_web_push(subscription_info: dict, title: str, body: str, url: str = "/dashboard"):
    """Sends an encrypted Web Push notification to the user's phone or desktop lock screen."""
    if not subscription_info or not VAPID_PRIVATE_KEY:
        return False, "Push subscription or VAPID_PRIVATE_KEY missing."

    payload = json.dumps({
        "title": title,
        "body": body,
        "url": url
    })

    try:
        webpush(
            subscription_info=subscription_info,
            data=payload,
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
            timeout=10
        )
        return True, "Lock-screen Web Push sent successfully!"
    except WebPushException as e:
        return False, f"WebPush error: {str(e)}"
    except Exception as e:
        return False, f"Push error: {str(e)}"


def send_absent_email(to_email, student_name, absent_list, smtp_user=None, smtp_pass=None):
    """
    Sends an HTML absent alert via Resend API (if RESEND_API_KEY is set)
    or server-side SMTP (without requiring the user to enter a password).
    """
    if not to_email or not absent_list:
        return False, "Recipient email saved to Supabase for background alerts."

    rows_html = "".join(
        f"<li><b>{item['subject']}</b> on <b>{item['date']}</b> — <span style='color:#ef4444;'>ABSENT</span></li>"
        for item in absent_list
    )

    html_body = f"""
    <div style="font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 24px; border-radius: 12px;">
        <h2 style="color: #ef4444; margin-top: 0;">⚠️ Krono Absent Alert</h2>
        <p>Hello <b>{student_name}</b>,</p>
        <p>New <b>ABSENT</b> attendance records were detected on your portal account:</p>
        <ul>{rows_html}</ul>
        <p style="color: #94a3b8; font-size: 0.9rem;">If this was marked by mistake, open Krono and use the <b>1-Click Dispute Generator</b>.</p>
    </div>
    """

    # Option 1: Zero-Config Cloud Email API (Resend.com - 3,000 free emails/mo)
    resend_key = os.environ.get("RESEND_API_KEY", "").strip()
    if resend_key:
        try:
            r = requests.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                json={
                    "from": os.environ.get("RESEND_FROM_EMAIL", "Krono <onboarding@resend.dev>"),
                    "to": [to_email],
                    "subject": f"⚠️ Attendance Alert: Marked ABSENT ({len(absent_list)} Lecture)",
                    "html": html_body
                },
                timeout=10
            )
            if r.status_code in (200, 201):
                return True, f"Email alert sent to {to_email}!"
        except Exception as e:
            print("Resend API error:", e)

    # Option 2: Server-level SMTP fallback
    sender_email = smtp_user or os.environ.get("ALERT_SMTP_EMAIL", "").strip()
    sender_pass = smtp_pass or os.environ.get("ALERT_SMTP_PASS", "").strip()

    if not sender_email or not sender_pass:
        return True, f"Email ({to_email}) saved to Supabase! Enable Web Push above for instant lock-screen alerts."

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"⚠️ Attendance Alert: Marked ABSENT ({len(absent_list)} Lecture)"
        msg["From"] = sender_email
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            server.login(sender_email, sender_pass)
            server.sendmail(sender_email, to_email, msg.as_string())

        return True, f"Email alert sent to {to_email}!"
    except Exception as e:
        return False, f"Email error: {str(e)}"