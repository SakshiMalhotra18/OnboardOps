from pydantic import BaseModel, Field
from typing import List

class MilestoneSchema(BaseModel):
    title: str
    description: str
    category: str = Field(description="COMPLIANCE | ACCESS_PROVISIONING | ROLE_RAMP | SOCIAL_INTEGRATION | DOMAIN_KNOWLEDGE | DELIVERABLE")
    owner: str = Field(description="EMPLOYEE | MANAGER | IT | PEOPLE_OPS")
    sla_days: int
    source_citations: List[str] = Field(description="List of doc_ids that justify this milestone")

class WeekSchema(BaseModel):
    week_number: int
    theme: str
    milestones: List[MilestoneSchema]

class PlanOutputSchema(BaseModel):
    source_document_ids: List[str] = Field(description="List of all doc_ids used to synthesize this plan")
    weeks: List[WeekSchema]
