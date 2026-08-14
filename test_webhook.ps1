$body = @{
    employee_id = "E1"
    full_name = "Alex Smith"
    start_date = "2026-09-01"
    job_title = "Senior Backend Engineer"
    department = "Engineering"
    manager_employee_id = "M1"
    event_type = "worker_add"
    hris_event_id = [guid]::NewGuid().ToString()
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/webhooks/hris/new-hire" -Method Post -Body $body -ContentType "application/json"
