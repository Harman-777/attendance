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
        alert("To install: Tap your browser's menu (⋮ or Share) and select 'Install app' or 'Add to Home screen'.");
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
    const shareUrl = window.location.origin;
    const msg = "⚡ Check your live college attendance in 0.4 seconds, calculate safe bunks, and get instant lock-screen absent alerts! Try Ultra Portal: " + shareUrl;
    window.open("https://api.whatsapp.com/send?text=" + encodeURIComponent(msg), "_blank");
}

function shareNativeSheet() {
    const shareUrl = window.location.origin;
    const shareData = {
        title: "⚡ Ultra Portal — Student Workspace",
        text: "Check your live college attendance in 0.4 seconds, calculate safe bunks, and get instant lock-screen absent alerts!",
        url: shareUrl
    };

    if (navigator.share) {
        navigator.share(shareData).catch(function () {
            // Ignored if user dismissed sheet
        });
    } else {
        copyPortalShareLink();
    }
}

function copyPortalShareLink() {
    const shareUrl = window.location.origin;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(shareUrl).then(function () {
            showCopyFeedback();
        }).catch(function () {
            fallbackCopy(shareUrl);
        });
    } else {
        fallbackCopy(shareUrl);
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
        prompt("Copy Ultra Portal Link:", text);
    }
    document.body.removeChild(t);
}

function showCopyFeedback() {
    const btn = document.getElementById("btn-copy-share-link");
    if (btn) {
        const originalHtml = btn.innerHTML;
        btn.innerHTML = "<span>✔</span> Copied Link!";
        btn.style.borderColor = "#4ade80";
        btn.style.color = "#4ade80";
        setTimeout(function () {
            btn.innerHTML = originalHtml;
            btn.style.borderColor = "";
            btn.style.color = "";
        }, 2000);
    }
}

// Initial setup on load
document.addEventListener("DOMContentLoaded", function () {
    updatePwaInstallButtonState();
});
