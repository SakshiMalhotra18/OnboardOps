from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Table, Boolean, JSON, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from src.database import Base
import uuid

employee_acl_groups = Table(
    'employee_acl_groups',
    Base.metadata,
    Column('employee_id', String, ForeignKey('employees.employee_id'), primary_key=True),
    Column('group_name', String, ForeignKey('acl_groups.group_name'), primary_key=True)
)

class Employee(Base):
    __tablename__ = "employees"

    employee_id = Column(String, primary_key=True, index=True)
    full_name = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    job_title = Column(String, nullable=False)
    department = Column(String, nullable=False)
    manager_employee_id = Column(String, ForeignKey("employees.employee_id"), nullable=True)
    team_id = Column(String, nullable=True)
    work_location = Column(String, nullable=True)
    employment_type = Column(String, nullable=True)

    acl_groups = relationship("AclGroup", secondary=employee_acl_groups, back_populates="employees")
    manager = relationship("Employee", remote_side=[employee_id])

class AclGroup(Base):
    __tablename__ = "acl_groups"

    group_name = Column(String, primary_key=True, index=True)
    description = Column(String, nullable=True)

    employees = relationship("Employee", secondary=employee_acl_groups, back_populates="acl_groups")

class IdempotencyLedger(Base):
    __tablename__ = "idempotency_ledger"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    employee_id = Column(String, index=True, nullable=False)
    event_type = Column(String, nullable=False)
    hris_event_id = Column(String, unique=True, index=True, nullable=False)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())

class Plan(Base):
    __tablename__ = "plans"

    plan_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id = Column(String, ForeignKey("employees.employee_id"), nullable=False)
    manager_employee_id = Column(String, ForeignKey("employees.employee_id"), nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    generation_model = Column(String, nullable=True)
    source_document_ids = Column(JSON, default=list) # List of doc ids
    status = Column(String, default="PENDING_MANAGER_APPROVAL")

    milestones = relationship("Milestone", back_populates="plan", cascade="all, delete-orphan")

class Milestone(Base):
    __tablename__ = "milestones"

    milestone_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    plan_id = Column(String, ForeignKey("plans.plan_id"), nullable=False)
    week_number = Column(Integer, nullable=False)
    theme = Column(String, nullable=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    category = Column(String, nullable=False)
    owner = Column(String, nullable=False, default="EMPLOYEE")
    sla_days = Column(Integer, nullable=False)
    dependencies = Column(JSON, default=list) # List of milestone_ids
    source_citations = Column(JSON, default=list) # List of doc ids
    status = Column(String, default="NOT_STARTED")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    plan = relationship("Plan", back_populates="milestones")

from sqlalchemy import Float

class CheckIn(Base):
    __tablename__ = "check_ins"

    checkin_id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    milestone_id = Column(String, ForeignKey("milestones.milestone_id"), nullable=False)
    status = Column(String, default="PENDING_RESPONSE") 
    prompt_text = Column(String, nullable=False)
    response_text = Column(String, nullable=True)
    confidence_score = Column(Float, nullable=True)
    reasoning_summary = Column(String, nullable=True)
    evaluation_method = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    responded_at = Column(DateTime(timezone=True), nullable=True)

    milestone = relationship("Milestone")

class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    actor = Column(String, nullable=True)
    before_state = Column(JSON, nullable=True)
    after_state = Column(JSON, nullable=True)
    prev_hash = Column(String, nullable=False)
    entry_hash = Column(String, nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    body = Column(String, nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    link = Column(String, nullable=True)

    # Link can point to relevant pages (e.g., /audit/<id>)
