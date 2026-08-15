import os
from src.database import SessionLocal, Base, engine
from src.models import Employee, AclGroup, Plan, Milestone
from src.audit import log_event
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

    # Dummy Employees with Role-Specific Milestone Plans
    dummies = [
        {
            "id": "E2", "name": "Sarah Jenkins", "title": "Frontend Developer", "department": "Frontend Engineering",
            "milestones": [
                {"week": 1, "theme": "Setup", "title": "Dev Environment & Figma Access", "desc": "Setup Node v20, Next.js repository, and request Figma team access.", "cat": "ACCESS_PROVISIONING", "sla": 2, "status": "COMPLETED"},
                {"week": 1, "theme": "Design System", "title": "Build First Design System Token", "desc": "Create a reusable Button variant matching the new brand system in Tailwind/CSS.", "cat": "ROLE_RAMP", "sla": 4, "status": "COMPLETED"},
                {"week": 2, "theme": "Performance", "title": "Core Web Vitals Audit", "desc": "Audit bundle size and reduce LCP score on landing pages below 1.2s.", "cat": "DELIVERABLE", "sla": 7, "status": "COMPLETED"},
                {"week": 2, "theme": "Review", "title": "Ship First Frontend Feature PR", "desc": "Implement dark mode toggle component and submit PR for senior review.", "cat": "ROLE_RAMP", "sla": 10, "status": "COMPLETED"}
            ]
        },
        {
            "id": "E3", "name": "Marcus Chen", "title": "Data Scientist", "department": "Data & Analytics",
            "milestones": [
                {"week": 1, "theme": "Infrastructure", "title": "Snowflake & PyTorch GPU Cluster Access", "desc": "Provision read access to data lake and configure CUDA PyTorch environment.", "cat": "ACCESS_PROVISIONING", "sla": 2, "status": "COMPLETED"},
                {"week": 1, "theme": "Data Exploration", "title": "Cohort Retention Dataset Audit", "desc": "Run exploratory data analysis on Q3 employee engagement metrics.", "cat": "DOMAIN_KNOWLEDGE", "sla": 5, "status": "COMPLETED"},
                {"week": 2, "theme": "Model Training", "title": "Build Baseline Sentiment Classifier", "desc": "Train baseline BERT classifier for check-in response friction evaluation.", "cat": "ROLE_RAMP", "sla": 8, "status": "COMPLETED"},
                {"week": 2, "theme": "Presentation", "title": "Present Model Metrics to Data Guild", "desc": "Present F1-score & confusion matrix results to data science team.", "cat": "DELIVERABLE", "sla": 12, "status": "IN_PROGRESS"}
            ]
        },
        {
            "id": "E4", "name": "Elena Rodriguez", "title": "DevOps Engineer", "department": "Infrastructure",
            "milestones": [
                {"week": 1, "theme": "Credentials", "title": "AWS IAM & YubiKey Hardware Setup", "desc": "Configure 2FA YubiKey hardware token and AWS SSO developer permissions.", "cat": "ACCESS_PROVISIONING", "sla": 1, "status": "COMPLETED"},
                {"week": 1, "theme": "Infrastructure", "title": "Kubernetes Cluster Health Audit", "desc": "Audit EKS production cluster memory utilization and pod autoscaling policies.", "cat": "DOMAIN_KNOWLEDGE", "sla": 4, "status": "ESCALATED"},
                {"week": 2, "theme": "CI/CD Pipeline", "title": "Deploy Canary Release Pipeline", "desc": "Configure ArgoCD canary deployment rollout strategy for core API service.", "cat": "ROLE_RAMP", "sla": 8, "status": "NOT_STARTED"},
                {"week": 2, "theme": "Operations", "title": "Shadow On-Call Rotation", "desc": "Shadow lead DevOps engineer during weekly incident response shift.", "cat": "SOCIAL_INTEGRATION", "sla": 14, "status": "NOT_STARTED"}
            ]
        },
        {
            "id": "E5", "name": "James Wilson", "title": "QA Automation Engineer", "department": "Quality Engineering",
            "milestones": [
                {"week": 1, "theme": "Setup", "title": "TestRail & Cypress E2E Suite Setup", "desc": "Install Cypress v13, configure Chrome headless runner, and link TestRail API.", "cat": "ACCESS_PROVISIONING", "sla": 2, "status": "COMPLETED"},
                {"week": 1, "theme": "Automation", "title": "Write Checkout E2E Regression Suite", "desc": "Automate 15 core regression tests for payment and subscription workflows.", "cat": "ROLE_RAMP", "sla": 5, "status": "COMPLETED"},
                {"week": 2, "theme": "Integration", "title": "Automate Webhook Payload Tests", "desc": "Create MockServer integration tests for HRIS webhook payload edge cases.", "cat": "DELIVERABLE", "sla": 8, "status": "IN_PROGRESS"},
                {"week": 2, "theme": "CI/CD", "title": "Flaky Test Detection Audit", "desc": "Identify and quarantine top 5 flaky tests in GitHub Actions workflow.", "cat": "ROLE_RAMP", "sla": 12, "status": "NOT_STARTED"}
            ]
        },
        {
            "id": "E6", "name": "Aisha Khan", "title": "Product Designer", "department": "Product Design",
            "milestones": [
                {"week": 1, "theme": "Setup", "title": "Figma Org & User Research Vault Access", "desc": "Request Figma editor seat and access past user research video transcripts.", "cat": "ACCESS_PROVISIONING", "sla": 2, "status": "COMPLETED"},
                {"week": 1, "theme": "Design Audit", "title": "Onboarding Flow Heuristic Evaluation", "desc": "Conduct usability audit of current onboarding manager setup steps.", "cat": "DOMAIN_KNOWLEDGE", "sla": 5, "status": "IN_PROGRESS"},
                {"week": 2, "theme": "User Research", "title": "Conduct 3 Manager Research Interviews", "desc": "Interview 3 engineering managers on onboarding friction pain points.", "cat": "SOCIAL_INTEGRATION", "sla": 9, "status": "NOT_STARTED"},
                {"week": 2, "theme": "Deliverable", "title": "Publish V2 Component Spec in Figma", "desc": "Deliver interactive Figma prototype for new check-in response cards.", "cat": "DELIVERABLE", "sla": 14, "status": "NOT_STARTED"}
            ]
        }
    ]

    for d in dummies:
        emp = Employee(
            employee_id=d["id"],
            full_name=d["name"],
            start_date=date(2026, 8, 15),
            job_title=d["title"],
            department=d["department"],
            manager_employee_id="M1"
        )
        emp.acl_groups.append(eng_group)
        db.add(emp)
        
        plan = Plan(
            employee_id=d["id"],
            manager_employee_id="M1",
            status="APPROVED"
        )
        db.add(plan)
        db.commit()
        
        for m in d["milestones"]:
            ms = Milestone(
                plan_id=plan.plan_id,
                week_number=m["week"],
                theme=m["theme"],
                title=m["title"],
                description=m["desc"],
                category=m["cat"],
                sla_days=m["sla"],
                status=m["status"]
            )
            db.add(ms)
        
        # Log plan approval for audit log chain
        log_event(db, "PLAN_APPROVED", plan.plan_id, actor="manager", before={"status": "PENDING"}, after={"status": "APPROVED"})
    
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
