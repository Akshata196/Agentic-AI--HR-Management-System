# from collections import defaultdict
# from datetime import date
# from typing import Dict, Any
# from hrms.schemas import LeaveApplyRequest


# class LeaveManager:
#     """Leave operations for the current in-memory prototype.

#     The storage implementation will be replaced by SQLite in the persistence phase.
#     All history entries use one consistent dictionary schema.
#     """
#     def __init__(self):
#         self.employee_leaves: Dict[str, Dict[str, Any]] = {}

#     def register_employee(self, employee_id: str, balance: int = 20) -> None:
#         if employee_id not in self.employee_leaves:
#             self.employee_leaves[employee_id] = {"balance": balance, "history": [], "pending": []}

#     def get_leave_balance(self, employee_id: str) -> dict:
#         data = self.employee_leaves.get(employee_id)
#         if data is None:
#             raise ValueError(f"Employee ID '{employee_id}' not found.")
#         return {"emp_id": employee_id, "balance": data["balance"]}

#     def apply_leave(self, req: LeaveApplyRequest) -> dict:
#         data = self.employee_leaves.get(req.emp_id)
#         if data is None:
#             raise ValueError(f"Employee ID '{req.emp_id}' not found.")
#         dates = sorted(set(req.leave_dates))
#         if not dates:
#             raise ValueError("At least one leave date is required.")
#         if len(dates) != len(req.leave_dates):
#             raise ValueError("Duplicate leave dates are not allowed.")
#         if any(day < date.today() for day in dates):
#             raise ValueError("Leave dates cannot be in the past.")
#         requested = len(dates)
#         if data["balance"] < requested:
#             raise ValueError(f"Insufficient leave balance: requested {requested}, available {data['balance']}.")
#         # Current demo behavior: apply immediately. The approval workflow phase changes this to pending.
#         request_id = max((row["request_id"] for row in data["history"]), default=0) + 1
#         for day in dates:
#             data["history"].append({"emp_id": req.emp_id, "leave_date": day.isoformat(), "request_id": request_id})
#         data["balance"] -= requested
#         return {"status": "approved", "emp_id": req.emp_id, "days_applied": requested, "remaining_balance": data["balance"], "request_id": request_id}

#     def get_leave_history(self, employee_id: str) -> dict:
#         data = self.employee_leaves.get(employee_id)
#         if data is None:
#             raise ValueError(f"Employee ID '{employee_id}' not found.")
#         return {"emp_id": employee_id, "history": list(data["history"])}





import json
from datetime import date, datetime, UTC

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from hrms.database import SessionLocal
from hrms.models import (
    Employee,
    LeaveBalance,
    LeaveHistory,
    LeaveRequest,
     AuditLog,
)
from hrms.schemas import LeaveApplyRequest



