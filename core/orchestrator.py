"""Deterministic draft routing; it records routes but performs no actions."""
from __future__ import annotations
import json
from config import get_settings
from database.db import get_connection, initialize_database

POLICY_VERSION = "routing-v1"
BLOCKERS = {"identity_unresolved", "total_mismatch", "canonical_uncertainty", "second_read_unavailable"}

def route_confidence(confidence: dict[str, object]) -> dict[str, object]:
    s=get_settings(); raw=float(confidence["raw_confidence"]); coverage=float(confidence["evidence_coverage"])
    signals=list(confidence.get("safety_signals", [])); blockers=sorted(set(signals)&BLOCKERS)
    if blockers: route, reasons="escalate", blockers
    elif raw < s.escalation_floor: route, reasons="escalate", ["below_escalation_floor"]
    elif raw >= s.auto_approve_threshold and coverage >= s.auto_approve_min_evidence_coverage: route, reasons="auto_approve", ["clean_evidence"]
    else: route, reasons="grey_zone", ["between_safety_rails" if raw >= s.escalation_floor else "insufficient_evidence_coverage"]
    explanation=f"Route {route}: confidence {raw:.2f}, coverage {coverage:.2f}; " + ", ".join(reasons) + "."
    return {"route":route,"raw_confidence":raw,"evidence_coverage":coverage,"floor_snapshot":s.escalation_floor,"auto_approve_threshold_snapshot":s.auto_approve_threshold,"safety_signals":signals,"reason_codes":reasons,"explanation":explanation,"policy_version":POLICY_VERSION}

def log_route(grading_record_id:int, confidence_evaluation_id:int, confidence:dict[str,object], db_path=None)->dict[str,object]:
    decision=route_confidence(confidence); initialize_database(db_path)
    with get_connection(db_path) as db:
        row=db.execute("SELECT id FROM orchestrator_decision_log WHERE grading_record_id=? AND confidence_evaluation_id=? AND policy_version=? AND floor_snapshot=? AND auto_approve_threshold_snapshot=?",(grading_record_id,confidence_evaluation_id,POLICY_VERSION,decision["floor_snapshot"],decision["auto_approve_threshold_snapshot"])).fetchone()
        if row: return {**decision,"id":row["id"],"idempotent":True}
        cursor=db.execute("INSERT INTO orchestrator_decision_log (grading_record_id,confidence_evaluation_id,route,raw_confidence,evidence_coverage,floor_snapshot,auto_approve_threshold_snapshot,safety_signals_json,reason_codes_json,explanation,policy_version) VALUES (?,?,?,?,?,?,?,?,?,?,?)",(grading_record_id,confidence_evaluation_id,decision["route"],decision["raw_confidence"],decision["evidence_coverage"],decision["floor_snapshot"],decision["auto_approve_threshold_snapshot"],json.dumps(decision["safety_signals"]),json.dumps(decision["reason_codes"]),decision["explanation"],POLICY_VERSION))
    return {**decision,"id":cursor.lastrowid,"idempotent":False}
