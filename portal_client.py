import re
import base64
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter
from bs4 import BeautifulSoup

IST = timezone(timedelta(hours=5, minutes=30))

LOGIN_URL = "https://agclms.in/Elogin/StudentLogin"
DASHBOARD_URL = "https://agclms.in/DashBoardStudent"
RESULTS_URL = "https://agclms.in/DashBoardStudent/Results"


def extract_student_name(dash_soup, fallback="Student"):
    """
    Bulletproof student name extraction matching the agclms.in header
    (e.g., `<span class="fs-4 ms-2">HARMAN</span>` right before `Role: STUDENT`).
    """
    if not dash_soup:
        return fallback
    txt_all = dash_soup.get_text(" ", strip=True)

    # 1. Look for specific tag near Role: STUDENT
    role_tag = dash_soup.find(string=re.compile(r"Role\s*:\s*STUDENT", re.I))
    if role_tag:
        parent = role_tag.find_parent(["div", "li", "header", "nav", "span"])
        if parent:
            for s in parent.find_all(["span", "h1", "h2", "h3", "h4", "h5", "h6", "b", "strong"]):
                txt = s.get_text(strip=True)
                if txt and not re.search(r"Role|STUDENT|Feedback|Logout|Change\s*Password|AGC|ERP", txt, re.I):
                    if len(txt) <= 40 and re.search(r"^[A-Za-z\s\.]+$", txt):
                        return txt.strip().title()

    # 2. Regex matching the name immediately preceding Role: STUDENT
    m = re.search(r"([A-Za-z][A-Za-z\s\.]{1,40}?)\s*Role\s*:\s*STUDENT", txt_all, re.I)
    if m:
        cand = m.group(1).strip()
        cand = re.sub(r"^(?:AGC\s*ERP|AGC|ERP|Home|Dashboard|Portal|Feedback|Welcome|Logout|-|\s)+", "", cand, flags=re.I).strip()
        if cand and len(cand) >= 2:
            return cand.title()

    # 3. Welcome ... regex fallback
    wm = re.search(r"Welcome\s+([A-Za-z\s]+?)(?:\||Student|Roll|Incharge|$)", txt_all, re.I)
    if wm:
        cand = wm.group(1).strip()
        if cand:
            return cand.title()

    return fallback


