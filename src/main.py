from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request, Response, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime, timezone
from src.audit import log_event
from src.anomaly import detect_anomalies
from src.database import engine, Base, SessionLocal, get_db
from src.models import Employee, IdempotencyLedger, Plan, Milestone, CheckIn, AuditLog, Notification
from apscheduler.schedulers.background import BackgroundScheduler
import uuid

# Create tables if they don't exist
try:
    Base.metadata.create_all(bind=engine)
except Exception as e:
    print("Could not create tables automatically:", e)

# --- APScheduler Cron Job ---
def dispatch_checkins():
    """Scans IN_PROGRESS milestones and dispatches a check-in if none is pending."""
    from src.database import SessionLocal
    from src.anomaly import detect_anomalies
    db = SessionLocal()
    in_progress = db.query(Milestone).filter_by(status="IN_PROGRESS").all()
    new_checkins = 0
    for ms in in_progress:
        pending = db.query(CheckIn).filter_by(
            milestone_id=ms.milestone_id,
            status="PENDING_RESPONSE"
        ).first()
        if not pending:
            checkin = CheckIn(
                milestone_id=ms.milestone_id,
                prompt_text=f"Hi! Quick check-in on your milestone: '{ms.title}'. How is it going? Any blockers?"
            )
            db.add(checkin)
            new_checkins += 1
    db.commit()
    log_event(db, "CHECKIN_DISPATCHED", "system", actor="system", before=None, after={"new_checkins": new_checkins})
    db.close()
    if new_checkins:
        print(f"[Scheduler] Dispatched {new_checkins} new check-in(s).")

import os
import uuid

# Base directory path resolution for templates on Vercel
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
possible_dirs = [
    os.path.join(BASE_DIR, "templates"),
    os.path.join(BASE_DIR, "api", "templates"),
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates"),
    "templates"
]
TEMPLATES_DIR = next((d for d in possible_dirs if os.path.exists(d)), "templates")

def ensure_db_seeded():
    try:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        from src.models import Employee
        if not db.query(Employee).first():
            db.close()
            from src.mock_data import seed_db_data
            seed_db_data()
        else:
            db.close()
    except Exception as e:
        print("[ensure_db_seeded] Error:", e)

# Always attempt initial DB seeding on module import for serverless
ensure_db_seeded()

@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_db_seeded()
    if not os.getenv("VERCEL"):
        # Run check-in dispatch every 60 seconds for local dev
        scheduler.add_job(dispatch_checkins, "interval", seconds=60, id="checkin_dispatch")
        scheduler.add_job(detect_anomalies, "interval", minutes=5, id="anomaly_detection")
        scheduler.start()
        print("[Scheduler] Started — dispatching check-ins every 60 seconds.")
    yield
    if not os.getenv("VERCEL"):
        scheduler.shutdown()

app = FastAPI(title="OnboardOps API", lifespan=lifespan)
templates = Jinja2Templates(directory=TEMPLATES_DIR)

@app.middleware("http")
async def fix_vercel_paths(request: Request, call_next):
    # Vercel sends the true user-requested path in x-matched-path header
    matched_path = request.headers.get("x-matched-path")
    if matched_path:
        request.scope["path"] = matched_path
    elif request.scope.get("path") in ("/api/index.py", "/api/index", "/api/index/"):
        request.scope["path"] = "/"
    return await call_next(request)

# --- Schemas ---
class WebhookPayload(BaseModel):
    employee_id: str
    full_name: str
    start_date: date
    job_title: str
    department: str
    manager_employee_id: Optional[str] = None
    team_id: Optional[str] = None
    work_location: Optional[str] = None
    employment_type: Optional[str] = None
    event_type: str
    hris_event_id: str

class CheckInResponse(BaseModel):
    response_text: str

class AssignMilestonePayload(BaseModel):
    plan_id: str
    title: str
    description: str
    sla_days: int

