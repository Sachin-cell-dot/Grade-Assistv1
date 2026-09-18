"""Explicitly labelled, deterministic fictional data for local demonstration only."""
from __future__ import annotations
from pathlib import Path
from contextlib import closing
from .db import get_connection, initialize_database

DEMO_PREFIX = "DEMO-"
ASSESSMENTS = [("[DEMO] Mathematics Checkpoint 1", "2026-01-15"), ("[DEMO] Mathematics Checkpoint 2", "2026-02-12"), ("[DEMO] Mathematics Checkpoint 3", "2026-03-12"), ("[DEMO] Mathematics Checkpoint 4", "2026-04-16")]
TOPICS = ("Fractions", "Algebra", "Geometry")
STUDENTS = (("DEMO-001", "Aarav Mehta"), ("DEMO-002", "Diya Sharma"), ("DEMO-003", "Kabir Singh"), ("DEMO-004", "Meera Iyer"), ("DEMO-005", "Rohan Patel"), ("DEMO-006", "Anaya Rao"), ("DEMO-007", "Vihaan Gupta"), ("DEMO-008", "Ishita Das"), ("DEMO-009", "Arjun Nair"), ("DEMO-010", "Sara Khan"))

# Scores are fictional out of 10, ordered by assessment. Aarav's Fraction trend declines;
# Diya remains strong; Kabir and Meera improve; class Fractions deterioration is intentional.
SCORES = {
    "DEMO-001": ((5, 7, 7), (4, 7, 7), (3, 7, 7), (2, 7, 7)),
    "DEMO-002": ((9, 9, 9), (9, 9, 9), (9, 9, 9), (9, 9, 9)),
    "DEMO-003": ((4, 5, 5), (5, 6, 6), (6, 7, 7), (7, 8, 8)),
    "DEMO-004": ((3, 4, 5), (4, 5, 6), (5, 6, 7), (6, 7, 8)),
    "DEMO-005": ((7, 7, 7), (6, 7, 7), (5, 7, 7), (4, 7, 7)),
    "DEMO-006": ((8, 7, 8), (7, 7, 8), (6, 7, 8), (5, 7, 8)),
    "DEMO-007": ((6, 6, 6), (5, 6, 6), (4, 6, 6), (3, 6, 6)),
    "DEMO-008": ((8, 8, 7), (7, 8, 7), (6, 8, 7), (5, 8, 7)),
    "DEMO-009": ((5, 6, 5), (5, 6, 5), (4, 6, 5), (3, 6, 5)),
    "DEMO-010": ((7, 7, 6), (6, 7, 6), (5, 7, 6), (4, 7, 6)),
}

def seed_demo_data(db_path: Path | None = None) -> None:
    """Insert the fictional demo dataset once; safe to call repeatedly."""
    initialize_database(db_path)
    with closing(get_connection(db_path)) as con:
        if con.execute("SELECT 1 FROM students WHERE student_code = 'DEMO-001'").fetchone():
            _ensure_demo_batches(con)
            con.commit()
            return
        con.executemany("INSERT INTO students(student_code, full_name, is_demo) VALUES (?, ?, 1)", STUDENTS)
        con.executemany("INSERT INTO topics(name, subject, description, is_demo) VALUES (?, 'Mathematics', 'Fictional demo topic', 1)", [(topic,) for topic in TOPICS])
        con.executemany("INSERT INTO assessments(title, subject, grade_level, assessment_date, max_score, is_demo) VALUES (?, 'Mathematics', 'Grade 7', ?, 30, 1)", ASSESSMENTS)
        _ensure_demo_batches(con)
        topic_ids = {row['name']: row['id'] for row in con.execute("SELECT id, name FROM topics WHERE is_demo = 1")}
        assessment_ids = [row['id'] for row in con.execute("SELECT id FROM assessments WHERE is_demo = 1 ORDER BY assessment_date")]
        student_ids = {row['student_code']: row['id'] for row in con.execute("SELECT id, student_code FROM students WHERE is_demo = 1")}
        for assessment_id in assessment_ids:
            for number, topic in enumerate(TOPICS, 1):
                cursor = con.execute("INSERT INTO assessment_questions(assessment_id, question_number, max_mark, topic_id, is_demo) VALUES (?, ?, 10, ?, 1)", (assessment_id, number, topic_ids[topic]))
                con.execute("INSERT INTO question_topic_mappings(assessment_question_id, topic_id) VALUES (?, ?)", (cursor.lastrowid, topic_ids[topic]))
        questions = {(row['assessment_id'], row['question_number']): row['id'] for row in con.execute("SELECT id, assessment_id, question_number FROM assessment_questions WHERE is_demo = 1")}
        for code, score_sets in SCORES.items():
            for index, scores in enumerate(score_sets):
                student_id, assessment_id = student_ids[code], assessment_ids[index]
                total = sum(scores)
                record = con.execute("INSERT INTO grading_records(student_id, assessment_id, total_score, max_score, is_demo) VALUES (?, ?, ?, 30, 1)", (student_id, assessment_id, total))
                for number, score in enumerate(scores, 1):
                    question_id = questions[(assessment_id, number)]
                    con.execute("INSERT INTO extracted_marks(grading_record_id, assessment_question_id, extracted_mark, extraction_confidence, extraction_source, raw_text, is_demo) VALUES (?, ?, ?, 1.0, 'demo_seed', 'Fictional demo mark', 1)", (record.lastrowid, question_id, score))
                    con.execute("INSERT INTO student_topic_history(student_id, topic_id, assessment_id, score, max_score, is_demo) VALUES (?, ?, ?, ?, 10, 1)", (student_id, topic_ids[TOPICS[number - 1]], assessment_id, score))
                con.execute("INSERT INTO student_history(student_id, assessment_id, metric_name, metric_value, is_demo) VALUES (?, ?, 'overall_percentage', ?, 1)", (student_id, assessment_id, total * 100 / 30))
        for assessment_id in assessment_ids:
            for number, topic in enumerate(TOPICS, 1):
                average = sum(SCORES[code][assessment_ids.index(assessment_id)][number - 1] for code in SCORES) / len(SCORES)
                con.execute("INSERT INTO class_topic_performance_history(assessment_id, topic_id, average_score, max_score, student_count, is_demo) VALUES (?, ?, ?, 10, 10, 1)", (assessment_id, topic_ids[topic], average))
                con.execute("INSERT INTO class_topic_trends(assessment_id, topic_id, average_score, student_count, is_demo) VALUES (?, ?, ?, 10, 1)", (assessment_id, topic_ids[topic], average))
        con.executemany("INSERT INTO threshold_history(threshold_name, previous_value, new_value, changed_by, reason, is_demo) VALUES (?, ?, ?, 'demo_seed', 'Fictional demo threshold history', 1)", [("low_confidence", None, 0.60), ("low_confidence", 0.60, 0.65), ("intervention_percentage", None, 45.0)])
        con.commit()


def _ensure_demo_batches(con) -> None:
    """Attach every fictional assessment to a stable, explicit demo batch."""
    for title, assessment_date in ASSESSMENTS:
        code = f"DEMO-MATH-{assessment_date}"
        con.execute("INSERT OR IGNORE INTO assessment_batches(batch_code, label, assessment_date, subject, grade_level) VALUES (?, ?, ?, 'Mathematics', 'Grade 7')", (code, f"[DEMO] Batch {assessment_date}", assessment_date))
        con.execute("UPDATE assessments SET batch_id = (SELECT id FROM assessment_batches WHERE batch_code = ?) WHERE title = ? AND assessment_date = ? AND is_demo = 1", (code, title, assessment_date))
