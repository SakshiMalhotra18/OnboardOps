import os
from src.audit import log_event
from src.models import AuditLog, Notification
from typing import TypedDict, Dict, Any
from langgraph.graph import StateGraph, END
from src.database import SessionLocal
from src.models import Employee, IdempotencyLedger, Plan, Milestone, CheckIn, AuditLog, Notification
from src.anomaly import detect_anomalies
from datetime import datetime, timezone

class MonitorState(TypedDict):
    checkin_id: str
    response_text: str
    friction_category: str
    action_taken: str

def evaluate_response(state: MonitorState):
    print("MOCKING Agent 2 LLM Friction Detection...")
    text = state["response_text"].lower()

    # Completion signals — requires manager approval
    completion_keywords = ["done", "completed", "finished", "all set", "sorted", "complete", "training completed", "done and completed"]
    # Blocker signals — natural language variations
    blocker_keywords = [
        "access", "block", "help", "don't have", "dont have",
        "issue", "problem", "stuck", "can't", "cannot", "unable",
        "waiting", "no one", "nobody", "haven't", "havent",
        "need", "facing", "escalate", "serious blocker", "immediate"
    ]
    # On-track signals — marks IN_PROGRESS
    on_track_keywords = ["good", "progress", "working", "going well", "on track", "in progress", "started"]

    if any(kw in text for kw in completion_keywords):
        return {"friction_category": "COMPLETED"}
    elif any(kw in text for kw in blocker_keywords):
        return {"friction_category": "ACCESS_BLOCKED"}
    elif any(kw in text for kw in on_track_keywords):
        return {"friction_category": "ON_TRACK"}
    else:
        return {"friction_category": "ON_TRACK"}

def update_milestone_state(state: MonitorState):
    db = SessionLocal()
    checkin = db.query(CheckIn).filter_by(checkin_id=state["checkin_id"]).first()
    if not checkin:
        db.close()
        return {"action_taken": "CHECKIN_NOT_FOUND"}
        
    milestone = checkin.milestone
    action = ""
    
    if state["friction_category"] == "COMPLETED":
        # Move to awaiting manager approval — not auto-completed
        milestone.status = "AWAITING_APPROVAL"
        action = "Milestone marked AWAITING_APPROVAL — pending manager verification."
        log_event(db, "MILESTONE_AWAITING_APPROVAL", milestone.milestone_id, actor="system", before=None, after={"status": "AWAITING_APPROVAL"})
    elif state["friction_category"] == "ACCESS_BLOCKED":
        milestone.status = "ESCALATED"
        action = "Escalated milestone to manager due to access friction."
        log_event(db, "MILESTONE_ESCALATED", milestone.milestone_id, actor="system", before=None, after={"status": "ESCALATED"})
    else:
        # ON_TRACK — mark as in progress so employee can see it's being tracked
        if milestone.status in ("NOT_STARTED", "IN_PROGRESS"):
            milestone.status = "IN_PROGRESS"
        action = "Milestone is in progress."

    checkin.status = "RESPONDED"
    checkin.responded_at = datetime.now(timezone.utc)
    
    db.commit()
    db.close()
    
    print(f"Monitor Action: {action}")
    return {"action_taken": action}

def build_monitor_graph():
    workflow = StateGraph(MonitorState)
    workflow.add_node("evaluate", evaluate_response)
    workflow.add_node("update", update_milestone_state)
    
    workflow.set_entry_point("evaluate")
    workflow.add_edge("evaluate", "update")
    workflow.add_edge("update", END)
    
    return workflow.compile()

monitor_graph = build_monitor_graph()

def process_checkin_response(checkin_id: str, response_text: str):
    print(f"Agent 2 processing response for check-in {checkin_id}")
    final_state = monitor_graph.invoke({
        "checkin_id": checkin_id,
        "response_text": response_text
    })
    return final_state
