
from hrms.database import SessionLocal
from hrms.models import Employee, LeaveBalance

db = SessionLocal()

try:
    employee = db.get(Employee, "E009")

    if employee is None:
        print("ERROR: Employee E009 was not found.")

    else:
        balance = db.get(LeaveBalance, "E009")

        if balance is not None:
            print(f"Balance already exists: {balance.balance} days")

        else:
            db.add(LeaveBalance(emp_id="E009", balance=20))
            db.commit()
            print("Successfully initialized Akshata's leave balance: 20 days")

except Exception:
    db.rollback()
    raise

finally:
    db.close()
