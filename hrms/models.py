
from datetime import date, datetime, timezone

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from hrms.database import Base


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


class Employee(Base):
    __tablename__ = "employees"

    emp_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    manager_id: Mapped[str | None] = mapped_column(
        ForeignKey("employees.emp_id"), nullable=True
    )
    email: Mapped[str | None] = mapped_column(
        String(254), unique=True, nullable=True
    )
    hired_date: Mapped[date] = mapped_column(
        Date, default=date.today, nullable=False
    )

    manager: Mapped["Employee | None"] = relationship(
        "Employee",
        remote_side="Employee.emp_id",
        back_populates="direct_reports",
    )
    direct_reports: Mapped[list["Employee"]] = relationship(
        "Employee",
        back_populates="manager",
    )
    leave_balance: Mapped["LeaveBalance | None"] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
        uselist=False,
    )
    leave_history: Mapped[list["LeaveHistory"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    meeting_attendances: Mapped[list["MeetingAttendee"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="employee",
        cascade="all, delete-orphan",
    )


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    emp_id: Mapped[str] = mapped_column(
        ForeignKey("employees.emp_id", ondelete="CASCADE"),
        primary_key=True,
    )
    balance: Mapped[int] = mapped_column(Integer, nullable=False, default=20)

    employee: Mapped["Employee"] = relationship(back_populates="leave_balance")


class LeaveHistory(Base):
    __tablename__ = "leave_history"

    __table_args__ = (
        UniqueConstraint(
            "emp_id",
            "leave_date",
            name="uq_leave_history_employee_date",
        ),
    )

    history_id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )
    emp_id: Mapped[str] = mapped_column(
        ForeignKey("employees.emp_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    leave_date: Mapped[date] = mapped_column(Date, nullable=False)
    request_id: Mapped[int] = mapped_column(Integer, nullable=False)

    employee: Mapped["Employee"] = relationship(
        back_populates="leave_history"
    )


class Meeting(Base):
    __tablename__ = "meetings"

    meeting_id: Mapped[int] = mapped_column(
        primary_key=True, autoincrement=True
    )
    meeting_dt: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, index=True
    )
    topic: Mapped[str] = mapped_column(String(250), nullable=False)

    attendees: Mapped[list["MeetingAttendee"]] = relationship(
        back_populates="meeting",
        cascade="all, delete-orphan",
    )


class MeetingAttendee(Base):
    __tablename__ = "meeting_attendees"

    __table_args__ = (
        UniqueConstraint("meeting_id", "emp_id", name="uq_meeting_attendee"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(
        ForeignKey("meetings.meeting_id", ondelete="CASCADE"),
        nullable=False,
    )
    emp_id: Mapped[str] = mapped_column(
        ForeignKey("employees.emp_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    meeting: Mapped["Meeting"] = relationship(back_populates="attendees")
    employee: Mapped["Employee"] = relationship(
        back_populates="meeting_attendances"
    )


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    emp_id: Mapped[str] = mapped_column(
        ForeignKey("employees.emp_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    item: Mapped[str] = mapped_column(String(150), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="Open"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    employee: Mapped["Employee"] = relationship(back_populates="tickets")


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    request_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    emp_id: Mapped[str] = mapped_column(
        ForeignKey("employees.emp_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    days_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(
        String(500), default="", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )
    approver_id: Mapped[str | None] = mapped_column(
        ForeignKey("employees.emp_id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    audit_id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    actor_id: Mapped[str | None] = mapped_column(
        String(20), nullable=True, index=True
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_id: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )
    details: Mapped[str] = mapped_column(
        Text, nullable=False, default="{}"
    )
