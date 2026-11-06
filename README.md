# ExamLMS - Enterprise Learning & Assessment Management System

A production-grade, enterprise-ready Learning Management System (LMS) with full course authoring, hierarchical modules & chapters, secure proctored examinations, question review workflows, and instant certification.

---

## Architecture Overview

```text
ExamLMS Monorepo
├── Lms_frontend_Gz/      # React 18 + TypeScript + Vite + Tailwind CSS Frontend
└── Lms_backend_Gz/       # FastAPI Microservices Backend Architecture
    ├── api-gateway/              # Port 8000 (Central Routing & JWT Proxy)
    ├── user-management/          # Port 8001 (Auth, RBAC, Sessions & MFA)
    ├── catalog-service/          # Port 8002 (Courses, Modules, Chapters)
    ├── media-service/            # Port 8003 (Video Transcoding, PDF Delivery)
    ├── subscription-service/     # Port 8004 (Institution Access & Course Requests)
    ├── learning-service/         # Port 8005 (Enrollments, Topic Progress, Unlock State)
    ├── assessment-service/       # Port 8007 (Tests, AI Question Review, Grading)
    └── notification-service/     # Port 8016 (Realtime Alerts & Webhooks)
```

---

## Microservices Port Allocation

| Service | Port | Description |
| :--- | :--- | :--- |
| **Frontend Dev Server** | `3000` | Vite React SPA with Tailwind UI |
| **API Gateway** | `8000` | Unified Reverse Proxy & Auth Gateway |
| **User Management** | `8001` | Authentication, RBAC, Sessions & 2FA |
| **Catalog Service** | `8002` | Courses, Modules, Chapters & Versions |
| **Media Service** | `8003` | Streaming & In-App View-Only PDF Serving |
| **Subscription Service** | `8004` | Institution Access Requests & Catalog Subscriptions |
| **Learning Service** | `8005` | Enrollment, Progress Tracking & Step Unlocking |
| **Assessment Service** | `8007` | Chapter, Module & Final Proctored Exams |
| **Notification Service** | `8016` | User & Institution System Notifications |

---

## Getting Started

### 1. Prerequisites
- **Node.js**: >= 18.0.0
- **Python**: >= 3.11
- **SQLite / PostgreSQL**: For database storage

### 2. Frontend Setup
```bash
cd Lms_frontend_Gz
npm install
npm run dev
# Running on http://127.0.0.1:3000
```

### 3. Backend Setup
```bash
cd Lms_backend_Gz
python -m venv .venv
# On Windows: .venv\Scripts\activate
# On Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

---

## Branches in this Repository
- **`main`**: Complete monorepo containing both frontend and backend.
- **`frontend`**: Frontend standalone repository history (`charan-teja`).
- **`backend`**: Backend standalone microservices history (`CharanTeja`).
