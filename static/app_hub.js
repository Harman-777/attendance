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

const EXTERNAL_APK_DOWNLOAD_URL = "https://github.com/Harman-777/attendance/raw/main/static/apk/Krono.apk";
const GITHUB_DIRECT_APK_URL = "https://github.com/Harman-777/attendance/raw/main/static/apk/Krono.apk";
const GITHUB_BROWSER_INTENT_URL = "intent://github.com/Harman-777/attendance/raw/main/static/apk/Krono.apk#Intent;scheme=https;action=android.intent.action.VIEW;category=android.intent.category.BROWSABLE;end";

function openExternalBrowser(url) {
    const targetUrl = url || GITHUB_DIRECT_APK_URL;
    if (window.AndroidApp && typeof window.AndroidApp.openExternalBrowser === "function") {
        window.AndroidApp.openExternalBrowser(targetUrl);
        return;
    }
    // Android intent scheme bypasses internal WebView .apk interception and launches Chrome / system browser
    if (/Android|wv/i.test(navigator.userAgent) || window.AndroidApp) {
        window.location.href = GITHUB_BROWSER_INTENT_URL;
    } else {
        window.open(targetUrl, "_blank", "noopener,noreferrer");
    }
}
window.openExternalBrowser = openExternalBrowser;

window.triggerInstallNow = function () {
    if (window.AndroidApp && typeof window.AndroidApp.installDownloadedUpdate === "function") {
        window.AndroidApp.installDownloadedUpdate();
    } else if (window.AndroidApp && typeof window.AndroidApp.installUpdate === "function") {
        window.AndroidApp.installUpdate();
    } else {
        openExternalBrowser(GITHUB_DIRECT_APK_URL);
    }
};

window.onKronoDownloadProgress = function (pct) {
    const bar = document.getElementById("krono-progress-bar");
    const label = document.getElementById("krono-progress-label");
    const safePct = Math.min(100, Math.max(0, parseInt(pct, 10) || 0));
    if (bar) bar.style.width = safePct + "%";
    if (label) label.textContent = safePct + "%";
    if (safePct >= 100) {
        window.onKronoDownloadComplete();
    }
};

window.onKronoDownloadComplete = function () {
    const modal = document.getElementById("krono-download-progress-modal");
    if (modal) {
        const title = modal.querySelector(".krono-modal-title");
        const desc = modal.querySelector(".krono-modal-desc");
        const bar = document.getElementById("krono-progress-bar");
        const label = document.getElementById("krono-progress-label");
        const actionBox = document.getElementById("krono-modal-actions");
        const iconWrap = document.getElementById("krono-modal-icon");

        if (bar) {
            bar.style.width = "100%";
            bar.style.background = "#22c55e";
        }
        if (label) label.textContent = "100% Ready";
        if (title) title.textContent = "Download Complete!";
        if (desc) desc.textContent = "The update is downloaded and ready to install. Opening Android Package Installer...";
        if (iconWrap) {
            iconWrap.innerHTML = '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#22c55e" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>';
        }
        if (actionBox) {
            actionBox.innerHTML = `
                <button type="button" onclick="triggerInstallNow()" style="width: 100%; height: 50px; background: #22c55e; color: #000; font-weight: 800; font-size: 1rem; border: none; border-radius: 12px; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px; box-shadow: 0 4px 16px rgba(34,197,94,0.4); margin-bottom: 12px;">
                    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                    Install Update Now
                </button>
                <div style="background: rgba(30, 41, 59, 0.7); border: 1px solid rgba(56, 189, 248, 0.2); border-radius: 10px; padding: 10px 12px; text-align: left; font-size: 0.8rem; color: #94a3b8; line-height: 1.45; margin-bottom: 12px;">
                    <b style="color: #4ade80;">Verified Safe:</b> Play Protect clean architecture. Tap below to launch installer directly.
                </div>
                <button type="button" onclick="document.getElementById('krono-download-progress-modal').remove()" style="background: transparent; border: none; color: #64748b; font-size: 0.84rem; cursor: pointer; text-decoration: underline;">
                    Close Window
                </button>
            `;
        }
    }

    // Update banner button if visible
    const banner = document.getElementById("apk-update-banner");
    if (banner) {
        const btn = banner.querySelector("button");
        if (btn) {
            btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg> Install Now';
            btn.style.background = "#22c55e";
            btn.style.color = "#000000";
            btn.style.opacity = "1";
            btn.disabled = false;
            btn.onclick = triggerInstallNow;
        }
    }
};

