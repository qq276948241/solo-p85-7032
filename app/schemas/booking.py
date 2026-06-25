from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field, field_validator
from app.models.models import BookingStatus, BookingType
from app.schemas.common import TimestampMixin


class BookingBase(BaseModel):
    pet_id: int = Field(..., description="宠物ID")
    store_id: int = Field(..., description="门店ID")
    booking_type: BookingType = Field(default=BookingType.BOARDING, description="寄养类型")
    checkin_date: date = Field(..., description="入住日期")
    checkout_date: date = Field(..., description="离店日期")
    checkin_time: Optional[str] = Field(default=None, max_length=10, description="入住时间")
    checkout_time: Optional[str] = Field(default=None, max_length=10, description="离店时间")
    extra_fee: float = Field(default=0.0, ge=0, description="额外费用")
    discount: float = Field(default=0.0, ge=0, description="折扣")
    paid_amount: float = Field(default=0.0, ge=0, description="已付金额")
    pickup_person: Optional[str] = Field(default=None, max_length=50, description="接宠人")
    pickup_phone: Optional[str] = Field(default=None, max_length=20, description="接宠人电话")
    dropoff_person: Optional[str] = Field(default=None, max_length=50, description="送宠人")
    dropoff_phone: Optional[str] = Field(default=None, max_length=20, description="送宠人电话")
    items_brought: Optional[str] = Field(default=None, description="携带物品")
    remark: Optional[str] = Field(default=None, description="备注")

    @field_validator("checkout_date")
    def checkout_must_after_checkin(cls, v, values):
        checkin = values.data.get("checkin_date")
        if checkin and v < checkin:
            raise ValueError("离店日期必须晚于或等于入住日期")
        return v


class BookingCreate(BookingBase):
    pass


class BookingUpdate(BaseModel):
    booking_type: Optional[BookingType] = None
    checkin_date: Optional[date] = None
    checkout_date: Optional[date] = None
    checkin_time: Optional[str] = Field(default=None, max_length=10)
    checkout_time: Optional[str] = Field(default=None, max_length=10)
    extra_fee: Optional[float] = Field(default=None, ge=0)
    discount: Optional[float] = Field(default=None, ge=0)
    paid_amount: Optional[float] = Field(default=None, ge=0)
    status: Optional[BookingStatus] = None
    pickup_person: Optional[str] = Field(default=None, max_length=50)
    pickup_phone: Optional[str] = Field(default=None, max_length=20)
    dropoff_person: Optional[str] = Field(default=None, max_length=50)
    dropoff_phone: Optional[str] = Field(default=None, max_length=20)
    items_brought: Optional[str] = None
    remark: Optional[str] = None


class BookingSimpleResp(BaseModel):
    id: int
    booking_no: str
    status: BookingStatus

    model_config = {"from_attributes": True}


class BookingResp(BookingBase, TimestampMixin):
    id: int
    booking_no: str
    total_days: int
    daily_rate: float
    total_amount: float
    status: BookingStatus
    pet: Optional["PetSimpleResp"] = None
    store: Optional["StoreSimpleResp"] = None

    model_config = {"from_attributes": True}


from app.schemas.pet import PetSimpleResp
from app.schemas.store import StoreResp as StoreSimpleResp
BookingResp.model_rebuild()


class FeeCalcReq(BaseModel):
    store_id: int
    checkin_date: date
    checkout_date: date
    booking_type: BookingType = BookingType.BOARDING
    extra_fee: float = 0.0
    discount: float = 0.0


class FeeCalcResp(BaseModel):
    total_days: int
    daily_rate: float
    subtotal: float
    extra_fee: float
    discount: float
    total_amount: float


class BookingAvailabilityReq(BaseModel):
    store_id: int
    checkin_date: date
    checkout_date: date
    exclude_booking_id: Optional[int] = None


class BookingAvailabilityResp(BaseModel):
    available: bool
    current_count: int
    capacity: int
    message: str
