document.addEventListener("DOMContentLoaded", function () {
    const rawData = document.getElementById("portal-data-json").textContent;
    const portalData = JSON.parse(rawData || "{}");
    const allRecords = portalData.calendar_records || [];
    const subjectsList = portalData.subjects || [];
    const newAbsents = portalData.new_absents || [];

    let targetThreshold = 75;
    let medicalMode = false;

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

        nextAttEl.textContent = "↗ Next Attend: " + nextAtt.toFixed(1) + "%";
        nextSkipEl.textContent = "↘ Next Skip: " + nextSkip.toFixed(1) + "%";

        if (t === 0) {
            boxEl.textContent = "No classes recorded yet.";
        } else if (isSafe) {
            const bunks = Math.floor((p - targetDec * t) / targetDec);
            if (bunks <= 2) {
                boxEl.textContent = "⚠️ Danger Zone: Only " + bunks + " safe skip(s) for " + target + "%!";
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
            copyDispBtn.textContent = "✔ Copied to Clipboard!";
            setTimeout(function () {
                copyDispBtn.textContent = "📋 Copy Application Text";
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
                ? "✔ Linked to Supabase! Lock-Screen Push Active."
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
                encryptVaultBtn.textContent = res.vault_enabled
                    ? "🔒 Re-Encrypt & Update Vault"
                    : "🔐 Encrypt & Save Password to Cloud";
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

    // 11. Two-Stage Real-Time Live Attendance Sync (<1.8s DOM Updates, Auto-Focus, Manual Button)
    window.triggerRealtimeAttendanceSync = function (isManual) {
        const syncPill = document.getElementById("sync-status-pill") || document.querySelector(".sync-pill");
        const syncBtn = document.getElementById("btn-live-attendance-sync");
        const syncIcon = syncBtn ? syncBtn.querySelector(".sync-icon-spin") : null;

        if (syncPill) {
            syncPill.className = "sync-pill sync-offline";
            syncPill.textContent = "⚡ Syncing live attendance from portal...";
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
            if (!res.ok) return;

            // 1. Update live sync header badge
            if (syncPill) {
                syncPill.className = "sync-pill sync-live";
                syncPill.innerHTML = '● LIVE PORTAL SYNC (<span id="sync-time-badge">' + res.last_synced + '</span>)';
            }

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

                    const container = document.getElementById("today-attendance-container") || todayBanner;
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
                    } else {
                        const dateText = res.today_date || (dateBadge ? dateBadge.textContent : "today");
                        container.innerHTML = `<p id="today-empty-msg" style="color: #9ca3af; font-size: 0.92rem;">No lectures marked for today (${dateText}) yet. Any new absent marks will trigger an instant alert.</p>`;
                    }
                }
            }

            // 5. Update Calendar entries in real time
            if (res.calendar_records && res.calendar_records.length > 0) {
                portalData.calendar_records = res.calendar_records;
                if (typeof renderCalendar === "function") {
                    renderCalendar();
                }
            }

            // 6. Manual Sync Toast Feedback
            if (isManual) {
                const syncToast = document.getElementById("bg-sync-toast");
                if (syncToast) {
                    syncToast.textContent = "⚡ Real-Time Attendance Synced (" + res.last_synced + ")";
                    syncToast.style.opacity = "1";
                    syncToast.style.transform = "translateY(0)";
                    setTimeout(function () {
                        syncToast.style.opacity = "0";
                        syncToast.style.transform = "translateY(-10px)";
                    }, 3000);
                }
            }

            // 7. Silent Stage 2 Deep Sync (Only if student has empty Results/SGPA)
            const hadNoResults = (!portalData.results || portalData.results.length === 0);
            if (hadNoResults && !window._hasFiredDeepSync) {
                window._hasFiredDeepSync = true;
                fetch("/api/background-sync", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ mode: "deep" })
                })
                .then(function (dr) { return dr.json(); })
                .then(function (deepRes) {
                    if (deepRes.ok && deepRes.results && deepRes.results.length > 0) {
                        portalData.results = deepRes.results;
                        portalData.sgpa_trend = deepRes.sgpa_trend;
                        portalData.fees = deepRes.fees;
                        portalData.profile = deepRes.profile;
                        if (typeof renderResults === "function") {
                            renderResults();
                        }
                    }
                })
                .catch(function () {});
            }
        })
        .catch(function () {
            if (syncBtn) {
                syncBtn.style.opacity = "1";
                syncBtn.disabled = false;
            }
            if (syncIcon) {
                syncIcon.style.animation = "none";
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