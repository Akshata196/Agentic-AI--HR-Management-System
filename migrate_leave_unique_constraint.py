
from sqlalchemy import inspect, text

from hrms.database import engine

CONSTRAINT_NAME = "uq_leave_history_employee_date"
INDEX_NAME = "uq_leave_history_employee_date"


def migrate():
    inspector = inspect(engine)

    # Confirm the table exists before changing anything.
    if "leave_history" not in inspector.get_table_names():
        raise RuntimeError(
            "leave_history table does not exist. Initialize the database first."
        )

    # SQLite implements this uniqueness guarantee using a unique index.
    with engine.begin() as connection:
        duplicates = connection.execute(
            text("""
                SELECT emp_id, leave_date, COUNT(*) AS record_count
                FROM leave_history
                GROUP BY emp_id, leave_date
                HAVING COUNT(*) > 1
            """)
        ).all()

        if duplicates:
            raise RuntimeError(
                f"Migration stopped: duplicate leave dates found: {duplicates}"
            )

        existing_indexes = inspector.get_indexes("leave_history")

        if any(
            index.get("name") == INDEX_NAME
            and index.get("unique")
            for index in existing_indexes
        ):
            print("Unique leave-date index already exists; no changes needed.")
            return

        connection.execute(
            text(f"""
                CREATE UNIQUE INDEX {INDEX_NAME}
                ON leave_history (emp_id, leave_date)
            """)
        )

    print("Migration successful.")
    print("Unique employee/date constraint is now enforced by SQLite.")


if __name__ == "__main__":
    migrate()
