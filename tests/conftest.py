
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hrms.database import Base
import hrms.models  # Register all ORM models


@pytest.fixture(autouse=True)
def isolated_test_database(tmp_path, monkeypatch):
    """Give each test its own temporary SQLite database."""
    test_db_path = tmp_path / "test_hrms.db"

    test_engine = create_engine(
        f"sqlite:///{test_db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    try:
        Base.metadata.create_all(test_engine)

        TestSessionLocal = sessionmaker(
            bind=test_engine,
            autoflush=False,
            expire_on_commit=False,
        )

        # Patch the database module's session factory.
        import hrms.database as database_module

        monkeypatch.setattr(
            database_module, "SessionLocal", TestSessionLocal
        )

        # Patch session factories imported by the managers.
        import hrms.employee_manager as employee_module
        import hrms.leave_manager as leave_module
        import hrms.meeting_manager as meeting_module
        import hrms.ticket_manager as ticket_module

        for module in (
            employee_module,
            leave_module,
            meeting_module,
            ticket_module,
        ):
            if hasattr(module, "SessionLocal"):
                monkeypatch.setattr(
                    module, "SessionLocal", TestSessionLocal
                )

        yield

    finally:
        test_engine.dispose()
