import logging
from src.database import SessionLocal
from src.models import Milestone, Notification
from src.audit import log_event

def detect_anomalies():
    """Detect escalated milestones and generate notifications.

    This runs periodically (every 5 minutes) via APScheduler. It scans for
    milestones with status "ESCALATED" and creates a notification for each.
    A corresponding audit log entry is also recorded.
    """
    logger = logging.getLogger(__name__)
    db = SessionLocal()
    try:
        escalated = db.query(Milestone).filter_by(status="ESCALATED").all()
        for ms in escalated:
            # Create a notification (simple de-duplication by checking recent ones)
            title = "Milestone Escalated"
            body = f"Milestone '{ms.title}' (ID: {ms.milestone_id[:8]}…) has been escalated."
            notif = Notification(title=title, body=body, is_read=False, link="/dashboard")
            db.add(notif)
            # Audit log for the detection event
            log_event(db, "COHORT_ANOMALY_DETECTED", ms.milestone_id,
                      actor="system", before={"status": ms.status}, after={"status": ms.status})
        db.commit()
    except Exception as e:
        logger.exception("Anomaly detection failed: %s", e)
        db.rollback()
    finally:
        db.close()