# --- HRIS Webhook ---
@app.post("/webhooks/hris/new-hire")
def receive_new_hire(payload: WebhookPayload, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):

    existing_event = db.query(IdempotencyLedger).filter_by(
        employee_id=payload.employee_id,
        event_type=payload.event_type,
        hris_event_id=payload.hris_event_id
    ).first()
    if existing_event:
        return {"status": "ignored", "reason": "duplicate event"}

    ledger_entry = IdempotencyLedger(
        employee_id=payload.employee_id,
        event_type=payload.event_type,
        hris_event_id=payload.hris_event_id
    )
    db.add(ledger_entry)

    if not payload.job_title or not payload.department:
        db.commit()
        return {"status": "pending_enrichment"}

    employee = db.query(Employee).filter_by(employee_id=payload.employee_id).first()
    if not employee:
        employee = Employee(
            employee_id=payload.employee_id,
            full_name=payload.full_name,
            start_date=payload.start_date,
            job_title=payload.job_title,
            department=payload.department,
            manager_employee_id=payload.manager_employee_id,
            team_id=payload.team_id,
            work_location=payload.work_location,
            employment_type=payload.employment_type
        )
        db.add(employee)
    db.commit()

    from src.agent import synthesize_plan
    background_tasks.add_task(synthesize_plan, employee.employee_id)
    return {"status": "accepted", "message": "Plan generation enqueued"}

# --- Manager: Approve Plan ---
@app.post("/plans/{plan_id}/approve")
def approve_plan(plan_id: str, db: Session = Depends(get_db)):
    plan = db.query(Plan).filter_by(plan_id=plan_id).first()
    
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status != "PENDING_MANAGER_APPROVAL":
        raise HTTPException(status_code=400, detail="Plan is not pending approval")

    plan.status = "ACTIVE"
    for ms in plan.milestones:
        ms.status = "IN_PROGRESS"
    db.commit()
    # Log plan approval event
    log_event(db, "PLAN_APPROVED", plan.plan_id, actor="manager", before=None, after={"status": "ACTIVE"})

    return {"status": "approved", "plan_id": plan_id}