class LeaveManager:
    """Manage employee leave balances and history using SQLAlchemy."""

    def register_employee(self, employee_id: str, balance: int = 20) -> None:
        """Create a leave balance for an existing employee."""
        if balance < 0:
            raise ValueError("Leave balance cannot be negative.")

        with SessionLocal() as db:
            employee = db.get(Employee, employee_id)
            if employee is None:
                raise ValueError(
                    f"Employee {employee_id} does not exist."
                )

            existing = db.get(LeaveBalance, employee_id)
            if existing is None:
                db.add(
                    LeaveBalance(emp_id=employee_id, balance=balance)
                )
                db.commit()

    def get_leave_balance(self, employee_id: str) -> dict:
        """Return the employee's remaining leave balance."""
        with SessionLocal() as db:
            employee = db.get(Employee, employee_id)
            if employee is None:
                raise ValueError(f"Employee {employee_id} not found.")

            balance = db.get(LeaveBalance, employee_id)
            if balance is None:
                raise ValueError(
                    f"Leave balance for {employee_id} is not registered."
                )

            return {
                "emp_id": employee_id,
                "balance": balance.balance,
            }

    def apply_leave(self, req: LeaveApplyRequest) -> dict:
        """Validate, approve, and record a leave request atomically."""
        dates = list(req.leave_dates)

        if not dates:
            raise ValueError("At least one leave date is required.")

        if len(set(dates)) != len(dates):
            raise ValueError("Duplicate leave dates are not allowed.")

        if any(leave_date < date.today() for leave_date in dates):
            raise ValueError("Leave dates cannot be in the past.")

        dates = sorted(dates)

        with SessionLocal() as db:
            try:
                employee = db.get(Employee, req.emp_id)
                if employee is None:
                    raise ValueError(
                        f"Employee {req.emp_id} not found."
                    )

                # Locking is database-specific; this query and validation
                # protect against ordinary repeated submissions.
                balance = db.get(LeaveBalance, req.emp_id)
                if balance is None:
                    raise ValueError(
                        f"Leave balance for {req.emp_id} is not registered."
                    )

                existing_dates = set(
                    db.scalars(
                        select(LeaveHistory.leave_date).where(
                            LeaveHistory.emp_id == req.emp_id,
                            LeaveHistory.leave_date.in_(dates),
                        )
                    ).all()
                )

                if existing_dates:
                    duplicates = ", ".join(
                        day.isoformat() for day in sorted(existing_dates)
                    )
                    raise ValueError(
                        f"Leave already exists for these dates: {duplicates}."
                    )

                if balance.balance < len(dates):
                    raise ValueError(
                        f"Insufficient leave balance: requested "
                        f"{len(dates)}, available {balance.balance}."
                    )

                latest_request_id = (
                    db.scalar(
                        select(func.max(LeaveHistory.request_id))
                    )
                    or 0
                )
                request_id = latest_request_id + 1

                for leave_date in dates:
                    db.add(
                        LeaveHistory(
                            emp_id=req.emp_id,
                            leave_date=leave_date,
                            request_id=request_id,
                        )
                    )

                balance.balance -= len(dates)
                remaining_balance = balance.balance

                try:
                   db.commit()
                except IntegrityError as exc:
                   db.rollback()
                   raise ValueError(
                       "Leave application conflicts with an existing leave record."
                ) from exc

                return {
                   "status": "approved",
                   "emp_id": req.emp_id,
                   "days_applied": len(dates),
                   "remaining_balance": remaining_balance,
                   "request_id": request_id,
                }

            except Exception:
                db.rollback()
                raise

    def get_leave_history(self, employee_id: str) -> dict:
        """Return leave history ordered by date and history ID."""
        with SessionLocal() as db:
            employee = db.get(Employee, employee_id)
            if employee is None:
                raise ValueError(
                    f"Employee {employee_id} does not exist."
                )

            statement = (
                select(LeaveHistory)
                .where(LeaveHistory.emp_id == employee_id)
                .order_by(
                    LeaveHistory.leave_date,
                    LeaveHistory.history_id,
                )
            )

            records = db.scalars(statement).all()

            return {
                "emp_id": employee_id,
                "history": [
                    {
                        "history_id": record.history_id,
                        "emp_id": record.emp_id,
                        "leave_date": record.leave_date.isoformat(),
                        "request_id": record.request_id,
                    }
                    for record in records
                ],
            }

    
    def submit_leave_request(
        self,
        employee_id: str,
        start_date: date,
        end_date: date,
        reason: str = "",
    ) -> dict:
        """Create a pending leave request without deducting balance."""
        if end_date < start_date:
            raise ValueError("End date cannot be before start date.")
        if start_date < date.today():
            raise ValueError("Leave dates cannot be in the past.")
        if len(reason) > 500:
            raise ValueError("Reason cannot exceed 500 characters.")

        days_requested = (end_date - start_date).days + 1

        with SessionLocal() as db:
            employee = db.get(Employee, employee_id)
            if employee is None:
                raise ValueError(f"Employee {employee_id} not found.")

            balance = db.get(LeaveBalance, employee_id)
            if balance is None:
                raise ValueError(
                    f"Leave balance for {employee_id} is not registered."
                )

            existing_dates = set(
                db.scalars(
                    select(LeaveHistory.leave_date).where(
                        LeaveHistory.emp_id == employee_id,
                        LeaveHistory.leave_date.between(
                            start_date, end_date
                        ),
                    )
                ).all()
            )
            if existing_dates:
                raise ValueError(
                    "Some requested dates already have approved leave."
                )

            request = LeaveRequest(
                emp_id=employee_id,
                start_date=start_date,
                end_date=end_date,
                days_requested=days_requested,
                reason=reason.strip(),
                status="pending",
            )
            db.add(request)
            db.flush()  # Generate request_id before creating the audit record

            db.add(
                 AuditLog(
                       action="leave_request.submitted",
                       actor_id=employee_id,
                       entity_type="leave_request",
                       entity_id=str(request.request_id),
                       details=json.dumps({
                           "days_requested": days_requested,
                           "status": "pending",
                       }),
                 )
            )

            db.commit()
            db.refresh(request)

            return {
                "request_id": request.request_id,
                "emp_id": request.emp_id,
                "start_date": request.start_date.isoformat(),
                "end_date": request.end_date.isoformat(),
                "days_requested": request.days_requested,
                "status": request.status,
                "reason": request.reason,
            }

    def list_pending_leave_requests(self) -> list[dict]:
        """Return all pending leave requests."""
        with SessionLocal() as db:
            requests = db.scalars(
                select(LeaveRequest)
                .where(LeaveRequest.status == "pending")
                .order_by(LeaveRequest.created_at, LeaveRequest.request_id)
            ).all()

            return [
                {
                    "request_id": item.request_id,
                    "emp_id": item.emp_id,
                    "start_date": item.start_date.isoformat(),
                    "end_date": item.end_date.isoformat(),
                    "days_requested": item.days_requested,
                    "reason": item.reason,
                    "status": item.status,
                }
                for item in requests
            ]

    def decide_leave_request(
        self,
        request_id: int,
        approver_id: str,
        decision: str,
    ) -> dict:
        """Approve or reject a pending request."""
        decision = decision.strip().lower()
        if decision not in {"approved", "rejected"}:
            raise ValueError("Decision must be 'approved' or 'rejected'.")

        with SessionLocal() as db:
            try:
                request = db.get(LeaveRequest, request_id)
                if request is None:
                    raise ValueError(
                        f"Leave request {request_id} not found."
                    )
                if request.status != "pending":
                    raise ValueError(
                        "Only pending leave requests can be decided."
                    )

                approver = db.get(Employee, approver_id)
                if approver is None:
                    raise ValueError(
                        f"Approver {approver_id} not found."
                    )

                request.status = decision
                request.approver_id = approver_id
                request.decided_at = datetime.now(UTC)

                if decision == "approved":
                    balance = db.get(LeaveBalance, request.emp_id)
                    if balance is None:
                        raise ValueError(
                            "Employee leave balance is not registered."
                        )
                    if balance.balance < request.days_requested:
                        raise ValueError("Insufficient leave balance.")

                    requested_dates = [
                        date.fromordinal(day)
                        for day in range(
                            request.start_date.toordinal(),
                            request.end_date.toordinal() + 1,
                        )
                    ]

                    existing_dates = set(
                        db.scalars(
                            select(LeaveHistory.leave_date).where(
                                LeaveHistory.emp_id == request.emp_id,
                                LeaveHistory.leave_date.in_(
                                    requested_dates
                                ),
                            )
                        ).all()
                    )
                    if existing_dates:
                        raise ValueError(
                            "Approved leave already exists for some dates."
                        )

                    latest_request_id = (
                        db.scalar(select(func.max(LeaveHistory.request_id)))
                        or 0
                    ) + 1

                    for leave_date in requested_dates:
                        db.add(
                            LeaveHistory(
                                emp_id=request.emp_id,
                                leave_date=leave_date,
                                request_id=latest_request_id,
                            )
                        )

                    balance.balance -= request.days_requested

                db.add(
                    AuditLog(
                        action=f"leave_request.{decision}",
                        actor_id=approver_id,
                        entity_type="leave_request",
                        entity_id=str(request.request_id),
                        details=json.dumps({
                        "days_requested": request.days_requested,
                        "status": decision,
                        }),
                    )
                )

                db.commit()

                return {
                    "request_id": request.request_id,
                    "emp_id": request.emp_id,
                    "status": request.status,
                    "approver_id": request.approver_id,
                    "days_requested": request.days_requested,
                    "decided_at": request.decided_at.isoformat(),
                }

            except Exception:
                db.rollback()
                raise