window.onKronoDownloadError = function (msg) {
    const modal = document.getElementById("krono-download-progress-modal");
    if (modal) {
        const title = modal.querySelector(".krono-modal-title");
        const desc = modal.querySelector(".krono-modal-desc");
        const actionBox = document.getElementById("krono-modal-actions");
        if (title) title.textContent = "Download Incomplete";
        if (desc) desc.textContent = msg || "Connection was interrupted. Tap below to retry or install via browser.";
        if (actionBox) {
            actionBox.innerHTML = `
                <button type="button" onclick="triggerApkUpdate()" style="width: 100%; height: 46px; background: #2563eb; color: #fff; font-weight: 700; font-size: 0.95rem; border: none; border-radius: 12px; cursor: pointer; margin-bottom: 10px;">
                    Retry Download
                </button>
                <button type="button" onclick="openExternalBrowser(GITHUB_DIRECT_APK_URL)" style="width: 100%; height: 42px; background: rgba(56, 189, 248, 0.12); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 12px; font-weight: 700; font-size: 0.88rem; cursor: pointer; margin-bottom: 10px;">
                    Install via Browser
                </button>
                <button type="button" onclick="document.getElementById('krono-download-progress-modal').remove()" style="background: transparent; border: none; color: #64748b; font-size: 0.84rem; cursor: pointer;">
                    Cancel
                </button>
            `;
        }
    }
};

