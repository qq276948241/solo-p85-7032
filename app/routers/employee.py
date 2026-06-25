from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.database import get_db
from app.models.models import Employee, EmployeeSchedule, PetAssignment, Store, Pet, Booking
from app.schemas.employee import (
    EmployeeCreate, EmployeeResp, EmployeeUpdate, EmployeeSimpleResp,
    ScheduleCreate, ScheduleResp, ScheduleUpdate,
    PetAssignmentCreate, PetAssignmentResp, PetAssignmentUpdate,
)
from app.schemas.common import ApiResponse, PageResult

router = APIRouter(prefix="/api/employees", tags=["员工管理"])


@router.post("", response_model=ApiResponse[EmployeeResp])
def create_employee(data: EmployeeCreate, db: Session = Depends(get_db)):
    if data.store_id:
        store = db.query(Store).filter(Store.id == data.store_id).first()
        if not store:
            raise HTTPException(status_code=400, detail="门店不存在")
    employee = Employee(**data.model_dump())
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return ApiResponse(data=EmployeeResp.model_validate(employee))


@router.get("", response_model=ApiResponse[PageResult[EmployeeResp]])
def list_employees(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: Optional[str] = None,
    store_id: Optional[int] = None,
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Employee)
    if keyword:
        query = query.filter(
            or_(
                Employee.name.like(f"%{keyword}%"),
                Employee.phone.like(f"%{keyword}%"),
            )
        )
    if store_id:
        query = query.filter(Employee.store_id == store_id)
    if role:
        query = query.filter(Employee.role == role)
    if is_active is not None:
        query = query.filter(Employee.is_active == is_active)
    total = query.count()
    items = (
        query.order_by(Employee.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    data = PageResult(
        total=total,
        page=page,
        page_size=page_size,
        list=[EmployeeResp.model_validate(i) for i in items],
    )
    return ApiResponse(data=data)


@router.get("/all", response_model=ApiResponse[List[EmployeeSimpleResp]])
def list_all_employees(
    store_id: Optional[int] = None,
    role: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Employee).filter(Employee.is_active == True)
    if store_id:
        query = query.filter(Employee.store_id == store_id)
    if role:
        query = query.filter(Employee.role == role)
    items = query.order_by(Employee.name.asc()).all()
    return ApiResponse(data=[EmployeeSimpleResp.model_validate(i) for i in items])


@router.get("/{employee_id}", response_model=ApiResponse[EmployeeResp])
def get_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="员工不存在")
    return ApiResponse(data=EmployeeResp.model_validate(employee))


@router.put("/{employee_id}", response_model=ApiResponse[EmployeeResp])
def update_employee(employee_id: int, data: EmployeeUpdate, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="员工不存在")
    update_data = data.model_dump(exclude_unset=True)
    if "store_id" in update_data and update_data["store_id"]:
        store = db.query(Store).filter(Store.id == update_data["store_id"]).first()
        if not store:
            raise HTTPException(status_code=400, detail="门店不存在")
    for k, v in update_data.items():
        setattr(employee, k, v)
    db.commit()
    db.refresh(employee)
    return ApiResponse(data=EmployeeResp.model_validate(employee))


@router.delete("/{employee_id}", response_model=ApiResponse)
def delete_employee(employee_id: int, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="员工不存在")
    employee.is_active = False
    db.commit()
    return ApiResponse(message="删除成功")


@router.post("/schedules", response_model=ApiResponse[ScheduleResp])
def create_schedule(data: ScheduleCreate, db: Session = Depends(get_db)):
    employee = db.query(Employee).filter(Employee.id == data.employee_id).first()
    if not employee:
        raise HTTPException(status_code=400, detail="员工不存在")
    existing = (
        db.query(EmployeeSchedule)
        .filter(
            EmployeeSchedule.employee_id == data.employee_id,
            EmployeeSchedule.work_date == data.work_date,
            EmployeeSchedule.shift_type == data.shift_type,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="该员工该日同班次已存在排班")
    schedule = EmployeeSchedule(**data.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return ApiResponse(data=ScheduleResp.model_validate(schedule))


@router.get("/schedules", response_model=ApiResponse[List[ScheduleResp]])
def list_schedules(
    employee_id: Optional[int] = None,
    store_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    query = db.query(EmployeeSchedule)
    if employee_id:
        query = query.filter(EmployeeSchedule.employee_id == employee_id)
    if store_id:
        query = query.join(Employee).filter(Employee.store_id == store_id)
    if start_date:
        query = query.filter(EmployeeSchedule.work_date >= start_date)
    if end_date:
        query = query.filter(EmployeeSchedule.work_date <= end_date)
    items = query.order_by(EmployeeSchedule.work_date.asc(), EmployeeSchedule.id.asc()).all()
    return ApiResponse(data=[ScheduleResp.model_validate(i) for i in items])


@router.put("/schedules/{schedule_id}", response_model=ApiResponse[ScheduleResp])
def update_schedule(schedule_id: int, data: ScheduleUpdate, db: Session = Depends(get_db)):
    schedule = db.query(EmployeeSchedule).filter(EmployeeSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="排班不存在")
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(schedule, k, v)
    db.commit()
    db.refresh(schedule)
    return ApiResponse(data=ScheduleResp.model_validate(schedule))


@router.delete("/schedules/{schedule_id}", response_model=ApiResponse)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = db.query(EmployeeSchedule).filter(EmployeeSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="排班不存在")
    db.delete(schedule)
    db.commit()
    return ApiResponse(message="删除成功")


@router.post("/assignments", response_model=ApiResponse[PetAssignmentResp])
def create_assignment(data: PetAssignmentCreate, db: Session = Depends(get_db)):
    pet = db.query(Pet).filter(Pet.id == data.pet_id).first()
    if not pet:
        raise HTTPException(status_code=400, detail="宠物不存在")
    employee = db.query(Employee).filter(Employee.id == data.employee_id).first()
    if not employee:
        raise HTTPException(status_code=400, detail="员工不存在")
    booking = db.query(Booking).filter(Booking.id == data.booking_id).first()
    if not booking:
        raise HTTPException(status_code=400, detail="预约不存在")
    if data.is_primary:
        db.query(PetAssignment).filter(
            PetAssignment.booking_id == data.booking_id,
            PetAssignment.pet_id == data.pet_id,
            PetAssignment.is_primary == True,
        ).update({"is_primary": False})
    assignment = PetAssignment(**data.model_dump())
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return ApiResponse(data=PetAssignmentResp.model_validate(assignment))


@router.get("/assignments", response_model=ApiResponse[List[PetAssignmentResp]])
def list_assignments(
    booking_id: Optional[int] = None,
    pet_id: Optional[int] = None,
    employee_id: Optional[int] = None,
    assigned_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    query = db.query(PetAssignment)
    if booking_id:
        query = query.filter(PetAssignment.booking_id == booking_id)
    if pet_id:
        query = query.filter(PetAssignment.pet_id == pet_id)
    if employee_id:
        query = query.filter(PetAssignment.employee_id == employee_id)
    if assigned_date:
        query = query.filter(PetAssignment.assigned_date == assigned_date)
    items = query.order_by(PetAssignment.id.desc()).all()
    return ApiResponse(data=[PetAssignmentResp.model_validate(i) for i in items])


@router.put("/assignments/{assignment_id}", response_model=ApiResponse[PetAssignmentResp])
def update_assignment(
    assignment_id: int, data: PetAssignmentUpdate, db: Session = Depends(get_db)
):
    assignment = db.query(PetAssignment).filter(PetAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="分配不存在")
    update_data = data.model_dump(exclude_unset=True)
    if update_data.get("is_primary"):
        db.query(PetAssignment).filter(
            PetAssignment.booking_id == assignment.booking_id,
            PetAssignment.pet_id == assignment.pet_id,
            PetAssignment.id != assignment_id,
            PetAssignment.is_primary == True,
        ).update({"is_primary": False})
    for k, v in update_data.items():
        setattr(assignment, k, v)
    db.commit()
    db.refresh(assignment)
    return ApiResponse(data=PetAssignmentResp.model_validate(assignment))


@router.delete("/assignments/{assignment_id}", response_model=ApiResponse)
def delete_assignment(assignment_id: int, db: Session = Depends(get_db)):
    assignment = db.query(PetAssignment).filter(PetAssignment.id == assignment_id).first()
    if not assignment:
        raise HTTPException(status_code=404, detail="分配不存在")
    db.delete(assignment)
    db.commit()
    return ApiResponse(message="删除成功")


@router.get("/{employee_id}/assigned-pets", response_model=ApiResponse[List[PetAssignmentResp]])
def get_employee_assigned_pets(
    employee_id: int,
    assigned_date: Optional[date] = None,
    db: Session = Depends(get_db),
):
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        raise HTTPException(status_code=404, detail="员工不存在")
    query = db.query(PetAssignment).filter(PetAssignment.employee_id == employee_id)
    if assigned_date:
        query = query.filter(PetAssignment.assigned_date == assigned_date)
    items = query.order_by(PetAssignment.id.desc()).all()
    return ApiResponse(data=[PetAssignmentResp.model_validate(i) for i in items])
