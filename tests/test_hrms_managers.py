from datetime import date, timedelta, datetime
import pytest
from hrms import leave_manager
from hrms.employee_manager import EmployeeManager
from hrms.leave_manager import LeaveManager
from hrms.meeting_manager import MeetingManager
from hrms.ticket_manager import TicketManager
from hrms.schemas import EmployeeCreate, LeaveApplyRequest, MeetingCreate, TicketCreate, TicketStatusUpdate
# from hrms.database import SessionLocal
from hrms.models import LeaveBalance
import hrms.leave_manager as leave_manager_module

from sqlalchemy import select
from hrms.models import AuditLog

def create_test_employee(emp_id="E001"):
    manager = EmployeeManager()
    manager.add_employee(
        EmployeeCreate(
            emp_id=emp_id,
            name="Test User",
            manager_id=None,
            email=f"{emp_id.lower()}@example.com",
        )
    )

    # Tests that call register_employee(balance=...) need a clean
    # balance record so they can set their intended starting balance.
    with leave_manager.SessionLocal() as db:
        balance = db.get(LeaveBalance, emp_id)
        if balance is not None:
            db.delete(balance)
            db.commit()


def test_employee_rejects_missing_manager():
    manager = EmployeeManager()
    with pytest.raises(ValueError, match="Manager ID"):
        manager.add_employee(EmployeeCreate(emp_id="E001", name="Test User", manager_id="E999", email="test@example.com"))


def test_employee_search_is_case_insensitive():
    manager = EmployeeManager()
    manager.add_employee(EmployeeCreate(emp_id="E001", name="Test User", manager_id=None, email="test@example.com"))
    assert manager.search_employee_by_name(" test user ") == ["E001"]


def test_leave_history_consistent_after_application():
    create_test_employee()


    manager = LeaveManager()
    manager.register_employee("E001", balance=5)
    result = manager.apply_leave(LeaveApplyRequest(emp_id="E001", leave_dates=[date.today() + timedelta(days=2)]))
    history = manager.get_leave_history("E001")
    assert result["remaining_balance"] == 4
    assert history["history"][0]["leave_date"] == (date.today() + timedelta(days=2)).isoformat()


def test_leave_rejects_unknown_employee_without_creating_record():
    manager = LeaveManager()
    with pytest.raises(ValueError, match="not found"):
        manager.get_leave_balance("E999")
    with leave_manager.SessionLocal() as db:
        assert db.get(LeaveBalance, "E999") is None


def test_leave_rejects_duplicate_dates():
    create_test_employee()

    manager = LeaveManager(); manager.register_employee("E001", 5)
    day = date.today() + timedelta(days=1)
    with pytest.raises(ValueError, match="Duplicate"):
        manager.apply_leave(LeaveApplyRequest(emp_id="E001", leave_dates=[day, day]))


def test_meeting_schedule_and_cancel():
    create_test_employee()


    manager = MeetingManager()
    req = MeetingCreate(emp_id="E001", meeting_dt=datetime.now().replace(microsecond=0) + timedelta(days=2), topic="Intro")
    manager.schedule_meeting(req)
    assert len(manager.get_meetings("E001")) == 1
    from hrms.schemas import MeetingCancelRequest
    manager.cancel_meeting(MeetingCancelRequest(emp_id=req.emp_id, meeting_dt=req.meeting_dt, topic=req.topic))
    assert manager.get_meetings("E001") == []



def test_ticket_status_update():
    create_test_employee()

    manager = TicketManager()
    manager.create_ticket(
        TicketCreate(emp_id="E001", item="Laptop", reason="New hire")
    )

    tickets = manager.list_tickets(employee_id="E001")
    assert len(tickets) == 1

    ticket_id = tickets[0]["ticket_id"]
    manager.update_ticket_status(
        TicketStatusUpdate(status="In Progress"),
        ticket_id,
    )

    updated_tickets = manager.list_tickets(
        employee_id="E001",
        status="In Progress",
    )
    assert len(updated_tickets) == 1
    assert updated_tickets[0]["status"] == "In Progress"



def test_leave_rejects_past_dates():
    create_test_employee()
    manager = LeaveManager()
    manager.register_employee("E001", balance=5)

    yesterday = date.today() - timedelta(days=1)

    with pytest.raises(ValueError):
        manager.apply_leave(
            LeaveApplyRequest(emp_id="E001", leave_dates=[yesterday])
        )