function showApkToast(msg) {
    let toast = document.getElementById("apk-update-toast");
    if (!toast) {
        toast = document.createElement("div");
        toast.id = "apk-update-toast";
        toast.style.cssText = "position: fixed; bottom: 30px; left: 50%; transform: translateX(-50%); z-index: 99999999; background: #0f172a; color: #38bdf8; border: 1.5px solid #38bdf8; padding: 12px 22px; border-radius: 14px; font-weight: 700; font-size: 0.9rem; box-shadow: 0 10px 30px rgba(0,0,0,0.8); text-align: center; max-width: 90%; transition: opacity 0.3s ease;";
        document.body.appendChild(toast);
    }
    toast.textContent = msg;
    toast.style.opacity = "1";
    setTimeout(function () {
        if (toast) toast.style.opacity = "0";
    }, 5000);
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
    const targetUrl = window.location.origin + "/download/Krono.apk";

    // Dismiss announcement modal if open
    const prevModal = document.getElementById("krono-update-modal");
    if (prevModal) prevModal.remove();
    const prevPopup = document.getElementById("ultra-update-popup");
    if (prevPopup) prevPopup.remove();

    // Render dedicated Progress Modal
    let progressModal = document.getElementById("krono-download-progress-modal");
    if (progressModal) progressModal.remove();

    progressModal = document.createElement("div");
    progressModal.id = "krono-download-progress-modal";
    progressModal.style.cssText = "position: fixed; inset: 0; z-index: 9999999; background: rgba(3, 7, 18, 0.88); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); display: flex; align-items: center; justify-content: center; padding: 20px;";
    progressModal.innerHTML = `
        <div style="background: #111827; border: 1.5px solid #38bdf8; border-radius: 20px; max-width: 420px; width: 100%; padding: 26px 22px; text-align: center; box-shadow: 0 25px 60px rgba(0,0,0,0.85); color: #f8fafc; font-family: system-ui, sans-serif;">
            <div id="krono-modal-icon" style="display: flex; justify-content: center; margin-bottom: 14px;">
                <svg class="krono-spin" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 21h5v-5"/></svg>
            </div>
            <h3 class="krono-modal-title" style="font-size: 1.35rem; font-weight: 800; margin-bottom: 8px; color: #f8fafc;">Downloading Update...</h3>
            <p class="krono-modal-desc" style="color: #94a3b8; font-size: 0.88rem; line-height: 1.45; margin-bottom: 18px;">
                Downloading signed Krono update (~58 KB). Please keep Krono open.
            </p>
            <div style="background: #1e293b; border: 1px solid #334155; border-radius: 10px; height: 12px; overflow: hidden; margin-bottom: 10px; position: relative;">
                <div id="krono-progress-bar" style="height: 100%; width: 15%; background: linear-gradient(90deg, #38bdf8, #818cf8); border-radius: 10px; transition: width 0.3s ease;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 0.78rem; color: #64748b; font-weight: 700; margin-bottom: 20px;">
                <span>Krono Package</span>
                <span id="krono-progress-label">Connecting...</span>
            </div>
            <div id="krono-modal-actions">
                <button type="button" onclick="openExternalBrowser(GITHUB_DIRECT_APK_URL)" style="width: 100%; height: 42px; background: rgba(56, 189, 248, 0.12); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 10px; font-weight: 700; font-size: 0.85rem; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 8px;">
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                    Download via Browser Fallback
                </button>
            </div>
        </div>
    `;
    document.body.appendChild(progressModal);

    // Update banner button if visible
    const banner = document.getElementById("apk-update-banner");
    if (banner) {
        const btn = banner.querySelector("button");
        if (btn) {
            btn.innerHTML = '<svg class="krono-spin" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16"/><path d="M16 21h5v-5"/></svg> Downloading...';
            btn.style.opacity = "0.85";
            btn.disabled = true;
        }
    }

    // Call native AndroidApp download bridge
    if (window.AndroidApp && typeof window.AndroidApp.downloadUpdate === "function") {
        window.AndroidApp.downloadUpdate(targetUrl);
    } else {
        // Fallback for external browser or PWA
        window.location.href = GITHUB_DIRECT_APK_URL;
    }
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

function compareSemVer(v1, v2) {
    const p1 = (v1 || "0").split(".").map(function (n) { return parseInt(n, 10) || 0; });
    const p2 = (v2 || "0").split(".").map(function (n) { return parseInt(n, 10) || 0; });
    const len = Math.max(p1.length, p2.length);
    for (let i = 0; i < len; i++) {
        const n1 = p1[i] || 0;
        const n2 = p2[i] || 0;
        if (n1 > n2) return 1;
        if (n1 < n2) return -1;
    }
    return 0;
}
window.compareSemVer = compareSemVer;

function isAndroidWebViewOrApk() {
    const ua = navigator.userAgent || "";
    return (
        window.AndroidApp !== undefined ||
        /UltraPortalApp/i.test(ua) ||
        /KronoApp/i.test(ua) ||
        (/Android/i.test(ua) && /; wv\)/i.test(ua))
    );
}