# --- Manager: Assign Activity ---
@app.post("/milestones/assign")
def assign_milestone(payload: AssignMilestonePayload, db: Session = Depends(get_db)):
    plan = db.query(Plan).filter_by(plan_id=payload.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    new_ms = Milestone(
        plan_id=payload.plan_id,
        week_number=1,
        title=payload.title,
        description=payload.description,
        category="ROLE_RAMP",
        owner="EMPLOYEE",
        sla_days=payload.sla_days,
        status="IN_PROGRESS" if plan.status == "ACTIVE" else "NOT_STARTED"
    )
    db.add(new_ms)
    db.commit()
    return {"status": "assigned", "milestone_id": new_ms.milestone_id}

# --- Employee: Submit Check-In Response ---
@app.post("/checkins/{checkin_id}/respond")
def respond_to_checkin(checkin_id: str, payload: CheckInResponse, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    checkin = db.query(CheckIn).filter_by(checkin_id=checkin_id).first()
    
    if not checkin:
        raise HTTPException(status_code=404, detail="Check-in not found")
    checkin.response_text = payload.response_text
    db.commit()

    from src.agent2_monitor import process_checkin_response
    background_tasks.add_task(process_checkin_response, checkin_id, payload.response_text)
    return {"status": "response_received", "message": "Agent 2 is evaluating your response."}

# --- UI Routes & Authentication ---
@app.get("/login")
def login_page(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

@app.api_route("/auth/login", methods=["GET", "POST"])
def authenticate(
    request: Request,
    employee_id: Optional[str] = Form(None),
    role: Optional[str] = Form(None)
):
    emp_id = employee_id or request.query_params.get("employee_id", "M1")
    r = role or request.query_params.get("role", "manager")
    
    target_url = "/dashboard" if r == "manager" else "/employee"
    res = RedirectResponse(url=target_url, status_code=303)
    res.set_cookie(key="mock_user_id", value=emp_id)
    res.set_cookie(key="mock_role", value=r)
    return res

@app.post("/notifications/mark/{notif_id}")
def mark_notification_read(notif_id: int, db: Session = Depends(get_db)):
    notif = db.query(Notification).filter_by(id=notif_id).first()
    
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    db.commit()
    return {"status": "marked_read", "id": notif_id}

@app.get("/notifications")
def get_notifications(db: Session = Depends(get_db)):
    # Unread count

    unread = db.query(Notification).filter_by(is_read=False).count()
    recent = db.query(Notification).order_by(Notification.created_at.desc()).limit(10).all()
    notif_list = [{
        "id": n.id,
        "title": n.title,
        "body": n.body,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat(),
        "link": n.link
    } for n in recent]
    return {"unread_count": unread, "notifications": notif_list}

@app.get("/audit")
def get_audit_logs(limit: int = 20, db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    
    result = [{
        "event_type": log.event_type,
        "entity_id": log.entity_id,
        "actor": log.actor,
        "before": log.before_state,
        "after": log.after_state,
        "timestamp": log.timestamp.isoformat()
    } for log in logs]
    return {"audit_logs": result}

@app.get("/dashboard")
def view_dashboard(request: Request, db: Session = Depends(get_db)):
    manager_id = request.query_params.get("mock_user_id") or request.cookies.get("mock_user_id", "M1")
    plans = db.query(Plan).filter_by(manager_employee_id=manager_id).all()
    
    # Build enriched plan data
    enriched_plans = []
    for plan in plans:
        employee = db.query(Employee).filter_by(employee_id=plan.employee_id).first()
        milestones = plan.milestones
        total = len(milestones)
        completed = sum(1 for m in milestones if m.status == "COMPLETED")
        escalated = sum(1 for m in milestones if m.status == "ESCALATED")
        in_progress = sum(1 for m in milestones if m.status == "IN_PROGRESS")
        progress_pct = int((completed / total) * 100) if total > 0 else 0
        enriched_plans.append({
            "plan": plan,
            "employee": employee,
            "milestones": milestones,
            "total": total,
            "completed": completed,
            "escalated": escalated,
            "in_progress": in_progress,
            "progress_pct": progress_pct,
        })

    # Global stats
    all_milestones = []
    for p in plans:
        all_milestones.extend(p.milestones)
        
    stats = {
        "total_plans": len(plans),
        "active_plans": sum(1 for p in plans if p.status == "ACTIVE"),
        "escalated_items": sum(1 for m in all_milestones if m.status == "ESCALATED"),
        "pending_checkins": db.query(CheckIn).join(Milestone).join(Plan).filter(Plan.manager_employee_id == manager_id, CheckIn.status == "PENDING_RESPONSE").count(),
    }
    
    user_role = request.query_params.get("mock_role") or request.cookies.get("mock_role", "manager")

    return templates.TemplateResponse(request=request, name="index.html", context={
        "enriched_plans": enriched_plans,
        "stats": stats,
        "user_role": user_role,
    })

@app.get("/employee")
def employee_portal(request: Request, db: Session = Depends(get_db)):
    employee_id = request.query_params.get("mock_user_id") or request.cookies.get("mock_user_id", "E1")
    
    employee_plans = db.query(Plan).filter_by(employee_id=employee_id).all()
    plan_ids = [p.plan_id for p in employee_plans]
    
    if plan_ids:
        all_milestones = db.query(Milestone).filter(Milestone.plan_id.in_(plan_ids)).all()
        milestone_ids = [m.milestone_id for m in all_milestones]
        if milestone_ids:
            checkins = db.query(CheckIn).filter(CheckIn.milestone_id.in_(milestone_ids), CheckIn.status=="PENDING_RESPONSE").all()
        else:
            checkins = []
    else:
        all_milestones = []
        checkins = []
        
    total = len(all_milestones)
    completed = sum(1 for m in all_milestones if m.status == "COMPLETED")
    progress_pct = int((completed / total) * 100) if total > 0 else 0
    
    user_role = request.query_params.get("mock_role") or request.cookies.get("mock_role", "employee")
    
    return templates.TemplateResponse(request=request, name="employee.html", context={
        "checkins": checkins,
        "progress_pct": progress_pct,
        "completed": completed,
        "total": total,
        "user_role": user_role,
        "all_milestones": all_milestones,
    })

@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")

# --- Manager: Approve a milestone completion ---
@app.post("/milestones/{milestone_id}/approve")
def approve_milestone(milestone_id: str, db: Session = Depends(get_db)):
    ms = db.query(Milestone).filter_by(milestone_id=milestone_id).first()
    if not ms:
        raise HTTPException(status_code=404, detail="Milestone not found")
    ms.status = "COMPLETED"
    log_event(db, "MILESTONE_APPROVED", milestone_id, actor="manager", before={"status": "AWAITING_APPROVAL"}, after={"status": "COMPLETED"})
    db.commit()
    return {"status": "approved", "milestone_id": milestone_id}

# --- Manager: Reject a milestone completion (sends back to IN_PROGRESS) ---
@app.post("/milestones/{milestone_id}/reject")
def reject_milestone(milestone_id: str, db: Session = Depends(get_db)):
    ms = db.query(Milestone).filter_by(milestone_id=milestone_id).first()
    if not ms:
        raise HTTPException(status_code=404, detail="Milestone not found")
    ms.status = "IN_PROGRESS"
    log_event(db, "MILESTONE_REJECTED", milestone_id, actor="manager", before={"status": "AWAITING_APPROVAL"}, after={"status": "IN_PROGRESS"})
    db.commit()
    return {"status": "rejected", "milestone_id": milestone_id}