def test_leave_rejects_insufficient_balance():
    create_test_employee()
    manager = LeaveManager()
    manager.register_employee("E001", balance=1)

    requested_dates = [
        date.today() + timedelta(days=2),
        date.today() + timedelta(days=3),
    ]

    with pytest.raises(ValueError):
        manager.apply_leave(
            LeaveApplyRequest(
                emp_id="E001",
                leave_dates=requested_dates,
            )
        )

    # A rejected request must not deduct the employee's balance.
    assert manager.get_leave_balance("E001")["balance"] == 1


def test_meeting_rejects_same_employee_same_datetime():
    create_test_employee()
    manager = MeetingManager()

    meeting_datetime = (
        datetime.now().replace(microsecond=0) + timedelta(days=3)
    )

    first_request = MeetingCreate(
        emp_id="E001",
        meeting_dt=meeting_datetime,
        topic="Project Review",
    )
    second_request = MeetingCreate(
        emp_id="E001",
        meeting_dt=meeting_datetime,
        topic="Team Sync",
    )

    manager.schedule_meeting(first_request)

    with pytest.raises(ValueError):
        manager.schedule_meeting(second_request)

    assert len(manager.get_meetings("E001")) == 1


def test_meeting_cancel_rejects_nonexistent_meeting():
    create_test_employee()
    manager = MeetingManager()

    from hrms.schemas import MeetingCancelRequest

    request = MeetingCancelRequest(
        emp_id="E001",
        meeting_dt=datetime.now().replace(microsecond=0)
        + timedelta(days=10),
        topic="Meeting That Does Not Exist",
    )

    with pytest.raises(ValueError):
        manager.cancel_meeting(request)


def test_ticket_rejects_unknown_employee():
    manager = TicketManager()

    with pytest.raises(ValueError, match="not found"):
        manager.create_ticket(
            TicketCreate(
                emp_id="E999",
                item="Laptop",
                reason="New hire",
            )
        )


def test_ticket_rejects_invalid_status():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        TicketStatusUpdate(status="Invalid Status")



def test_leave_rejects_reapplication_for_existing_date():
    create_test_employee()
    manager = LeaveManager()
    manager.register_employee("E001", balance=5)

    leave_day = date.today() + timedelta(days=5)
    request = LeaveApplyRequest(
        emp_id="E001",
        leave_dates=[leave_day],
    )

    manager.apply_leave(request)

    with pytest.raises(ValueError, match="already exists"):
        manager.apply_leave(request)

    assert manager.get_leave_balance("E001")["balance"] == 4


def test_leave_balance_unchanged_after_rejected_request():
    create_test_employee()
    manager = LeaveManager()
    manager.register_employee("E001", balance=1)

    request = LeaveApplyRequest(
        emp_id="E001",
        leave_dates=[
            date.today() + timedelta(days=2),
            date.today() + timedelta(days=3),
        ],
    )

    with pytest.raises(ValueError, match="Insufficient"):
        manager.apply_leave(request)

    assert manager.get_leave_balance("E001")["balance"] == 1
    assert manager.get_leave_history("E001")["history"] == []


    

def test_database_rejects_duplicate_employee_leave_date():
    from sqlalchemy.exc import IntegrityError
    from hrms.models import LeaveHistory
    import hrms.leave_manager as leave_manager_module

    create_test_employee()
    manager = LeaveManager()
    manager.register_employee("E001", balance=5)

    leave_day = date.today() + timedelta(days=6)
    manager.apply_leave(
        LeaveApplyRequest(
            emp_id="E001",
            leave_dates=[leave_day],
        )
    )

    # Use the same isolated test database as LeaveManager.
    with leave_manager_module.SessionLocal() as db:
        db.add(
            LeaveHistory(
                emp_id="E001",
                leave_date=leave_day,
                request_id=9999,
            )
        )

        with pytest.raises(IntegrityError):
            db.commit()

        db.rollback()

    assert manager.get_leave_balance("E001")["balance"] == 4



def test_leave_request_starts_pending_without_deducting_balance():
    from hrms.models import LeaveRequest

    create_test_employee()
    manager = LeaveManager()
    manager.register_employee("E001", balance=5)

    start = date.today() + timedelta(days=10)
    result = manager.submit_leave_request(
        "E001", start, start + timedelta(days=1), "Personal leave"
    )

    assert result["status"] == "pending"
    assert result["days_requested"] == 2
    assert manager.get_leave_balance("E001")["balance"] == 5

    

    with leave_manager_module.SessionLocal() as db:
       request = db.get(LeaveRequest, result["request_id"])
       assert request is not None
       assert request.status == "pending"


