
import random
from datetime import date, datetime, timedelta

from sqlalchemy import func, select

from hrms import (
    EmployeeCreate,
    EmployeeManager,
    LeaveManager,
    MeetingManager,
    TicketManager,
)
from hrms.database import SessionLocal
from hrms.models import Employee, LeaveBalance, LeaveHistory, Meeting, Ticket
from hrms.schemas import LeaveApplyRequest, MeetingBase, TicketCreate


def seed_services(
    employee_manager,
    leave_manager,
    meeting_manager,
    ticket_manager,
):
    """Seed sample HR data without duplicating existing records."""

    employees_data = [
        {"emp_id": "E001", "name": "Sarah Johnson", "manager_id": None,
         "email": "sarah.johnson@atliq.com"},
        {"emp_id": "E002", "name": "Michael Chen", "manager_id": None,
         "email": "michael.chen@atliq.com"},
        {"emp_id": "E003", "name": "David Wilson", "manager_id": "E001",
         "email": "david.wilson@atliq.com"},
        {"emp_id": "E004", "name": "Tony Sharma", "manager_id": "E003",
         "email": "tony.sharma@atliq.com"},
        {"emp_id": "E005", "name": "James Rodriguez", "manager_id": "E003",
         "email": "james.rodriguez@atliq.com"},
        {"emp_id": "E006", "name": "Emily Kim", "manager_id": "E002",
         "email": "emily.kim@atliq.com"},
        {"emp_id": "E007", "name": "Carlos Mendez", "manager_id": "E006",
         "email": "carlos.mendez@atliq.com"},
        {"emp_id": "E008", "name": "Lisa Wong", "manager_id": "E006",
         "email": "lisa.wong@atliq.com"},
    ]

    # 1. Employees: create only missing employees.
    for employee_data in employees_data:
        try:
            employee_manager.get_employee_details(employee_data["emp_id"])
        except ValueError:
            employee_manager.add_employee(EmployeeCreate(**employee_data))

    # 2. Leave balances and history: seed history only when none exists.
    current_date = date.today()

    for employee_data in employees_data:
        emp_id = employee_data["emp_id"]

        with SessionLocal() as db:
            employee_exists = db.get(Employee, emp_id) is not None
            balance_exists = db.get(LeaveBalance, emp_id) is not None
            history_exists = db.scalar(
                select(func.count())
                .select_from(LeaveHistory)
                .where(LeaveHistory.emp_id == emp_id)
            ) > 0

        if not employee_exists:
            continue

        if not balance_exists:
            leave_manager.register_employee(emp_id, balance=random.randint(5, 20))

        if not history_exists:
            # Seed historical dates directly. These are historical records,
            # not new leave requests requiring balance deductions.
            with SessionLocal() as db:
                request_id = db.scalar(select(func.max(LeaveHistory.request_id)))
                request_id = (request_id or 0) + 1
                num_leaves = random.randint(1, 5)
                history_rows = []

                for _ in range(num_leaves):
                    leave_date = current_date - timedelta(days=random.randint(1, 90))
                    history_rows.append(
                        LeaveHistory(
                            emp_id=emp_id,
                            leave_date=leave_date,
                            request_id=request_id,
                        )
                    )
                    request_id += 1

                    if random.random() > 0.7:
                        for offset in range(1, random.randint(2, 5)):
                            history_rows.append(
                                LeaveHistory(
                                    emp_id=emp_id,
                                    leave_date=leave_date + timedelta(days=offset),
                                    request_id=request_id - 1,
                                )
                            )

                db.add_all(history_rows)
                db.commit()

    # 3. Meetings: create sample meetings only if the database has none.
    with SessionLocal() as db:
        meeting_count = db.scalar(select(func.count()).select_from(Meeting)) or 0

    meeting_types = [
        "Team Sync",
        "Project Review",
        "Client Meeting",
        "1:1",
        "Planning",
    ]

    if meeting_count == 0:
        for employee_data in employees_data:
            emp_id = employee_data["emp_id"]

            # Use distinct dates/times for each employee to avoid the
            # manager's duplicate employee/time validation.
            for day_offset in (1, 4):
                meeting_dt = datetime.combine(
                    current_date + timedelta(days=day_offset),
                    datetime.min.time(),
                ).replace(hour=9 + (int(emp_id[1:]) % 7))

                try:
                    meeting_manager.schedule_meeting(
                        MeetingBase(
                            emp_id=emp_id,
                            meeting_dt=meeting_dt,
                            topic=random.choice(meeting_types),
                        )
                    )
                except ValueError:
                    # A conflicting existing meeting should not stop seeding.
                    continue

    # 4. Tickets: create sample tickets only if none exist.
    with SessionLocal() as db:
        ticket_count = db.scalar(select(func.count()).select_from(Ticket)) or 0

    ticket_items = [
        "Laptop",
        "Monitor",
        "Keyboard",
        "Mouse",
        "Headset",
        "Office Chair",
        "Software License",
    ]
    ticket_reasons = [
        "New hire setup",
        "Replacement for broken item",
        "Upgrade request",
        "Project requirement",
        "Ergonomic needs",
    ]

    if ticket_count == 0:
        for _ in range(random.randint(8, 15)):
            employee_data = random.choice(employees_data)
            ticket_manager.create_ticket(
                TicketCreate(
                    emp_id=employee_data["emp_id"],
                    item=random.choice(ticket_items),
                    reason=random.choice(ticket_reasons),
                )
            )

    # Return current database counts, not counts of attempted inserts.
    with SessionLocal() as db:
        return {
            "employees": db.scalar(
                select(func.count()).select_from(Employee)
            ) or 0,
            "leave_records": db.scalar(
                select(func.count()).select_from(LeaveHistory)
            ) or 0,
            "meetings": db.scalar(
                select(func.count()).select_from(Meeting)
            ) or 0,
            "tickets": db.scalar(
                select(func.count()).select_from(Ticket)
            ) or 0,
        }


if __name__ == "__main__":
    from hrms.database import init_db

    init_db()

    employee_manager = EmployeeManager()
    leave_manager = LeaveManager()
    meeting_manager = MeetingManager()
    ticket_manager = TicketManager()

    result = seed_services(
        employee_manager,
        leave_manager,
        meeting_manager,
        ticket_manager,
    )

    print(f"Employees in database: {result['employees']}")
    print(f"Leave records in database: {result['leave_records']}")
    print(f"Meetings in database: {result['meetings']}")
    print(f"Tickets in database: {result['tickets']}")
    print(leave_manager.get_leave_history("E004"))
