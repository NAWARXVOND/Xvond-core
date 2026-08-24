# Xvond Core

Xvond Core is a modular AI business platform built with FastAPI, SQLAlchemy, PostgreSQL, and Alembic.

## Requirements

- Python 3.14
- PostgreSQL 17

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Copy `.env.example` to `.env` and replace every placeholder.
4. Start PostgreSQL:

   ```powershell
   docker compose up -d postgres
   ```

5. Apply database migrations:

   ```powershell
   alembic upgrade head
   ```

6. Create the first super administrator:

   ```powershell
   python scripts/create_superadmin.py
   ```

7. Start the API:

   ```powershell
   uvicorn backend.app.main:app --reload
   ```

Open `http://127.0.0.1:8000/health`, `/admin-ui`, or `/customer-ui`.

## Tests

```powershell
pytest -q
```

GitHub CI also builds a completely fresh PostgreSQL database with Alembic before running tests.

## Production checklist

- Set `APP_ENV=production`.
- Use a unique JWT secret of at least 32 random characters.
- Configure a real AI provider; mock is development-only.
- Configure SMTP before enabling password reset.
- Put the API behind HTTPS and a trusted reverse proxy.
- Run `alembic upgrade head` before starting the new release.
- Use a shared Redis-backed rate limiter before running multiple API workers.
- Keep `.env`, database backups, logs, and provider credentials out of Git.

## Deployment flow

`VS Code -> GitHub -> server`. Commit and push reviewed changes, pull the tagged release on the server, apply migrations, and restart the service.
