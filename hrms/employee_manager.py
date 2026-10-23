
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from hrms.database import SessionLocal
from hrms.models import Employee, LeaveBalance
from hrms.schemas import EmployeeCreate


class EmployeeManager:
    """Manage employee records and leave balance initialization."""

    def get_next_emp_id(self) -> str:
        """Generate the next employee ID, such as E009."""
        with SessionLocal() as db:
            employees = db.scalars(select(Employee.emp_id)).all()

            existing_numbers = [
                int(emp_id[1:])
                for emp_id in employees
                if emp_id.startswith("E") and emp_id[1:].isdigit()
            ]

            next_number = max(existing_numbers, default=0) + 1
            return f"E{next_number:03d}"

    def add_employee(self, emp: EmployeeCreate) -> dict:
        """Create an employee and initialize their leave balance atomically."""
        with SessionLocal() as db:
            if db.get(Employee, emp.emp_id):
                raise ValueError(
                    f"Employee ID {emp.emp_id} already exists."
                )

            if emp.manager_id:
                manager = db.get(Employee, emp.manager_id)
                if manager is None:
                    raise ValueError(
                        f"Manager ID {emp.manager_id} does not exist."
                    )

            employee = Employee(
                emp_id=emp.emp_id,
                name=emp.name,
                manager_id=emp.manager_id,
                email=emp.email,
            )

            try:
                db.add(employee)
                db.flush()

                db.add(
                    LeaveBalance(
                        emp_id=employee.emp_id,
                        balance=20,
                    )
                )

                db.commit()
                db.refresh(employee)

            except IntegrityError as exc:
                db.rollback()
                raise ValueError(
                    "Employee could not be saved. Check the employee ID, "
                    "email, manager, and leave balance."
                ) from exc

            except Exception:
                db.rollback()
                raise

            return self._employee_to_dict(employee)

    def get_manager(self, emp_id: str) -> str:
        """Return an employee's manager."""
        with SessionLocal() as db:
            employee = db.get(Employee, emp_id)

            if employee is None:
                raise ValueError(
                    f"Employee {emp_id} does not exist."
                )

            if not employee.manager_id:
                return "No manager assigned."

            manager = db.get(Employee, employee.manager_id)

            if manager is None:
                return "No manager assigned."

            return f"{manager.emp_id}: {manager.name}"

    def search_employee_by_name(self, name_query: str) -> list[str]:
        """Find employee IDs by exact, case-insensitive name."""
        normalized_name = name_query.strip()

        with SessionLocal() as db:
            statement = (
                select(Employee.emp_id)
                .where(Employee.name.ilike(normalized_name))
                .order_by(Employee.emp_id)
            )
            return list(db.scalars(statement).all())

    def get_employee_details(self, emp_id: str) -> dict:
        """Return details for one employee."""
        with SessionLocal() as db:
            employee = db.get(Employee, emp_id)

            if employee is None:
                raise ValueError(
                    f"Employee {emp_id} does not exist."
                )

            return self._employee_to_dict(employee)

    def get_direct_reports(self, manager_id: str) -> list[str]:
        """Return IDs of employees reporting directly to a manager."""
        with SessionLocal() as db:
            manager = db.get(Employee, manager_id)

            if manager is None:
                raise ValueError(
                    f"Manager {manager_id} does not exist."
                )

            statement = (
                select(Employee.emp_id)
                .where(Employee.manager_id == manager_id)
                .order_by(Employee.emp_id)
            )

            return list(db.scalars(statement).all())

    @staticmethod
    def _employee_to_dict(employee: Employee) -> dict:
        """Convert a database employee into a plain dictionary."""
        return {
            "emp_id": employee.emp_id,
            "name": employee.name,
            "manager_id": employee.manager_id,
            "email": employee.email,
            "hired_date": employee.hired_date,
        }
