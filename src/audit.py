import json
from datetime import datetime
from sqlalchemy.orm import Session
from src.models import AuditLog, Notification

def log_event(db: Session, event_type: str, entity_id: str, actor: str = None, before: dict = None, after: dict = None):
    """Create an audit log entry and optionally a notification.
    Args:
        db: SQLAlchemy session.
        event_type: Type of event, e.g., 'PLAN_APPROVED'.
        entity_id: Identifier of the affected entity (plan_id, milestone_id, etc.).
        actor: Who performed the action (user id, 'system', etc.).
        before: JSON-serializable dict of state before change.
        after: JSON-serializable dict of state after change.
    """
    audit = AuditLog(
        event_type=event_type,
        entity_id=entity_id,
        actor=actor,
        before_state=before,
        after_state=after,
        timestamp=datetime.utcnow()
    )
    db.add(audit)
    # Create a notification for key events
    if event_type in {"PLAN_APPROVED", "MILESTONE_ESCALATED", "COHORT_ANOMALY_DETECTED"}:
        title_map = {
            "PLAN_APPROVED": "Plan Approved",
            "MILESTONE_ESCALATED": "Milestone Escalated",
            "COHORT_ANOMALY_DETECTED": "Cohort Anomaly Detected"
        }
        body = f"{title_map[event_type]} for entity {entity_id}."
        notif = Notification(
            title=title_map[event_type],
            body=body,
            is_read=False,
            created_at=datetime.utcnow(),
            link="/dashboard"  # generic link; could be more specific
        )
        db.add(notif)
    db.flush()
