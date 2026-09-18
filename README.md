# GradeAssist

GradeAssist is a local-first Assessment-to-Action Agent for DSU DevHack 3.0.

The current build includes the project foundation, idempotent SQLite persistence, explicitly labelled demo data, typed models, logging, deterministic scoring helpers, and local granular Vision/OCR extraction. Vision/OCR uses the local Ollama model `qwen3-vl:4b-instruct` with structured JSON and schema validation.

The canonical Vision/OCR path was validated against a real worksheet: it completed successfully with 5 sections and 20 subquestions. This validates extraction only; it does not make OCR output authoritative student history.

## Prerequisites

- Python 3.11+
- Ollama running locally with `qwen3-vl:4b-instruct` for Vision/OCR inspection
- Optional: Twilio and SMTP credentials for later integrations

## Setup and run

```powershell
python -m venv .venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python initialize_db.py
streamlit run app.py
```

The app is available at the local URL shown by Streamlit, normally `http://localhost:8501`.

## Configuration

Copy `.env.example` to `.env` and change only values needed for the local environment. Secrets are not stored in source files. Hosted LLM configuration remains reserved for later, genuine grey-zone reasoning with a local fallback.

## Data policy

All seeded records and repository fixtures under `data/demo/` are explicitly labelled demo data. They must not be presented as measured classroom results.

## Current scope

Implemented and validated:

- SQLite initialization, foreign keys, demo history, topic history, threshold history, and class-topic trends.
- Canonical granular Vision/OCR extraction with local Ollama and schema validation.
- Deterministic score computation helpers that do not trust a model-reported total.
- Raw confidence-evidence helpers and an inspection UI for local dual-read extraction.

Not implemented yet: draft score persistence, teacher confirmation UI, confidence-band routing, orchestrator, grey-zone reasoning, escalation, notifications, class heatmap, homework, and portal automation.

## Test status

The latest full local test run completed with **25 passing tests**. Run the complete suite with:

```powershell
python -m pytest -v
```
