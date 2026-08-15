import os
from typing import TypedDict, Dict, Any, Literal
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from src.database import SessionLocal
from src.models import CheckIn, Milestone
from src.audit import log_event
from datetime import datetime, timezone

class Agent2EvaluationSchema(BaseModel):
    friction_category: Literal["COMPLETED", "ACCESS_BLOCKED", "ON_TRACK"]
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Enforced confidence score between 0.00 and 1.00")
    reasoning_summary: str = Field(..., description="Structured explanation of evaluation")
    evaluation_method: Literal["LLM_STRUCTURED", "RULE_BASED_MATCHER"]

class MonitorState(TypedDict):
    checkin_id: str
    response_text: str
    friction_category: str
    confidence_score: float
    reasoning_summary: str
    evaluation_method: str
    action_taken: str

def evaluate_response(state: MonitorState) -> Dict[str, Any]:
    text = state["response_text"]
    text_lower = text.lower()
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key and not api_key.startswith("mock"):
        try:
            from langchain_anthropic import ChatAnthropic
            llm = ChatAnthropic(model="claude-3-haiku-20240307", api_key=api_key)
            structured_llm = llm.with_structured_output(Agent2EvaluationSchema)
            prompt = f"Evaluate this employee check-in response for onboarding friction: '{text}'. Classify into COMPLETED, ACCESS_BLOCKED, or ON_TRACK, provide confidence between 0.0 and 1.0, and explain reasoning."
            res: Agent2EvaluationSchema = structured_llm.invoke(prompt)
            return {
                "friction_category": res.friction_category,
                "confidence_score": round(res.confidence_score, 2),
                "reasoning_summary": res.reasoning_summary,
                "evaluation_method": "LLM_STRUCTURED"
            }
        except Exception as e:
            print("[Agent 2] LLM classification fallback:", e)

    # Honest Rule-Based Fallback
    completion_keywords = ["done", "completed", "finished", "all set", "sorted", "complete", "training completed"]
    blocker_keywords = ["access", "block", "help", "don't have", "dont have", "issue", "problem", "stuck", "can't", "cannot", "unable", "waiting", "need", "facing", "escalate"]
    
    if any(kw in text_lower for kw in completion_keywords):
        matched_kw = next(kw for kw in completion_keywords if kw in text_lower)
        cat = "COMPLETED"
        reasoning = f"Rule matcher detected completion signal '{matched_kw}'. Submitted for manager review."
    elif any(kw in text_lower for kw in blocker_keywords):
        matched_kw = next(kw for kw in blocker_keywords if kw in text_lower)
        cat = "ACCESS_BLOCKED"
        reasoning = f"Rule matcher detected friction signal '{matched_kw}'. Escalated to manager."
    else:
        cat = "ON_TRACK"
        reasoning = "Rule matcher detected on-track response with no friction signals."
        
    eval_obj = Agent2EvaluationSchema(
        friction_category=cat,
        confidence_score=1.0,
        reasoning_summary=reasoning,
        evaluation_method="RULE_BASED_MATCHER"
    )
    
    return {
        "friction_category": eval_obj.friction_category,
        "confidence_score": eval_obj.confidence_score,
        "reasoning_summary": eval_obj.reasoning_summary,
        "evaluation_method": eval_obj.evaluation_method
    }

def update_milestone_state(state: MonitorState):
    db = SessionLocal()
    checkin = db.query(CheckIn).filter_by(checkin_id=state["checkin_id"]).first()
    if not checkin:
        db.close()
        return {"action_taken": "CHECKIN_NOT_FOUND"}
        
    milestone = checkin.milestone
    action = ""
    
    # Store Agent 2 evaluation results on the check-in record
    checkin.confidence_score = state.get("confidence_score", 1.0)
    checkin.reasoning_summary = state.get("reasoning_summary", "Evaluated by Agent 2")
    checkin.evaluation_method = state.get("evaluation_method", "RULE_BASED_MATCHER")
    
    cat = state["friction_category"]
    if cat == "COMPLETED":
        milestone.status = "AWAITING_APPROVAL"
        action = f"Milestone marked AWAITING_APPROVAL. [{checkin.evaluation_method}]"
        log_event(
            db,
            "MILESTONE_AWAITING_APPROVAL",
            milestone.milestone_id,
            actor="agent_2_monitor",
            before={"status": "IN_PROGRESS"},
            after={
                "status": "AWAITING_APPROVAL",
                "method": checkin.evaluation_method,
                "confidence": checkin.confidence_score,
                "reasoning": checkin.reasoning_summary
            }
        )
    elif cat == "ACCESS_BLOCKED":
        milestone.status = "ESCALATED"
        action = f"Escalated milestone due to access friction. [{checkin.evaluation_method}]"
        log_event(
            db,
            "MILESTONE_ESCALATED",
            milestone.milestone_id,
            actor="agent_2_monitor",
            before={"status": "IN_PROGRESS"},
            after={
                "status": "ESCALATED",
                "method": checkin.evaluation_method,
                "confidence": checkin.confidence_score,
                "reasoning": checkin.reasoning_summary
            }
        )
    else:
        if milestone.status in ("NOT_STARTED", "IN_PROGRESS"):
            milestone.status = "IN_PROGRESS"
        action = f"Milestone on track. [{checkin.evaluation_method}]"
        log_event(
            db,
            "CHECKIN_EVALUATED_ON_TRACK",
            milestone.milestone_id,
            actor="agent_2_monitor",
            before={"status": milestone.status},
            after={
                "status": "IN_PROGRESS",
                "method": checkin.evaluation_method,
                "reasoning": checkin.reasoning_summary
            }
        )

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
