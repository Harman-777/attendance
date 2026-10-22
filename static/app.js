// ==========================================================================
// Krono Theme Controller (OLED Dark + Paper-White Dual System)
// ==========================================================================
window.initKronoTheme = function () {
    var theme = localStorage.getItem("krono_theme") || "dark";
    document.documentElement.setAttribute("data-theme", theme);
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
        meta.setAttribute("content", theme === "light" ? "#FAFAFA" : "#000000");
    }
    if (window.AndroidApp && typeof window.AndroidApp.setSystemBarTheme === "function") {
        try {
            window.AndroidApp.setSystemBarTheme(theme);
        } catch (e) {}
    }
};

window.toggleKronoTheme = function () {
    var cur = document.documentElement.getAttribute("data-theme") || "dark";
    var next = cur === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    try {
        localStorage.setItem("krono_theme", next);
    } catch (e) {}

    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) {
        meta.setAttribute("content", next === "light" ? "#FAFAFA" : "#000000");
    }

    if (window.AndroidApp && typeof window.AndroidApp.setSystemBarTheme === "function") {
        try {
            window.AndroidApp.setSystemBarTheme(next);
        } catch (e) {}
    }
};

// Auto initialize immediately
window.initKronoTheme();

document.addEventListener("DOMContentLoaded", function () {
    const rawData = document.getElementById("portal-data-json").textContent;
    const portalData = JSON.parse(rawData || "{}");
    let allRecords = portalData.calendar_records || [];
    const subjectsList = portalData.subjects || [];
    const newAbsents = portalData.new_absents || [];

    let targetThreshold = 75;
    let medicalMode = false;

    function getInitials(name) {
        if (!name || name.trim().toLowerCase() === "student") return "ST";
        const parts = name.trim().split(/\s+/);
        if (parts.length >= 2) {
            return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
        }
        return name.slice(0, 2).toUpperCase();
    }

    // 1. Sidebar Navigation Tab Switching
    const navButtons = document.querySelectorAll(".nav-btn");
    const tabPanels = document.querySelectorAll(".tab-panel");

    function activateTab(targetId) {
        navButtons.forEach(function (b) {
            const isActive = b.getAttribute("data-target") === targetId;
            b.classList.toggle("active", isActive);
            if (isActive && window.innerWidth <= 900) {
                try {
                    b.scrollIntoView({ behavior: "smooth", inline: "center", block: "nearest" });
                } catch (e) {}
            }
        });
        tabPanels.forEach(function (p) {
            p.classList.toggle("active", p.id === targetId);
        });
        if (window.innerWidth <= 900) {
            window.scrollTo({ top: 0, behavior: "smooth" });
        }
    }

    navButtons.forEach(function (btn) {
        btn.addEventListener("click", function () {
            activateTab(btn.getAttribute("data-target"));
        });
    });

    const jumpVacBtn = document.getElementById("btn-jump-vacation");
    if (jumpVacBtn) {
        jumpVacBtn.addEventListener("click", function () {
            activateTab("tab-vacation");
        });
    }

    // 2. 1-Click PDF Report Export (Desktop & Mobile App APK)
    document.querySelectorAll(".trigger-export-pdf, #btn-export-pdf").forEach(function (btn) {
        btn.addEventListener("click", function () {
            if (window.AndroidApp && typeof window.AndroidApp.printPage === "function") {
                window.AndroidApp.printPage();
            } else {
                window.print();
            }
        });
    });

    // 3. Attendance Card Calculations, Progress Bars & Target Slider
    function getEffectiveTarget() {
        return medicalMode ? 65 : targetThreshold;
    }

    function refreshCard(card) {
        const idx = card.getAttribute("data-idx");
        const p = parseInt(card.getAttribute("data-present"), 10);
        const t = parseInt(card.getAttribute("data-total"), 10);
        const target = getEffectiveTarget();
        const targetDec = target / 100.0;

        const pct = t > 0 ? (p / t) * 100 : 0;
        const nextAtt = ((p + 1) / (t + 1)) * 100;
        const nextSkip = (p / (t + 1)) * 100;

        const pctEl = document.getElementById("pct-" + idx);
        const barEl = document.getElementById("bar-" + idx);
        const countEl = document.getElementById("count-" + idx);
        const nextAttEl = document.getElementById("next-att-" + idx);
        const nextSkipEl = document.getElementById("next-skip-" + idx);
        const boxEl = document.getElementById("status-box-" + idx);

        const isSafe = pct >= target;
        const color = isSafe ? "#22c55e" : "#ef4444";

        pctEl.textContent = pct.toFixed(2) + "%";
        pctEl.style.color = color;
        barEl.style.width = Math.min(pct, 100) + "%";
        barEl.style.background = color;
        countEl.innerHTML = "Attended: <b>" + p + "</b> / <b>" + t + "</b> classes";

        nextAttEl.textContent = "Next Attend: " + nextAtt.toFixed(1) + "%";
        nextSkipEl.textContent = "Next Skip: " + nextSkip.toFixed(1) + "%";

        if (t === 0) {
            boxEl.textContent = "No classes recorded yet.";
        } else if (isSafe) {
            const bunks = Math.floor((p - targetDec * t) / targetDec);
            if (bunks <= 2) {
                boxEl.textContent = "Danger Zone: Only " + bunks + " safe skip(s) for " + target + "%!";
            } else {
                boxEl.textContent = "Safe! You can skip " + bunks + " classes for " + target + "%.";
            }
        } else {
            const needed = Math.ceil((targetDec * t - p) / (1.0 - targetDec));
            boxEl.textContent = "Below " + target + "%! Attend next " + needed + " classes.";
        }
    }

    function refreshAllCards() {
        document.querySelectorAll(".sub-card").forEach(function (card) {
            refreshCard(card);
        });
    }

    // Target Slider & Medical Mode Listeners
    const targetSlider = document.getElementById("target-slider");
    const targetLabel = document.getElementById("target-label");
    const medicalToggle = document.getElementById("medical-toggle");

    if (targetSlider) {
        targetSlider.addEventListener("input", function () {
            targetThreshold = parseInt(targetSlider.value, 10);
            targetLabel.textContent = getEffectiveTarget() + "%";
            refreshAllCards();
            renderVacationTable();
        });
    }

    if (medicalToggle) {
        medicalToggle.addEventListener("change", function () {
            medicalMode = medicalToggle.checked;
            targetLabel.textContent = getEffectiveTarget() + "%";
            refreshAllCards();
            renderVacationTable();
        });
    }

    document.querySelectorAll(".sim-action").forEach(function (btn) {
        btn.addEventListener("click", function () {
            const idx = btn.getAttribute("data-idx");
            const addP = parseInt(btn.getAttribute("data-add-p"), 10);
            const addT = parseInt(btn.getAttribute("data-add-t"), 10);
            const card = document.querySelector('.sub-card[data-idx="' + idx + '"]');

            card.setAttribute("data-present", parseInt(card.getAttribute("data-present"), 10) + addP);
            card.setAttribute("data-total", parseInt(card.getAttribute("data-total"), 10) + addT);
            refreshCard(card);
        });
    });

    document.querySelectorAll(".sim-reset").forEach(function (btn) {
        btn.addEventListener("click", function () {
            const idx = btn.getAttribute("data-idx");
            const card = document.querySelector('.sub-card[data-idx="' + idx + '"]');
            card.setAttribute("data-present", card.getAttribute("data-orig-p"));
            card.setAttribute("data-total", card.getAttribute("data-orig-t"));
            refreshCard(card);
        });
    });

    refreshAllCards();

    // 4. Multi-Day Vacation / Mass-Bunk Planner
    const vacInput = document.getElementById("vacation-days-input");
    const vacBody = document.getElementById("vacation-table-body");
    const vacBtn = document.getElementById("btn-calc-vacation");

    function renderVacationTable() {
        if (!vacBody) return;
        const skipCount = parseInt(vacInput.value, 10) || 1;
        const target = getEffectiveTarget();
        const targetDec = target / 100.0;
        vacBody.innerHTML = "";

        subjectsList.forEach(function (s) {
            const newTotal = s.total + skipCount;
            const newPct = newTotal > 0 ? (s.present / newTotal) * 100 : 0;
            const isSafe = newPct >= target;

            let verdictHtml = "";
            if (isSafe) {
                const remBunks = Math.floor((s.present - targetDec * newTotal) / targetDec);
                verdictHtml = '<span class="badge-present">SAFE (' + remBunks + " skips left)</span>";
            } else {
                const needAfter = Math.ceil((targetDec * newTotal - s.present) / (1.0 - targetDec));
                verdictHtml = '<span class="badge-absent">DANGER (Need ' + needAfter + " classes after trip)</span>";
            }

            const tr = document.createElement("tr");
            tr.innerHTML =
                "<td><b>" + s.name + "</b></td>" +
                "<td>" + s.pct.toFixed(2) + "% (" + s.present + "/" + s.total + ")</td>" +
                "<td style='color:" + (isSafe ? "#4ade80" : "#f87171") + "; font-weight:700;'>" +
                newPct.toFixed(2) + "% (" + s.present + "/" + newTotal + ")</td>" +
                "<td>" + verdictHtml + "</td>";
            vacBody.appendChild(tr);
        });
    }

    if (vacBtn) {
        vacBtn.addEventListener("click", renderVacationTable);
        vacInput.addEventListener("input", renderVacationTable);
        renderVacationTable();
    }

    // 5. SGPA Trend Bar Heights & Target Grade Predictor
    document.querySelectorAll(".chart-bar").forEach(function (bar) {
        const sgpa = parseFloat(bar.getAttribute("data-sgpa")) || 0;
        const heightPct = sgpa > 0 ? Math.min((sgpa / 10.0) * 100, 100) : 15;
        bar.style.height = heightPct + "%";
    });

    const predInt = document.getElementById("pred-internal");
    const predExtMax = document.getElementById("pred-external-max");
    const predOut = document.getElementById("grade-predictor-output");

    function updateGradePredictor() {
        if (!predOut) return;
        const internal = parseFloat(predInt.value) || 0;
        const extMax = parseFloat(predExtMax.value) || 60;
        const totalMax = 40 + extMax;

        const targets = [
            { grade: "O (90%+)", reqPct: 0.90 },
            { grade: "A+ (80%+)", reqPct: 0.80 },
            { grade: "A (70%+)", reqPct: 0.70 },
            { grade: "B+ (60%+)", reqPct: 0.60 }
        ];

        predOut.innerHTML = "";
        targets.forEach(function (t) {
            const neededTotal = Math.ceil(t.reqPct * totalMax);
            const neededExt = Math.max(0, neededTotal - internal);
            const achievable = neededExt <= extMax;

            const box = document.createElement("div");
            box.style.background = "#1e293b";
            box.style.padding = "10px 12px";
            box.style.borderRadius = "8px";
            box.innerHTML =
                "<div style='color:#9ca3af; font-size:0.78rem;'>" + t.grade + "</div>" +
                "<div style='font-weight:700; color:" + (achievable ? "#38bdf8" : "#f87171") + ";'>" +
                (achievable ? "Need " + neededExt + " / " + extMax : "Out of reach") + "</div>";
            predOut.appendChild(box);
        });
    }

    if (predInt && predExtMax) {
        predInt.addEventListener("input", updateGradePredictor);
        predExtMax.addEventListener("input", updateGradePredictor);
        updateGradePredictor();
    }

    // Semester Dropdown Switching
    const semSelect = document.getElementById("sem-select");
    if (semSelect) {
        semSelect.addEventListener("change", function () {
            document.querySelectorAll(".sem-block").forEach(function (blk) {
                blk.classList.remove("active");
            });
            const chosen = document.getElementById(semSelect.value);
            if (chosen) chosen.classList.add("active");
        });
    }

    // 6. Wrong-Absent Dispute Generator
    const dispSubj = document.getElementById("dispute-subject");
    const dispDate = document.getElementById("dispute-date");
    const dispReason = document.getElementById("dispute-reason");
    const dispOut = document.getElementById("dispute-output");
    const genDispBtn = document.getElementById("btn-generate-dispute");
    const copyDispBtn = document.getElementById("btn-copy-dispute");

    function generateDisputeText() {
        if (!dispOut) return;
        const subj = dispSubj.value;
        const dt = dispDate.value;
        const rsn = dispReason.value;

        dispOut.value =
            "To,\n" +
            "Prof. " + (portalData.incharge || "Faculty Incharge") + ",\n" +
            "Department Faculty Incharge, AGC\n\n" +
            "Subject: Request for Attendance Correction in " + subj + " (" + dt + ")\n\n" +
            "Respected Sir/Madam,\n" +
            "I am " + (portalData.student_name || "Student") + " (Student ID / Roll No: " + portalData.student_id + "). " +
            "On " + dt + ", my attendance in the subject '" + subj + "' was marked as ABSENT on the AGC LMS portal. " +
            rsn + "\n\n" +
            "Kindly verify and update my attendance record for this lecture.\n\n" +
            "Thanking you,\n" +
            (portalData.student_name || "Student") + "\n" +
            "Student ID: " + portalData.student_id;
    }

    if (genDispBtn) {
        genDispBtn.addEventListener("click", generateDisputeText);
        generateDisputeText();
    }

    if (copyDispBtn) {
        copyDispBtn.addEventListener("click", function () {
            dispOut.select();
            navigator.clipboard.writeText(dispOut.value);
            copyDispBtn.innerHTML = '<svg class="krono-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Copied to Clipboard!';
            setTimeout(function () {
                copyDispBtn.innerHTML = '<svg class="krono-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/></svg> Copy Application Text';
            }, 2000);
        });
    }

    function openDisputeFor(subjectName, dateStr) {
        activateTab("tab-alerts");
        if (dispSubj) dispSubj.value = subjectName;
        if (dispDate) dispDate.value = dateStr;
        generateDisputeText();
    }

    document.querySelectorAll(".open-dispute-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            openDisputeFor(btn.getAttribute("data-subject"), btn.getAttribute("data-date"));
        });
    });

    // 7. Service Worker Lock-Screen Web Push & Supabase Email Alerts
    const pushBtn = document.getElementById("btn-enable-push");
    const pushStatus = document.getElementById("push-status-text");

    // Hide legacy SMTP inputs automatically so students only enter their own email
    const smtpUserInp = document.getElementById("alert-smtp-user");
    const smtpPassInp = document.getElementById("alert-smtp-pass");
    if (smtpUserInp) smtpUserInp.style.display = "none";
    if (smtpPassInp) smtpPassInp.style.display = "none";

    function urlBase64ToUint8Array(base64String) {
        const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
        const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
        const rawData = window.atob(base64);
        const outputArray = new Uint8Array(rawData.length);
        for (let i = 0; i < rawData.length; ++i) {
            outputArray[i] = rawData.charCodeAt(i);
        }
        return outputArray;
    }

    async function subscribeUserToPush() {
        if (!("serviceWorker" in navigator) || !("PushManager" in window)) {
            pushStatus.textContent = "Web Push is not supported on this browser.";
            return;
        }

        try {
            pushStatus.textContent = "Registering background Service Worker...";
            const registration = await navigator.serviceWorker.register("/sw.js");
            await navigator.serviceWorker.ready;

            const perm = await Notification.requestPermission();
            if (perm !== "granted") {
                pushStatus.textContent = "Notification permission denied by browser.";
                pushStatus.style.color = "#f87171";
                return;
            }

            const keyRes = await fetch("/api/vapid-public-key");
            const keyData = await keyRes.json();
            if (!keyData.publicKey) {
                pushStatus.textContent = "VAPID_PUBLIC_KEY missing in .env.local";
                return;
            }

            const subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(keyData.publicKey)
            });

            pushStatus.textContent = "Linking device to Supabase & sending test push...";
            const res = await fetch("/api/test-push", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ subscription: subscription.toJSON() })
            });
            const result = await res.json();

            pushStatus.textContent = result.ok
                ? "Linked to Supabase! Lock-Screen Push Active."
                : result.message;
            pushStatus.style.color = result.ok ? "#4ade80" : "#fbbf24";
        } catch (err) {
            pushStatus.textContent = "Push setup error: " + err.message;
            pushStatus.style.color = "#f87171";
        }
    }

    if (pushBtn) {
        pushBtn.addEventListener("click", subscribeUserToPush);
    }

    const sendEmailBtn = document.getElementById("btn-send-email-alert");
    const emailStatus = document.getElementById("email-alert-status");
    if (sendEmailBtn) {
        sendEmailBtn.textContent = "Save Email for Background Alerts";
        sendEmailBtn.addEventListener("click", function () {
            emailStatus.textContent = "Saving email to Supabase...";
            fetch("/api/send-alert", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    email: document.getElementById("alert-to-email").value
                })
            })
            .then(function (r) { return r.json(); })
            .then(function (res) {
                emailStatus.textContent = res.message;
            });
        });
    }

    // 8. In-App Portal Password Changer
    const submitPwBtn = document.getElementById("btn-submit-password");
    const cpStatus = document.getElementById("cp-status-msg");
    if (submitPwBtn) {
        submitPwBtn.addEventListener("click", function () {
            cpStatus.textContent = "Updating password on college portal...";
            cpStatus.style.color = "#38bdf8";
            fetch("/api/change-password", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    old_password: document.getElementById("cp-old").value,
                    new_password: document.getElementById("cp-new").value,
                    confirm_password: document.getElementById("cp-confirm").value
                })
            })
            .then(function (r) { return r.json(); })
            .then(function (res) {
                cpStatus.textContent = res.message;
                cpStatus.style.color = res.ok ? "#4ade80" : "#f87171";
            });
        });
    }

    // 9. Interactive Attendance Calendar
    const subjFilter = document.getElementById("cal-subject-filter");
    const calBody = document.getElementById("cal-body");
    const monthLabel = document.getElementById("cal-month-label");
    const dateTitle = document.getElementById("selected-date-title");
    const dateList = document.getElementById("selected-date-list");

    const now = new Date();
    let currentMonth = now.getMonth();
    let currentYear = now.getFullYear();
    let selectedDateStr = null;

    const monthNames = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ];

    function pad2(n) {
        return n < 10 ? "0" + n : "" + n;
    }

    function showDayDetails(dateStr) {
        selectedDateStr = dateStr;
        const filterVal = subjFilter.value;
        const matches = allRecords.filter(function (r) {
            return r.date === dateStr && (filterVal === "ALL" || r.subject === filterVal);
        });

        dateTitle.textContent = "Lectures on " + dateStr;
        dateList.innerHTML = "";

        if (matches.length === 0) {
            dateList.innerHTML = '<div style="color:#9ca3af; font-size:0.9rem;">No attendance records recorded for this date.</div>';
            return;
        }

        matches.forEach(function (m) {
            const item = document.createElement("div");
            item.className = "today-pill";
            const badgeClass = m.status === "PRESENT" ? "badge-present" : "badge-absent";

            let rightHtml = '<span class="' + badgeClass + '">' + m.status + "</span>";
            if (m.status === "ABSENT") {
                rightHtml += '<button type="button" class="btn-dispute-pill cal-dispute-btn">Dispute</button>';
            }

            item.innerHTML = '<span class="today-subj-name">' + m.subject + '</span><div class="today-status-wrap">' + rightHtml + '</div>';
            const dispBtn = item.querySelector(".cal-dispute-btn");
            if (dispBtn) {
                dispBtn.addEventListener("click", function () {
                    openDisputeFor(m.subject, m.date);
                });
            }
            dateList.appendChild(item);
        });
    }

    function renderCalendar() {
        if (!calBody) return;
        calBody.innerHTML = "";
        monthLabel.textContent = monthNames[currentMonth] + " " + currentYear;

        const firstDay = new Date(currentYear, currentMonth, 1).getDay();
        const daysInMonth = new Date(currentYear, currentMonth + 1, 0).getDate();
        const filterVal = subjFilter.value;

        for (let i = 0; i < firstDay; i++) {
            const emptyCell = document.createElement("div");
            emptyCell.className = "cal-cell empty";
            calBody.appendChild(emptyCell);
        }

        for (let d = 1; d <= daysInMonth; d++) {
            const dateStr = pad2(d) + "-" + pad2(currentMonth + 1) + "-" + currentYear;
            const dayRecords = allRecords.filter(function (r) {
                return r.date === dateStr && (filterVal === "ALL" || r.subject === filterVal);
            });

            const cell = document.createElement("div");
            cell.className = "cal-cell";

            if (dayRecords.length > 0) {
                const presCount = dayRecords.filter(function (r) { return r.status === "PRESENT"; }).length;
                const absCount = dayRecords.length - presCount;

                if (presCount > 0 && absCount === 0) {
                    cell.classList.add("day-present");
                } else if (absCount > 0 && presCount === 0) {
                    cell.classList.add("day-absent");
                } else {
                    cell.classList.add("day-mixed");
                }
                cell.innerHTML = "<span>" + d + '</span><span class="cal-dot-count">' + dayRecords.length + " lec</span>";
            } else {
                cell.innerHTML = "<span>" + d + "</span>";
            }

            if (selectedDateStr === dateStr) {
                cell.classList.add("selected");
            }

            cell.addEventListener("click", function () {
                document.querySelectorAll(".cal-cell").forEach(function (c) { c.classList.remove("selected"); });
                cell.classList.add("selected");
                showDayDetails(dateStr);
            });

            calBody.appendChild(cell);
        }
    }

    if (calBody) {
        document.getElementById("cal-prev").addEventListener("click", function () {
            currentMonth--;
            if (currentMonth < 0) { currentMonth = 11; currentYear--; }
            renderCalendar();
        });

        document.getElementById("cal-next").addEventListener("click", function () {
            currentMonth++;
            if (currentMonth > 11) { currentMonth = 0; currentYear++; }
            renderCalendar();
        });

        subjFilter.addEventListener("change", function () {
            renderCalendar();
            if (selectedDateStr) showDayDetails(selectedDateStr);
        });

        renderCalendar();
        if (allRecords.length > 0) {
            showDayDetails(allRecords[allRecords.length - 1].date);
        }
    }
});
// 10. 1-Click Cloud Password Vault Toggle (Encrypt / Wipe in Supabase)
    const encryptVaultBtn = document.getElementById("btn-encrypt-vault");
    const wipeVaultBtn = document.getElementById("btn-wipe-vault");
    const vaultStatusMsg = document.getElementById("vault-status-msg");

    function updateVaultState(enableVault) {
        if (!vaultStatusMsg) return;
        vaultStatusMsg.textContent = enableVault
            ? "Encrypting password with AES-256 & saving to Supabase..."
            : "Wiping encrypted password from Supabase...";
        vaultStatusMsg.style.color = "#38bdf8";

        fetch("/api/toggle-vault", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ enable: enableVault })
        })
        .then(function (r) { return r.json(); })
        .then(function (res) {
            vaultStatusMsg.textContent = res.message;
            vaultStatusMsg.style.color = res.vault_enabled ? "#4ade80" : "#fbbf24";
            if (encryptVaultBtn) {
                encryptVaultBtn.innerHTML = res.vault_enabled
                    ? '<svg class="krono-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg> Re-Encrypt & Update Vault'
                    : '<svg class="krono-icon" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg> Encrypt & Save Password to Cloud';
            }
        });
    }

    if (encryptVaultBtn) {
        encryptVaultBtn.addEventListener("click", function () {
            updateVaultState(true);
        });
    }

    if (wipeVaultBtn) {
        wipeVaultBtn.addEventListener("click", function () {
            updateVaultState(false);
        });
    }

    // Dynamic Results & Marksheets Tab Renderer (Updates DOM without full reload)
    window.renderResultsTabDynamically = function (results) {
        if (!results || results.length === 0) return;

        // 1. Re-render SGPA Trend Card
        const sgpaCard = document.getElementById("sgpa-trend-card");
        if (sgpaCard) {
            let chartHtml = `
                <h3 style="font-size: 1.15rem; color: var(--accent-primary); margin-bottom: 6px; display: flex; align-items: center; gap: 8px;"><svg class="krono-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg> Semester SGPA Performance Trend</h3>
                <p style="color: #9ca3af; font-size: 0.85rem; margin-bottom: 12px;">Automated grade-point progression across published semesters</p>
                <div class="chart-row">
            `;
            let reappearCount = 0;
            let reappearDetails = [];

            results.forEach(function (sem) {
                const isRa = Boolean(sem.has_reappear);
                if (isRa) {
                    reappearCount++;
                    reappearDetails.push({ sem: sem.semester, subs: sem.reappear_subjects || [] });
                    chartHtml += `
                        <div class="chart-bar-wrap">
                            <span style="font-size: 0.74rem; font-weight: 800; color: #fb7185; margin-bottom: 6px; background: rgba(244, 63, 94, 0.15); border: 1px solid rgba(244, 63, 94, 0.4); padding: 2px 6px; border-radius: 6px;">
                                <svg class="krono-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> RA (${sem.sgpa > 0 ? sem.sgpa : 'Backlog'})
                            </span>
                            <div class="chart-bar" data-sgpa="${sem.sgpa}" style="background: linear-gradient(180deg, #f43f5e 0%, #e11d48 100%) !important; border: 1px solid #fda4af;"></div>
                            <span style="font-size: 0.78rem; color: #9ca3af; margin-top: 8px;">${sem.semester}</span>
                        </div>
                    `;
                } else {
                    chartHtml += `
                        <div class="chart-bar-wrap">
                            <span style="font-size: 0.82rem; font-weight: 700; color: #38bdf8; margin-bottom: 6px;">${sem.sgpa > 0 ? sem.sgpa : 'N/A'}</span>
                            <div class="chart-bar" data-sgpa="${sem.sgpa}"></div>
                            <span style="font-size: 0.78rem; color: #9ca3af; margin-top: 8px;">${sem.semester}</span>
                        </div>
                    `;
                }
            });

            chartHtml += `</div>`;

            if (reappearCount > 0) {
                chartHtml += `
                    <div style="margin-top: 18px; padding: 12px 16px; border-radius: 10px; background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); font-size: 0.85rem;">
                        <div style="font-weight: 700; color: #f87171; display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
                            <svg class="krono-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg> Active Re-appear / Backlog Notice
                        </div>
                `;
                reappearDetails.forEach(function (rd) {
                    const subText = rd.subs && rd.subs.length > 0 ? rd.subs.join(", ") : "Pending re-examination required";
                    chartHtml += `
                        <div style="color: #cbd5e1; margin-bottom: 4px;">
                            <b style="color: #fca5a5;">${rd.sem}:</b> Re-appear in <span style="color: #f87171; font-weight: 600;">${subText}</span>
                        </div>
                    `;
                });
                chartHtml += `</div>`;
            } else {
                chartHtml += `
                    <div style="margin-top: 18px; padding: 10px 14px; border-radius: 10px; background: rgba(34, 197, 94, 0.08); border: 1px solid rgba(34, 197, 94, 0.25); font-size: 0.82rem; color: #86efac; display: flex; align-items: center; gap: 8px;">
                        <svg class="krono-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg> <b>Academic Record Cleared:</b> All published semesters cleared with zero backlogs!
                    </div>
                `;
            }

            sgpaCard.innerHTML = chartHtml;

            // Animate bar heights
            sgpaCard.querySelectorAll(".chart-bar").forEach(function (bar) {
                const sgpa = parseFloat(bar.getAttribute("data-sgpa")) || 0;
                const heightPct = sgpa > 0 ? Math.min((sgpa / 10.0) * 100, 100) : 15;
                bar.style.height = heightPct + "%";
            });
        }

        // 2. Re-render Marksheets Section
        const msSection = document.getElementById("marksheets-section");
        if (msSection) {
            let msHtml = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px;">
                    <h2 style="font-size: 1.3rem;">Official Semester Marksheets</h2>
                    <div>
                        <label style="color: #9ca3af; margin-right: 10px; font-weight: 600;">Select Semester:</label>
                        <select class="sem-dropdown" id="sem-select">
            `;
            results.forEach(function (sem, idx) {
                const isLast = (idx === results.length - 1);
                msHtml += `<option value="sem-${sem.code}" ${isLast ? 'selected' : ''}>${sem.semester}</option>`;
            });
            msHtml += `</select></div></div>`;

            results.forEach(function (sem, idx) {
                const isLast = (idx === results.length - 1);
                msHtml += `<div id="sem-${sem.code}" class="sem-block ${isLast ? 'active' : ''}">`;
                msHtml += `<h3 style="color: #38bdf8; margin-bottom: 12px; font-size: 1.12rem;">${sem.semester} Marksheet</h3>`;
                if (sem.tables && sem.tables.length > 0) {
                    sem.tables.forEach(function (table) {
                        msHtml += `<div class="table-responsive" style="margin-bottom: 24px;"><table>`;
                        table.forEach(function (row, rIdx) {
                            msHtml += `<tr>`;
                            row.forEach(function (cell) {
                                if (rIdx === 0) msHtml += `<th>${cell}</th>`;
                                else msHtml += `<td>${cell}</td>`;
                            });
                            msHtml += `</tr>`;
                        });
                        msHtml += `</table></div>`;
                    });
                } else {
                    msHtml += `<div class="card" style="text-align: center; color: #9ca3af;">No published mark records found for ${sem.semester}.</div>`;
                }
                msHtml += `</div>`;
            });

            msSection.innerHTML = msHtml;

            // Re-bind sem-select
            const newSemSelect = document.getElementById("sem-select");
            if (newSemSelect) {
                newSemSelect.addEventListener("change", function () {
                    document.querySelectorAll(".sem-block").forEach(function (blk) {
                        blk.classList.remove("active");
                    });
                    const chosen = document.getElementById(newSemSelect.value);
                    if (chosen) chosen.classList.add("active");
                });
            }
        }
    };

    // 11. Two-Stage Real-Time Live Attendance Sync (<1.8s DOM Updates, Auto-Focus, Interactive Smart Pill)
    window.triggerRealtimeAttendanceSync = function (isManual) {
        const syncPill = document.getElementById("sync-status-pill");
        const syncBtn = document.getElementById("btn-live-attendance-sync");
        const syncIcon = syncBtn ? syncBtn.querySelector(".sync-icon-spin") : (syncPill ? syncPill.querySelector(".sync-spin-icon") : null);

        if (syncPill) {
            syncPill.className = "sync-pill is-syncing";
            syncPill.disabled = true;
            syncPill.innerHTML = '<span class="sync-spin-icon"><svg class="krono-icon krono-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 21h5v-5"/></svg></span> <span class="sync-pill-text">Syncing live attendance...</span>';
        }
        if (syncIcon) {
            syncIcon.style.animation = "spin 1s linear infinite";
        }
        if (syncBtn) {
            syncBtn.style.opacity = "0.7";
            syncBtn.disabled = true;
        }

        fetch("/api/background-sync", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: "attendance" })
        })
        .then(function (r) { return r.json(); })
        .then(function (res) {
            if (syncBtn) {
                syncBtn.style.opacity = "1";
                syncBtn.disabled = false;
            }
            if (syncIcon) {
                syncIcon.style.animation = "none";
            }
            if (!res.ok) {
                if (syncPill) {
                    syncPill.className = "sync-pill sync-offline";
                    syncPill.disabled = false;
                    syncPill.innerHTML = '<span class="sync-dot"><svg class="krono-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></span> <span class="sync-pill-text">Offline Snapshot (Tap to retry)</span> <span class="sync-spin-icon"><svg class="krono-icon krono-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 21h5v-5"/></svg></span>';
                }
                return;
            }

            // 0. Update student name immediately if real name returned from fast sync
            if (res.student_name && res.student_name.toLowerCase() !== "student") {
                portalData.student_name = res.student_name;
                const welcomeEl = document.getElementById("welcome-student-name");
                if (welcomeEl) welcomeEl.textContent = res.student_name;
                const mobileSub = document.querySelector(".mobile-student-sub");
                if (mobileSub) mobileSub.innerHTML = `<span class="student-name">${res.student_name}</span> • ${portalData.student_id || ""}`;
                const heroName = document.getElementById("profile-hero-name") || document.querySelector(".profile-name");
                if (heroName) heroName.textContent = res.student_name;
                document.querySelectorAll(".student-name, .user-name, #sidebar-student-name").forEach(function (el) {
                    el.textContent = res.student_name;
                });
                const initialsEl = document.getElementById("profile-avatar-initials");
                if (initialsEl && (!portalData.profile || !portalData.profile.photo_url)) {
                    initialsEl.textContent = getInitials(res.student_name);
                }
            }

            // 1. Update live sync smart pill badge
            if (syncPill) {
                syncPill.className = "sync-pill sync-live";
                syncPill.disabled = false;
                syncPill.innerHTML = '<span class="sync-dot">●</span> <span class="sync-pill-text">Live Synced (<span id="sync-time-badge">' + (res.last_synced || 'Just now') + '</span>)</span> <span class="sync-spin-icon"><svg class="krono-icon krono-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 21h5v-5"/></svg></span>';
            }

            // Visual feedback pulse on overall stats and subject cards
            const overallCard = document.querySelector(".header-stats-card");
            if (overallCard) {
                overallCard.classList.remove("sync-pulse");
                void overallCard.offsetWidth;
                overallCard.classList.add("sync-pulse");
                setTimeout(function () {
                    overallCard.classList.remove("sync-pulse");
                }, 1500);
            }
            document.querySelectorAll(".sub-card").forEach(function (card) {
                card.classList.remove("sync-pulse");
                void card.offsetWidth;
                card.classList.add("sync-pulse");
                setTimeout(function () {
                    card.classList.remove("sync-pulse");
                }, 1500);
            });

            // 2. Update overall percentage and counters in real time
            const overallEl = document.getElementById("overall-pct-display");
            if (overallEl && res.overall_pct !== undefined) {
                overallEl.textContent = res.overall_pct + "%";
            }
            const statusPill = document.getElementById("overall-status-pill");
            if (statusPill && res.overall_pct !== undefined) {
                if (res.overall_pct >= 75) {
                    statusPill.className = "stats-status-pill pct-safe";
                    statusPill.textContent = "Safe";
                } else {
                    statusPill.className = "stats-status-pill pct-danger";
                    statusPill.textContent = "Needs Boost";
                }
            }
            const presNum = document.getElementById("overall-present-num");
            const classNum = document.getElementById("overall-classes-num");
            if (presNum && res.overall_present !== undefined) presNum.textContent = res.overall_present;
            if (classNum && res.overall_classes !== undefined) classNum.textContent = res.overall_classes;

            // 3. Update every Subject Card dynamically without page reload
            if (res.subjects && res.subjects.length > 0) {
                portalData.subjects = res.subjects;
                res.subjects.forEach(function (s, idx) {
                    const card = document.querySelector(`.sub-card[data-idx="${idx}"]`) ||
                                 document.querySelector(`.sub-card[data-name="${s.name}"]`);
                    if (card) {
                        card.dataset.present = s.present;
                        card.dataset.total = s.total;
                        card.dataset.origP = s.present;
                        card.dataset.origT = s.total;

                        card.classList.remove("danger-border", "warn-border");
                        if (s.danger_level === "critical") card.classList.add("danger-border");
                        else if (s.danger_level === "warning") card.classList.add("warn-border");

                        const pctEl = document.getElementById(`pct-${idx}`) || card.querySelector(".pct-display");
                        if (pctEl) {
                            pctEl.textContent = s.pct + "%";
                            pctEl.className = "pct-display " + (s.pct >= 75 ? "pct-safe" : "pct-danger");
                        }

                        const barEl = document.getElementById(`bar-${idx}`) || card.querySelector(".progress-fill");
                        if (barEl) {
                            barEl.style.width = Math.min(100, Math.max(0, s.pct)) + "%";
                            barEl.dataset.pct = s.pct;
                        }

                        const countEl = document.getElementById(`count-${idx}`);
                        if (countEl) {
                            countEl.innerHTML = `Attended: <b>${s.present}</b> / <b>${s.total}</b> classes`;
                        }

                        const statusBox = document.getElementById(`status-box-${idx}`);
                        if (statusBox) {
                            statusBox.textContent = s.status_msg;
                        }

                        const nextAtt = document.getElementById(`next-att-${idx}`);
                        const nextSkip = document.getElementById(`next-skip-${idx}`);
                        const nextAttPct = ((s.present + 1) / (s.total + 1) * 100).toFixed(1);
                        const nextSkipPct = (s.total > 0 ? (s.present / (s.total + 1) * 100) : 0).toFixed(1);
                        if (nextAtt) nextAtt.textContent = `↗ Next Attend: ${nextAttPct}%`;
                        if (nextSkip) nextSkip.textContent = `↘ Next Skip: ${nextSkipPct}%`;
                    }
                });
            }

            // 4. Update Today's Live Attendance list in real time
            if (res.today_attendance !== undefined) {
                portalData.today_attendance = res.today_attendance;
                const todayBanner = document.getElementById("today-live-banner") || document.querySelector(".today-banner") || document.querySelector(".today-card");
                if (todayBanner) {
                    const dateBadge = document.getElementById("today-date-badge") || todayBanner.querySelector(".today-header span");
                    if (dateBadge && res.today_date) {
                        dateBadge.textContent = res.today_date;
                    }

                    const container = document.getElementById("today-live-attendance-body") || document.getElementById("today-attendance-container") || todayBanner;
                    if (res.today_attendance && res.today_attendance.length > 0) {
                        let html = '<div class="today-list" id="today-list">';
                        res.today_attendance.forEach(function (item) {
                            const isPres = item.status === "PRESENT";
                            html += `
                                <div class="today-pill">
                                    <span class="today-subj-name">${item.subject}</span>
                                    <div class="today-status-wrap">
                                        <span class="${isPres ? 'badge-present' : 'badge-absent'}">${item.status}</span>
                                        ${!isPres ? `<button type="button" class="btn-dispute-pill open-dispute-btn" data-subject="${item.subject}" data-date="${item.date}">Dispute</button>` : ''}
                                    </div>
                                </div>
                            `;
                        });
                        html += '</div>';
                        container.innerHTML = html;
                    } else if (res.latest_attendance_records && res.latest_attendance_records.length > 0) {
                        const dateText = res.today_date || (dateBadge ? dateBadge.textContent : "today");
                        let fallbackHtml = `
                            <p id="today-empty-msg" style="color: #9ca3af; font-size: 0.90rem; margin-bottom: 8px;">No lectures marked for today (${dateText}) yet. Any new marks will trigger an instant alert.</p>
                            <div style="font-size: 0.82rem; color: #38bdf8; font-weight: 600; margin-bottom: 8px; display: flex; align-items: center; gap: 6px;">
                                <span><svg class="krono-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="17" x2="12" y2="22"/><path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"/></svg> Last Uploaded on College Portal (${res.latest_attendance_date || ''}):</span>
                            </div>
                            <div class="today-list" id="today-list">
                        `;
                        res.latest_attendance_records.forEach(function (item) {
                            const isPres = item.status === "PRESENT";
                            fallbackHtml += `
                                <div class="today-pill" style="opacity: 0.94; border-color: rgba(56, 189, 248, 0.25);">
                                    <span class="today-subj-name">${item.subject}</span>
                                    <div class="today-status-wrap">
                                        <span class="${isPres ? 'badge-present' : 'badge-absent'}">${item.status}</span>
                                        ${!isPres ? `<button type="button" class="btn-dispute-pill open-dispute-btn" data-subject="${item.subject}" data-date="${item.date}">Dispute</button>` : ''}
                                    </div>
                                </div>
                            `;
                        });
                        fallbackHtml += '</div>';
                        container.innerHTML = fallbackHtml;
                    } else {
                        const dateText = res.today_date || (dateBadge ? dateBadge.textContent : "today");
                        container.innerHTML = `<p id="today-empty-msg" style="color: #9ca3af; font-size: 0.92rem;">No lectures marked for today (${dateText}) yet. Any new absent marks will trigger an instant alert.</p>`;
                    }
                }
            }

            // 5. Update Calendar entries in real time
            if (res.calendar_records && res.calendar_records.length > 0) {
                portalData.calendar_records = res.calendar_records;
                allRecords = res.calendar_records;
                window.calendarRecords = res.calendar_records;
                if (typeof renderCalendar === "function") {
                    renderCalendar();
                }
            }

            // 6. Manual Sync Toast Feedback
            if (isManual) {
                const syncToast = document.getElementById("bg-sync-toast");
                if (syncToast) {
                    syncToast.innerHTML = '<svg class="krono-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> Real-Time Attendance Synced (' + res.last_synced + ')';
                    syncToast.style.opacity = "1";
                    syncToast.style.transform = "translateY(0)";
                    setTimeout(function () {
                        syncToast.style.opacity = "0";
                        syncToast.style.transform = "translateY(-10px)";
                    }, 3000);
                }
            }

            // 7. Dynamic Stage 2 Deep Sync (Triggers if name is "Student", profile details <= 4, or results are empty)
            const needsNameRefresh = (!portalData.student_name || portalData.student_name.toLowerCase() === "student");
            const needsProfileRefresh = (!portalData.profile || !portalData.profile.details || portalData.profile.details.length <= 4);
            const needsResultsRefresh = (!portalData.results || portalData.results.length === 0);

            if ((needsNameRefresh || needsProfileRefresh || needsResultsRefresh) && !window._hasFiredDeepSync) {
                window._hasFiredDeepSync = true;
                fetch("/api/background-sync", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ mode: "deep" })
                })
                .then(function (dr) { return dr.json(); })
                .then(function (deepRes) {
                    if (!deepRes.ok) return;

                    // A. Dynamically update student name in header, sidebar & profile
                    if (deepRes.student_name && deepRes.student_name.toLowerCase() !== "student") {
                        portalData.student_name = deepRes.student_name;
                        const welcomeEl = document.getElementById("welcome-student-name");
                        if (welcomeEl) welcomeEl.textContent = deepRes.student_name;
                        const mobileSub = document.querySelector(".mobile-student-sub");
                        if (mobileSub) {
                            mobileSub.innerHTML = `<span class="student-name">${deepRes.student_name}</span> • ${portalData.student_id || ""}`;
                        }
                        const heroName = document.getElementById("profile-hero-name") || document.querySelector(".profile-name");
                        if (heroName) {
                            heroName.textContent = deepRes.student_name;
                        }
                        document.querySelectorAll(".student-name, .user-name, #sidebar-student-name").forEach(function (el) {
                            el.textContent = deepRes.student_name;
                        });
                    }

                    // B. Dynamically update Profile tab (#tab-profile)
                    if (deepRes.profile) {
                        portalData.profile = deepRes.profile;
                        const avatarEl = document.getElementById("profile-avatar-container") || document.querySelector(".profile-avatar");
                        if (avatarEl) {
                            if (deepRes.profile.photo_url) {
                                avatarEl.innerHTML = `<img src="${deepRes.profile.photo_url}" alt="Student" style="width: 100%; height: 100%; object-fit: cover; border-radius: 50%;">`;
                            } else {
                                const initials = getInitials(deepRes.student_name || portalData.student_name);
                                avatarEl.innerHTML = `<span id="profile-avatar-initials" style="font-size: 2.2rem; font-weight: 800; color: #ffffff; letter-spacing: 0.05em; text-shadow: 0 2px 8px rgba(0,0,0,0.4);">${initials}</span>`;
                            }
                        }

                        if (deepRes.profile.details && deepRes.profile.details.length > 0) {
                            const gridEl = document.getElementById("profile-grid-container") || document.querySelector(".profile-grid");
                            if (gridEl) {
                                let profHtml = "";
                                deepRes.profile.details.forEach(function (pair) {
                                    profHtml += `
                                        <div class="profile-item">
                                            <div class="profile-label">${pair[0]}</div>
                                            <div class="profile-val">${pair[1]}</div>
                                        </div>
                                    `;
                                });
                                gridEl.innerHTML = profHtml;
                            }
                        }
                    }

                    // C. Dynamically update Results tab (#tab-results)
                    if (deepRes.results && deepRes.results.length > 0) {
                        portalData.results = deepRes.results;
                        if (deepRes.sgpa_trend) portalData.sgpa_trend = deepRes.sgpa_trend;
                        if (deepRes.fees) portalData.fees = deepRes.fees;

                        if (typeof window.renderResultsTabDynamically === "function") {
                            window.renderResultsTabDynamically(deepRes.results);
                        }
                    }
                })
                .catch(function () {});
            }
        })
        .catch(function (err) {
            if (syncBtn) {
                syncBtn.style.opacity = "1";
                syncBtn.disabled = false;
            }
            if (syncIcon) {
                syncIcon.style.animation = "none";
            }
            if (syncPill) {
                syncPill.className = "sync-pill sync-offline";
                syncPill.disabled = false;
                syncPill.innerHTML = '<span class="sync-dot"><svg class="krono-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg></span> <span class="sync-pill-text">Offline Snapshot (Tap to retry)</span> <span class="sync-spin-icon"><svg class="krono-icon krono-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 21h5v-5"/></svg></span>';
            }
        });
    };

    // Auto-trigger live attendance sync on initial load (250ms)
    setTimeout(function () {
        window.triggerRealtimeAttendanceSync(false);
    }, 250);

    // Auto-sync on window/tab focus if more than 60 seconds have elapsed
    let lastTabSyncTime = Date.now();
    document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "visible") {
            if (Date.now() - lastTabSyncTime > 60000) {
                lastTabSyncTime = Date.now();
                window.triggerRealtimeAttendanceSync(false);
            }
        }
    });

    // Auto-sync periodic interval every 180 seconds while dashboard is open
    setInterval(function () {
        if (document.visibilityState === "visible") {
            window.triggerRealtimeAttendanceSync(false);
        }
    }, 180000);
    // // 12. Submit Feedback & Suggestions to Supabase
    // const fbBtn = document.getElementById("btn-submit-feedback");
    // const fbStatus = document.getElementById("fb-status-msg");
    // if (fbBtn) {
    //     fbBtn.addEventListener("click", function () {
    //         const category = document.getElementById("fb-category").value;
    //         const rating = document.getElementById("fb-rating").value;
    //         const message = document.getElementById("fb-message").value.trim();

    //         if (!message) {
    //             fbStatus.textContent = "Please write a message before submitting.";
    //             fbStatus.style.color = "#f87171";
    //             return;
    //         }

    //         fbBtn.disabled = true;
    //         fbStatus.textContent = "Sending feedback to developer...";
    //         fbStatus.style.color = "#38bdf8";

    //         fetch("/api/submit-feedback", {
    //             method: "POST",
    //             headers: { "Content-Type": "application/json" },
    //             body: JSON.stringify({ category: category, rating: rating, message: message })
    //         })
    //         .then(function (r) { return r.json(); })
    //         .then(function (res) {
    //             fbBtn.disabled = false;
    //             fbStatus.textContent = res.message;
    //             fbStatus.style.color = res.ok ? "#4ade80" : "#f87171";
    //             if (res.ok) {
    //                 document.getElementById("fb-message").value = "";
    //                 setTimeout(function () { window.location.reload(); }, 1000);
    //             }
    //         });
    //     });
    // }