window.openKronoUpdateModal = function () {
    const data = window.__kronoLatestData || { latest_version: "3.3", version_code: 15 };
    let installedVer = "3.1";
    if (window.AndroidApp && typeof window.AndroidApp.getAppVersion === "function") {
        installedVer = window.AndroidApp.getAppVersion();
    }

    let modal = document.getElementById("krono-update-modal");
    if (modal) modal.remove();

    modal = document.createElement("div");
    modal.id = "krono-update-modal";
    modal.style.cssText = "position: fixed; inset: 0; z-index: 9999999; background: rgba(3, 7, 18, 0.88); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); display: flex; align-items: center; justify-content: center; padding: 20px;";
    modal.innerHTML = `
        <div style="background: #111827; border: 2px solid #38bdf8; border-radius: 22px; max-width: 440px; width: 100%; padding: 28px 24px; text-align: center; box-shadow: 0 25px 60px rgba(0,0,0,0.85); color: #f8fafc; font-family: system-ui, sans-serif;">
            <div style="display: flex; justify-content: center; margin-bottom: 12px;">
                <div style="width: 52px; height: 52px; border-radius: 14px; background: rgba(56, 189, 248, 0.15); border: 1.5px solid rgba(56, 189, 248, 0.4); display: flex; align-items: center; justify-content: center;">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 9V4s3.03.55 4 2c1.08 1.62 0 5 0 5"/></svg>
                </div>
            </div>
            <div style="display: inline-block; background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid #f59e0b; padding: 4px 14px; border-radius: 20px; font-size: 0.75rem; font-weight: 700; margin-bottom: 10px; letter-spacing: 0.05em;">
                OFFICIAL KRONO UPDATE READY
            </div>
            <h3 style="color: #f8fafc; font-size: 1.45rem; font-weight: 800; margin-bottom: 6px;">Krono v${data.latest_version}</h3>
            <div style="display: flex; align-items: center; justify-content: center; gap: 8px; font-size: 0.85rem; color: #94a3b8; margin-bottom: 16px;">
                <span>Installed: <b style="color: #cbd5e1;">v${installedVer}</b></span>
                <span style="color: #38bdf8;">➔</span>
                <span>Latest: <b style="color: #4ade80;">v${data.latest_version}</b></span>
            </div>
            <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(51, 65, 85, 0.8); border-radius: 12px; padding: 14px 16px; text-align: left; margin-bottom: 20px; font-size: 0.82rem; color: #cbd5e1; line-height: 1.5;">
                <b style="color: #38bdf8; display: block; margin-bottom: 6px;">What's New in v${data.latest_version}:</b>
                <ul style="margin-left: 18px; margin-bottom: 0;">
                    <li>Google Play Protect Clean: Zero elevated installer permissions</li>
                    <li>Studio UI Overhaul: Cosmic Slate Dark + Alabaster Mist Light Mode</li>
                    <li>Floating Mobile Island Dock navigation with frosted glass blur</li>
                    <li>Streamlined 1-Click native APK updater with real-time download progress</li>
                </ul>
            </div>
            <button type="button" onclick="triggerApkUpdate()" style="width: 100%; height: 50px; background: linear-gradient(135deg, #2563eb, #7c3aed); color: white; font-weight: 800; font-size: 1rem; border: none; border-radius: 12px; cursor: pointer; margin-bottom: 10px; box-shadow: 0 4px 20px rgba(37,99,235,0.45); display: flex; align-items: center; justify-content: center; gap: 8px;">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
                Update App Now (1-Click)
            </button>
            <button type="button" onclick="copyApkDownloadLink()" style="width: 100%; height: 42px; background: rgba(56, 189, 248, 0.12); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.35); border-radius: 10px; font-weight: 700; font-size: 0.88rem; cursor: pointer; margin-bottom: 12px; display: flex; align-items: center; justify-content: center; gap: 8px;">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round"><rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/></svg>
                Copy Direct Download Link
            </button>
            <button type="button" onclick="sessionStorage.setItem('apk_update_dismissed_v' + '${data.latest_version}', '1'); document.getElementById('krono-update-modal').remove();" style="background: transparent; border: none; color: #64748b; font-size: 0.84rem; cursor: pointer; text-decoration: underline;">
                Remind Me Later
            </button>
        </div>
    `;
    document.body.appendChild(modal);
};
// In-App APK Version & Auto-Update Checker
function checkApkUpdate() {
    if (!isAndroidWebViewOrApk()) {
        const stalePopup = document.getElementById("krono-update-modal") || document.getElementById("ultra-update-popup");
        if (stalePopup) stalePopup.remove();
        const staleBanner = document.getElementById("apk-update-banner");
        if (staleBanner) staleBanner.remove();
        return;
    }

    fetch("/api/app-version?t=" + Date.now(), { cache: "no-store" })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            window.__kronoLatestData = data;

            let installedCode = 0;
            let installedVer = "2.0";
            if (window.AndroidApp) {
                if (typeof window.AndroidApp.getAppVersionCode === "function") {
                    installedCode = parseInt(window.AndroidApp.getAppVersionCode(), 10) || 0;
                }
                if (typeof window.AndroidApp.getAppVersion === "function") {
                    installedVer = window.AndroidApp.getAppVersion();
                }
            } else {
                const match = navigator.userAgent.match(/(?:UltraPortalApp|KronoApp)\/([\d\.]+)/);
                if (match) {
                    installedVer = match[1];
                }
            }

            const latestCode = parseInt(data.version_code, 10) || 0;
            const isUpdateAvailable = (installedCode > 0 && latestCode > 0)
                ? (installedCode < latestCode)
                : (compareSemVer(installedVer, data.latest_version) < 0);

            const verBadge = document.getElementById("apk-version-badge");
            if (verBadge) {
                if (!isUpdateAvailable) {
                    verBadge.textContent = "v" + installedVer + " (Latest Up-to-Date)";
                    verBadge.style.color = "#4ade80";
                } else {
                    verBadge.textContent = "v" + installedVer + " (Update to v" + data.latest_version + " Available!)";
                    verBadge.style.color = "#f59e0b";
                }
            }

            if (isUpdateAvailable) {
                // 1. Highlight header & sidebar badges as clickable update triggers
                const appBadges = document.querySelectorAll(".app-badge");
                appBadges.forEach(function (badge) {
                    badge.innerHTML = "UPDATE v" + data.latest_version;
                    badge.style.background = "linear-gradient(135deg, #0284c7, #7c3aed)";
                    badge.style.color = "#ffffff";
                    badge.style.cursor = "pointer";
                    badge.style.border = "1px solid #38bdf8";
                    badge.style.boxShadow = "0 0 12px rgba(56, 189, 248, 0.5)";
                    badge.onclick = window.openKronoUpdateModal;
                });

                // 2. Trigger native Android notification via Java bridge
                if (window.AndroidApp && typeof window.AndroidApp.showNativeNotification === "function") {
                    window.AndroidApp.showNativeNotification(
                        "Krono v" + data.latest_version + " Ready!",
                        "Tap to install the latest Krono update with 1-click speed & mobile navigation."
                    );
                }

                // 3. Fallback: Browser/Web Push System Notification
                try {
                    if ("Notification" in window && Notification.permission === "granted") {
                        if (navigator.serviceWorker && navigator.serviceWorker.ready) {
                            navigator.serviceWorker.ready.then(function (reg) {
                                reg.showNotification("Krono Update (v" + data.latest_version + ") Ready!", {
                                    body: "Tap to install the latest update with 1-click speed & mobile navigation.",
                                    icon: "/static/icons/icon-192.png",
                                    badge: "/static/icons/icon-192.png",
                                    data: { url: "/update" }
                                });
                            });
                        }
                    }
                } catch (e) {}

                // 4. Render Fixed Top Floating Banner
                if (!document.getElementById("apk-update-banner")) {
                    const banner = document.createElement("div");
                    banner.id = "apk-update-banner";
                    banner.style.cssText = "position: fixed; top: 0; left: 0; right: 0; z-index: 999998; background: linear-gradient(135deg, #0b1120 0%, #1e1b4b 100%); border-bottom: 2px solid #38bdf8; padding: 10px 16px; display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; box-shadow: 0 4px 25px rgba(0,0,0,0.6);";
                    banner.innerHTML = `
                        <div style="display: flex; align-items: center; gap: 8px; font-size: 0.86rem; color: #f8fafc; font-weight: 600;">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#38bdf8" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z"/><path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z"/><path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0"/><path d="M12 9V4s3.03.55 4 2c1.08 1.62 0 5 0 5"/></svg>
                            <span><b>Krono Update (v${data.latest_version})</b> is ready!</span>
                        </div>
                        <div style="display: flex; gap: 8px; align-items: center;">
                            <button type="button" onclick="triggerApkUpdate()" style="background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%); color: #fff; border: none; cursor: pointer; padding: 7px 16px; border-radius: 9px; font-weight: 700; font-size: 0.82rem; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 10px rgba(37,99,235,0.45);">
                                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg> 1-Click Update
                            </button>
                            <button type="button" onclick="this.parentElement.parentElement.remove()" style="background: transparent; border: none; color: #94a3b8; cursor: pointer; padding: 0 6px; display: inline-flex; align-items: center;"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg></button>
                        </div>
                    `;
                    document.body.prepend(banner);
                }

                // 5. Render Centered Modal Popup (once per version session)
                const dismissedKey = "apk_update_dismissed_v" + data.latest_version;
                if (!sessionStorage.getItem(dismissedKey) && !document.getElementById("krono-update-modal")) {
                    window.openKronoUpdateModal();
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
