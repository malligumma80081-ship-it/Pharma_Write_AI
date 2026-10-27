# PharmaWrite AI

Prototype for human-reviewed, evidence-grounded scientific summaries.
The application includes authentication, PDF processing, persistent
knowledge-base indexing, document retrieval, citation checks, and a
multi-role assignment and approval workflow.

## Project architecture

PharmaWrite AI is a retrieval-augmented generation (RAG) application. It
retrieves relevant passages from a user's uploaded research documents and
provides those passages to a language model as the evidence for its answer or
draft.

```mermaid
flowchart TD
    Writer[Writer / Researcher] --> UI[Streamlit dashboard]
    Reviewer[Team Lead / Reviewer] --> UI
    Manager[Project Manager] --> UI
    Admin[Administrator] --> UI
    UI -->|HTTP + bearer token| API[FastAPI REST API]
    API --> Auth[Authentication and role checks]
    API --> SQL[(PostgreSQL / SQLite<br/>users, projects, documents, workflows, revisions, assignments)]

    API --> Upload[PDF validation and text extraction]
    Upload --> Chunk[Page-aware chunking]
    Chunk --> Embed[Sentence Transformers embeddings]
    Embed --> Vectors[(Persistent ChromaDB vector store)]

    UI -->|Question or draft request| API
    API --> Search[Project-scoped vector search]
    Search --> Vectors
    Search --> Prompt[Evidence passages with backend-assigned citation IDs]
    Prompt --> Model[Ollama language model]
    Model --> Validate[Structured response and citation validation]
    Validate --> SQL
    Validate --> UI

    UI -->|Submit draft| API
    API --> Review[Role-based assignment and review workflow]
    Review --> SQL
    Review -->|Final Admin approval| Export[PDF / Word export]
    Export --> UI
```

### How a request moves through the system

1. A writer signs in, creates a project, and uploads a PDF through the
   Streamlit dashboard. The dashboard calls the FastAPI REST API and sends
   the user's bearer token.
2. The API checks the user's role and validates the PDF file type, signature,
   and size. It extracts text, preserving page information, then splits that
   text into searchable chunks.
3. The embedding service converts each chunk to a vector. ChromaDB stores the
   vectors with project, document, filename, and page metadata. SQLAlchemy
   stores application records such as users, projects, uploaded documents,
   workflows, review revisions, and assignment history in PostgreSQL
   (Docker) or SQLite (local development).
4. For a question or draft, the API embeds the query and searches ChromaDB
   within the selected project, with optional document and page filters. It
   sends the most relevant passages—not the entire document collection—to
   Ollama with instructions to use only that source material.
5. The model returns structured output. The API validates its shape and
   checks generated citation IDs against IDs assigned to the retrieved
   passages. Knowledge-base questions abstain when the passages do not
   support an answer; draft warnings explain that citation existence alone
   does not verify scientific claims.
6. A completed draft is assigned through the human workflow. Administrators
   assign it to Project Manager(s), Project Managers assign it to Team
   Leader(s), and Team Leaders assign it to Writer(s). Writers submit the
   revised draft to the Team Leaders, then the Project Managers, and finally
   the Administrators review it. At each stage every assigned person must
   act before the workflow advances. Team Leaders and Project Managers can
   request changes back to the Writers; Administrators can return it to the
   Team Leaders. Assignment rounds and comments are retained as history.
   Export for an assigned workflow is enabled only after final Admin
   approval. Existing workflows without assignment history retain their
   existing review behavior.

### Interview walkthrough

**Short project introduction:** PharmaWrite AI is a human-reviewed scientific
literature assistant. It uses RAG to find evidence in uploaded PDFs, drafts
structured summaries with citations, and routes those drafts through an
auditable Writer → Team Lead → Project Manager → Admin workflow before export.

**End-to-end explanation:** I would start with the user journey: a writer
creates a project and uploads research PDFs. The FastAPI backend validates
each upload, extracts page-aware text, chunks it, and stores its embeddings
in ChromaDB. When the writer asks a question or starts a draft, the backend
performs project-scoped semantic retrieval and sends only the matching
passages to Ollama. The response is structured and its citation IDs are
checked against the retrieved evidence. The draft is saved for human review,
assigned through the role-based approval chain, and exported only after final
Admin approval.

**Design choices to discuss:**

- **Why RAG?** It grounds generated responses in the project's uploaded
  documents and lets the application return source filenames and page
  references instead of relying solely on a model's general knowledge.
- **Why two stores?** SQL stores relational application state and review
  history; ChromaDB stores and searches document-chunk embeddings.
- **How are unsupported claims handled?** The model is instructed to use
  supplied evidence only; response schemas and citation validation catch
  malformed or fabricated references, and the workflow preserves abstention,
  warnings, and human review.
- **What are the limitations?** Citation validation proves that a cited
  passage was retrieved, not that it scientifically supports every claim.
  Human review remains necessary, and image-only or scanned PDFs may need
  OCR before their text can be searched.

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

Use the UI's **Create account** tab to register. Applicants can select
**Writer**, **Team Leader**, or **Project Manager**; every new account starts
with Writer permissions, and elevated selections are saved as pending role
requests until an administrator approves them from **User Management**. The
signup confirmation identifies the account's active Writer role separately
from the requested role. Admin accounts cannot be self-registered; an
existing administrator must grant that role.
All roles use **My Assignments** to act on work routed to them. Admins assign
completed workflows to one or more Project Managers; each assigned Manager
must forward the work to one or more Team Leaders. Each assigned Team Leader
must assign one or more Writers. Every assigned Writer updates and submits
the draft, after which all assigned Team Leaders review it, then all assigned
Project Managers review it, and finally all active Admins approve it.
Team Leaders and Project Managers can request Writer changes; Admins can
return a workflow to the Team Leaders. Each assignment round remains in the
database for auditability. Writers can work on drafts assigned to them even
when another user owns the project. Project Managers can create and manage
projects across accounts and generate drafts. For newly assigned workflows,
PDF and Word downloads require final Admin approval; older workflows without
assignment history keep their existing Team Lead approval behavior. The
`admin` role is reserved for administration and has access to all workspaces.
Run
`python scripts/create_admin.py` to create the initial administrator. API
clients must send the login token as a bearer token.

Database migrations must be applied before running the updated API. For local
SQLite development in PowerShell:

```powershell
$env:DATABASE_URL = "sqlite:///./pharmawrite.db"
python -m alembic upgrade head
```

Administrators can approve role requests or change existing roles from
**User Management**. Users must sign out and back in after a role change.

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

To stop the Compose services, rebuild with the role updates, and start again
in the background, run these commands from the project root:

```powershell
docker compose down
docker compose up --build -d
docker compose ps
```

`docker compose down` preserves the named PostgreSQL, ChromaDB, and Ollama
volumes. Do not add `-v` unless you intend to delete that stored data. Once
the API is running, an administrator can review and assign account roles from
the **User Management** page.

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
![alt text](image-17.png)
![alt text](image-18.png)

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

## Database Screenshots
## Document
![alt text](image-19.png)

## Draft_revision
![alt text](image-20.png)

## Literature_workflow
![alt text](image-21.png)

## Projects
![alt text](image-22.png)

## Study_Evidence
![alt text](image-23.png)

## User
![alt text](image-24.png)

## Alembic_Version
![alt text](image-25.png)