# PharmaWrite AI

PharmaWrite AI is a prototype for AI-assisted scientific literature writing. It is designed to help turn source text from authorized scientific materials into a structured, human-reviewable summary while preserving uncertainty and limitations.

## Project goal

The current project focuses on a safe and transparent workflow for drafting evidence summaries without making unsupported clinical recommendations. The output is intended to be reviewed by a qualified human before it is used in professional or regulatory contexts.

## What the app does today

- Accepts source text through a FastAPI API
- Sends that text to a local Ollama model for a structured scientific summary
- Enforces validation rules such as minimum input and maximum length
- Returns a draft summary with a clear review-required flag
- Provides a lightweight Streamlit dashboard for manual testing

## Architecture

### Backend
- FastAPI app in `app/main.py`
- App configuration in `app/config.py`
- LLM integration in `app/llm.py`

### Frontend
- Streamlit UI in `ui/dashboard.py`

### Configuration
- `.env.example` contains sample environment values
- `requirements.txt` lists the Python dependencies

## Tech stack

- Python
- FastAPI
- Streamlit
- Ollama
- Pydantic
- Requests

## Current workflow

1. User pastes scientific text into the Streamlit dashboard.
2. The UI sends the text to the FastAPI backend.
3. The backend validates the request.
4. The backend calls Ollama using the configured model.
5. The model returns a draft summary in a fixed structure.
6. The user reviews the summary before using it.

## API endpoints

### `GET /`
Returns basic app metadata.

### `GET /health`
Returns backend health status.

### `POST /api/v1/summary`
Creates a preliminary summary from source text.

Example payload:

```json
{
  "source_text": "Background: ..."
}
```

Example response:

```json
{
  "status": "success",
  "summary": "Objective or context...",
  "review_required": true
}
```

## Environment variables

Create a local `.env` file using `.env.example` as a template.

Example:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2
```

## Local setup

1. Open the project folder.
2. Create a virtual environment if needed.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Make sure Ollama is installed and running locally.
5. Confirm the model exists, for example:

```bash
ollama list
```

6. Start the backend:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

7. Start the dashboard in a second terminal:

```bash
streamlit run ui/dashboard.py
```

## Important project note

This is a prototype and not a final clinical or regulatory system. It is intended to support drafting only, and all generated outputs require human review and validation against the original evidence.

## Project status

Current stage: early prototype / Day 1 foundation.


## day -2 Database Connections 

for PostgreSQL is used to connect the project and it is working 

## Install dependency 
python -m pip install sqlalchemy "psycopg[binary]" alembic
## Create database
CREATE DATABASE pharmawrite;

## Requirements.txt  
fastapi
uvicorn[standard]
streamlit
requests
pydantic-settings
sqlalchemy
psycopg[binary]
alembic
python-dotenv

## Database URL
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/pharmawrite

## Folder Structure for Database connections

app/
├── db/
│   ├── __init__.py
│   ├── session.py
│   └── models.py
├── schemas/
│   ├── __init__.py
│   └── project.py
├── api/
│   ├── __init__.py
│   └── routes/
│       ├── __init__.py
│       └── projects.py
├── config.py
├── main.py
└── llm.py
