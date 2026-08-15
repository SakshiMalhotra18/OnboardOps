import os
from src.database import SessionLocal, Base, engine
from src.models import Employee, AclGroup, Plan, Milestone
from datetime import date

def seed_db_data():
    db = SessionLocal()
    if db.query(Employee).first():
        print("Relational data already seeded.")
        db.close()
        return

    eng_group = AclGroup(group_name="engineering_all", description="All Engineering docs")
    hr_group = AclGroup(group_name="hr_general", description="General HR docs")
    db.add(eng_group)
    db.add(hr_group)
    
    manager = Employee(
        employee_id="M1",
        full_name="Priya Patel",
        start_date=date(2020, 1, 1),
        job_title="Engineering Manager",
        department="Engineering",
    )
    manager.acl_groups.append(eng_group)
    db.add(manager)
    
    # E1: Alex Smith
    employee = Employee(
        employee_id="E1",
        full_name="Alex Smith",
        start_date=date(2026, 9, 1),
        job_title="Senior Backend Engineer",
        department="Engineering",
        manager_employee_id="M1"
    )
    employee.acl_groups.append(eng_group)
    employee.acl_groups.append(hr_group)
    db.add(employee)
    db.commit()

    # Create Alex's onboarding plan
    alex_plan = Plan(employee_id="E1", manager_employee_id="M1", status="APPROVED")
    db.add(alex_plan)
    db.commit()

    # Alex's milestones — 1 completed, 1 in progress (with a check-in), 2 not started
    from src.models import CheckIn
    alex_ms1 = Milestone(plan_id=alex_plan.plan_id, week_number=1, theme="Setup", title="IT Setup & 1Password", description="Request access to IT portal, set up MacBook, configure 1Password and AWS SSO.", category="ACCESS_PROVISIONING", sla_days=2, status="COMPLETED")
    alex_ms2 = Milestone(plan_id=alex_plan.plan_id, week_number=1, theme="Compliance", title="Complete Security Training", description="Complete the mandatory HR security and code of conduct training on Workday.", category="COMPLIANCE", sla_days=5, status="IN_PROGRESS")
    alex_ms3 = Milestone(plan_id=alex_plan.plan_id, week_number=2, theme="Codebase", title="Codebase Familiarisation", description="Shadow a senior engineer, read the architecture docs, and review 2 open PRs.", category="ROLE_RAMP", sla_days=7, status="NOT_STARTED")
    alex_ms4 = Milestone(plan_id=alex_plan.plan_id, week_number=2, theme="Culture", title="Team Meet & Greet", description="Schedule 1:1s with at least 3 team members and attend the weekly eng all-hands.", category="ROLE_RAMP", sla_days=14, status="NOT_STARTED")
    db.add_all([alex_ms1, alex_ms2, alex_ms3, alex_ms4])
    db.commit()

    # Add a pending check-in for the IN_PROGRESS milestone so Alex can respond
    alex_checkin = CheckIn(
        milestone_id=alex_ms2.milestone_id,
        status="PENDING_RESPONSE",
        prompt_text="Hey Alex 👋 — how is the Security Training going? Have you completed it on Workday, or are you running into any blockers?"
    )
    db.add(alex_checkin)

    # Dummy Employees
    dummies = [
        {"id": "E2", "name": "Sarah Jenkins", "title": "Frontend Developer", "pct": 100},
        {"id": "E3", "name": "Marcus Chen", "title": "Data Scientist", "pct": 75},
        {"id": "E4", "name": "Elena Rodriguez", "title": "DevOps Engineer", "pct": 25},
        {"id": "E5", "name": "James Wilson", "title": "QA Automation", "pct": 50},
        {"id": "E6", "name": "Aisha Khan", "title": "Product Designer", "pct": 10},
    ]

    for d in dummies:
        emp = Employee(
            employee_id=d["id"],
            full_name=d["name"],
            start_date=date(2026, 8, 15),
            job_title=d["title"],
            department="Engineering",
            manager_employee_id="M1"
        )
        emp.acl_groups.append(eng_group)
        db.add(emp)
        
        # Create a mock plan
        plan = Plan(
            employee_id=d["id"],
            manager_employee_id="M1",
            status="APPROVED"
        )
        db.add(plan)
        db.commit() # commit to get plan_id
        
        # Create milestones based on pct
        ms1 = Milestone(plan_id=plan.plan_id, week_number=1, theme="Setup", title="IT Setup & Hardware", description="Get your Macbook, YubiKey, and security keys from IT portal.", category="ACCESS_PROVISIONING", sla_days=2, status="COMPLETED" if d["pct"] > 0 else "NOT_STARTED")
        ms2 = Milestone(plan_id=plan.plan_id, week_number=1, theme="Compliance", title="HR Orientation", description="Attend the HR welcome session and review code of conduct.", category="COMPLIANCE", sla_days=3, status="COMPLETED" if d["pct"] > 25 else ("IN_PROGRESS" if d["pct"] > 0 else "NOT_STARTED"))
        ms3 = Milestone(plan_id=plan.plan_id, week_number=2, theme="Codebase", title="First Code Commit", description="Shadow a senior engineer and push a minor fix to main.", category="ROLE_RAMP", sla_days=7, status="COMPLETED" if d["pct"] > 50 else ("ESCALATED" if d["pct"] == 25 else "NOT_STARTED"))
        ms4 = Milestone(plan_id=plan.plan_id, week_number=2, theme="Culture", title="Team Meet & Greet", description="Schedule 1:1s with at least 3 team members.", category="ROLE_RAMP", sla_days=14, status="COMPLETED" if d["pct"] == 100 else ("IN_PROGRESS" if d["pct"] > 50 else "NOT_STARTED"))

        db.add_all([ms1, ms2, ms3, ms4])
    
    db.commit()
    db.close()
    print("Mock relational data seeded successfully.")

