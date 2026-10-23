/**
 * Ultra Mobile App Hub & Viral Share Controller
 * Handles WebAPK PWA installation, native APK downloads, WhatsApp viral sharing,
 * Native Share Sheet API, and offline Classroom QR Code generation.
 */

let deferredInstallPrompt = null;
let qrCodeGenerated = false;

// Listen for PWA beforeinstallprompt (Chrome / Android / Edge WebAPK installer)
window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferredInstallPrompt = e;
    updatePwaInstallButtonState();
});

function isAppStandalone() {
    return (
        window.matchMedia("(display-mode: standalone)").matches ||
        window.navigator.standalone === true ||
        document.referrer.includes("android-app://")
    );
}

function isIosDevice() {
    return (
        /iPad|iPhone|iPod/.test(navigator.userAgent) && !window.MSStream
    );
}

function updatePwaInstallButtonState() {
    const btn = document.getElementById("btn-pwa-install");
    const iosBox = document.getElementById("ios-install-guide");
    if (!btn) return;

    if (isAppStandalone()) {
        btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:4px;"><polyline points="20 6 9 17 4 12"/></svg> App Already Installed & Running';
        btn.className = "btn-hub-action btn-hub-installed";
        btn.onclick = null;
        if (iosBox) iosBox.style.display = "none";
    } else if (deferredInstallPrompt) {
        btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:4px;"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> 1-Click Install WebAPK';
        btn.className = "btn-hub-action btn-hub-primary";
        btn.onclick = triggerPwaInstall;
        if (iosBox) iosBox.style.display = "none";
    } else if (isIosDevice()) {
        btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:4px;"><rect width="14" height="20" x="5" y="2" rx="2" ry="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg> Add to Home Screen (iOS)';
        btn.className = "btn-hub-action btn-hub-primary";
        btn.onclick = function () {
            if (iosBox) iosBox.style.display = "block";
        };
        if (iosBox) iosBox.style.display = "block";
    } else {
        btn.innerHTML = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:4px;"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> Install WebAPK Shortcut';
        btn.className = "btn-hub-action btn-hub-primary";
        btn.onclick = triggerPwaInstall;
        if (iosBox) iosBox.style.display = "none";
    }
}

const EXTERNAL_APK_DOWNLOAD_URL = "https://raw.githubusercontent.com/Harman-777/attendance/main/static/apk/Krono.apk";

function showApkToast(msg) {
    let toast = document.getElementById("apk-update-toast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "apk-update-toast";
        toast.style.cssText = "position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%); z-index: 99999999; background: #1e1b4b; color: #38bdf8; border: 2px solid #38bdf8; padding: 12px 20px; border-radius: 12px; font-weight: 700; font-size: 0.9rem; box-shadow: 0 10px 30px rgba(0,0,0,0.8); text-align: center; max-width: 90%; transition: opacity 0.3s ease;";
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.opacity = "1";
    setTimeout(function () {
        if (toast) toast.style.opacity = "0";
    }, 6000);
}

function copyApkDownloadLink() {
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(EXTERNAL_APK_DOWNLOAD_URL).then(function () {
            showApkToast("Direct APK download link copied to clipboard!");
        }).catch(function () {
            showApkToast("Direct link: " + EXTERNAL_APK_DOWNLOAD_URL);
        });
    } else {
        showApkToast("Direct link: " + EXTERNAL_APK_DOWNLOAD_URL);
    }
}

function triggerApkUpdate() {
    const isApk = isAndroidWebViewOrApk();
    // In APK shells, use external GitHub URL to avoid self-recursive App Link loops into the app
    const targetUrl = isApk ? EXTERNAL_APK_DOWNLOAD_URL : (window.location.origin + "/download/Krono.apk");

    // Dismiss update popup so it doesn't stay on screen or cause any loops
    sessionStorage.setItem("apk_update_popup_dismissed", "1");
    const popup = document.getElementById("ultra-update-popup");
    if (popup) popup.remove();

    showApkToast("Starting download... Check notification bar or Chrome downloads.");

    // 1. If running in updated native APK with Java download bridge
    if (window.AndroidApp && typeof window.AndroidApp.downloadUpdate === "function") {
        window.AndroidApp.downloadUpdate(targetUrl);
        return;
    }

    // 2. Browser or WebView location navigation to initiate direct download
    window.location.href = targetUrl;
}

