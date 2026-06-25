from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
from app.schemas.common import TimestampMixin


class OwnerBase(BaseModel):
    name: str = Field(..., max_length=50, description="主人姓名")
    phone: str = Field(..., max_length=20, description="联系电话")
    wechat: Optional[str] = Field(default=None, max_length=50, description="微信号")
    email: Optional[EmailStr] = Field(default=None, description="邮箱")
    address: Optional[str] = Field(default=None, max_length=255, description="地址")
    remark: Optional[str] = Field(default=None, description="备注")


class OwnerCreate(OwnerBase):
    pass


class OwnerUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=50)
    phone: Optional[str] = Field(default=None, max_length=20)
    wechat: Optional[str] = Field(default=None, max_length=50)
    email: Optional[EmailStr] = None
    address: Optional[str] = Field(default=None, max_length=255)
    remark: Optional[str] = None


class OwnerSimpleResp(BaseModel):
    id: int
    name: str
    phone: Optional[str] = None

    model_config = {"from_attributes": True}


class OwnerResp(OwnerBase, TimestampMixin):
    id: int

    model_config = {"from_attributes": True}
