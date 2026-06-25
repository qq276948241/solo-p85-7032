from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field
from app.models.models import FeedingStatus, StoolStatus
from app.schemas.common import TimestampMixin


class CarePhotoBase(BaseModel):
    photo_url: str = Field(..., max_length=255, description="照片URL")
    photo_type: Optional[str] = Field(default=None, max_length=50, description="照片类型")
    caption: Optional[str] = Field(default=None, max_length=255, description="说明")


class CarePhotoCreate(CarePhotoBase):
    care_record_id: int


class CarePhotoResp(CarePhotoBase):
    id: int
    created_at: Optional[date] = None

    model_config = {"from_attributes": True}


class CareRecordBase(BaseModel):
    booking_id: int = Field(..., description="预约ID")
    pet_id: int = Field(..., description="宠物ID")
    caretaker_id: int = Field(..., description="护理员ID")
    record_date: Optional[date] = Field(default=None, description="记录日期")
    record_time: str = Field(..., max_length=10, description="记录时间 HH:MM")

    feeding: bool = Field(default=False, description="是否喂食")
    feeding_status: Optional[FeedingStatus] = Field(default=None, description="进食状态")
    feeding_food: Optional[str] = Field(default=None, max_length=255, description="食物")
    feeding_amount: Optional[str] = Field(default=None, max_length=50, description="食量")
    feeding_note: Optional[str] = Field(default=None, max_length=255, description="喂食备注")

    walking: bool = Field(default=False, description="是否遛弯")
    walking_duration: Optional[int] = Field(default=None, ge=0, description="遛弯时长(分钟)")
    walking_note: Optional[str] = Field(default=None, max_length=255, description="遛弯备注")

    stool: bool = Field(default=False, description="是否排便")
    stool_status: Optional[StoolStatus] = Field(default=None, description="便便状态")
    stool_count: int = Field(default=0, ge=0, description="排便次数")
    stool_note: Optional[str] = Field(default=None, max_length=255, description="便便备注")

    water: bool = Field(default=False, description="是否喂水")
    water_note: Optional[str] = Field(default=None, max_length=255, description="喂水备注")

    grooming: bool = Field(default=False, description="是否美容/洗澡")
    grooming_note: Optional[str] = Field(default=None, max_length=255, description="美容备注")

    mood: Optional[str] = Field(default=None, max_length=50, description="精神状态")
    temperature: Optional[float] = Field(default=None, description="体温")
    weight: Optional[float] = Field(default=None, description="体重")

    general_note: Optional[str] = Field(default=None, description="总体情况")
    abnormal_flag: bool = Field(default=False, description="是否异常")
    abnormal_note: Optional[str] = Field(default=None, description="异常情况说明")


class CareRecordCreate(CareRecordBase):
    photos: List[CarePhotoBase] = Field(default=[], description="照片列表")


class CareRecordUpdate(BaseModel):
    feeding: Optional[bool] = None
    feeding_status: Optional[FeedingStatus] = None
    feeding_food: Optional[str] = Field(default=None, max_length=255)
    feeding_amount: Optional[str] = Field(default=None, max_length=50)
    feeding_note: Optional[str] = Field(default=None, max_length=255)

    walking: Optional[bool] = None
    walking_duration: Optional[int] = Field(default=None, ge=0)
    walking_note: Optional[str] = Field(default=None, max_length=255)

    stool: Optional[bool] = None
    stool_status: Optional[StoolStatus] = None
    stool_count: Optional[int] = Field(default=None, ge=0)
    stool_note: Optional[str] = Field(default=None, max_length=255)

    water: Optional[bool] = None
    water_note: Optional[str] = Field(default=None, max_length=255)

    grooming: Optional[bool] = None
    grooming_note: Optional[str] = Field(default=None, max_length=255)

    mood: Optional[str] = Field(default=None, max_length=50)
    temperature: Optional[float] = None
    weight: Optional[float] = None

    general_note: Optional[str] = None
    abnormal_flag: Optional[bool] = None
    abnormal_note: Optional[str] = None


class CareRecordResp(CareRecordBase):
    id: int
    photos: List[CarePhotoResp] = []
    created_at: Optional[date] = None
    updated_at: Optional[date] = None

    model_config = {"from_attributes": True}


class CareRecordListResp(BaseModel):
    id: int
    booking_id: int
    pet_id: int
    caretaker_id: int
    record_date: date
    record_time: str
    feeding: bool
    walking: bool
    stool: bool
    water: bool
    grooming: bool
    abnormal_flag: bool
    general_note: Optional[str] = None
    photos: List[CarePhotoResp] = []
    created_at: Optional[date] = None

    model_config = {"from_attributes": True}
