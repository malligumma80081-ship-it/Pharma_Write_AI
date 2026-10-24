# PharmaWrite AI

Prototype for human-reviewed scientific evidence summaries.

The existing project, summary, and health endpoints are retained. The
other route and service modules are scaffolds for the next implementation
steps; they do not yet provide authentication, PDF processing, retrieval,
citation verification, or document review workflows.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
docker compose up -d db
```

Set `DATABASE_URL` in `.env` to the following local development value
(already present in `.env.example`):

```text
postgresql+psycopg://pharmawrite:pharmawrite_dev@localhost:5432/pharmawrite
```

If PostgreSQL is unavailable, SQLite can be used for local development by
setting `DATABASE_URL=sqlite:///./pharmawrite.db` in `.env`. The SQLite
database file is created in the project root when migrations run.

Start the API in one terminal. The dashboard command below serves the
overview, document upload, draft generation, draft review, and export screens
in one Streamlit app; do not launch `app/ui/review_page.py` separately.

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

In another terminal, run the complete UI:

```powershell
python -m streamlit run app/ui/dashboard.py
```

The API docs are available at <http://127.0.0.1:8000/docs>.
Ollama must be running separately with the configured model installed.

Use the UI's **Create account** tab to register, then sign in. New accounts
receive the `writer` role and can upload documents and generate drafts.
`reviewer` and `admin` roles can review/export drafts; admins can use all UI
pages. Elevated roles are assigned by an administrator, not selected during
registration. Run `python scripts/create_admin.py` to create the initial
administrator. API clients must send the login token as a bearer token.

## Docker

```powershell
docker compose up --build
```

The Compose setup starts PostgreSQL and the API, and applies migrations
before starting the API. Set `POSTGRES_PASSWORD` before deployment; the
default is intended only for local development.

## Tests

```powershell
python -m pytest
python -c "import secrets; print(secrets.token_urlsafe(48))"
```
