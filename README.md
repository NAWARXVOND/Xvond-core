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
- Use Redis-backed runtime services before running multiple API workers.
- Keep `.env`, database backups, logs, and provider credentials out of Git.
- Keep an encrypted off-server database backup in storage approved for the deployment's data-residency requirements.

## Deployment flow

`VS Code -> GitHub -> server`. Commit and push reviewed changes, pull the tagged release on the server, apply migrations, and restart the service.

## First customer acceptance

After deployment and migrations, seed the current provider/model catalog:

```bash
python -m xvond_seed_providers
```

Run the non-billable production gate for the customer:

```bash
python -m scripts.production_acceptance --company-id COMPANY_ID
```

Then perform one explicit billable provider health check using the employee's resolved production route. This call does not create a customer conversation and does not run customer tools:

```bash
python -m scripts.production_acceptance \
  --company-id COMPANY_ID \
  --agent-id AGENT_ID \
  --live-ai
```

Do not activate customer traffic unless the report returns
`"overall_ok": true`.

## Encrypted off-server PostgreSQL backups

Local PostgreSQL dumps are created first in the `xvond_backups` volume. The optional `offsite-backup` profile then sends that backup set to a Restic repository. Restic encrypts repository contents client-side using `RESTIC_PASSWORD`.

Configure `RESTIC_REPOSITORY` and `RESTIC_PASSWORD` in `.env`. For S3-compatible repositories, also configure the required AWS-style credentials and region. Choose a repository location that satisfies the deployment's data-residency requirements.

Start production with encrypted offsite backup enabled:

```bash
docker compose -f docker-compose.production.yml \
  --profile offsite-backup up -d
```

Verify that the remote repository can actually be restored and that the restored PostgreSQL dump checksum is valid:

```bash
docker compose -f docker-compose.production.yml \
  --profile offsite-verify run --rm offsite-restore-verify
```

A successful upload is not considered a verified backup until the restore verification command succeeds.
