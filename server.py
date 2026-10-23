
import os
import logging
from datetime import date, datetime
from typing import Dict, List, Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP
from hrms.audit_manager import AuditManager


from emails import EmailSender
from hrms import (
    EmployeeCreate,
    EmployeeManager,
    LeaveApplyRequest,
    LeaveManager,
    MeetingCancelRequest,
    MeetingCreate,
    MeetingManager,
    TicketCreate,
    TicketManager,
    TicketStatusUpdate,
)
from hrms.database import init_db
from observability import observed
from utils import seed_services


# Load environment variables before initializing services.
load_dotenv()

# Initialize the database tables before any manager queries them.
init_db()

# Initialize database-backed managers.
employee_manager = EmployeeManager()
meeting_manager = MeetingManager()
leave_manager = LeaveManager()
ticket_manager = TicketManager()
audit_manager = AuditManager()

# Seed sample data only after database initialization.
seed_services(
    employee_manager,
    leave_manager,
    meeting_manager,
    ticket_manager,
)

# Configure email delivery. Actual credentials are required to send email.
emailer = EmailSender(
    smtp_server="smtp.gmail.com",
    port=587,
    username=os.getenv("CB_EMAIL"),
    password=os.getenv("CB_EMAIL_PWD"),
    use_tls=True,
)

mcp = FastMCP("hr-assist")

@mcp.tool()
@observed()
def add_employee(
    emp_name: str,
    manager_id: Optional[str] = None,
    email: Optional[str] = None,
) -> str:
    """Add an employee to the HRMS system."""
    emp = EmployeeCreate(
        emp_id=employee_manager.get_next_emp_id(),
        name=emp_name,
        manager_id=manager_id,
        email=email,
    )
    employee_manager.add_employee(emp)
    return f"Employee {emp_name} added successfully."



@mcp.tool()
@observed()
def get_employee_details(name: str) -> Dict:
    
    """Get employee details by exact employee name."""

    
    matches = employee_manager.search_employee_by_name(name)

    if not matches:
        raise ValueError(f"No employee found with name '{name}'.")

    if len(matches) > 1:
        raise ValueError(
            f"Multiple employees found with name '{name}'. "
            "Please use a more specific name."
        )

    return employee_manager.get_employee_details(matches[0])


@mcp.tool()
@observed()
def send_email(
    to_emails: List[str],
    subject: str,
    body: str,
    html: bool = False,
) -> dict:
    """Send email only to recipients on the configured corporate domain."""
    username = os.getenv("CB_EMAIL")
    password = os.getenv("CB_EMAIL_PWD")

    if not username or not password:
        raise ValueError(
            "Email sending is not configured. Set CB_EMAIL and "
            "CB_EMAIL_PWD in your environment."
        )

    if not to_emails:
        raise ValueError("At least one recipient email address is required.")

    allowed_domain = (
        os.getenv("HR_ALLOWED_EMAIL_DOMAIN", "atliq.com")
        .strip()
        .lower()
        .lstrip("@")
    )

    invalid = [
        address
        for address in to_emails
        if not isinstance(address, str)
        or "@" not in address
        or address.rsplit("@", 1)[-1].strip().lower() != allowed_domain
    ]

    if invalid:
        raise ValueError(
            f"Recipient domain is not allowed. "
            f"Allowed domain: {allowed_domain}"
        )

    return emailer.send_email(
        subject,
        body,
        to_emails,
        from_email=emailer.username,
        html=html,
    )


@mcp.tool()
@observed()
def create_ticket(emp_id: str, item: str, reason: str) -> str:
    """Create an IT or equipment request for an employee."""
    ticket_req = TicketCreate(
        emp_id=emp_id,
        item=item,
        reason=reason,
    )
    return ticket_manager.create_ticket(ticket_req)


@mcp.tool()
@observed()
def update_ticket_status(ticket_id: str, status: str) -> str:
    """Update the status of an existing ticket."""
    ticket_status_update = TicketStatusUpdate(status=status)
    return ticket_manager.update_ticket_status(
        ticket_status_update,
        ticket_id,
    )


@mcp.tool()
@observed()
def list_tickets(
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
) -> List[Dict[str, str]]:
    """List tickets, optionally filtering by employee and status."""
    return ticket_manager.list_tickets(
        employee_id=employee_id,
        status=status,
    )