def seed_vector_data():
    try:
        import chromadb
        from llama_index.core import VectorStoreIndex, Document, StorageContext
        from llama_index.vector_stores.chroma import ChromaVectorStore
        from llama_index.embeddings.fastembed import FastEmbedEmbedding
    except ImportError:
        print("Vector store dependencies missing — skipping vector seed.")
        return

    # Initialize embedding model
    print("Initializing embedding model (FastEmbed)...")
    embed_model = FastEmbedEmbedding(model_name="BAAI/bge-small-en-v1.5")
    
    # Initialize Chroma DB
    chroma_client = chromadb.PersistentClient(path="./chroma_db")
    try:
        chroma_client.delete_collection("onboardops_docs")
    except ValueError:
        pass
        
    chroma_collection = chroma_client.create_collection("onboardops_docs")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    
    documents = [
        Document(
            text="Welcome to Engineering! Standard IT setup includes a Macbook Pro, a YubiKey, and access to 1Password and AWS SSO. Please request these via the IT portal.",
            metadata={"acl_group": "engineering_all", "doc_id": "eng_doc_1"},
        ),
        Document(
            text="First 30 days engineering roadmap: focus on codebase familiarization in the onboardops monorepo. Goal is to shadow a deployment by week 3 and ship a minor bugfix by week 4.",
            metadata={"acl_group": "engineering_all", "doc_id": "eng_doc_2"},
        ),
        Document(
            text="General HR Onboarding: Complete mandatory security training, code of conduct review, and enroll in benefits via Workday within your first week.",
            metadata={"acl_group": "hr_general", "doc_id": "hr_doc_1"},
        ),
        Document(
            text="Executive Strategy 2027: Confidential pivot to enterprise AI. Only accessible by execs.",
            metadata={"acl_group": "executive_strategy", "doc_id": "exec_doc_1"},
        )
    ]
    
    index = VectorStoreIndex.from_documents(
        documents, 
        storage_context=storage_context, 
        embed_model=embed_model
    )
    print("Mock vector data seeded successfully in ChromaDB.")

if __name__ == "__main__":
    try:
        Base.metadata.create_all(bind=engine)
        seed_db_data()
    except Exception as e:
        print("Failed to seed relational data:", e)
