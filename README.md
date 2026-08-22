# 🚀 OnboardOps — Autonomous Employee Onboarding & Task Operations System

> **An enterprise-grade employee onboarding platform with automated task tracking, background cron check-ins, statistical anomaly detection, audit logging, and an idempotency ledger.**

---

## ⚡ Overview

**OnboardOps** streamlines complex HR and DevOps onboarding workflows for growing teams. Built with **FastAPI**, **SQLAlchemy**, and **APScheduler**, the system automates milestone progress monitoring, dispatches automated check-in prompts to new hires, detects onboarding friction or delays using statistical anomaly detection heuristics, and guarantees safe action execution with an idempotency ledger.

---

## ✨ Core Features

- 👤 **Employee Onboarding Lifecycle**: Manage employees, onboarding plans, sequential milestones, and check-in responses.
- ⏰ **Automated APScheduler Cron Engine**: Background scheduler scans in-progress milestones and automatically dispatches check-in notifications without human intervention.
- 🚨 **Statistical Anomaly Detection**: `detect_anomalies` engine monitors milestone completion times and flags onboarding bottlenecks or overdue check-ins.
- 📜 **Idempotency Ledger**: Prevents duplicate webhook or action processing across distributed network retry attempts.
- 🔒 **Comprehensive Audit Logging**: Immutable event ledger tracking all CRUD operations (`CHECKIN_DISPATCHED`, `MILESTONE_UPDATED`, etc.) with `actor`, `before`, and `after` states.
- 🎨 **Server-Rendered UI**: Interactive Jinja2 web interface (`index.html`, `employee.html`, `login.html`) styled for immediate usability.
- ⚡ **Vercel Serverless Deployment**: Configured for Vercel deployment via `api/index.py` and `vercel.json`.

---

## 🛠️ Architecture & Tech Stack

```
                     ┌────────────────────────┐
                     │   Jinja2 Web Interface │
                     └───────────┬────────────┘
                                 │
                                 ▼
 ┌─────────────────┐      ┌─────────────┐      ┌────────────────────────┐
 │  APScheduler    ├─────►│   FastAPI   ├─────►│  SQLite / PostgreSQL   │
 │ Cron Dispatcher │      │ Core Engine │      │  SQLAlchemy ORM        │
 └─────────────────┘      └──────┬──────┘      └────────────────────────┘
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
     ┌───────────────────────┐       ┌───────────────────────┐
     │ Anomaly Detection     │       │ Idempotency Ledger &  │
     │ Heuristic Engine      │       │ Audit Event Logging   │
     └───────────────────────┘       └───────────────────────┘
```

| Component | Technology |
|---|---|
| **Web Framework** | [FastAPI](https://fastapi.tiangolo.com/) (Python 3.12) |
| **Database & ORM** | SQLite / PostgreSQL + [SQLAlchemy](https://www.sqlalchemy.org/) |
| **Migrations** | [Alembic](https://alembic.sqlalchemy.org/) |
| **Background Cron** | [APScheduler](https://apscheduler.readthedocs.io/) |
| **Templating** | Jinja2 + HTML5/CSS3 |
| **Deployment** | Docker Compose / Vercel Serverless Functions |

---

## 📁 Project Structure

```
onboardops/
├── alembic/                  # Database migration scripts & environments
├── alembic.ini               # Alembic configuration settings
├── api/                      # Vercel serverless entrypoint & templates
│   ├── index.py              # Serverless app wrapper
│   └── templates/            # Web interface templates
├── docker-compose.yml        # Multi-container orchestration
├── requirements.txt          # Python dependencies
├── src/
│   ├── agent.py              # Agentic task execution logic
│   ├── agent2_monitor.py     # Background monitoring services
│   ├── anomaly.py            # Statistical anomaly & bottleneck detection
│   ├── audit.py              # Immutable audit logging engine
│   ├── database.py           # Database sessions & engine binding
│   ├── main.py               # FastAPI application & cron job setup
│   ├── mock_data.py          # Synthetic employee onboarding data seeders
│   ├── models.py             # SQLAlchemy schemas (Employee, Plan, Milestone, CheckIn)
│   └── schema.py             # Pydantic request/response validators
├── templates/                # Root web interface templates
│   ├── employee.html         # Individual employee workspace
│   ├── index.html            # Admin dashboard & task status overview
│   └── login.html            # User authentication view
├── test_webhook.ps1          # Webhook integration testing script
└── vercel.json               # Vercel deployment routes
```

---

## 🚀 Quick Start & Local Setup

### 1. Prerequisites
- Python 3.10+
- Git

### 2. Installation
```bash
# Clone the repository
git clone https://github.com/SakshiMalhotra18/onboardops.git
cd onboardops

# Create & activate a virtual environment
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Database Migrations
```bash
alembic upgrade head
```

### 4. Start the Application
```bash
uvicorn src.main:app --reload --port 8000
```
Navigate to [http://localhost:8000](http://localhost:8000) in your browser to view the OnboardOps dashboard.

---

## 🐳 Docker Deployment

To launch OnboardOps with Docker Compose:
```bash
docker-compose up --build
```

---

## 📄 License

Distributed under the MIT License.