function triggerPwaInstall() {
    if (deferredInstallPrompt) {
        deferredInstallPrompt.prompt();
        deferredInstallPrompt.userChoice.then(function (choice) {
            if (choice.outcome === "accepted") {
                console.log("Krono WebAPK installed!");
                updatePwaInstallButtonState();
            }
            deferredInstallPrompt = null;
        });
    } else if (isIosDevice()) {
        const iosBox = document.getElementById("ios-install-guide");
        if (iosBox) iosBox.style.display = "block";
    } else {
        const confirmDownload = confirm("WebAPK prompt is preparing. Would you like to download the direct signed Android APK (Krono.apk) right now?");
        if (confirmDownload) {
            triggerApkUpdate();
        }
    }
}

function openUltraAppModal() {
    const modal = document.getElementById("ultra-app-modal");
    if (!modal) return;
    modal.style.display = "flex";
    document.body.style.overflow = "hidden";
    updatePwaInstallButtonState();

    // Render Classroom QR Code once
    if (!qrCodeGenerated) {
        const qrContainer = document.getElementById("app-qr-code");
        if (qrContainer && typeof QRCode !== "undefined") {
            qrContainer.innerHTML = "";
            new QRCode(qrContainer, {
                text: window.location.origin,
                width: 140,
                height: 140,
                colorDark: "#090d16",
                colorLight: "#ffffff",
                correctLevel: QRCode.CorrectLevel.M
            });
            qrCodeGenerated = true;
        }
    }
}

function closeUltraAppModal() {
    const modal = document.getElementById("ultra-app-modal");
    if (!modal) return;
    modal.style.display = "none";
    document.body.style.overflow = "";
}

// Close on backdrop click or Escape key
document.addEventListener("click", function (e) {
    const modal = document.getElementById("ultra-app-modal");
    if (modal && e.target === modal) {
        closeUltraAppModal();
    }
});

document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
        closeUltraAppModal();
    }
});

// Viral Share Actions
function shareOnWhatsApp() {
    const origin = window.location.origin;
    const downloadUrl = origin + "/download/Krono.apk";
    const msg = "Check your live college attendance in 0.4 seconds, calculate safe bunks, and get instant absent alerts!\n\nDirect Android App Download: " + downloadUrl + "\nWeb Workspace: " + origin;

    // 1. Android APK native bridge -> launches WhatsApp mobile app directly
    if (window.AndroidApp && typeof window.AndroidApp.shareWhatsApp === "function") {
        window.AndroidApp.shareWhatsApp(msg);
        return;
    }

    // 2. Mobile Browser -> try whatsapp:// URI first to open app, fallback to web
    if (/Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) {
        window.location.href = "whatsapp://send?text=" + encodeURIComponent(msg);
        setTimeout(function () {
            window.open("https://api.whatsapp.com/send?text=" + encodeURIComponent(msg), "_blank");
        }, 800);
    } else {
        window.open("https://api.whatsapp.com/send?text=" + encodeURIComponent(msg), "_blank");
    }
}

function shareNativeSheet() {
    const origin = window.location.origin;
    const downloadUrl = origin + "/download/Krono.apk";
    const shareText = "Krono — Check your live college attendance in 0.4 seconds, calculate safe bunks & get absent alerts!\n\nDirect APK Download:\n" + downloadUrl + "\n\nWeb Portal:\n" + origin;

    // 1. Android APK native share drawer bridge
    if (window.AndroidApp && typeof window.AndroidApp.shareApp === "function") {
        window.AndroidApp.shareApp(shareText, downloadUrl);
        return;
    }

    // 2. Standard Web Share API (Chrome / Safari / Edge mobile)
    if (navigator.share) {
        navigator.share({
            title: "Krono — Student Workspace",
            text: shareText,
            url: downloadUrl
        }).catch(function () {
            // Ignored if user dismissed sheet
        });
    } else {
        copyPortalShareLink();
    }
}

function copyPortalShareLink() {
    const origin = window.location.origin;
    const downloadUrl = origin + "/download/Krono.apk";
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(downloadUrl).then(function () {
            showCopyFeedback();
        }).catch(function () {
            fallbackCopy(downloadUrl);
        });
    } else {
        fallbackCopy(downloadUrl);
    }
}

