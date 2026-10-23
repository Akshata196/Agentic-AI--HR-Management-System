
import json

from sqlalchemy import select

from hrms.database import SessionLocal
from hrms.models import AuditLog


class AuditManager:
    """Read persistent audit records."""

    def list_audit_logs(
        self,
        limit: int = 50,
        action: str | None = None,
        actor_id: str | None = None,
    ) -> list[dict]:
        if not 1 <= limit <= 200:
            raise ValueError("Limit must be between 1 and 200.")

        with SessionLocal() as db:
            statement = select(AuditLog)

            if action:
                statement = statement.where(AuditLog.action == action)

            if actor_id:
                statement = statement.where(AuditLog.actor_id == actor_id)

            statement = (
                statement
                .order_by(
                    AuditLog.timestamp.desc(),
                    AuditLog.audit_id.desc(),
                )
                .limit(limit)
            )

            records = db.scalars(statement).all()

            return [
                {
                    "audit_id": item.audit_id,
                    "action": item.action,
                    "actor_id": item.actor_id,
                    "entity_type": item.entity_type,
                    "entity_id": item.entity_id,
                    "timestamp": (
                        item.timestamp.isoformat()
                        if item.timestamp
                        else None
                    ),
                    "details": json.loads(item.details or "{}"),
                }
                for item in records
            ]
