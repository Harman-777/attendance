# ⚡ Krono — Student Attendance Intelligence & High-Performance Workspace (v3.3)

[![Version](https://img.shields.io/badge/Version-v3.3-38bdf8?style=for-the-badge&logo=android)](https://attendance-liard-three.vercel.app/update)
[![Live WebApp](https://img.shields.io/badge/Live-Vercel%20Production-black?style=for-the-badge&logo=vercel)](https://attendance-liard-three.vercel.app)
[![Download APK](https://img.shields.io/badge/Download-Krono.apk%20(~58KB)-22c55e?style=for-the-badge&logo=android)](https://attendance-liard-three.vercel.app/download/Krono.apk)
[![Play Protect](https://img.shields.io/badge/Google%20Play%20Protect-Verified%20Clean-4ade80?style=for-the-badge&logo=googleplay)](https://attendance-liard-three.vercel.app/update)
[![Python](https://img.shields.io/badge/Python-3.12-blue?style=for-the-badge&logo=python)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)](#-license)

**Krono** is a studio-grade student workspace and attendance intelligence suite designed for college students. Engineered with real-time timetable synchronization, interactive attendance simulation, a floating mobile island dock, dual OLED/Alabaster themes, and an in-app native APK updater.

🌐 **Live Web Application:** [attendance-liard-three.vercel.app](https://attendance-liard-three.vercel.app)  
📲 **Direct Android APK Download:** [Krono.apk (~58 KB)](https://attendance-liard-three.vercel.app/download/Krono.apk)  
🔄 **Official Update Center:** [attendance-liard-three.vercel.app/update](https://attendance-liard-three.vercel.app/update)

---

## 🌟 What's New in v3.3

- 🛡️ **Google Play Protect Clean Architecture:**
  - Removed privileged `REQUEST_INSTALL_PACKAGES` and dropper-heuristic queries.
  - Passes Google Play Protect on-device & cloud scans with **100% clean device trust**.
  - Update downloads route through clean Android system intents.

- 🎨 **Studio-Grade Balanced Dual Themes:**
  - **Cosmic Slate Dark Mode (`#0B0F17`):** Elevated card surfaces (`#151D2A`), subtle border contrast (`#243044`), and glowing cyan/amber accents.
  - **Alabaster Mist Light Mode (`#EBEEF3`):** Pure white content cards (`#FFFFFF`), crisp slate borders (`#D8DFE9`), and high-readability typography replacing washed-out backgrounds.
  - Persistent theme synchronization across system status bars and navigation bars.

- 🏝️ **Floating Mobile Island Dock:**
  - Frosted glass floating navigation dock (`backdrop-filter: blur(28px)`) with rounded island geometry (`border-radius: 28px`).
  - Tactile micro-interactions with smooth tab switching and active indicator pills.
  - Safe-area bottom padding ensuring seamless usability on all mobile aspect ratios.

- 🚀 **1-Click Seamless In-App APK Updater:**
  - Live byte-level progress bar (`0%` $\rightarrow$ `100%`) streamed directly from native background download threads.
  - Version synchronization across client JS, Flask backend, and Android native layer (`versionCode 15`).
  - Direct Android system notification click handling with single-top activity resumption.

- 🎯 **Target Grade & Sessional Exam Predictor:**
  - Interactive calculator computing exact external scores needed from internal marks (40/60 scale).
  - Target grade thresholds for $O\ (90\%\text{+})$, $A+\ (80\%\text{+})$, $A\ (70\%\text{+})$, and $B+\ (60\%\text{+})$.

---

## ⚡ Core Feature Ecosystem

### 📊 Attendance Simulator & Intelligence
- **Real-Time Threshold Calculations:** Instant percentage tracking with 75% mandatory threshold margin computation.
- **Interactive "+1 Attend" / "+1 Skip" Simulator:** Project future standing before stepping into class.
- **Configurable Target Slider:** Adjust safety margins from 60% to 90%, including a dedicated **Medical Condonation Mode (65%)**.
- **Monospace Tabular Precision:** High-contrast numeric typography for razor-sharp figures.

### 🏖️ Vacation & Mass-Bunk Planner
- Multi-day absence forecasting across all subjects simultaneously.
- Simulates exact margin deficits before holidays, college fests, or personal leaves.

### 📅 History & Calendar Ledger
- Day-by-day and subject-by-subject attendance audit trail.
- Color-coded daily statuses (All Present, Absent, Mixed, Condoned).

### ⚖️ 1-Click Absent Dispute Generator
- Automatically drafts formal, formatted attendance correction dispute letters addressed to the Faculty Incharge.
- Pre-fills student credentials, dates, subjects, and reason templates ready for submission.

### 🔔 Real-Time Absent & Bunk Alerts
- Native browser push notifications.
- Background Gmail SMTP notification bridge for low-attendance warnings.

### 🛡️ Offline Snapshot & Session Hardening
- Client-side and local caching ensures student dashboards remain accessible even during official college portal downtime.
- Hardened session cookies (`HttpOnly`, `SameSite=Lax`, deterministic serverless secret keys).

---

## 🏗️ Technology Stack

| Tier | Technologies |
| :--- | :--- |
| **Backend** | Python 3.12, Flask 3.x, `uv`, Cryptography, BeautifulSoup4 |
| **Frontend** | Vanilla JavaScript (ES6+), Modern CSS3 Custom Properties, Lucide Icons, Glassmorphism |
| **Mobile Shell** | Android SDK 34 (`compileSdk 34`, `minSdk 24`), Pure Native Java, Zero external runtime bloat (~58 KB APK) |
| **Deployment** | Vercel Serverless Edge Functions (`maxDuration: 60`), Production CDN Aliasing |
| **CI / CD** | GitHub Actions automated signed release APK build pipeline (`.github/workflows/build_apk.yml`) |

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.10+** (Python 3.12 recommended)
- **Git**
- **Node.js 18+** (Optional, for Vercel CLI deployment)

### 1. Clone the Repository
```bash
git clone https://github.com/Harman-777/attendance.git
cd attendance
```

### 2. Install Dependencies
```bash
# Using standard pip
pip install -r requirements.txt

# Or with ultra-fast uv
uv pip install -r requirements.txt
```

### 3. Run Locally
```bash
python app.py
```
Open [http://localhost:5000](http://localhost:5000) in your web browser.

---

## 📱 Android APK Build & Setup

The Android companion application is located in `android_app/`:
- **Compile SDK:** 34
- **Target SDK:** 34
- **Min SDK:** 24 (Android 7.0+)
- **APK Size:** ~58 KB

To build the signed release APK locally:
```bash
cd android_app
./gradlew assembleRelease
```
Compiled APKs will be located at:
`android_app/app/build/outputs/apk/release/app-release.apk`

*Note: Pushing code changes to `main` touching `android_app/**` or `app.py` triggers `.github/workflows/build_apk.yml` to automatically compile and deploy the signed APK.*

---

## 🌐 Production Deployment

The project is pre-configured for zero-configuration serverless deployment on **Vercel**:

```bash
# Deploy to preview
vercel

# Deploy to production
vercel --prod
```

---

## 📄 License

This project is licensed under the **MIT License**.