function fallbackCopy(text) {
    const t = document.createElement("textarea");
    t.value = text;
    t.style.position = "fixed";
    t.style.opacity = "0";
    document.body.appendChild(t);
    t.select();
    try {
        document.execCommand("copy");
        showCopyFeedback();
    } catch (e) {
        prompt("Copy Krono APK Download Link:", text);
    }
    document.body.removeChild(t);
}

function showCopyFeedback() {
    const btn = document.getElementById("btn-copy-share-link");
    if (btn) {
        const originalHtml = btn.innerHTML;
        btn.innerHTML = "<span><svg width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='currentColor' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round' style='vertical-align:-2px;margin-right:3px;'><polyline points='20 6 9 17 4 12'/></svg></span> Copied APK Link!";
        btn.style.borderColor = "#4ade80";
        btn.style.color = "#4ade80";
        setTimeout(function () {
            btn.innerHTML = originalHtml;
            btn.style.borderColor = "";
            btn.style.color = "";
        }, 2000);
    }
}

function isAndroidWebViewOrApk() {
    const ua = navigator.userAgent || "";
    return (
        window.AndroidApp !== undefined ||
        /UltraPortalApp/i.test(ua) ||
        (/Android/i.test(ua) && /; wv\)/i.test(ua))
    );
}