@mcp.tool()
@observed()
def schedule_meeting(
    employee_id: str,
    meeting_datetime: datetime,
    topic: str,
    attendee_ids: Optional[List[str]] = None,
) -> str:
    """Schedule one meeting for an employee and optional additional attendees."""
    meeting_req = MeetingCreate(
        emp_id=employee_id,
        attendee_ids=attendee_ids or [],
        meeting_dt=meeting_datetime,
        topic=topic,
    )
    return meeting_manager.schedule_meeting(meeting_req)



@mcp.tool()
@observed()
def get_meetings(employee_id: str) -> List[Dict]:
    """Get the meetings scheduled for an employee."""
    return meeting_manager.get_meetings(employee_id)


@mcp.tool()
@observed()
def cancel_meeting(
    employee_id: str,
    meeting_datetime: datetime,
    topic: Optional[str] = None,
) -> str:
    """Cancel a meeting, optionally matching its topic."""
    meeting_req = MeetingCancelRequest(
        emp_id=employee_id,
        meeting_dt=meeting_datetime,
        topic=topic,
    )
    return meeting_manager.cancel_meeting(meeting_req)


@mcp.tool()
@observed()
def get_employee_leave_balance(emp_id: str) -> Dict:
    """Get an employee's current leave balance."""
    return leave_manager.get_leave_balance(emp_id)



@observed()
def apply_leave(emp_id: str, leave_dates: List[date]) -> str:
    """Legacy direct leave application; use submit_leave_request instead."""
    return (
        "This legacy tool is disabled. "
        "Use submit_leave_request to submit leave for approval."
    )


@mcp.tool()
@observed()
def submit_leave_request(
    employee_id: str,
    start_date: str,
    end_date: str,
    reason: str = "",
) -> dict:
    """Submit a leave request for approval. Dates must use YYYY-MM-DD."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        return leave_manager.submit_leave_request(
            employee_id, start, end, reason
        )
    except ValueError as exc:
        return {"error": str(exc)}


@mcp.tool()
@observed()
def list_pending_leave_requests() -> list[dict]:
    """List leave requests awaiting a decision."""
    return leave_manager.list_pending_leave_requests()


@mcp.tool()
@observed()
def decide_leave_request(
    request_id: int,
    approver_id: str,
    decision: str,
) -> dict:
    """Approve or reject a pending leave request; approver must be allowlisted."""
    allowed_approvers = {
        item.strip()
        for item in os.getenv("HR_APPROVER_IDS", "").split(",")
        if item.strip()
    }

    if not allowed_approvers:
        return {"error": "Leave approval is not configured."}

    if approver_id not in allowed_approvers:
        return {"error": "Not authorized to approve leave requests."}

    try:
        return leave_manager.decide_leave_request(
            request_id, approver_id, decision
        )
    except ValueError as exc:
        return {"error": str(exc)}



@mcp.tool()
@observed()
def get_leave_history(emp_id: str) -> Dict:
    """Get an employee's leave history."""
    return leave_manager.get_leave_history(emp_id)


@mcp.tool()
@observed()
def get_manager(emp_id: str) -> Dict:
    """Return an employee's manager."""
    return {
        "emp_id": emp_id,
        "manager": employee_manager.get_manager(emp_id),
    }



@mcp.tool()
@observed()
def get_direct_reports(manager_id: str) -> Dict:
    """Return the IDs of employees who report directly to a manager."""
    return {
        "manager_id": manager_id,
        "direct_reports": employee_manager.get_direct_reports(manager_id),
    }



@mcp.tool()
@observed()
def list_audit_logs(
    limit: int = 50,
    action: str = "",
    actor_id: str = "",
) -> list[dict]:
    """List recent HR audit records, optionally filtered by action or actor."""
    return audit_manager.list_audit_logs(
        limit=limit,
        action=action or None,
        actor_id=actor_id or None,
    )



@mcp.prompt("onboard_new_employee")
def onboard_new_employee(employee_name: str, manager_name: str) -> str:
    """Provide a workflow prompt for onboarding a new employee."""
    return f"""Onboard a new employee with the following details:
- Name: {employee_name}
- Manager Name: {manager_name}

Steps:
1. Add the employee to the HRMS system.
2. Send a welcome email to the employee using the approved email policy.
3. Notify the manager about the new employee's onboarding.
4. Raise tickets for a laptop, ID card, and other required equipment.
5. Schedule an introductory meeting between the employee and manager.
6. Verify each action and report any failures. Do not claim an action succeeded
   unless the corresponding tool confirms it.
"""


if __name__ == "__main__":
    mcp.run(transport="stdio")
