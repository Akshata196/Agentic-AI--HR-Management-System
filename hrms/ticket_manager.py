
from typing import List, Dict, Optional
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from hrms.database import SessionLocal
from hrms.models import Employee, Ticket
from hrms.schemas import TicketCreate, TicketStatusUpdate


class TicketManager:
    def create_ticket(self, req: TicketCreate) -> str:
        with SessionLocal() as db:
            employee = db.get(Employee, req.emp_id)
            if employee is None:
                raise ValueError(f"Employee '{req.emp_id}' not found.")

            # Generate the next ticket ID using IDs already stored in the DB.
            existing_ids = db.scalars(select(Ticket.ticket_id)).all()
            max_number = max(
                (
                    int(ticket_id[1:])
                    for ticket_id in existing_ids
                    if ticket_id.startswith("T")
                    and ticket_id[1:].isdigit()
                ),
                default=0,
            )
            ticket_id = f"T{max_number + 1:04d}"

            now = datetime.now(timezone.utc)
            ticket = Ticket(
                ticket_id=ticket_id,
                emp_id=req.emp_id,
                item=req.item,
                reason=req.reason,
                status="Open",
                created_at=now,
                updated_at=now,
            )
            db.add(ticket)

            try:
                db.commit()
            except IntegrityError as exc:
                db.rollback()
                raise ValueError(
                    "Could not create ticket due to a database constraint."
                ) from exc

            return f"Ticket {ticket_id} created for {req.emp_id}."

    def update_ticket_status(
        self,
        req: TicketStatusUpdate,
        ticket_id: str,
    ) -> str:
        with SessionLocal() as db:
            ticket = db.get(Ticket, ticket_id)

            if ticket is None:
                raise ValueError(f"Ticket '{ticket_id}' not found.")

            ticket.status = req.status
            ticket.updated_at = datetime.now(timezone.utc)

            db.commit()
            return f"Ticket {ticket_id} status updated to {req.status}."

    def list_tickets(
        self,
        employee_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        with SessionLocal() as db:
            statement = select(Ticket).order_by(Ticket.created_at.desc())

            if employee_id:
                statement = statement.where(Ticket.emp_id == employee_id)

            if status:
                statement = statement.where(Ticket.status.ilike(status))

            tickets = db.scalars(statement).all()

            return [
                {
                    "ticket_id": ticket.ticket_id,
                    "emp_id": ticket.emp_id,
                    "item": ticket.item,
                    "reason": ticket.reason,
                    "status": ticket.status,
                    "created_at": (
                        ticket.created_at.isoformat()
                        if ticket.created_at
                        else ""
                    ),
                    "updated_at": (
                        ticket.updated_at.isoformat()
                        if ticket.updated_at
                        else ""
                    ),
                }
                for ticket in tickets
            ]
