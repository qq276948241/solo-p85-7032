from typing import Optional
from pydantic import BaseModel, Field
from app.models.models import StoreStatus
from app.schemas.common import TimestampMixin


class StoreBase(BaseModel):
    name: str = Field(..., max_length=100, description="门店名称")
    address: str = Field(..., max_length=255, description="门店地址")
    phone: str = Field(..., max_length=20, description="联系电话")
    capacity: int = Field(default=20, ge=1, description="容纳宠物数量")
    status: StoreStatus = Field(default=StoreStatus.OPEN, description="门店状态")
    daily_rate: float = Field(default=120.0, ge=0, description="单日寄养价格")
    hourly_rate: float = Field(default=20.0, ge=0, description="小时寄养价格")


class StoreCreate(StoreBase):
    pass


class StoreUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    address: Optional[str] = Field(default=None, max_length=255)
    phone: Optional[str] = Field(default=None, max_length=20)
    capacity: Optional[int] = Field(default=None, ge=1)
    status: Optional[StoreStatus] = None
    daily_rate: Optional[float] = Field(default=None, ge=0)
    hourly_rate: Optional[float] = Field(default=None, ge=0)


class StoreResp(StoreBase, TimestampMixin):
    id: int

    model_config = {"from_attributes": True}
