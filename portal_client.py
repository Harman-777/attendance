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
    def __init__(self, student_id, password, cookies=None):
        self.student_id = student_id
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.logged_in = False
        if cookies:
            self.session.cookies.update(cookies)
            self.logged_in = True

    def get_cookies(self):
        return self.session.cookies.get_dict()

    def authenticate(self):
        if not self.student_id or not self.password:
            return False, "Missing Student ID or Password."
        try:
            res = self.session.get(LOGIN_URL, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            form = soup.find("form")

            payload = {}
            id_field_found = False
            pw_field_found = False

            # Dynamically grab all hidden tokens and exact field names from the login form
            for inp in (form.find_all("input") if form else soup.find_all("input")):
                name = inp.get("name")
                if not name:
                    continue
                itype = (inp.get("type") or "text").lower()
                if itype == "hidden":
                    payload[name] = inp.get("value", "")
                elif itype == "password" or "pass" in name.lower():
                    payload[name] = self.password
                    pw_field_found = True
                elif itype in ("text", "number", "tel") and not id_field_found:
                    payload[name] = self.student_id
                    id_field_found = True

            if not id_field_found:
                payload["StudentId"] = self.student_id
                payload["SId"] = self.student_id
            if not pw_field_found:
                payload["Password"] = self.password

            post_url = urljoin(LOGIN_URL, form["action"]) if (form and form.get("action")) else LOGIN_URL
            self.session.post(post_url, data=payload, timeout=10)

            dash_res = self.session.get(DASHBOARD_URL, timeout=10)
            if "StudentLogin" in dash_res.url or "AttendanceReport" not in dash_res.text:
                return False, "Invalid Student ID or Password on college portal."

            self.logged_in = True
            self._cached_dash_html = dash_res.text
            return True, None
        except Exception as e:
            return False, f"Portal unreachable: {str(e)}"

    def change_password(self, old_password, new_password, confirm_password):
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
            candidate_urls = []
            for a in dash_soup.find_all("a"):
                txt = a.get_text(" ", strip=True).lower()
                href = a.get("href", "")
                onclick = a.get("onclick", "")
                if any(k in txt for k in ["profile", "bio", "student info", "personal", "details"]) or any(k in href.lower() for k in ["profile", "studentinfo", "biodata"]):
                    if href and not href.startswith("#") and not href.startswith("javascript"):
                        candidate_urls.append(urljoin(DASHBOARD_URL + "/", href))
                    elif onclick:
                        m = re.search(r"['\"]([^'\"]*profile[^'\"]*)['\"]", onclick, re.I)
                        if m:
                            candidate_urls.append(urljoin(DASHBOARD_URL + "/", m.group(1)))

            candidate_urls.extend([
                "https://agclms.in/DashBoardStudent/StudentProfile",
                "https://agclms.in/DashBoardStudent/StudentProfileNew",
                "https://agclms.in/DashBoardStudent/Profile",
                "https://agclms.in/DashBoardStudent/MyProfile",
                "https://agclms.in/DashBoardStudent/StudentInfo",
                "https://agclms.in/StudentProfile",
                "https://agclms.in/Student/StudentProfile",
                "https://agclms.in/Student/Profile",
                "https://agclms.in/Student/StudentInfo"
            ])

            # Deduplicate URLs maintaining order
            seen_urls = set()
            clean_candidates = []
            for u in candidate_urls:
                if u and u not in seen_urls:
                    seen_urls.add(u)
                    clean_candidates.append(u)

            p_soup = None
            active_url = DASHBOARD_URL
            for url in clean_candidates:
                try:
                    r = self.session.get(url, timeout=8)
                    if r.status_code == 200 and "StudentLogin" not in r.url and len(r.text) > 400:
                        if any(k in r.text for k in ["Roll", "Student", "Class", "Course", "Father", "Mother", "Batch", "Mobile", "Email", "Enrollment"]):
                            p_soup = BeautifulSoup(r.text, "html.parser")
                            active_url = url
                            break
                except Exception:
                    continue

            photo_url = None
            details = []

            if p_soup:
                for img in p_soup.find_all("img"):
                    src = img.get("src", "")
                    if src and not any(ig in src.lower() for ig in ["logo", "naac", "banner", "icon", "footer", "header"]):
                        photo_url = urljoin(active_url, src)
                        break

                known_labels = [
                    "Name", "Student Id", "Email Id", "Mobile No",
                    "Batch", "Class Name", "University Rollno",
                    "Father Name", "Mother Name", "Date of Birth",
                    "Aadhaar No", "Address", "City", "State", "Country"
                ]

                for tr in p_soup.find_all("tr"):
                    cells = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"]) if td.get_text(strip=True)]
                    if len(cells) == 2:
                        details.append((cells[0].rstrip(":").strip(), cells[1].strip()))
                    elif len(cells) >= 4:
                        details.append((cells[0].rstrip(":").strip(), cells[1].strip()))
                        details.append((cells[2].rstrip(":").strip(), cells[3].strip()))

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

            # Robust Dashboard Fallback: ensure core fields are always populated for every student
            dash_text = dash_soup.get_text(" ", strip=True)
            existing_keys = {k.lower() for k, v in details}

            if "name" not in existing_keys:
                name_match = re.search(r"Welcome\s+([A-Za-z\s]+?)(?:\||Student|Roll|Incharge|$)", dash_text, re.I)
                if name_match:
                    details.insert(0, ("Name", name_match.group(1).strip()))

            if "student id" not in existing_keys and "university rollno" not in existing_keys:
                details.append(("Student Id", str(self.student_id)))

            if "faculty incharge" not in existing_keys:
                inc_match = re.search(r"Incharge\s*Name\s*:\s*([A-Za-z\s\.]+?)(?:Subjects|Session|$)", dash_text, re.I)
                if inc_match:
                    details.append(("Faculty Incharge", inc_match.group(1).strip()))

            sess_match = re.search(r"Session\s*:\s*([0-9\-\s]+)", dash_text, re.I)
            if sess_match and "batch" not in existing_keys:
                details.append(("Batch", sess_match.group(1).strip()))

            cls_match = re.search(r"(?:Class|Course)\s*:\s*([A-Za-z0-9\-\.\s]+?)(?:\||Section|Roll|$)", dash_text, re.I)
            if cls_match and "class name" not in existing_keys:
                details.append(("Class Name", cls_match.group(1).strip()))

            unique_details = []
            seen = set()
            for k, v in details:
                k_clean = k.strip().rstrip(":")
                v_clean = v.strip()
                if k_clean.lower() not in seen and v_clean:
                    seen.add(k_clean.lower())
                    unique_details.append((k_clean, v_clean))

            return {"photo_url": photo_url, "details": unique_details}
        except Exception:
            return {"photo_url": None, "details": [("Student Id", str(self.student_id))]}

    def get_exam_results(self):
        try:
            res = self.session.get(RESULTS_URL, timeout=8)
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
                r = self.session.get(sem_url, timeout=8)
                s = BeautifulSoup(r.text, "html.parser")
                tables = []
                extracted_grades = []
                has_reappear = False
                reappear_subjects = []

                for table in s.find_all("table"):
                    rows = []
                    for tr in table.find_all("tr"):
                        cols = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                        if cols:
                            rows.append(cols)
                            # Check for individual subject grades
                            for cell in cols:
                                cell_up = cell.upper()
                                if cell_up in grade_points:
                                    extracted_grades.append(grade_points[cell_up])

                            # Detect Re-appear / Compartment / Backlog in subject row
                            row_str = " ".join(cols).upper()
                            is_reappear = (
                                any(re.search(rf"\b{re.escape(k)}\b", row_str) for k in ["REAPPEAR", "RE-APPEAR", "FAIL", "COMPARTMENT", "BACKLOG"])
                                or any(c.upper() in ["F", "RA", "AB"] for c in cols)
                            )
                            if is_reappear:
                                has_reappear = True
                                subj = cols[1] if len(cols) > 1 and not cols[1].isdigit() else (cols[2] if len(cols) > 2 else (cols[0] if cols else "Subject"))
                                if subj and not any(h in subj.lower() for h in ["subject", "course", "paper", "s.no"]):
                                    reappear_subjects.append(subj)

                    if rows:
                        tables.append(rows)

                sgpa = round(sum(extracted_grades) / len(extracted_grades), 2) if extracted_grades else 0.0
                status = "RE-APPEAR" if has_reappear else ("PASSED" if sgpa > 0 else "PUBLISHED")

                return {
                    "code": code,
                    "semester": sem_name,
                    "tables": tables,
                    "sgpa": sgpa,
                    "has_reappear": has_reappear,
                    "reappear_subjects": list(dict.fromkeys(reappear_subjects)),
                    "status": status
                }

            with ThreadPoolExecutor(max_workers=5) as executor:
                return list(executor.map(fetch_single_sem, options))
        except Exception:
            return []

    def get_fees(self, dash_soup):
        try:
            candidate_urls = []
            for a in dash_soup.find_all("a"):
                href = a.get("href", "")
                txt = a.get_text(strip=True).lower()
                if any(k in txt or k in href.lower() for k in ["fee", "dues", "ledger", "receipt"]):
                    if href and not href.startswith("#"):
                        candidate_urls.append(urljoin(DASHBOARD_URL + "/", href))

            candidate_urls.extend([
                "https://agclms.in/DashBoardStudent/StudentFeeDetails",
                "https://agclms.in/DashBoardStudent/FeeDetails",
                "https://agclms.in/DashBoardStudent/Fees",
                "https://agclms.in/StudentFee/StudentFeeDetails",
                "https://agclms.in/DashBoardStudent/FeeReceipt",
                "https://agclms.in/Student/FeeDetails"
            ])

            seen_fee_urls = set()
            fee_tables = []
            for f_url in candidate_urls:
                if not f_url or f_url in seen_fee_urls:
                    continue
                seen_fee_urls.add(f_url)
                try:
                    r = self.session.get(f_url, timeout=8)
                    if r.status_code == 200 and "StudentLogin" not in r.url and len(r.text) > 400:
                        s = BeautifulSoup(r.text, "html.parser")
                        for table in s.find_all("table"):
                            rows = []
                            for tr in table.find_all("tr"):
                                cols = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                                if cols:
                                    rows.append(cols)
                            if rows and len(rows) > 0:
                                fee_tables.append(rows)
                        if fee_tables:
                            break
                except Exception:
                    continue

            return fee_tables
        except Exception:
            return []

    def get_full_profile(self, fast_mode=False):
        """
        If fast_mode=True, only scrapes Attendance subjects (~2 seconds) so the
        Attendance & Simulator tab renders immediately.
        """
        dash_html = getattr(self, "_cached_dash_html", None)
        if not dash_html:
            if not self.logged_in:
                success, err = self.authenticate()
                if not success:
                    return None, err
                dash_html = getattr(self, "_cached_dash_html", None)

            if not dash_html:
                dash_res = self.session.get(DASHBOARD_URL, timeout=10)
                if "StudentLogin" in dash_res.url or "AttendanceReport" not in dash_res.text:
                    success, err = self.authenticate()
                    if not success:
                        return None, err
                    dash_html = getattr(self, "_cached_dash_html", "")
                else:
                    dash_html = dash_res.text

        today_str = datetime.now().strftime("%d-%m-%Y")
        today_pretty = datetime.now().strftime("%a, %d %b %Y")
        sync_time = datetime.now().strftime("%d %b %Y, %I:%M %p")

        dash_soup = BeautifulSoup(dash_html, "html.parser")
        text = dash_soup.get_text(" ", strip=True)

        incharge_match = re.search(r"Incharge\s*Name\s*:\s*([A-Za-z\s\.]+?)(?:Subjects|Session|$)", text, re.I)
        incharge_name = incharge_match.group(1).strip() if incharge_match else "Vinod Kumar"

        # Try extracting student name directly from dashboard header for fast_mode
        name_match = re.search(r"Welcome\s+([A-Za-z\s]+?)(?:\||Student|Roll|Incharge|$)", text, re.I)
        student_name = name_match.group(1).strip() if name_match else "Student"

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
            r = self.session.get(url, timeout=8)
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

        if fast_mode:
            return {
                "student_id": self.student_id,
                "student_name": student_name,
                "student_email": "",
                "incharge": incharge_name,
                "today_date": today_pretty,
                "last_synced": sync_time + " (Fast Sync)",
                "is_offline": False,
                "partial_load": True,
                "today_attendance": today_attendance,
                "calendar_records": all_records,
                "subjects": subject_results,
                "results": [],
                "profile": {"photo_url": None, "details": []},
                "fees": []
            }, None

        # Fetch Results, Profile, and Fees in parallel so background sync is also 3x faster
        with ThreadPoolExecutor(max_workers=3) as extra_exec:
            f_results = extra_exec.submit(self.get_exam_results)
            f_profile = extra_exec.submit(self.get_student_profile, dash_soup)
            f_fees = extra_exec.submit(self.get_fees, dash_soup)

            results_data = f_results.result()
            profile_data = f_profile.result()
            fees_data = f_fees.result()

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
            "partial_load": False,
            "today_attendance": today_attendance,
            "calendar_records": all_records,
            "subjects": subject_results,
            "results": results_data,
            "profile": profile_data,
            "fees": fees_data
        }, None