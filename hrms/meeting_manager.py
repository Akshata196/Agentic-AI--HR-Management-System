# from typing import List, Dict
# from collections import defaultdict
# from datetime import datetime
# from hrms.schemas import MeetingCreate, MeetingCancelRequest

# class MeetingManager:
#     def __init__(self):
#         self.meetings: Dict[str, List[Dict[str, str]]] = defaultdict(list)

#     def schedule_meeting(self, req: MeetingCreate) -> str:
#         dt_str = req.meeting_dt.isoformat()
#         try:
#             datetime.fromisoformat(dt_str)
#         except ValueError:
#             raise ValueError("Invalid datetime format; use ISO format.")
#         emp_id = req.emp_id
#         if any(m["date"] == dt_str for m in self.meetings[emp_id]):
#             raise ValueError(f"Conflict: {emp_id} already has a meeting at {dt_str}.")
#         self.meetings[emp_id].append({"date": dt_str, "topic": req.topic})
#         return f"Meeting scheduled for {emp_id} on {dt_str} about '{req.topic}'."

#     def get_meetings(self, employee_id: str) -> List[Dict[str, str]]:
#         return sorted(self.meetings.get(employee_id, []), key=lambda m: m["date"])

#     def cancel_meeting(self, req: MeetingCancelRequest) -> str:
#         emp_id = req.emp_id
#         dt_str = req.meeting_dt.isoformat()
#         original = list(self.meetings.get(emp_id, []))
#         self.meetings[emp_id] = [m for m in original if not (
#             m["date"] == dt_str and (req.topic is None or m["topic"] == req.topic)
#         )]
#         if len(self.meetings[emp_id]) == len(original):
#             raise ValueError("No matching meeting to cancel.")
#         return f"Canceled meeting for {emp_id} on {dt_str}{f' about {req.topic}' if req.topic else ''}."





from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from hrms.database import SessionLocal
from hrms.models import Employee, Meeting, MeetingAttendee
from hrms.schemas import MeetingBase, MeetingCancelRequest


class MeetingManager:
    """Manage meetings and attendees using SQLAlchemy."""

    
    def schedule_meeting(self, req: MeetingBase) -> str:
        """Schedule one meeting with one or more attendees."""
        meeting_dt = req.meeting_dt.replace(tzinfo=None)

        # Include the primary employee and all additional attendees.
        attendee_ids = list(dict.fromkeys([req.emp_id, *req.attendee_ids]))

        with SessionLocal() as db:
            employees = db.scalars(
                select(Employee).where(Employee.emp_id.in_(attendee_ids))
            ).all()
            found_ids = {employee.emp_id for employee in employees}
            missing_ids = set(attendee_ids) - found_ids

            if missing_ids:
                raise ValueError(
                    f"Employee(s) not found: {', '.join(sorted(missing_ids))}"
                )

            # Prevent scheduling conflicts for every attendee.
            statement = (
                select(Meeting)
                .join(MeetingAttendee)
                .where(
                    MeetingAttendee.emp_id.in_(attendee_ids),
                    Meeting.meeting_dt == meeting_dt,
                )
            )
            conflicting = db.scalars(statement).first()

            if conflicting:
                raise ValueError(
                    f"One or more attendees already have a meeting "
                    f"at {meeting_dt.isoformat()}."
                )

            meeting = Meeting(
                meeting_dt=meeting_dt,
                topic=req.topic,
            )
            meeting.attendees.extend(
                MeetingAttendee(emp_id=emp_id)
                for emp_id in attendee_ids
            )
            db.add(meeting)

            try:
                db.commit()
                db.refresh(meeting)
            except IntegrityError as exc:
                db.rollback()
                raise ValueError(
                    "Meeting could not be saved. Check the employee IDs "
                    "and attendee records."
                ) from exc

            return (
                f"Meeting '{meeting.topic}' scheduled for "
                f"{meeting.meeting_dt.isoformat()} "
                f"with attendees {', '.join(attendee_ids)} "
                f"(Meeting ID: {meeting.meeting_id})."
            )


    def get_meetings(self, employee_id: str) -> list[dict]:
        """Return meetings for an employee, including attendee IDs."""
        with SessionLocal() as db:
            employee = db.get(Employee, employee_id)
            if employee is None:
                raise ValueError(
                    f"Employee {employee_id} not found."
                )

            statement = (
                select(Meeting)
                .join(MeetingAttendee)
                .where(MeetingAttendee.emp_id == employee_id)
                .options(selectinload(Meeting.attendees))
                .order_by(Meeting.meeting_dt)
            )
            meetings = db.scalars(statement).unique().all()

            return [
                {
                    "meeting_id": meeting.meeting_id,
                    "date": meeting.meeting_dt.isoformat(),
                    "topic": meeting.topic,
                    "attendees": [
                        attendee.emp_id
                        for attendee in meeting.attendees
                    ],
                }
                for meeting in meetings
            ]

    def cancel_meeting(self, req: MeetingCancelRequest) -> str:
        """Cancel a matching meeting for an employee."""
        meeting_dt = req.meeting_dt.replace(tzinfo=None)

        with SessionLocal() as db:
            statement = (
                select(Meeting)
                .join(MeetingAttendee)
                .where(
                    MeetingAttendee.emp_id == req.emp_id,
                    Meeting.meeting_dt == meeting_dt,
                )
                .options(selectinload(Meeting.attendees))
            )

            if req.topic:
                statement = statement.where(Meeting.topic == req.topic)

            meeting = db.scalars(statement).unique().first()

            if meeting is None:
                raise ValueError(
                    f"No matching meeting found for employee {req.emp_id}."
                )

            # Remove the entire meeting and its attendee associations.
            # This matches the original manager's meeting-removal behavior.
            meeting_id = meeting.meeting_id
            topic = meeting.topic
            db.delete(meeting)
            db.commit()

            return (
                f"Meeting '{topic}' at {meeting_dt.isoformat()} "
                f"(Meeting ID: {meeting_id}) cancelled."
            )
