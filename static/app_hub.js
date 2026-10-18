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
        btn.textContent = "✅ App Already Installed & Running";
        btn.className = "btn-hub-action btn-hub-installed";
        btn.onclick = null;
        if (iosBox) iosBox.style.display = "none";
    } else if (deferredInstallPrompt) {
        btn.textContent = "⚡ 1-Click Install WebAPK";
        btn.className = "btn-hub-action btn-hub-primary";
        btn.onclick = triggerPwaInstall;
        if (iosBox) iosBox.style.display = "none";
    } else if (isIosDevice()) {
        btn.textContent = "📲 Add to Home Screen (iOS)";
        btn.className = "btn-hub-action btn-hub-primary";
        btn.onclick = function () {
            if (iosBox) iosBox.style.display = "block";
        };
        if (iosBox) iosBox.style.display = "block";
    } else {
        btn.textContent = "⚡ Install WebAPK Shortcut";
        btn.className = "btn-hub-action btn-hub-primary";
        btn.onclick = triggerPwaInstall;
        if (iosBox) iosBox.style.display = "none";
    }
}

function triggerApkUpdate() {
    const apkUrl = window.location.origin + "/download/UltraPortal.apk";

    // 1. If running in native APK with Java bridge (v2.1+)
    if (window.AndroidApp && typeof window.AndroidApp.downloadUpdate === "function") {
        window.AndroidApp.downloadUpdate(apkUrl);
        return;
    }

    // 2. Android Intent delegation to system browser / download manager
    if (/Android/i.test(navigator.userAgent)) {
        try {
            const hostPath = window.location.host + "/download/UltraPortal.apk";
            const intentUrl = "intent://" + hostPath + "#Intent;scheme=https;action=android.intent.action.VIEW;end;";
            const a = document.createElement("a");
            a.href = intentUrl;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        } catch (e) {}

        // Immediate direct navigation fallback
        setTimeout(function () {
            window.location.href = apkUrl;
        }, 400);
        return;
    }

    // 3. Desktop / General browser direct download
    window.location.href = apkUrl;
}

function triggerPwaInstall() {
    if (deferredInstallPrompt) {
        deferredInstallPrompt.prompt();
        deferredInstallPrompt.userChoice.then(function (choice) {
            if (choice.outcome === "accepted") {
                console.log("Ultra Portal WebAPK installed!");
                updatePwaInstallButtonState();
            }
            deferredInstallPrompt = null;
        });
    } else if (isIosDevice()) {
        const iosBox = document.getElementById("ios-install-guide");
        if (iosBox) iosBox.style.display = "block";
    } else {
        const confirmDownload = confirm("WebAPK prompt is preparing. Would you like to download the direct signed Android APK (UltraPortal.apk) right now?");
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
    const downloadUrl = origin + "/download/UltraPortal.apk";
    const msg = "⚡ Check your live college attendance in 0.4 seconds, calculate safe bunks, and get instant absent alerts!\n\n📲 Direct Android App Download: " + downloadUrl + "\n🌐 Web Workspace: " + origin;

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
    const downloadUrl = origin + "/download/UltraPortal.apk";
    const shareText = "⚡ Ultra Portal — Check your live college attendance in 0.4 seconds, calculate safe bunks & get absent alerts!\n\n📲 Direct APK Download:\n" + downloadUrl + "\n\n🌐 Web Portal:\n" + origin;

    // 1. Android APK native share drawer bridge
    if (window.AndroidApp && typeof window.AndroidApp.shareApp === "function") {
        window.AndroidApp.shareApp(shareText, downloadUrl);
        return;
    }

    // 2. Standard Web Share API (Chrome / Safari / Edge mobile)
    if (navigator.share) {
        navigator.share({
            title: "⚡ Ultra Portal — Student Workspace",
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
    const downloadUrl = origin + "/download/UltraPortal.apk";
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
        prompt("Copy Ultra Portal APK Download Link:", text);
    }
    document.body.removeChild(t);
}

function showCopyFeedback() {
    const btn = document.getElementById("btn-copy-share-link");
    if (btn) {
        const originalHtml = btn.innerHTML;
        btn.innerHTML = "<span>✔</span> Copied APK Link!";
        btn.style.borderColor = "#4ade80";
        btn.style.color = "#4ade80";
        setTimeout(function () {
            btn.innerHTML = originalHtml;
            btn.style.borderColor = "";
            btn.style.color = "";
        }, 2000);
    }
}

// In-App APK Version & Auto-Update Checker
function checkApkUpdate() {
    const isApk = (window.AndroidApp !== undefined) || (navigator.userAgent && navigator.userAgent.includes("UltraPortalApp"));
    if (!isApk) return;

    fetch("/api/app-version")
        .then(function (r) { return r.json(); })
        .then(function (data) {
            let installedVer = "2.0";
            if (window.AndroidApp && typeof window.AndroidApp.getAppVersion === "function") {
                installedVer = window.AndroidApp.getAppVersion();
            } else {
                const match = navigator.userAgent.match(/UltraPortalApp\/([\d\.]+)/);
                if (match) installedVer = match[1];
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

            // If installed version is older, display high-visibility 1-click update banner
            if (parseFloat(installedVer) < parseFloat(data.latest_version)) {
                if (document.getElementById("apk-update-banner")) return;
                const banner = document.createElement("div");
                banner.id = "apk-update-banner";
                banner.style.cssText = "position: sticky; top: 0; z-index: 99999; background: linear-gradient(135deg, #1e1b4b 0%, #1e3a8a 100%); border-bottom: 2px solid #38bdf8; padding: 10px 16px; display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; box-shadow: 0 4px 20px rgba(0,0,0,0.5);";
                banner.innerHTML = `
                    <div style="display: flex; align-items: center; gap: 8px; font-size: 0.88rem; color: #f8fafc;">
                        <span style="font-size: 1.15rem;">🚀</span>
                        <span><b>New Ultra Portal Update (v${data.latest_version})</b> is ready for your app!</span>
                    </div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                        <button type="button" onclick="triggerApkUpdate()" style="background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%); color: #fff; border: none; cursor: pointer; padding: 7px 16px; border-radius: 8px; font-weight: 700; font-size: 0.84rem; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 8px rgba(37,99,235,0.4);">
                            ⚡ 1-Click Update Now
                        </button>
                        <button type="button" onclick="this.parentElement.parentElement.remove()" style="background: transparent; border: none; color: #94a3b8; font-size: 1.1rem; cursor: pointer; padding: 0 6px;">✕</button>
                    </div>
                `;
                document.body.prepend(banner);
            }
        })
        .catch(function () {});
}

// Initial setup on load
document.addEventListener("DOMContentLoaded", function () {
    updatePwaInstallButtonState();
    checkApkUpdate();
});
