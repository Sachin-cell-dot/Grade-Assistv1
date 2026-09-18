PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY, student_code TEXT NOT NULL UNIQUE, full_name TEXT NOT NULL,
    email TEXT, guardian_phone TEXT, active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS assessment_batches (
    id INTEGER PRIMARY KEY, batch_code TEXT NOT NULL UNIQUE, label TEXT NOT NULL,
    assessment_date TEXT, subject TEXT, grade_level TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS assessments (
    id INTEGER PRIMARY KEY, title TEXT NOT NULL, subject TEXT, grade_level TEXT,
    assessment_date TEXT, batch_id INTEGER REFERENCES assessment_batches(id) ON DELETE SET NULL,
    max_score REAL NOT NULL CHECK(max_score > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, subject TEXT, description TEXT,
    UNIQUE(name, subject)
);
CREATE TABLE IF NOT EXISTS assessment_questions (
    id INTEGER PRIMARY KEY, assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    question_number INTEGER NOT NULL, max_mark REAL NOT NULL CHECK(max_mark > 0),
    topic_id INTEGER REFERENCES topics(id) ON DELETE SET NULL, UNIQUE(assessment_id, question_number)
);
CREATE TABLE IF NOT EXISTS question_marks (
    id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    assessment_question_id INTEGER NOT NULL REFERENCES assessment_questions(id) ON DELETE CASCADE,
    mark REAL CHECK(mark >= 0), extraction_confidence REAL CHECK(extraction_confidence BETWEEN 0 AND 1),
    source_path TEXT, teacher_confirmed INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, assessment_question_id)
);
CREATE TABLE IF NOT EXISTS student_history (
    id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    assessment_id INTEGER REFERENCES assessments(id) ON DELETE SET NULL, metric_name TEXT NOT NULL,
    metric_value REAL NOT NULL, recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    assessment_id INTEGER REFERENCES assessments(id) ON DELETE SET NULL, status TEXT NOT NULL,
    recommended_action TEXT NOT NULL, rationale TEXT NOT NULL, confidence REAL CHECK(confidence BETWEEN 0 AND 1),
    requires_teacher_confirmation INTEGER NOT NULL DEFAULT 1, reasoning_tier TEXT NOT NULL DEFAULT 'not_applicable', metadata_json TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TEXT
);
CREATE TABLE IF NOT EXISTS orchestrator_decision_log (
 id INTEGER PRIMARY KEY, grading_record_id INTEGER NOT NULL REFERENCES grading_records(id) ON DELETE CASCADE,
 confidence_evaluation_id INTEGER NOT NULL REFERENCES confidence_evaluations(id) ON DELETE CASCADE,
 route TEXT NOT NULL, raw_confidence REAL NOT NULL, evidence_coverage REAL NOT NULL,
 floor_snapshot REAL NOT NULL, auto_approve_threshold_snapshot REAL NOT NULL,
 safety_signals_json TEXT NOT NULL, reason_codes_json TEXT NOT NULL, explanation TEXT NOT NULL,
 policy_version TEXT NOT NULL DEFAULT 'routing-v1', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 UNIQUE(grading_record_id, confidence_evaluation_id, policy_version, floor_snapshot, auto_approve_threshold_snapshot)
);
CREATE TABLE IF NOT EXISTS escalations (
    id INTEGER PRIMARY KEY, decision_id INTEGER REFERENCES decisions(id) ON DELETE SET NULL,
    reason TEXT NOT NULL, reasoning_tier TEXT NOT NULL DEFAULT 'not_applicable', status TEXT NOT NULL DEFAULT 'open', assigned_to TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS teacher_outcomes (
    id INTEGER PRIMARY KEY, decision_id INTEGER REFERENCES decisions(id) ON DELETE SET NULL,
    outcome TEXT NOT NULL, notes TEXT, recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS threshold_history (
    id INTEGER PRIMARY KEY, threshold_name TEXT NOT NULL, previous_value REAL, new_value REAL NOT NULL,
    changed_by TEXT, reason TEXT, changed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY, student_id INTEGER REFERENCES students(id) ON DELETE SET NULL,
    decision_id INTEGER REFERENCES decisions(id) ON DELETE SET NULL, channel TEXT NOT NULL, recipient TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', provider_message_id TEXT, error_message TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    sent_at TEXT
);
CREATE TABLE IF NOT EXISTS class_topic_trends (
    id INTEGER PRIMARY KEY, assessment_id INTEGER REFERENCES assessments(id) ON DELETE CASCADE,
    topic_id INTEGER REFERENCES topics(id) ON DELETE CASCADE, average_score REAL NOT NULL,
    student_count INTEGER NOT NULL DEFAULT 0, calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(assessment_id, topic_id)
);
CREATE INDEX IF NOT EXISTS idx_marks_student ON question_marks(student_id);
CREATE INDEX IF NOT EXISTS idx_decisions_student ON decisions(student_id);
CREATE INDEX IF NOT EXISTS idx_history_student ON student_history(student_id);

-- Segment 2 normalized persistence additions. Existing foundation tables remain
-- compatible; initialize_database() applies non-destructive column migrations.
CREATE TABLE IF NOT EXISTS question_topic_mappings (
    id INTEGER PRIMARY KEY,
    assessment_question_id INTEGER NOT NULL REFERENCES assessment_questions(id) ON DELETE CASCADE,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    weight REAL NOT NULL DEFAULT 1.0 CHECK(weight > 0),
    UNIQUE(assessment_question_id, topic_id)
);
CREATE TABLE IF NOT EXISTS grading_records (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    total_score REAL CHECK(total_score >= 0),
    max_score REAL NOT NULL CHECK(max_score > 0),
    grading_status TEXT NOT NULL DEFAULT 'recorded',
    is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, assessment_id)
);
CREATE TABLE IF NOT EXISTS extraction_sections (
    id INTEGER PRIMARY KEY,
    grading_record_id INTEGER NOT NULL REFERENCES grading_records(id) ON DELETE CASCADE,
    section_index INTEGER NOT NULL,
    section_name TEXT,
    reported_score REAL,
    reported_max_score REAL,
    uncertain_fields_json TEXT NOT NULL DEFAULT '[]',
    UNIQUE(grading_record_id, section_index)
);
CREATE TABLE IF NOT EXISTS confidence_evaluations (
    id INTEGER PRIMARY KEY,
    grading_record_id INTEGER NOT NULL REFERENCES grading_records(id) ON DELETE CASCADE,
    evidence_fingerprint TEXT NOT NULL,
    raw_confidence REAL NOT NULL CHECK(raw_confidence BETWEEN 0 AND 1), evidence_coverage REAL NOT NULL DEFAULT 0 CHECK(evidence_coverage BETWEEN 0 AND 1),
    dual_read_agreement REAL, total_cross_check TEXT NOT NULL,
    roster_match_json TEXT NOT NULL, uncertainty_signals_json TEXT NOT NULL,
    reasons_json TEXT NOT NULL, evidence_json TEXT NOT NULL,
    evaluator_version TEXT NOT NULL DEFAULT 'canonical-v1',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(grading_record_id, evidence_fingerprint)
);
CREATE TABLE IF NOT EXISTS extracted_marks (
    id INTEGER PRIMARY KEY,
    grading_record_id INTEGER NOT NULL REFERENCES grading_records(id) ON DELETE CASCADE,
    assessment_question_id INTEGER NOT NULL REFERENCES assessment_questions(id) ON DELETE CASCADE,
    extracted_mark REAL CHECK(extracted_mark >= 0),
    extraction_confidence REAL CHECK(extraction_confidence BETWEEN 0 AND 1),
    extraction_source TEXT NOT NULL DEFAULT 'manual',
    raw_text TEXT,
    is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(grading_record_id, assessment_question_id)
);
CREATE TABLE IF NOT EXISTS student_topic_history (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    score REAL NOT NULL CHECK(score >= 0),
    max_score REAL NOT NULL CHECK(max_score > 0),
    is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1)),
    recorded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(student_id, topic_id, assessment_id)
);
CREATE TABLE IF NOT EXISTS class_topic_performance_history (
    id INTEGER PRIMARY KEY,
    assessment_id INTEGER NOT NULL REFERENCES assessments(id) ON DELETE CASCADE,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    average_score REAL NOT NULL CHECK(average_score >= 0),
    max_score REAL NOT NULL CHECK(max_score > 0),
    student_count INTEGER NOT NULL CHECK(student_count >= 0),
    is_demo INTEGER NOT NULL DEFAULT 0 CHECK(is_demo IN (0, 1)),
    calculated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(assessment_id, topic_id)
);
CREATE INDEX IF NOT EXISTS idx_grading_records_student ON grading_records(student_id);
CREATE INDEX IF NOT EXISTS idx_extraction_sections_record ON extraction_sections(grading_record_id);
CREATE INDEX IF NOT EXISTS idx_confidence_evaluations_record ON confidence_evaluations(grading_record_id);
CREATE INDEX IF NOT EXISTS idx_topic_history_student_topic ON student_topic_history(student_id, topic_id);
CREATE INDEX IF NOT EXISTS idx_class_topic_history_topic ON class_topic_performance_history(topic_id);
