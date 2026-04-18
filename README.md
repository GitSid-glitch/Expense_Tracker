# Personal Finance Tracker

A backend-focused Django application for tracking income, expenses, investments, budgets, receipts, and multi-currency reporting.

## Stack

- Django
- Django REST Framework
- Django Templates
- PostgreSQL
- django-allauth for Google OAuth

## Features Implemented

- user signup, login, logout, and profile management
- Google OAuth foundation via `django-allauth`
- category and transaction CRUD
- refund handling through negative expense transactions
- receipt uploads
- budget creation, tracking, and alert notifications
- dashboard with charted monthly trends
- preferred currency summaries and reports
- CSV export for transactions and reports
- read-only DRF endpoints for finance summary and monthly breakdown
- demo data seeding command

## Local Setup

1. Create and activate the virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Copy environment values from `.env.example`.

4. Start PostgreSQL locally.
   You can either use Docker or the project-local Homebrew/Postgres flow:

```bash
docker compose up -d
```

or

```bash
brew install postgresql@16
./scripts/start_postgres.sh
```

5. Run migrations:

```bash
POSTGRES_HOST="$PWD/.postgres-run" POSTGRES_PORT=5432 POSTGRES_USER=postgres POSTGRES_DB=finance_tracker python manage.py migrate
```

6. Run the server:

```bash
POSTGRES_HOST="$PWD/.postgres-run" POSTGRES_PORT=5432 POSTGRES_USER=postgres POSTGRES_DB=finance_tracker python manage.py runserver
```

## Environment Variables

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `GOOGLE_OAUTH_CLIENT_ID`
- `GOOGLE_OAUTH_CLIENT_SECRET`
- `APP_BASE_URL`

`USE_SQLITE_FOR_LOCAL_DEV=1` exists only as a temporary fallback for environments without a running PostgreSQL server. The intended project database is PostgreSQL.

For the project-local Postgres runtime started by `./scripts/start_postgres.sh`, use:

- `POSTGRES_HOST=$PWD/.postgres-run`
- `POSTGRES_PORT=5432`
- `POSTGRES_USER=postgres`
- `POSTGRES_DB=finance_tracker`

## Google OAuth Setup

Google OAuth is free to configure using Google Cloud's OAuth consent screen and web application credentials.

1. Open Google Cloud Console.
2. Create or select a project.
3. Configure the OAuth consent screen.
4. Create an OAuth Client ID for a Web application.
5. Add these Authorized redirect URIs:

```text
http://127.0.0.1:8000/oauth/google/login/callback/
http://localhost:8000/oauth/google/login/callback/
```

6. Put the generated values into your environment:

```bash
export APP_BASE_URL="http://127.0.0.1:8000"
export GOOGLE_OAUTH_CLIENT_ID="your-client-id"
export GOOGLE_OAUTH_CLIENT_SECRET="your-client-secret"
```

7. Restart the Django server.

Once those values are present, the login and signup pages will show active Google buttons and the callback flow will work.

## Demo Data

To load demo data:

```bash
python manage.py seed_demo_data
```

Demo login:

- username: `demo`
- password: `demo12345`

## API Endpoints

- `/reports/api/summary/`
- `/reports/api/monthly-breakdown/`

## Testing

```bash
python manage.py test
```

## Deployment

The fastest deployment path for this project is a managed PostgreSQL database plus a Django web service running `gunicorn`.

### Required production variables

- `DJANGO_SECRET_KEY`
- `DEBUG=0`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- either `DATABASE_URL` or the `POSTGRES_*` variables
- `APP_BASE_URL`
- optional Google OAuth and email variables

### Production commands

```bash
pip install -r requirements.txt
./build.sh
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

### Fast Render deployment

1. Create a PostgreSQL database on Render.
2. Create a Web Service from this repo.
3. Use build command:

```bash
pip install -r requirements.txt && ./build.sh
```

4. Use start command:

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
```

5. Set environment variables:
   - `DJANGO_SECRET_KEY`
   - `DEBUG=0`
   - `DATABASE_URL`
   - `ALLOWED_HOSTS=<your-domain>`
   - `CSRF_TRUSTED_ORIGINS=https://<your-domain>`
   - `APP_BASE_URL=https://<your-domain>`

### AWS EC2 deployment outline

1. Provision EC2 and PostgreSQL or RDS.
2. Install Python, `nginx`, and requirements.
3. Export production environment variables.
4. Run `./build.sh`.
5. Start `gunicorn`.
6. Put `nginx` in front as the reverse proxy.

If you are short on time, Render is usually the fastest path to a working deployed demo.