def test_leave_request_rejection_does_not_deduct_balance():
    create_test_employee()
    manager = LeaveManager()
    manager.register_employee("E001", balance=5)

    start = date.today() + timedelta(days=10)
    request = manager.submit_leave_request(
        "E001", start, start + timedelta(days=1), "Personal leave"
    )

    result = manager.decide_leave_request(
        request["request_id"], "E001", "rejected"
    )

    assert result["status"] == "rejected"
    assert manager.get_leave_balance("E001")["balance"] == 5


def test_approved_leave_deducts_balance_and_creates_history():
    create_test_employee()
    manager = LeaveManager()
    manager.register_employee("E001", balance=5)

    start = date.today() + timedelta(days=10)
    request = manager.submit_leave_request(
        "E001", start, start + timedelta(days=1), "Personal leave"
    )

    result = manager.decide_leave_request(
        request["request_id"], "E001", "approved"
    )

    assert result["status"] == "approved"
    assert manager.get_leave_balance("E001")["balance"] == 3
    history = manager.get_leave_history("E001")["history"]
    approved_dates = {item["leave_date"] for item in history}
    assert start.isoformat() in approved_dates
    assert (start + timedelta(days=1)).isoformat() in approved_dates




def test_leave_request_cannot_be_approved_twice():
    create_test_employee()
    manager = LeaveManager()
    manager.register_employee("E001", balance=5)

    start = date.today() + timedelta(days=10)
    request = manager.submit_leave_request(
        "E001", start, start + timedelta(days=1),
        "Test duplicate approval",
    )

    first = manager.decide_leave_request(
        request["request_id"], "E001", "approved"
    )
    assert first["status"] == "approved"

    with pytest.raises(ValueError):
        manager.decide_leave_request(
            request["request_id"], "E001", "approved"
        )


def test_leave_request_rejects_invalid_decision():
    create_test_employee()
    manager = LeaveManager()
    manager.register_employee("E001", balance=5)

    start = date.today() + timedelta(days=10)
    request = manager.submit_leave_request(
        "E001", start, start, "Test invalid decision"
    )

    with pytest.raises(ValueError):
        manager.decide_leave_request(
            request["request_id"], "E001", "maybe"
        )





def test_leave_request_submission_creates_audit_log():
    create_test_employee()

    manager = LeaveManager()
    manager.register_employee("E001", balance=5)

    start = date.today() + timedelta(days=10)
    request = manager.submit_leave_request(
        "E001",
        start,
        start + timedelta(days=1),
        "Audit test",
    )

    with leave_manager.SessionLocal() as db:
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.entity_id == str(request["request_id"]),
                AuditLog.action == "leave_request.submitted",
            )
        )

        assert audit is not None
        assert audit.actor_id == "E001"
        assert audit.entity_type == "leave_request"


def test_approved_leave_creates_audit_log():
    create_test_employee()
    manager = LeaveManager()
    manager.register_employee("E001", balance=5)

    start = date.today() + timedelta(days=10)
    request = manager.submit_leave_request(
        "E001", start, start, "Approval audit test"
    )
    result = manager.decide_leave_request(
        request["request_id"], "E001", "approved"
    )

    assert result["status"] == "approved"

    with leave_manager.SessionLocal() as db:
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.entity_id == str(request["request_id"]),
                AuditLog.action == "leave_request.approved",
            )
        )
        assert audit is not None
        assert audit.actor_id == "E001"


def test_rejected_leave_creates_audit_log():
    create_test_employee()
    manager = LeaveManager()
    manager.register_employee("E001", balance=5)

    start = date.today() + timedelta(days=10)
    request = manager.submit_leave_request(
        "E001", start, start, "Rejection audit test"
    )
    result = manager.decide_leave_request(
        request["request_id"], "E001", "rejected"
    )

    assert result["status"] == "rejected"

    with leave_manager.SessionLocal() as db:
        audit = db.scalar(
            select(AuditLog).where(
                AuditLog.entity_id == str(request["request_id"]),
                AuditLog.action == "leave_request.rejected",
            )
        )
        assert audit is not None
        assert audit.actor_id == "E001"