// In-App APK Version & Auto-Update Checker (Strictly isolated to Android APK / WebView)
function checkApkUpdate() {
    if (!isAndroidWebViewOrApk()) {
        const stalePopup = document.getElementById("ultra-update-popup");
        if (stalePopup) stalePopup.remove();
        const staleBanner = document.getElementById("apk-update-banner");
        if (staleBanner) staleBanner.remove();
        return;
    }

    fetch("/api/app-version?t=" + Date.now(), { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            let installedVer = "2.0";
            if (window.AndroidApp && typeof window.AndroidApp.getAppVersion === "function") {
                installedVer = window.AndroidApp.getAppVersion();
            } else {
                const match = navigator.userAgent.match(/UltraPortalApp\/([\d\.]+)/);
                if (match) {
                    installedVer = match[1];
                } else {
                    installedVer = "2.0";
                }
            }

            const verBadge = document.getElementById("apk-version-badge");
            if (verBadge) {
                if (parseFloat(installedVer) >= parseFloat(data.latest_version)) {
                    verBadge.textContent = "v" + installedVer + " (Latest Up-to-Date)";
                    verBadge.style.color = "#4ade80";
                } else {
                    verBadge.textContent = "v" + installedVer + " (Update to v" + data.latest_version + " Available!)";
                    verBadge.style.color = "#f59e0b";
                }
            }

            // Whenever installed version is older, display high-visibility 1-click update modal, banner & badge highlights
            if (parseFloat(installedVer) < parseFloat(data.latest_version)) {
                // 1. Highlight header & sidebar badges as clickable update triggers
                const appBadges = document.querySelectorAll(".app-badge");
                appBadges.forEach(function (badge) {
                    badge.innerHTML = "UPDATE v" + data.latest_version;
                    badge.style.background = "linear-gradient(135deg, #d97706, #b45309)";
                    badge.style.color = "#ffffff";
                    badge.style.cursor = "pointer";
                    badge.style.border = "1px solid #f59e0b";
                    badge.onclick = triggerApkUpdate;
                });

                // 2. Trigger native Android notification if Java bridge is available
                if (window.AndroidApp && typeof window.AndroidApp.showNativeNotification === "function") {
                    window.AndroidApp.showNativeNotification(
                        "Krono v" + data.latest_version + " Ready!",
                        "Tap to install the latest update with faster login & new features."
                    );
                }

                // 3. Fallback: Browser/Web Push System Notification if permission is granted
                try {
                    if ("Notification" in window && Notification.permission === "granted") {
                        if (navigator.serviceWorker && navigator.serviceWorker.ready) {
                            navigator.serviceWorker.ready.then(function (reg) {
                                reg.showNotification("Krono Update (v" + data.latest_version + ") Ready!", {
                                    body: "Tap to update your app with 5x faster login & automatic SGPA records.",
                                    icon: "/static/icons/icon-192.png",
                                    badge: "/static/icons/icon-192.png",
                                    data: { url: "/update" }
                                });
                            });
                        }
                    }
                } catch (e) {}

                // 4. Render prominent centered modal popup dialog (once per session)
                if (!sessionStorage.getItem("apk_update_popup_dismissed") && !document.getElementById("ultra-update-popup")) {
                    const popup = document.createElement("div");
                    popup.id = "ultra-update-popup";
                    popup.style.cssText = "position: fixed; inset: 0; z-index: 9999999; background: rgba(0,0,0,0.85); backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px); display: flex; align-items: center; justify-content: center; padding: 20px;";
                    popup.innerHTML = `
                        <div style="background: #111827; border: 2px solid #38bdf8; border-radius: 20px; max-width: 400px; width: 100%; padding: 26px 22px; text-align: center; box-shadow: 0 20px 50px rgba(0,0,0,0.8);">
                            <div style="display: flex; justify-content: center; margin-bottom: 12px;"><svg width="44" height="44" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 9V4s3.03.55 4 2c1.08 1.62 0 5 0 5"/></svg></div>
                            <div style="display: inline-block; background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid #f59e0b; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; margin-bottom: 12px; letter-spacing: 0.04em;">NEW UPDATE READY</div>
                            <h3 style="color: #f8fafc; font-size: 1.35rem; font-weight: 800; margin-bottom: 8px;">Krono v${data.latest_version}</h3>
                            <p style="color: #94a3b8; font-size: 0.88rem; line-height: 1.45; margin-bottom: 18px;">
                                Your installed app is <b>v${installedVer}</b>. An updated version is available with <b>5x faster login</b>, <b>automated SGPA marksheets</b>, and mobile fixes!
                            </p>
                            <button type="button" onclick="triggerApkUpdate()" style="width: 100%; height: 48px; background: linear-gradient(135deg, #2563eb, #7c3aed); color: white; font-weight: 800; font-size: 1rem; border: none; border-radius: 12px; cursor: pointer; margin-bottom: 10px; box-shadow: 0 4px 15px rgba(37,99,235,0.4);">
                                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-3px;margin-right:6px;"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>Update App Now (1-Click)
                            </button>
                            <button type="button" onclick="copyApkDownloadLink()" style="width: 100%; height: 40px; background: rgba(56, 189, 248, 0.12); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 10px; font-weight: 700; font-size: 0.88rem; cursor: pointer; margin-bottom: 12px; display: flex; align-items: center; justify-content: center; gap: 8px;">
                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" style="vertical-align:-2px;margin-right:6px;"><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/></svg>Copy Direct Download Link
                            </button>
                            <button type="button" onclick="sessionStorage.setItem('apk_update_popup_dismissed', '1'); document.getElementById('ultra-update-popup').remove();" style="background: transparent; border: none; color: #64748b; font-size: 0.84rem; cursor: pointer; text-decoration: underline;">
                                Remind Me Later
                            </button>
                        </div>
                    `;
                    document.body.appendChild(popup);
                }

                // 5. Fixed Top Floating Banner
                if (!document.getElementById("apk-update-banner")) {
                    const banner = document.createElement("div");
                    banner.id = "apk-update-banner";
                    banner.style.cssText = "position: fixed; top: 0; left: 0; right: 0; z-index: 999998; background: linear-gradient(135deg, #1e1b4b 0%, #1e3a8a 100%); border-bottom: 2px solid #38bdf8; padding: 10px 16px; display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; box-shadow: 0 4px 20px rgba(0,0,0,0.5);";
                    banner.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px; font-size: 0.86rem; color: #f8fafc;">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 9V4s3.03.55 4 2c1.08 1.62 0 5 0 5"/></svg>
                            <span><b>Krono Update (v${data.latest_version})</b> is ready!</span>
                        </div>
                        <div style="display: flex; gap: 8px; align-items: center;">
                            <button type="button" onclick="triggerApkUpdate()" style="background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%); color: #fff; border: none; cursor: pointer; padding: 6px 14px; border-radius: 8px; font-weight: 700; font-size: 0.82rem; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 8px rgba(37,99,235,0.4);">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> 1-Click Update
                            </button>
                            <button type="button" onclick="this.parentElement.parentElement.remove()" style="background: transparent; border: none; color: #94a3b8; cursor: pointer; padding: 0 6px; display: inline-flex; align-items: center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
                        </div>
                    `;
                    document.body.prepend(banner);
                }
            }
        })
        .catch(function () {});
}

// Initial setup on load
document.addEventListener("DOMContentLoaded", function () {
    updatePwaInstallButtonState();
    checkApkUpdate();
});

// Backward and forward compatibility aliases
window.openKronoAppModal = openUltraAppModal;
window.closeKronoAppModal = closeUltraAppModal;
