# Personal Finance Tracker

A backend-focused finance management application built with Django and Django REST Framework for tracking income, expenses, investments, budgets, and multi-currency financial reports.

---

## Features

### Authentication & User Management
- User signup, login, and logout
- Profile management
- Google OAuth authentication via `django-allauth`

### Transactions & Categories
- Category CRUD operations
- Income and expense tracking
- Refund handling through negative expense transactions
- Receipt uploads and storage

### Budgets & Reports
- Budget creation and tracking
- Currency-aware budget limits and spending, with alerts at 80% and 100%
- Monthly dashboard analytics with charts
- Preferred currency summaries
- Multi-currency reporting
- CSV export for transactions and reports

### API Support
Read-only REST API endpoints:
- `/reports/api/summary/`
- `/reports/api/monthly-breakdown/`

### Utilities
- Demo data seeding command
- CSV and PDF statement imports with duplicate detection and malformed-row counts
- Bulk CSV transaction upload
- PostgreSQL-first configuration
- Optional SQLite fallback for local development

---

# Tech Stack

- Django
- Django REST Framework
- PostgreSQL
- Django Templates
- `django-allauth`
- Gunicorn

---

# Project Setup

## 1. Clone the Repository

```bash
git clone <your-repo-url>
cd <your-project-folder>
```

---

## 2. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 4. Configure Environment Variables

Copy values from `.env.example` and configure the required variables.
The app reads environment variables directly; it does not load `.env` automatically. To use a local `.env` file in a shell, run `set -a; source .env; set +a` before Django commands.

### Required Variables

```env
POSTGRES_DB=finance_tracker
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

APP_BASE_URL=http://127.0.0.1:8000

GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
```

### Optional Local Development Fallback

```env
USE_SQLITE_FOR_LOCAL_DEV=1
```

> SQLite support exists only as a temporary fallback. PostgreSQL is the intended database for this project.

---

# Database Setup

## Option 1 — Docker (Recommended)

```bash
docker compose up -d
```

---

## Option 2 — Local PostgreSQL

Install PostgreSQL locally:

```bash
brew install postgresql@16
```

Start the local runtime:

```bash
./scripts/start_postgres.sh
```

Use the following environment values:

```bash
POSTGRES_HOST="$PWD/.postgres-run"
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_DB=finance_tracker
```

---

# Run Migrations

```bash
python manage.py migrate
```

---

# Start the Development Server

```bash
python manage.py runserver
```

Application URL:

```text
http://127.0.0.1:8000
```

---

# Google OAuth Setup

Google OAuth can be configured through Google Cloud Console.

## Steps

1. Open Google Cloud Console
2. Create or select a project
3. Configure the OAuth consent screen
4. Create OAuth credentials for a Web Application
5. Add the following redirect URIs:

```text
http://127.0.0.1:8000/oauth/google/login/callback/
http://localhost:8000/oauth/google/login/callback/
```

6. Add credentials to your environment:

```bash
export APP_BASE_URL="http://127.0.0.1:8000"
export GOOGLE_OAUTH_CLIENT_ID="your-client-id"
export GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"
```

7. Restart the Django server

Once configured, Google login and signup will be enabled automatically.

---

# Demo Data

Load demo data:

```bash
python manage.py seed_demo_data
```

## Demo Credentials

```text
username: demo
password: demo12345
```

The demo workspace is deterministic and includes six months of income, expenses and investments across five currencies; refunds; a deliberately unusual purchase for the anomaly view; monthly budgets with 80% and 100% alerts; sample notifications; and CSV, PDF and bulk-upload history with duplicate and invalid rows. The dashboard also offers **Explore with sample data** for an empty account. It adds the walkthrough to that signed-in account, so the dashboard, reports, filters, budgets, imports and authenticated APIs all have data to explore. It will not mix sample records into an account that already has financial records.

Receipt links are served through an authenticated view that checks ownership before returning the uploaded file.
---

# Running Tests

```bash
python manage.py test
```

GitHub Actions runs the Django checks, migration check, and test suite against PostgreSQL on each push and pull request.

---

# Statement Import Format

CSV statements accept `date,amount,description,currency,transaction_type` headers. Dates use `YYYY-MM-DD`. The `transaction_type` column is optional; when omitted, positive amounts are interpreted as expenses and negative amounts as income. Include it when your bank uses a different sign convention.

```csv
date,amount,description,currency,transaction_type
2026-04-10,1200.00,Salary,INR,income
2026-04-11,250.00,Groceries,INR,expense
```

The PDF importer supports text-based statements whose transaction lines contain comma-separated date, amount, description, and currency fields. Scanned and bank-specific PDF layouts are not supported yet. Uploaded statement and bulk CSV files are limited to 5 MB.

---

# Deployment

The [live demo](https://expense-tracker-250p.onrender.com/) runs on Render. Configure a PostgreSQL database and set `DATABASE_URL`, `DJANGO_SECRET_KEY`, `DEBUG=0`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `APP_BASE_URL` on the web service. The build command should install requirements and run `./build.sh`; the start command is `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT`.

`/health/` checks database connectivity. The scheduled GitHub Action calls this endpoint and reports failures.

Render's free PostgreSQL databases expire after 30 days. A durable deployment needs a database plan that does not expire; the free database should not be used for important user data.

---
