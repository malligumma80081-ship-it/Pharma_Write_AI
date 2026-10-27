# PharmaWrite AI

Prototype for human-reviewed, evidence-grounded scientific summaries.
The application includes authentication, PDF processing, persistent
knowledge-base indexing, document retrieval, citation checks, and Team Lead
review workflows.

## Local setup

Run the following commands from the project root (the directory containing
this README). If your terminal is at the parent directory, enter the project
first:

```powershell
Set-Location .\pharmawrite-ai
```

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

The `DATABASE_URL` in `.env.example` is for Docker Compose, where `postgres`
resolves to the PostgreSQL service. The sample value below is for Docker only;
it will not resolve when Uvicorn runs directly on Windows:

```text
postgresql+psycopg://pharmawrite:pharmawrite_dev@localhost:5432/pharmawrite
```

```powershell
$env:DATABASE_URL = "sqlite:///./pharmawrite.db"
```

The SQLite database file is created in the project root when migrations run.

Local Ollama generation is allowed up to 15 minutes per model request by
`OLLAMA_TIMEOUT_SECONDS`. The UI allows up to about 32 minutes for a complete
workflow, which can make two sequential model requests. If timeouts continue,
check Ollama load and available system resources; increasing the timeout
cannot make a stalled or overloaded model complete.

Database schema changes are applied by Alembic; importing the API does not
connect to the database or create tables automatically.

Start the API in one terminal. The dashboard command below serves the
overview, document upload, draft generation, draft review, and export screens
in one Streamlit app; do not launch `app/ui/review_page.py` separately.

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Open another terminal at the project root and activate the virtual environment
there too, then run the complete UI:

```powershell
.\.venv\Scripts\Activate.ps1
python -m streamlit run app/ui/dashboard.py
```

The API docs are available at <http://127.0.0.1:8000/docs>.
Ollama must be running separately with the configured model installed.

Use the UI's **Create account** tab to register, then sign in. New accounts
receive the `writer` role. Create a project from **Projects** before uploading
documents and generating drafts; the sidebar lists only projects the signed-in
writer owns. Admins and Team Leads can view projects across accounts.
Writers can view a completed summary and submit it to the Team Lead queue.
PDF and Word downloads are enabled only after approval. `reviewer` accounts
have a Team Lead Queue and can review submitted summaries; admins can use all
UI pages. Elevated roles are assigned by an administrator, not selected
during registration. Run `python scripts/create_admin.py` to create the
initial administrator. API clients must send the login token as a bearer
token.

Uploaded PDFs are text-extracted and indexed into the project's persistent
Chroma knowledge base immediately. The index is stored under `data/chroma`
by default (configurable with `CHROMA_PATH`). In the **Knowledge Base** page,
ask questions across all indexed project PDFs or select specific documents.
Answers include source filenames and page numbers; if the retrieved passages
do not support an answer, the assistant abstains. Important claims should
still be checked against the cited pages: retrieval and model-generated
answers cannot guarantee scientific accuracy, and scanned/image-only PDFs
may require OCR before their contents can be searched.

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
## UI  Screenshots 

## Login & Register Page 
![Sign in ](image-1.png)
![Create_account](image-2.png)

## Creates Projects
![Crate Projects](image-3.png)

## Overview
![Project_Overview & Workflow Summary](image-4.png)

## Documents Uploads
![Document_Management & Project Document ](image-5.png)

## Knowledge_base
![Research_Question](image-6.png)
![Answer & Source](image-7.png)

## Generate_draft
![Generate_draft & Research question & document UUID](image-8.png)

## Summary & Submit to Team_Lead
![Summary Answer](image-11.png)
![Key_Finding_1](image-12.png)
![Key_Finding_2](image-13.png)
![Key_Finding_3](image-14.png)
![Key_Finding_4](image-15.png)
![Key_Finding_5](image-16.png)
![Conclusion](image-17.png)
## PDF & Word Document Download 
When it give the Team Lead Approval  it can access to download it 

![Download_PDF](image-18.png)
![Download_Word](image-19.png)