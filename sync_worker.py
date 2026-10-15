import sys
from concurrent.futures import ThreadPoolExecutor
from portal_client import PortalClient
from db_client import (
    get_all_auto_sync_users,
    decrypt_password,
    sync_user_to_supabase
)
from notifier import send_web_push, send_absent_email


def process_single_user(user_row: dict, force_test: bool = False):
    student_id = user_row.get("student_id")
    student_name = user_row.get("student_name") or "User"
    enc_pw = user_row.get("encrypted_password")
    push_sub = user_row.get("push_subscription")
    email = user_row.get("email")

    if not student_id or not enc_pw:
        print(f"[SKIP] {student_id}: Missing encrypted credentials.")
        return

    plain_pw = decrypt_password(enc_pw)
    if not plain_pw:
        print(f"[ERROR] {student_id}: Could not decrypt password (check ENCRYPTION_KEY).")
        return

    print(f"[SYNC] Checking portal attendance for {student_id} ({student_name})...")
    client = PortalClient(student_id, plain_pw)
    data, err = client.get_full_profile()

    if err or not data:
        print(f"[WARN] {student_id}: Portal unreachable or login failed -> {err}")
        return

    # Compare against Supabase known_absents and update cloud snapshot
    new_absents = sync_user_to_supabase(student_id, plain_pw, data, is_login_event=False)

    # Allow "--test" flag to simulate a newly detected absent for instant verification
    if force_test and not new_absents:
        today_str = data.get("today_date", "Today")
        sample_subj = data["subjects"][0]["name"] if data.get("subjects") else "Information Security"
        new_absents = [{"subject": sample_subj, "date": today_str, "status": "ABSENT"}]
        print(f"[TEST MODE] Simulating new ABSENT in '{sample_subj}' for {student_id}...")

    if not new_absents:
        print(f"[OK] {student_id}: Synced cleanly. No new absents detected.")
        return

    # Format notification text for newly detected absents
    subjects_str = ", ".join(f"{a['subject']} ({a['date']})" for a in new_absents)
    title = f"⚠️ Marked ABSENT: {new_absents[0]['subject']}"
    body = f"New absent recorded: {subjects_str}. Tap to view attendance impact or generate a dispute."

    # 1. Fire Lock-Screen Web Push Notification
    if push_sub:
        ok, msg = send_web_push(push_sub, title=title, body=body, url="/dashboard")
        print(f"[PUSH] {student_id}: {ok} -> {msg}")

    # 2. Fire Email Notification (if configured)
    if email:
        ok, msg = send_absent_email(email, student_name, new_absents)
        print(f"[EMAIL] {student_id}: {ok} -> {msg}")


def run_background_sync(force_test: bool = False):
    print("=== Ultra Portal Background Auto-Sync Started ===")
    users = get_all_auto_sync_users()
    print(f"Found {len(users)} opted-in user(s) in Supabase.")

    if not users:
        print("No users found. Log in once on the dashboard to register your account.")
        return

    # Process up to 5 accounts concurrently for fast execution
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_single_user, u, force_test) for u in users]
        for f in futures:
            try:
                f.result()
            except Exception as e:
                print("Worker thread error:", e)

    print("=== Background Auto-Sync Completed ===")


if __name__ == "__main__":
    is_test = "--test" in sys.argv
    run_background_sync(force_test=is_test)