"""Manual inspection page for real dual-read Ollama extraction."""
from pathlib import Path
from uuid import uuid4
import cv2
import numpy as np
import streamlit as st

from database import get_roster
from tools.confidence import check_confidence
from tools.scoring import compute_score
from tools.vision import extract_marks


def render() -> None:
    st.header("Extraction inspection")
    st.caption("Runs two real reads against the configured local Ollama vision model. No output is persisted.")
    sample_path = _ensure_demo_sample()
    image = st.file_uploader("Optional: replace the provided demo image", type=["png", "jpg", "jpeg"])
    destination = sample_path
    if image is not None:
        destination = Path("data/uploads") / f"{uuid4().hex}_{image.name}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(image.getvalue())
    st.image(str(destination), caption="Explicitly labelled demo image" if image is None else "Selected image")
    if st.button("Run dual extraction", type="primary"):
        try:
            dual = extract_marks(destination)
            st.subheader("Read 1")
            st.json(dual.first_read.model_dump(mode="json"))
            st.subheader("Read 2")
            st.json(dual.second_read.model_dump(mode="json"))
            st.metric("Field agreement", f"{dual.agreement_score:.1%}")
            score = compute_score(assessment_id=dual.first_read.assessment_id or 0, student_id=0, questions=dual.first_read.questions)
            confidence = check_confidence(dual, score, get_roster())
            st.metric("Raw confidence", f"{confidence.raw_confidence:.1%}")
            st.json({"field_agreement": dual.field_agreement, "confidence_checks": confidence.checks})
        except Exception as error:
            st.error(f"Extraction did not complete: {error}")


def _ensure_demo_sample() -> Path:
    """Create a clearly fictional image only; no output is precomputed or stored."""
    path = Path("data/demo/sample_assessment.png")
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    canvas = np.full((640, 960, 3), 255, dtype=np.uint8)
    lines = ["DEMO ONLY - FICTIONAL ASSESSMENT", "Student: Aarav Mehta", "Question 1: 4 / 5", "Question 2: 3 / 5", "Question 3: 5 / 5", "Handwritten marks are simulated text for UI inspection."]
    for index, line in enumerate(lines):
        cv2.putText(canvas, line, (55, 85 + index * 75), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (25, 25, 25), 2, cv2.LINE_AA)
    cv2.imwrite(str(path), canvas)
    return path
