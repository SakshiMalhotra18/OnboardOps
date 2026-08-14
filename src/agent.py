import os
import uuid
from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph import StateGraph, END
from src.schema import PlanOutputSchema
from src.database import SessionLocal
from src.models import Employee, Plan, Milestone

class AgentState(TypedDict):
    employee_id: str
    employee_data: Dict[str, Any]
    acl_groups: List[str]
    retrieved_docs: List[Dict[str, Any]]
    fallback_mode: bool
    plan_output: PlanOutputSchema

def fetch_employee_context(state: AgentState):
    db = SessionLocal()
    employee = db.query(Employee).filter_by(employee_id=state['employee_id']).first()
    
    if not employee:
        db.close()
        raise ValueError(f"Employee {state['employee_id']} not found")
        
    employee_data = {
        "full_name": employee.full_name,
        "job_title": employee.job_title,
        "department": employee.department,
    }
    
    acl_groups = [g.group_name for g in employee.acl_groups]
    db.close()
    return {"employee_data": employee_data, "acl_groups": acl_groups}

def retrieve_documents(state: AgentState):
    print("MOCKING Retrieval to avoid ONNX/PyTorch DLL issues on Windows...")
    docs = [
        {"doc_id": "doc_1", "content": "Welcome to Engineering! Standard IT setup includes Macbook and 1Password."},
        {"doc_id": "doc_2", "content": "First 30 days: focus on codebase familiarization and shadow a deployment."},
        {"doc_id": "doc_3", "content": "Complete mandatory security training within first week."}
    ]
    fallback = len(docs) < 3
    return {"retrieved_docs": docs, "fallback_mode": fallback}

def route_after_retrieval(state: AgentState):
    if state.get("fallback_mode"):
        return "low_context_fallback"
    return "synthesize_plan"

def low_context_fallback(state: AgentState):
    print(f"Fallback mode triggered for {state['employee_id']}. Need manual manager input.")
    # Here we would send a Slack message to the manager asking for manual input
    return {}

def synthesize_plan_node(state: AgentState):
    print("MOCKING LLM generation to avoid API key requirements...")
    from src.schema import PlanOutputSchema, WeekSchema, MilestoneSchema
    output = PlanOutputSchema(
        source_document_ids=["doc_1", "doc_2", "doc_3"],
        weeks=[
            WeekSchema(
                week_number=1,
                theme="Environment & Access Setup",
                milestones=[
                    MilestoneSchema(
                        title="Set up Macbook and 1Password",
                        description="Request access to 1Password and setup development environment.",
                        category="ACCESS_PROVISIONING",
                        owner="EMPLOYEE",
                        sla_days=2,
                        source_citations=["doc_1"]
                    ),
                    MilestoneSchema(
                        title="Complete Security Training",
                        description="Complete the mandatory HR security training.",
                        category="COMPLIANCE",
                        owner="EMPLOYEE",
                        sla_days=5,
                        source_citations=["doc_3"]
                    )
                ]
            )
        ]
    )
    return {"plan_output": output}

def persist_plan(state: AgentState):
    if not state.get("plan_output"):
        return {}
        
    db = SessionLocal()
    employee = db.query(Employee).filter_by(employee_id=state['employee_id']).first()
    
    new_plan = Plan(
        employee_id=employee.employee_id,
        manager_employee_id=employee.manager_employee_id or "admin",
        generation_model="claude-3-5-sonnet-20240620",
        source_document_ids=state["plan_output"].source_document_ids,
        status="PENDING_MANAGER_APPROVAL"
    )
    db.add(new_plan)
    db.flush() # to get new_plan.plan_id
    
    for week in state["plan_output"].weeks:
        for ms in week.milestones:
            db.add(Milestone(
                plan_id=new_plan.plan_id,
                week_number=week.week_number,
                theme=week.theme,
                title=ms.title,
                description=ms.description,
                category=ms.category,
                owner=ms.owner,
                sla_days=ms.sla_days,
                source_citations=ms.source_citations
            ))
            
    db.commit()
    db.close()
    
    print(f"Plan {new_plan.plan_id} created and awaiting approval for {state['employee_id']}")
    return {}

def build_graph():
    workflow = StateGraph(AgentState)
    
    workflow.add_node("fetch_context", fetch_employee_context)
    workflow.add_node("retrieve_docs", retrieve_documents)
    workflow.add_node("low_context_fallback", low_context_fallback)
    workflow.add_node("synthesize_plan", synthesize_plan_node)
    workflow.add_node("persist_plan", persist_plan)
    
    workflow.set_entry_point("fetch_context")
    workflow.add_edge("fetch_context", "retrieve_docs")
    workflow.add_conditional_edges(
        "retrieve_docs",
        route_after_retrieval,
        {
            "low_context_fallback": "low_context_fallback",
            "synthesize_plan": "synthesize_plan"
        }
    )
    workflow.add_edge("low_context_fallback", END)
    workflow.add_edge("synthesize_plan", "persist_plan")
    workflow.add_edge("persist_plan", END)
    
    return workflow.compile()

graph = build_graph()

def synthesize_plan(employee_id: str):
    print(f"Starting plan synthesis for {employee_id}")
    final_state = graph.invoke({"employee_id": employee_id})
    return final_state
