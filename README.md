# ⚡ Ultra Portal — Student Attendance Intelligence & Analytics

An advanced, responsive, and mobile-ready college student attendance dashboard with attendance simulation, mass-bunk planning, interactive history calendar, dispute generator, and absent alerts.

![Python](https://img.shields.io/badge/Python-3.12-38bdf8?style=flat-square&logo=python)
![Flask](https://img.shields.io/badge/Flask-3.x-22c55e?style=flat-square&logo=flask)
![Vercel](https://img.shields.io/badge/Deployed-Vercel-black?style=flat-square&logo=vercel)
![PWA](https://img.shields.io/badge/PWA-Ready-f59e0b?style=flat-square)

---

## 🌟 Key Features

- **📊 Attendance & Simulator:**
  - Real-time attendance percentage computation.
  - Interactive "+1 Attend" / "+1 Skip" simulator with instant standing recalculations.
  - Dynamic 75% danger zone warnings and safety margin tracking.
  - Adjustable attendance target slider (60% to 90%) and Medical Condonation mode (65%).

- **🏖️ Vacation & Mass-Bunk Planner:**
  - Forecast multi-day vacation impacts across all subjects at once.

- **📅 Interactive History Calendar:**
  - Complete day-by-day and subject-by-subject attendance records.
  - Color-coded daily statuses (All Present, Absent, Mixed).

- **⚖️ 1-Click Absent Dispute Generator:**
  - Automatically formats official attendance correction letters addressed to the Faculty Incharge.

- **🔔 Smart Absent Alerts:**
  - Native browser push notifications.
  - Optional Gmail SMTP email alerts.

- **📱 Dynamic Web & Mobile Layout:**
  - Adaptive desktop sidebar and modern mobile bottom dock.
  - Responsive tables with horizontal touch-scrolling.
  - Touch-optimized controls preventing mobile browser auto-zoom.

- **🛡️ Offline Snapshot Mode:**
  - Caches student data locally so profiles remain accessible even when the official college portal is down.

---

## 🚀 Getting Started

### 1. Prerequisites
- Python 3.10+
- Git

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/Harman-777/attendance.git
cd attendance

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Locally
```bash
python app.py
```
Open [http://localhost:5000](http://localhost:5000) in your browser.

---

## 🌐 Deployment

Configured for zero-config deployment on **Vercel** with serverless Python runtime.

```bash
vercel deploy --prod
```

---

## 📄 License
MIT License
