import json
import hashlib
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.models import AuditLog, Notification

GENESIS_HASH = "0" * 64

def compute_entry_hash(prev_hash: str, event_type: str, entity_id: str, actor: str, before: dict, after: dict, timestamp_str: str) -> str:
    canonical_payload = json.dumps({
        "prev_hash": prev_hash,
        "event_type": event_type,
        "entity_id": str(entity_id),
        "actor": actor or "system",
        "before_state": before,
        "after_state": after,
        "timestamp": timestamp_str
    }, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical_payload).hexdigest()

def log_event(db: Session, event_type: str, entity_id: str, actor: str = None, before: dict = None, after: dict = None):
    # Fetch last audit entry to get prev_hash
    last_log = db.query(AuditLog).order_by(AuditLog.id.desc()).first()
    prev_hash = last_log.entry_hash if (last_log and last_log.entry_hash) else GENESIS_HASH
    
    now = datetime.now(timezone.utc)
    # Use strict formatting so DB parsing doesn't change string representation
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    actor_str = actor or "system"
    
    entry_hash = compute_entry_hash(prev_hash, event_type, entity_id, actor_str, before, after, now_iso)
    
    audit = AuditLog(
        event_type=event_type,
        entity_id=str(entity_id),
        actor=actor_str,
        before_state=before,
        after_state=after,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
        timestamp=now
    )
    db.add(audit)
    
    if event_type in {"PLAN_APPROVED", "MILESTONE_ESCALATED", "COHORT_ANOMALY_DETECTED", "MILESTONE_AWAITING_APPROVAL"}:
        title_map = {
            "PLAN_APPROVED": "Plan Approved",
            "MILESTONE_ESCALATED": "Milestone Escalated",
            "MILESTONE_AWAITING_APPROVAL": "Milestone Awaiting Approval",
            "COHORT_ANOMALY_DETECTED": "Cohort Anomaly Detected"
        }
        body = f"{title_map.get(event_type, 'Event')} for entity {entity_id}."
        notif = Notification(
            title=title_map.get(event_type, "Event"),
            body=body,
            is_read=False,
            created_at=now,
            link="/dashboard"
        )
        db.add(notif)
    db.flush()

def verify_audit_chain(db: Session) -> dict:
    """Verifies SHA-256 hash chain integrity across all AuditLog entries."""
    logs = db.query(AuditLog).order_by(AuditLog.id.asc()).all()
    if not logs:
        return {"valid": True, "total_records": 0, "message": "Empty log chain."}
        
    expected_prev = GENESIS_HASH
    for idx, log in enumerate(logs):
        if log.prev_hash != expected_prev:
            return {
                "valid": False,
                "total_records": len(logs),
                "failed_index": idx,
                "log_id": log.id,
                "error": f"Previous hash mismatch at ID {log.id}. Expected {expected_prev[:12]}..., got {log.prev_hash[:12]}..."
            }
        recomputed = compute_entry_hash(
            log.prev_hash,
            log.event_type,
            log.entity_id,
            log.actor,
            log.before_state,
            log.after_state,
            log.timestamp.strftime("%Y-%m-%dT%H:%M:%SZ") if log.timestamp else ""
        )
        if log.entry_hash != recomputed:
            return {
                "valid": False,
                "total_records": len(logs),
                "failed_index": idx,
                "log_id": log.id,
                "error": f"Entry hash tampered at ID {log.id}. Expected {recomputed[:12]}..., got {log.entry_hash[:12]}..."
            }
        expected_prev = log.entry_hash
        
    return {"valid": True, "total_records": len(logs), "message": "All hash signatures verified intact."}
