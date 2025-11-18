from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from faker import Faker
import random

# Initialize FastAPI app
app = FastAPI(title="Simple HR API", version="1.0.0")

fake = Faker()

# Pydantic Models
class Employee(BaseModel):
    employee_id: int
    first_name: str
    last_name: str
    email: str
    department: str
    designation: str
    phone: str
    bank_name: str
    bank_account_number: str
    account_balance: float


class BalanceUpdate(BaseModel):
    employee_id: Optional[int] = None
    name: Optional[str] = None
    # Either set an absolute new balance or provide a delta to add/subtract
    new_balance: Optional[float] = None
    delta: Optional[float] = None

# In-memory employee database
employees_db: List[Employee] = []

# Configuration
DEPARTMENTS = ["Engineering", "Sales", "Marketing", "HR", "Finance", "Operations"]
DESIGNATIONS = ["Manager", "Senior Engineer", "Engineer", "Analyst", "Specialist", "Coordinator"]
BANKS = ["Chase Bank", "Bank of America", "Wells Fargo", "Citibank", "US Bank"]

def generate_employees(count: int = 15):
    """Generate toy employees"""
    employees = []
    
    for i in range(1, count + 1):
        first_name = fake.first_name()
        last_name = fake.last_name()
        
        employee = Employee(
            employee_id=i,
            first_name=first_name,
            last_name=last_name,
            email=f"{first_name.lower()}.{last_name.lower()}@company.com",
            department=random.choice(DEPARTMENTS),
            designation=random.choice(DESIGNATIONS),
            phone=fake.phone_number(),
            bank_name=random.choice(BANKS),
            bank_account_number=fake.bban(),
            account_balance=round(random.uniform(5000, 50000), 2)
        )
        employees.append(employee)
    
    return employees

# Startup: Populate database
@app.on_event("startup")
async def startup_event():
    global employees_db
    employees_db = generate_employees(15)
    print(f"✓ Generated {len(employees_db)} toy employees")

# API Endpoints

@app.get("/")
async def root():
    """API root"""
    return {
        "message": "Simple HR API",
        "total_employees": len(employees_db),
        "endpoints": {
            "list_names": "/employees/names",
            "list_all": "/employees",
            "search_by_name": "/employees/search/by-name?name=John",
            "get_by_id": "/employees/{id}"
        }
    }

@app.get("/employees", response_model=List[Employee])
async def list_all_employees():
    """List all employees"""
    return employees_db

@app.get("/employees/{employee_id}", response_model=Employee)
async def get_employee_by_id(employee_id: int):
    """Get employee by ID"""
    employee = next((emp for emp in employees_db if emp.employee_id == employee_id), None)
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    return employee

@app.get("/employees/names")
async def list_employee_names():
    """Get a simple list of all employee names and IDs"""
    return [
        {
            "employee_id": emp.employee_id,
            "name": f"{emp.first_name} {emp.last_name}",
            "department": emp.department
        }
        for emp in employees_db
    ]

@app.get("/employees/search/by-name", response_model=List[Employee])
async def search_employees_by_name(name: str = Query(..., min_length=2, description="Search by first or last name")):
    """Search employees by name (partial match supported)"""
    name_lower = name.lower()
    
    results = [
        emp for emp in employees_db
        if name_lower in emp.first_name.lower() 
        or name_lower in emp.last_name.lower()
        or name_lower in f"{emp.first_name} {emp.last_name}".lower()
    ]
    
    if not results:
        raise HTTPException(status_code=404, detail=f"No employees found matching '{name}'")
    
    return results


def _find_employee(employee_id: Optional[int] = None, name: Optional[str] = None) -> Optional[Employee]:
    """Helper: find an employee by id or by name (first, last, or full name).

    Name matching is case-insensitive. If both provided, id takes precedence.
    Returns the first match or None.
    """
    if employee_id is not None:
        return next((emp for emp in employees_db if emp.employee_id == employee_id), None)

    if name:
        name_lower = name.strip().lower()
        # Exact full-name match first
        full_match = next((emp for emp in employees_db if f"{emp.first_name} {emp.last_name}".lower() == name_lower), None)
        if full_match:
            return full_match

        # Then try first or last name match
        return next((emp for emp in employees_db if emp.first_name.lower() == name_lower or emp.last_name.lower() == name_lower), None)

    return None


@app.get("/employees/balance")
async def get_employee_balance(employee_id: Optional[int] = None, name: Optional[str] = None):
    """Return account balance for employee looked up by `employee_id` or `name`.

    Provide either `employee_id` or `name` as query parameter. `employee_id` takes precedence.
    """
    if employee_id is None and (not name):
        raise HTTPException(status_code=400, detail="Provide `employee_id` or `name` query parameter")

    emp = _find_employee(employee_id=employee_id, name=name)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    return {
        "employee_id": emp.employee_id,
        "name": f"{emp.first_name} {emp.last_name}",
        "account_balance": emp.account_balance,
        "bank_name": emp.bank_name,
        "bank_account_number": emp.bank_account_number,
    }


@app.post("/employees/balance")
async def update_employee_balance(payload: BalanceUpdate):
    """Change an employee's account balance.

    Provide either `employee_id` or `name` and either `new_balance` or `delta` in JSON body.
    - `new_balance` sets the balance outright.
    - `delta` applies a relative change (positive or negative).
    """
    if payload.employee_id is None and (not payload.name):
        raise HTTPException(status_code=400, detail="Provide `employee_id` or `name` in payload")

    if payload.new_balance is None and payload.delta is None:
        raise HTTPException(status_code=400, detail="Provide `new_balance` or `delta` in payload")

    emp = _find_employee(employee_id=payload.employee_id, name=payload.name)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    # Apply change
    if payload.new_balance is not None:
        emp.account_balance = float(payload.new_balance)
    else:
        emp.account_balance = float(round(emp.account_balance + float(payload.delta), 2))

    return {
        "employee_id": emp.employee_id,
        "name": f"{emp.first_name} {emp.last_name}",
        "account_balance": emp.account_balance,
    }

# Run with: uvicorn filename:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)