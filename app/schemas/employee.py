from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field
from app.models.models import EmployeeRole, ShiftType
from app.schemas.common import TimestampMixin


class EmployeeBase(BaseModel):
    name: str = Field(..., max_length=50, description="员工姓名")
    phone: str = Field(..., max_length=20, description="电话")
    id_card: Optional[str] = Field(default=None, max_length=18, description="身份证号")
    role: EmployeeRole = Field(default=EmployeeRole.CARETAKER, description="角色")
    store_id: Optional[int] = Field(default=None, description="所属门店")
    avatar_url: Optional[str] = Field(default=None, max_length=255, description="头像URL")
    hire_date: Optional[date] = Field(default=None, description="入职日期")
    remark: Optional[str] = Field(default=None, description="备注")


class EmployeeCreate(EmployeeBase):
    pass


class EmployeeUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=50)
    phone: Optional[str] = Field(default=None, max_length=20)
    id_card: Optional[str] = Field(default=None, max_length=18)
    role: Optional[EmployeeRole] = None
    store_id: Optional[int] = None
    avatar_url: Optional[str] = Field(default=None, max_length=255)
    hire_date: Optional[date] = None
    is_active: Optional[bool] = None
    remark: Optional[str] = None


class EmployeeSimpleResp(BaseModel):
    id: int
    name: str
    role: Optional[EmployeeRole] = None
    store_id: Optional[int] = None

    model_config = {"from_attributes": True}


class EmployeeResp(EmployeeBase, TimestampMixin):
    id: int
    is_active: bool

    model_config = {"from_attributes": True}


class ScheduleBase(BaseModel):
    employee_id: int = Field(..., description="员工ID")
    work_date: date = Field(..., description="工作日期")
    shift_type: ShiftType = Field(..., description="班次")
    start_time: Optional[str] = Field(default=None, max_length=10, description="开始时间 HH:MM")
    end_time: Optional[str] = Field(default=None, max_length=10, description="结束时间 HH:MM")
    remark: Optional[str] = Field(default=None, max_length=255, description="备注")


class ScheduleCreate(ScheduleBase):
    pass


class ScheduleUpdate(BaseModel):
    shift_type: Optional[ShiftType] = None
    start_time: Optional[str] = Field(default=None, max_length=10)
    end_time: Optional[str] = Field(default=None, max_length=10)
    remark: Optional[str] = Field(default=None, max_length=255)


class ScheduleResp(ScheduleBase):
    id: int
    employee: Optional[EmployeeSimpleResp] = None

    model_config = {"from_attributes": True}


class PetAssignmentBase(BaseModel):
    pet_id: int = Field(..., description="宠物ID")
    employee_id: int = Field(..., description="护理员ID")
    booking_id: int = Field(..., description="预约ID")
    assigned_date: Optional[date] = Field(default=None, description="分配日期")
    is_primary: bool = Field(default=True, description="是否主要负责人")
    remark: Optional[str] = Field(default=None, max_length=255, description="备注")


class PetAssignmentCreate(PetAssignmentBase):
    pass


class PetAssignmentUpdate(BaseModel):
    employee_id: Optional[int] = None
    is_primary: Optional[bool] = None
    remark: Optional[str] = Field(default=None, max_length=255)


class PetAssignmentResp(PetAssignmentBase):
    id: int
    pet: Optional["PetSimpleResp"] = None
    employee: Optional[EmployeeSimpleResp] = None

    model_config = {"from_attributes": True}


from app.schemas.pet import PetSimpleResp
PetAssignmentResp.model_rebuild()