class PortalClient:
    def __init__(self, student_id, password, cookies=None):
        self.student_id = student_id
        self.password = password
        self.session = requests.Session()
        adapter = HTTPAdapter(pool_connections=15, pool_maxsize=15, max_retries=1)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Connection": "keep-alive"
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
            # 1. Post with allow_redirects=False to prevent IIS keepalive socket drops
            r_post = self.session.post(post_url, data=payload, timeout=12, allow_redirects=False)

            post_loc = r_post.headers.get("Location") or ""
            target_dash_url = urljoin(LOGIN_URL, post_loc) if post_loc else DASHBOARD_URL

            # 2. Spawn a clean session to avoid pooled TCP resets from Microsoft-IIS
            fresh_session = requests.Session()
            adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=2)
            fresh_session.mount("https://", adapter)
            fresh_session.mount("http://", adapter)
            fresh_session.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": LOGIN_URL,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            })
            fresh_session.cookies.update(self.session.cookies)
            self.session = fresh_session

            dash_res = self.session.get(target_dash_url, timeout=12)
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
            candidate_urls = [
                "https://agclms.in/DashBoardStudent/Detail",
                "https://agclms.in/DashBoardStudent/StudentProfile",
                "https://agclms.in/DashBoardStudent/Profile"
            ]
            if dash_soup:
                for a in dash_soup.find_all("a"):
                    txt = a.get_text(" ", strip=True).lower()
                    href = a.get("href", "")
                    onclick = a.get("onclick", "")
                    if any(k in txt for k in ["profile", "bio", "student info", "personal", "detail"]) or any(k in href.lower() for k in ["detail", "profile", "studentinfo", "biodata"]):
                        if href and not href.startswith("#") and not href.startswith("javascript"):
                            candidate_urls.insert(0, urljoin(DASHBOARD_URL + "/", href))
                        elif onclick:
                            m = re.search(r"['\"]([^'\"]*(?:profile|detail)[^'\"]*)['\"]", onclick, re.I)
                            if m:
                                candidate_urls.insert(0, urljoin(DASHBOARD_URL + "/", m.group(1)))

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
                    r = self.session.get(url, timeout=5)
                    if r.status_code == 200 and "StudentLogin" not in r.url and len(r.text) > 400:
                        if any(k in r.text for k in ["Roll", "Student", "Class", "Course", "Father", "Mother", "Batch", "Mobile", "Email", "Enrollment", "Detail"]):
                            p_soup = BeautifulSoup(r.text, "html.parser")
                            active_url = url
                            break
                except Exception:
                    continue

            photo_url = None
            details = []

            if p_soup:
                # 1. Parse div.row key-value pairs (left column has <b>)
                for r in p_soup.find_all("div", class_="row"):
                    b = r.find("b")
                    if b:
                        lbl = b.get_text(strip=True).rstrip(":")
                        right = r.find("div", class_=re.compile(r"col-md-7|col-sm-7|col-7"))
                        val = right.get_text(" ", strip=True) if right else r.get_text(" ", strip=True).replace(b.get_text(strip=True), "").strip()
                        val = re.sub(r"\s+", " ", val).strip()
                        if lbl and val and lbl.lower() not in [d[0].lower() for d in details]:
                            details.append((lbl, val))

                # 2. Parse <dl class="row"> with <dt> and <dd>
                dts = p_soup.find_all("dt")
                dds = p_soup.find_all("dd")
                for dt, dd in zip(dts, dds):
                    lbl = dt.get_text(strip=True).rstrip(":")
                    val = re.sub(r"\s+", " ", dd.get_text(" ", strip=True)).strip()
                    if lbl and val and lbl.lower() not in [d[0].lower() for d in details]:
                        details.append((lbl, val))

                # 3. Parse table rows <tr>
                for tr in p_soup.find_all("tr"):
                    cells = [td.get_text(" ", strip=True) for td in tr.find_all(["th", "td"]) if td.get_text(strip=True)]
                    if len(cells) == 2:
                        k = cells[0].rstrip(":").strip()
                        v = cells[1].strip()
                        if k and v and k.lower() not in [d[0].lower() for d in details]:
                            details.append((k, v))
                    elif len(cells) >= 4:
                        k1, v1 = cells[0].rstrip(":").strip(), cells[1].strip()
                        k2, v2 = cells[2].rstrip(":").strip(), cells[3].strip()
                        if k1 and v1 and k1.lower() not in [d[0].lower() for d in details]:
                            details.append((k1, v1))
                        if k2 and v2 and k2.lower() not in [d[0].lower() for d in details]:
                            details.append((k2, v2))

                # 4. Extract student photo if genuine (ignoring logos, default user icons, navbars)
                for img in p_soup.find_all("img"):
                    src = img.get("src", "")
                    if not src:
                        continue
                    is_ignore = any(ig in src.lower() for ig in ["logo", "naac", "banner", "icon", "footer", "agc-amritsar", "dummy", "avatar", "default"]) or any(p.name in ["header", "nav"] for p in img.parents)
                    if not is_ignore:
                        img_full_url = urljoin(active_url, src)
                        try:
                            img_res = self.session.get(img_full_url, timeout=6)
                            if img_res.status_code == 200 and len(img_res.content) > 300:
                                ctype = img_res.headers.get("Content-Type") or "image/jpeg"
                                if "image" not in ctype:
                                    ctype = "image/jpeg"
                                b64_bytes = base64.b64encode(img_res.content).decode("ascii")
                                photo_url = f"data:{ctype};base64,{b64_bytes}"
                                break
                        except Exception:
                            continue

            # Robust Dashboard Fallback: ensure core fields are always populated for every student
            dash_text = dash_soup.get_text(" ", strip=True) if dash_soup else ""
            existing_keys = {k.lower() for k, v in details}

            # Extract student name
            student_name_found = None
            for k, v in details:
                if k.lower() == "name" and v and v.strip() and v.strip().lower() != "student":
                    student_name_found = v.strip().title()
                    break

            if not student_name_found and dash_soup:
                student_name_found = extract_student_name(dash_soup, fallback="")

            if not student_name_found:
                student_name_found = str(self.student_id)

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

            # Ensure ("Name", student_name_found) is always first
            unique_details = [d for d in unique_details if d[0].lower() != "name"]
            unique_details.insert(0, ("Name", student_name_found))

            return {"photo_url": photo_url, "details": unique_details}
        except Exception:
            std_name = extract_student_name(dash_soup, fallback=str(self.student_id)) if dash_soup else str(self.student_id)
            return {"photo_url": None, "details": [("Name", std_name), ("Student Id", str(self.student_id))]}

    def get_exam_results(self, dash_soup=None):
        try:
            candidate_urls = [
                RESULTS_URL,
                "https://agclms.in/DashBoardStudent/Results"
            ]
            if dash_soup:
                for a in dash_soup.find_all("a"):
                    txt = a.get_text(" ", strip=True).lower()
                    href = a.get("href", "")
                    if any(k in txt or k in href.lower() for k in ["result", "marksheet", "grade", "marks", "exam"]):
                        if href and not href.startswith("#") and not href.startswith("javascript"):
                            candidate_urls.insert(0, urljoin(DASHBOARD_URL + "/", href))

            seen_r_urls = set()
            clean_candidates = []
            for u in candidate_urls:
                if u and u not in seen_r_urls:
                    seen_r_urls.add(u)
                    clean_candidates.append(u)

            res = None
            active_results_url = RESULTS_URL
            for url in clean_candidates:
                try:
                    r = self.session.get(url, timeout=5)
                    if r.status_code == 200 and "StudentLogin" not in r.url and len(r.text) > 400:
                        s = BeautifulSoup(r.text, "html.parser")
                        select = s.find("select", {"name": re.compile(r"ClassCode|Semester|Sem|Course", re.I)}) or s.find("select")
                        if select:
                            res = r
                            active_results_url = url
                            break
                except Exception:
                    continue

            if not res:
                return []

            soup = BeautifulSoup(res.text, "html.parser")
            select = soup.find("select", {"name": re.compile(r"ClassCode|Semester|Sem|Course", re.I)}) or soup.find("select")
            if not select:
                return []

            param_name = select.get("name", "ClassCode")
            options = []
            for opt in select.find_all("option"):
                val = opt.get("value", "").strip()
                label = opt.get_text(strip=True)
                if val and val not in ("-1", "0", "") and not label.lower().startswith("select"):
                    options.append((val, label))

            grade_points = {"O": 10, "A+": 9, "A": 8, "B+": 7, "B": 6, "C": 5, "P": 4, "F": 0, "NAF": 0, "NAF(EXT)": 0, "AB": 0, "E": 0, "I": 0}

            def fetch_single_sem(item):
                code, sem_name = item
                sem_url = f"{active_results_url}?{param_name}={code}"
                try:
                    r = self.session.get(sem_url, timeout=6)
                except Exception:
                    return {
                        "code": code,
                        "semester": sem_name,
                        "tables": [],
                        "sgpa": 0.0,
                        "has_reappear": False,
                        "reappear_subjects": [],
                        "status": "UNAVAILABLE"
                    }

                s = BeautifulSoup(r.text, "html.parser")
                tables = []
                extracted_grades = []
                weighted_points = 0.0
                total_credits = 0.0
                has_reappear = False
                reappear_subjects = []
                portal_sgpa = None
                portal_status = None

                for table in s.find_all("table"):
                    rows = []
                    for tr in table.find_all("tr"):
                        cols = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                        if cols:
                            rows.append(cols)
                            row_str = " ".join(cols)

                            sgpa_m = re.search(r"SGPA\s*[:\|]?\s*([0-9\.]+)", row_str, re.I)
                            if sgpa_m:
                                try:
                                    portal_sgpa = float(sgpa_m.group(1))
                                except Exception:
                                    pass

                            status_m = re.search(r"Result\s*Status\s*[:\|]?\s*([A-Za-z\s\-]+)", row_str, re.I)
                            if status_m:
                                portal_status = status_m.group(1).strip()
                                if any(k in portal_status.lower() for k in ["re-appear", "reappear", "fail", "compartment", "backlog"]):
                                    has_reappear = True

                            # Detect subject row: usually starts with digit S.No and has >= 4 columns
                            if len(cols) >= 4 and cols[0].isdigit():
                                subj_name = cols[1]
                                creds = 1.0
                                grade_col = cols[-1]
                                for c in cols[2:]:
                                    try:
                                        creds = float(c)
                                        break
                                    except Exception:
                                        pass

                                grade_clean = grade_col.split("(")[0].strip().upper()
                                pt = grade_points.get(grade_clean, None)
                                if pt is not None:
                                    weighted_points += creds * pt
                                    total_credits += creds
                                    extracted_grades.append(pt)
                                    if pt == 0 or any(k in grade_col.upper() for k in ["F", "RA", "NAF", "AB"]):
                                        has_reappear = True
                                        reappear_subjects.append(subj_name)
                            else:
                                for c in cols:
                                    c_up = c.upper()
                                    if c_up in grade_points:
                                        extracted_grades.append(grade_points[c_up])
                                row_up = row_str.upper()
                                if any(re.search(rf"\b{re.escape(k)}\b", row_up) for k in ["REAPPEAR", "RE-APPEAR", "FAIL", "COMPARTMENT", "BACKLOG"]):
                                    has_reappear = True

                    if rows:
                        tables.append(rows)

                calc_sgpa = round(weighted_points / total_credits, 2) if total_credits > 0 else (round(sum(extracted_grades) / len(extracted_grades), 2) if extracted_grades else 0.0)
                final_sgpa = portal_sgpa if (portal_sgpa is not None and portal_sgpa > 0) else calc_sgpa
                status = "RE-APPEAR" if has_reappear else ("PASSED" if (portal_status == "Pass" or final_sgpa > 0) else "PUBLISHED")

                return {
                    "code": code,
                    "semester": sem_name,
                    "tables": tables,
                    "sgpa": final_sgpa,
                    "has_reappear": has_reappear,
                    "reappear_subjects": list(dict.fromkeys(reappear_subjects)),
                    "status": status
                }

            with ThreadPoolExecutor(max_workers=6) as executor:
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
                "https://agclms.in/DashBoardStudent/FeeDetails"
            ])

            seen_fee_urls = set()
            fee_tables = []
            for f_url in candidate_urls:
                if not f_url or f_url in seen_fee_urls:
                    continue
                seen_fee_urls.add(f_url)
                try:
                    r = self.session.get(f_url, timeout=4)
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

    def get_academic_and_profile(self, dash_soup=None):
        """
        Ultra-Fast Stage 2 Deep Sync (<1.8 seconds):
        Scrapes student profile details, exam results/marksheets, and fees concurrently
        WITHOUT re-scraping attendance subjects. Prevents Vercel 10s Serverless timeout.
        """
        dash_html = getattr(self, "_cached_dash_html", None)
        if dash_soup is None:
            if not dash_html or "AttendanceReport" not in dash_html:
                try:
                    dash_res = self.session.get(DASHBOARD_URL, timeout=8)
                    if "StudentLogin" in dash_res.url or "AttendanceReport" not in dash_res.text:
                        ok, err = self.authenticate()
                        if not ok:
                            return None, err
                        dash_html = getattr(self, "_cached_dash_html", "")
                    else:
                        dash_html = dash_res.text
                except Exception:
                    ok, err = self.authenticate()
                    if not ok:
                        return None, err
                    dash_html = getattr(self, "_cached_dash_html", "")
            dash_soup = BeautifulSoup(dash_html, "html.parser")

        student_name = extract_student_name(dash_soup, fallback=str(self.student_id))

        with ThreadPoolExecutor(max_workers=3) as exec:
            fut_prof = exec.submit(self.get_student_profile, dash_soup)
            fut_res = exec.submit(self.get_exam_results, dash_soup)
            fut_fees = exec.submit(self.get_fees, dash_soup)

            profile_data = fut_prof.result()
            results_data = fut_res.result()
            fees_data = fut_fees.result()

        student_email = ""
        for k, v in profile_data.get("details", []):
            if k.lower() == "name" and v and v.strip() and v.strip().lower() != "student":
                student_name = v.strip().title()
            elif "email" in k.lower() and v:
                student_email = v.strip()

        profile_data["details"] = [d for d in profile_data.get("details", []) if d[0].lower() != "name"]
        profile_data["details"].insert(0, ("Name", student_name))

        return {
            "student_name": student_name,
            "student_email": student_email,
            "profile": profile_data,
            "results": results_data,
            "fees": fees_data
        }, None

    def get_full_profile(self, fast_mode=False):
        """
        If fast_mode=True, only scrapes Attendance subjects (~2 seconds) so the
        Attendance & Simulator tab renders immediately.
        """
        dash_html = getattr(self, "_cached_dash_html", None)
        if not dash_html or "AttendanceReport" not in dash_html:
            try:
                dash_res = self.session.get(DASHBOARD_URL, timeout=10)
                if "StudentLogin" in dash_res.url or "AttendanceReport" not in dash_res.text:
                    success, err = self.authenticate()
                    if not success:
                        return None, err
                    dash_html = getattr(self, "_cached_dash_html", "")
                else:
                    dash_html = dash_res.text
            except Exception:
                success, err = self.authenticate()
                if not success:
                    return None, err
                dash_html = getattr(self, "_cached_dash_html", "")

        today_str = datetime.now(IST).strftime("%d-%m-%Y")
        today_pretty = datetime.now(IST).strftime("%a, %d %b %Y")
        sync_time = datetime.now(IST).strftime("%d %b %Y, %I:%M %p")

        dash_soup = BeautifulSoup(dash_html, "html.parser")
        text = dash_soup.get_text(" ", strip=True)

        incharge_match = re.search(r"Incharge\s*Name\s*:\s*([A-Za-z\s\.]+?)(?:Subjects|Session|$)", text, re.I)
        incharge_name = incharge_match.group(1).strip() if incharge_match else "Vinod Kumar"

        # Extract student name directly from dashboard header
        student_name = extract_student_name(dash_soup, fallback="Student")

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

                    # Parse fallback present / total numbers directly from main dashboard table
                    fallback_p, fallback_t = 0, 0
                    for c in cols[1:]:
                        nums = re.findall(r"\b\d+\b", c)
                        if len(nums) == 2:
                            t_cand, p_cand = int(nums[0]), int(nums[1])
                            fallback_p = min(t_cand, p_cand)
                            fallback_t = max(t_cand, p_cand)
                            break
                        elif len(nums) == 1 and "/" in c:
                            parts = c.split("/")
                            if len(parts) == 2 and parts[0].strip().isdigit() and parts[1].strip().isdigit():
                                fallback_p, fallback_t = int(parts[0]), int(parts[1])
                                break

                    subjects.append({
                        "name": subject_name,
                        "url": full_url,
                        "fallback_p": fallback_p,
                        "fallback_t": fallback_t
                    })

        def fetch_subject(item):
            name = item["name"]
            url = item["url"]
            fallback_p = item.get("fallback_p", 0)
            fallback_t = item.get("fallback_t", 0)
            present = fallback_p
            absent = max(0, fallback_t - fallback_p)
            records = []

            for attempt in range(2):
                try:
                    r = self.session.get(url, timeout=8)
                    if "StudentLogin" in r.url:
                        # Session expired; re-authenticate and retry GET once
                        self.authenticate()
                        r = self.session.get(url, timeout=8)

                    if r.status_code == 200 and len(r.text) > 200:
                        s = BeautifulSoup(r.text, "html.parser")
                        scrape_p, scrape_a = 0, 0
                        scrape_records = []
                        for row in s.find_all("tr"):
                            row_text = row.get_text(" ", strip=True)
                            upper_text = row_text.upper()
                            date_val = None

                            # Universal Date Normalization to DD-MM-YYYY
                            d_match = re.search(r"\b(\d{1,2})[-/\.](\d{1,2})[-/\.](\d{2,4})\b", row_text)
                            if d_match:
                                d_num = int(d_match.group(1))
                                m_num = int(d_match.group(2))
                                y_str = d_match.group(3)
                                if len(y_str) == 2:
                                    y_str = "20" + y_str
                                if d_num > 12 and m_num <= 12:
                                    date_val = f"{d_num:02d}-{m_num:02d}-{y_str}"
                                elif m_num > 12 and d_num <= 12:
                                    date_val = f"{m_num:02d}-{d_num:02d}-{y_str}"
                                else:
                                    date_val = f"{d_num:02d}-{m_num:02d}-{y_str}"
                            else:
                                m_text = re.search(r"\b(\d{1,2})[-/\s]+([A-Za-z]{3,9})[-/\s]+(\d{4})\b", row_text)
                                if m_text:
                                    try:
                                        dt = datetime.strptime(f"{int(m_text.group(1)):02d} {m_text.group(2)[:3].title()} {m_text.group(3)}", "%d %b %Y")
                                        date_val = dt.strftime("%d-%m-%Y")
                                    except Exception:
                                        date_val = None

                            if "PRESENT" in upper_text:
                                scrape_p += 1
                                if date_val:
                                    scrape_records.append({"date": date_val, "subject": name, "status": "PRESENT"})
                            elif "ABSENT" in upper_text:
                                scrape_a += 1
                                if date_val:
                                    scrape_records.append({"date": date_val, "subject": name, "status": "ABSENT"})

                        if scrape_p + scrape_a > 0 or len(scrape_records) > 0:
                            present = scrape_p
                            absent = scrape_a
                            records = scrape_records
                        break
                except Exception:
                    if attempt == 1:
                        pass

            total = present + absent
            if total == 0 and fallback_t > 0:
                total = fallback_t
                present = fallback_p
                absent = max(0, total - present)

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

        # Fast parallel scrape of all subjects concurrently
        with ThreadPoolExecutor(max_workers=10) as executor:
            subject_results = list(executor.map(fetch_subject, subjects))

        all_records = []
        today_attendance = []
        seen_today_keys = set()
        for subj in subject_results:
            for rec in subj.get("records", []):
                all_records.append(rec)
                if rec.get("date") == today_str:
                    today_key = (rec.get("subject"), rec.get("status"))
                    if today_key not in seen_today_keys:
                        seen_today_keys.add(today_key)
                        today_attendance.append(rec)

        # Compute latest_attendance_date and latest_attendance_records across all records
        latest_attendance_date = None
        latest_attendance_records = []
        if all_records:
            def parse_rec_date(r):
                try:
                    return datetime.strptime(r.get("date", ""), "%d-%m-%Y")
                except Exception:
                    return datetime.min

            valid_records = [r for r in all_records if r.get("date")]
            if valid_records:
                valid_records.sort(key=parse_rec_date, reverse=True)
                latest_attendance_date = valid_records[0].get("date")
                seen_latest = set()
                for r in valid_records:
                    if r.get("date") == latest_attendance_date:
                        k = (r.get("subject"), r.get("status"))
                        if k not in seen_latest:
                            seen_latest.add(k)
                            latest_attendance_records.append(r)

        if fast_mode:
            return {
                "student_id": self.student_id,
                "student_name": student_name,
                "student_email": "",
                "incharge": incharge_name,
                "today_date": today_pretty,
                "last_synced": sync_time + " (Live)",
                "is_offline": False,
                "partial_load": True,
                "today_attendance": today_attendance,
                "latest_attendance_date": latest_attendance_date,
                "latest_attendance_records": latest_attendance_records,
                "calendar_records": all_records,
                "subjects": subject_results,
                "results": [],
                "profile": {"details": [("Name", student_name), ("Student Id", str(self.student_id)), ("Faculty Incharge", incharge_name)]},
                "fees": []
            }, None

        # Deep Sync: Fetch Profile, Results and Fees concurrently in a single thread pool (prevents 10s timeout)
        with ThreadPoolExecutor(max_workers=3) as extra_exec:
            fut_profile = extra_exec.submit(self.get_student_profile, dash_soup)
            fut_results = extra_exec.submit(self.get_exam_results, dash_soup)
            fut_fees = extra_exec.submit(self.get_fees, dash_soup)

            profile_data = fut_profile.result()
            results_data = fut_results.result()
            fees_data = fut_fees.result()

        student_email = ""
        for k, v in profile_data.get("details", []):
            if k.lower() == "name" and v and v.strip() and v.strip().lower() != "student":
                student_name = v.strip().title()
            elif "email" in k.lower() and v:
                student_email = v.strip()

        # Ensure ("Name", student_name) is always at index 0 of profile details
        profile_data["details"] = [d for d in profile_data.get("details", []) if d[0].lower() != "name"]
        profile_data["details"].insert(0, ("Name", student_name))

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
            "latest_attendance_date": latest_attendance_date,
            "latest_attendance_records": latest_attendance_records,
            "calendar_records": all_records,
            "subjects": subject_results,
            "results": results_data,
            "profile": profile_data,
            "fees": fees_data
        }, None