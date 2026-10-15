import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

LOGIN_URL = "https://agclms.in/Elogin/StudentLogin"
DASHBOARD_URL = "https://agclms.in/DashBoardStudent"
RESULTS_URL = "https://agclms.in/DashBoardStudent/Results"


class PortalClient:
    def __init__(self, student_id, password):
        self.student_id = student_id
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.logged_in = False

    def authenticate(self):
        try:
            res = self.session.get(LOGIN_URL, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            token = soup.find("input", {"name": "__RequestVerificationToken"})
            if not token:
                return False, "Security token not found on login page."

            payload = {
                "StudentId": self.student_id,
                "Password": self.password,
                "__RequestVerificationToken": token.get("value", "")
            }
            self.session.post(LOGIN_URL, data=payload, timeout=10)

            dash_res = self.session.get(DASHBOARD_URL, timeout=10)
            if "StudentLogin" in dash_res.url or "AttendanceReport" not in dash_res.text:
                return False, "Invalid Student ID or Password."

            self.logged_in = True
            return True, None
        except Exception as e:
            return False, f"Portal unreachable: {str(e)}"

    def change_password(self, old_password, new_password, confirm_password):
        """Submits a password change request directly to the college portal."""
        if not self.logged_in:
            ok, err = self.authenticate()
            if not ok:
                return False, err

        try:
            dash_res = self.session.get(DASHBOARD_URL, timeout=10)
            dash_soup = BeautifulSoup(dash_res.text, "html.parser")

            cp_url = None
            for a in dash_soup.find_all("a"):
                txt = a.get_text(strip=True).lower()
                href = a.get("href", "")
                if "password" in txt or "password" in href.lower():
                    if href and href != "#":
                        cp_url = urljoin(DASHBOARD_URL + "/", href)
                        break

            if not cp_url:
                cp_url = f"{DASHBOARD_URL}/ChangePassword"

            cp_page = self.session.get(cp_url, timeout=10)
            cp_soup = BeautifulSoup(cp_page.text, "html.parser")

            form = cp_soup.find("form")
            post_url = urljoin(cp_url, form["action"]) if (form and form.get("action")) else cp_url

            payload = {}
            pwd_inputs = []
            for inp in cp_soup.find_all("input"):
                name = inp.get("name")
                itype = (inp.get("type") or "").lower()
                if not name:
                    continue
                if itype == "hidden":
                    payload[name] = inp.get("value", "")
                elif itype == "password" or "pass" in name.lower():
                    pwd_inputs.append(name)

            # Map old, new, and confirm fields dynamically
            if len(pwd_inputs) >= 3:
                payload[pwd_inputs[0]] = old_password
                payload[pwd_inputs[1]] = new_password
                payload[pwd_inputs[2]] = confirm_password
            else:
                payload.update({
                    "OldPassword": old_password,
                    "CurrentPassword": old_password,
                    "NewPassword": new_password,
                    "ConfirmPassword": confirm_password
                })

            res = self.session.post(post_url, data=payload, timeout=10)
            if res.status_code == 200 and ("success" in res.text.lower() or "changed" in res.text.lower()):
                return True, "Password updated successfully on college portal!"
            return True, "Password change request submitted to portal."
        except Exception as e:
            return False, f"Could not update password: {str(e)}"

    def get_student_profile(self, dash_soup):
        try:
            profile_url = None
            for a in dash_soup.find_all("a"):
                txt = a.get_text(strip=True).lower()
                href = a.get("href", "")
                if txt == "profile" or "profile" in href.lower():
                    if href and href != "#":
                        profile_url = urljoin(DASHBOARD_URL + "/", href)
                        break

            candidate_urls = [profile_url] if profile_url else []
            candidate_urls.extend([
                "https://agclms.in/DashBoardStudent/StudentProfile",
                "https://agclms.in/DashBoardStudent/Profile",
                "https://agclms.in/Student/Profile"
            ])

            p_soup = None
            active_url = DASHBOARD_URL
            for url in candidate_urls:
                if not url:
                    continue
                r = self.session.get(url, timeout=10)
                if r.status_code == 200 and "StudentLogin" not in r.url and len(r.text) > 500:
                    if "Batch" in r.text or "Father" in r.text or "Mobile" in r.text:
                        p_soup = BeautifulSoup(r.text, "html.parser")
                        active_url = url
                        break

            if not p_soup:
                return {"photo_url": None, "details": []}

            photo_url = None
            for img in p_soup.find_all("img"):
                src = img.get("src", "")
                if src and not any(ig in src.lower() for ig in ["logo", "naac", "banner", "icon"]):
                    photo_url = urljoin(active_url, src)
                    break

            known_labels = [
                "Name", "Student Id", "Email Id", "Mobile No",
                "Batch", "Class Name", "University Rollno",
                "Father Name", "Mother Name", "Date of Birth",
                "Aadhaar No", "Address", "City", "State", "Country"
            ]

            details = []
            for tr in p_soup.find_all("tr"):
                cells = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"]) if td.get_text(strip=True)]
                if len(cells) == 2:
                    details.append((cells[0].rstrip(":"), cells[1]))
                elif len(cells) >= 4:
                    details.append((cells[0].rstrip(":"), cells[1]))
                    details.append((cells[2].rstrip(":"), cells[3]))

            if len(details) < 4:
                strings = [s.strip().rstrip(":") for s in p_soup.stripped_strings if s.strip() and s.strip() != ":"]
                lower_known = {k.lower(): k for k in known_labels}

                for i, s in enumerate(strings):
                    if s.lower() in lower_known and i + 1 < len(strings):
                        nxt = strings[i + 1]
                        if nxt.lower() not in lower_known:
                            details.append((lower_known[s.lower()], nxt))

                if len(details) < 4:
                    for group in [
                        ["Name", "Student Id", "Email Id", "Mobile No"],
                        ["Batch", "Class Name", "University Rollno", "Father Name", "Mother Name", "Date of Birth", "Aadhaar No", "Address", "City", "State", "Country"]
                    ]:
                        indices = []
                        for lbl in group:
                            for idx, text_item in enumerate(strings):
                                if text_item.lower() == lbl.lower():
                                    indices.append(idx)
                                    break
                        if len(indices) >= 3 and indices == sorted(indices):
                            last_lbl_idx = indices[-1]
                            count = len(indices)
                            values = strings[last_lbl_idx + 1 : last_lbl_idx + 1 + count]
                            for lbl_idx, val in zip(indices, values):
                                details.append((strings[lbl_idx], val))

            unique_details = []
            seen = set()
            for k, v in details:
                if k.lower() not in seen and v:
                    seen.add(k.lower())
                    unique_details.append((k, v))

            return {"photo_url": photo_url, "details": unique_details}
        except Exception:
            return {"photo_url": None, "details": []}

    def get_exam_results(self):
        try:
            res = self.session.get(RESULTS_URL, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            select = soup.find("select", {"name": "ClassCode"})
            if not select:
                return []

            options = []
            for opt in select.find_all("option"):
                val = opt.get("value", "").strip()
                label = opt.get_text(strip=True)
                if val and val != "-1":
                    options.append((val, label))

            grade_points = {"O": 10, "A+": 9, "A": 8, "B+": 7, "B": 6, "C": 5, "P": 4, "F": 0, "E": 0, "I": 0}

            def fetch_single_sem(item):
                code, sem_name = item
                sem_url = f"{RESULTS_URL}?ClassCode={code}"
                r = self.session.get(sem_url, timeout=10)
                s = BeautifulSoup(r.text, "html.parser")
                tables = []
                extracted_grades = []

                for table in s.find_all("table"):
                    rows = []
                    for tr in table.find_all("tr"):
                        cols = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                        if cols:
                            rows.append(cols)
                            for cell in cols:
                                if cell.upper() in grade_points:
                                    extracted_grades.append(grade_points[cell.upper()])
                    if rows:
                        tables.append(rows)

                # Calculate estimated SGPA from letter grades or numeric marks
                sgpa = round(sum(extracted_grades) / len(extracted_grades), 2) if extracted_grades else 0.0
                return {"code": code, "semester": sem_name, "tables": tables, "sgpa": sgpa}

            with ThreadPoolExecutor(max_workers=5) as executor:
                return list(executor.map(fetch_single_sem, options))
        except Exception:
            return []

    def get_fees(self, dash_soup):
        try:
            fee_tables = []
            for a in dash_soup.find_all("a"):
                href = a.get("href", "")
                txt = a.get_text(strip=True).lower()
                if ("fee" in txt or "fee" in href.lower()) and href and href != "#":
                    f_url = urljoin(DASHBOARD_URL + "/", href)
                    r = self.session.get(f_url, timeout=10)
                    s = BeautifulSoup(r.text, "html.parser")
                    for table in s.find_all("table"):
                        rows = []
                        for tr in table.find_all("tr"):
                            cols = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                            if cols:
                                rows.append(cols)
                        if rows:
                            fee_tables.append(rows)
            return fee_tables
        except Exception:
            return []

    def get_full_profile(self):
        if not self.logged_in:
            success, err = self.authenticate()
            if not success:
                return None, err

        today_str = datetime.now().strftime("%d-%m-%Y")
        today_pretty = datetime.now().strftime("%a, %d %b %Y")
        sync_time = datetime.now().strftime("%d %b %Y, %I:%M %p")

        dash_res = self.session.get(DASHBOARD_URL, timeout=10)
        dash_soup = BeautifulSoup(dash_res.text, "html.parser")
        text = dash_soup.get_text(" ", strip=True)

        incharge_match = re.search(r"Incharge\s*Name\s*:\s*([A-Za-z\s\.]+?)(?:Subjects|Session|$)", text, re.I)
        incharge_name = incharge_match.group(1).strip() if incharge_match else "Vinod Kumar"

        subjects = []
        seen_urls = set()
        for row in dash_soup.find_all("tr"):
            link_tag = row.find("a", href=re.compile(r"AttendanceReport", re.I))
            href = link_tag["href"] if link_tag else None
            if not href:
                match = re.search(r"([/a-zA-Z0-9_]*AttendanceReport\?[^'\"\s>]+)", str(row))
                if match:
                    href = match.group(1)
            if href:
                full_url = urljoin(DASHBOARD_URL + "/", href)
                if full_url not in seen_urls:
                    seen_urls.add(full_url)
                    cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"]) if c.get_text(strip=True)]
                    subject_name = cols[0] if cols else "Subject"
                    subjects.append((subject_name, full_url))

        def fetch_subject(item):
            name, url = item
            r = self.session.get(url, timeout=10)
            s = BeautifulSoup(r.text, "html.parser")
            present, absent = 0, 0
            records = []

            for row in s.find_all("tr"):
                row_text = row.get_text(" ", strip=True)
                upper_text = row_text.upper()
                date_match = re.search(r"(\d{2}-\d{2}-\d{4})", row_text)
                date_val = date_match.group(1) if date_match else None

                if "PRESENT" in upper_text:
                    present += 1
                    if date_val:
                        records.append({"date": date_val, "subject": name, "status": "PRESENT"})
                elif "ABSENT" in upper_text:
                    absent += 1
                    if date_val:
                        records.append({"date": date_val, "subject": name, "status": "ABSENT"})

            total = present + absent
            pct = (present / total * 100) if total > 0 else 0.0
            bunks = int((present - 0.75 * total) // 0.75) if pct >= 75 else 0
            needed = int(((0.75 * total - present) / 0.25) + 0.999) if pct < 75 else 0

            if total == 0:
                status_msg = "No classes held yet."
                danger_level = "none"
            elif pct < 75:
                status_msg = f"Below 75%! Attend next {needed} classes."
                danger_level = "critical"
            elif bunks <= 2:
                status_msg = f"⚠️ Danger Zone: Only {bunks} safe skip(s) left!"
                danger_level = "warning"
            else:
                status_msg = f"Safe! You can skip {bunks} classes."
                danger_level = "safe"

            return {
                "name": name,
                "present": present,
                "total": total,
                "pct": round(pct, 2),
                "bunks": bunks,
                "needed": needed,
                "danger_level": danger_level,
                "status_msg": status_msg,
                "records": records
            }

        with ThreadPoolExecutor(max_workers=8) as executor:
            subject_results = list(executor.map(fetch_subject, subjects))

        all_records = []
        today_attendance = []
        for subj in subject_results:
            for rec in subj["records"]:
                all_records.append(rec)
                if rec["date"] == today_str:
                    today_attendance.append(rec)

        results_data = self.get_exam_results()
        profile_data = self.get_student_profile(dash_soup)
        fees_data = self.get_fees(dash_soup)

        student_name = "Harman"
        student_email = ""
        for k, v in profile_data.get("details", []):
            if k.lower() == "name":
                student_name = v
            elif "email" in k.lower():
                student_email = v

        return {
            "student_id": self.student_id,
            "student_name": student_name,
            "student_email": student_email,
            "incharge": incharge_name,
            "today_date": today_pretty,
            "last_synced": sync_time,
            "is_offline": False,
            "today_attendance": today_attendance,
            "calendar_records": all_records,
            "subjects": subject_results,
            "results": results_data,
            "profile": profile_data,
            "fees": fees_data
        }, None