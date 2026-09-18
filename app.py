"""GradeAssist Streamlit application foundation."""
from pathlib import Path

import streamlit as st

from config import get_settings
from core.logger import configure_logging
from database import get_connection, initialize_database
from ui.extraction_demo import render as render_extraction_demo

configure_logging()
settings = get_settings()

st.set_page_config(page_title="GradeAssist", page_icon="📚", layout="wide")
st.title("GradeAssist")
st.caption("Assessment-to-Action Agent - Foundation and Vision/OCR build")
st.info("Local granular Vision/OCR extraction is available for inspection. Draft score persistence and review workflow are built in later stages.")

try:
    initialize_database()
    with get_connection() as connection:
        table_count = connection.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    st.success("Local SQLite database is ready.")
except Exception as error:
    st.error(f"Database setup failed: {error}")
    table_count = 0

left, right = st.columns(2)
left.metric("Schema tables", table_count)
right.metric("Environment", settings.environment)

st.subheader("Integration readiness")
st.write({
    "Ollama vision": f"configured ({settings.ollama_vision_model})",
    "Hosted LLM grey-zone reasoning": "configured" if settings.hosted_llm_api_key else "not configured",
    "Twilio WhatsApp": "configured" if settings.twilio_account_sid else "not configured",
    "SMTP fallback": "configured" if settings.smtp_host else "not configured",
})

st.caption(f"Database: {Path(settings.database_path).relative_to(settings.project_root)}")

st.divider()
render_extraction_demo()
