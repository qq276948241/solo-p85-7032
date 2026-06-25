from typing import Optional, List
from datetime import date
from pydantic import BaseModel, Field
from app.models.models import PetGender, VaccineStatus
from app.schemas.common import TimestampMixin


class PetBase(BaseModel):
    name: str = Field(..., max_length=50, description="宠物名称")
    species: str = Field(..., max_length=50, description="物种，如狗/猫/兔")
    breed: Optional[str] = Field(default=None, max_length=100, description="品种")
    gender: PetGender = Field(default=PetGender.UNKNOWN, description="性别")
    birthday: Optional[date] = Field(default=None, description="生日")
    weight: Optional[float] = Field(default=None, ge=0, description="体重 kg")
    color: Optional[str] = Field(default=None, max_length=50, description="毛色")
    chip_number: Optional[str] = Field(default=None, max_length=50, description="芯片号")
    avatar_url: Optional[str] = Field(default=None, max_length=255, description="头像URL")
    allergies: Optional[str] = Field(default=None, description="过敏史")
    dietary_notes: Optional[str] = Field(default=None, description="饮食注意")
    behavioral_notes: Optional[str] = Field(default=None, description="行为注意")
    medical_notes: Optional[str] = Field(default=None, description="医疗注意")
    remark: Optional[str] = Field(default=None, description="备注")


class PetCreate(PetBase):
    owner_id: int = Field(..., description="主人ID")


class PetUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=50)
    species: Optional[str] = Field(default=None, max_length=50)
    breed: Optional[str] = Field(default=None, max_length=100)
    gender: Optional[PetGender] = None
    birthday: Optional[date] = None
    weight: Optional[float] = Field(default=None, ge=0)
    color: Optional[str] = Field(default=None, max_length=50)
    chip_number: Optional[str] = Field(default=None, max_length=50)
    avatar_url: Optional[str] = Field(default=None, max_length=255)
    owner_id: Optional[int] = None
    allergies: Optional[str] = None
    dietary_notes: Optional[str] = None
    behavioral_notes: Optional[str] = None
    medical_notes: Optional[str] = None
    remark: Optional[str] = None
    is_active: Optional[bool] = None


class PetSimpleResp(BaseModel):
    id: int
    name: str
    species: Optional[str] = None
    breed: Optional[str] = None

    model_config = {"from_attributes": True}


class VaccineBase(BaseModel):
    name: str = Field(..., max_length=100, description="疫苗名称")
    manufacturer: Optional[str] = Field(default=None, max_length=100, description="生产厂家")
    batch_number: Optional[str] = Field(default=None, max_length=50, description="批号")
    vaccinated_date: date = Field(..., description="接种日期")
    expiry_date: date = Field(..., description="到期日期")
    status: VaccineStatus = Field(default=VaccineStatus.VALID, description="疫苗状态")
    certificate_url: Optional[str] = Field(default=None, max_length=255, description="证书URL")
    remark: Optional[str] = Field(default=None, description="备注")


class VaccineCreate(VaccineBase):
    pet_id: int


class VaccineUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    manufacturer: Optional[str] = Field(default=None, max_length=100)
    batch_number: Optional[str] = Field(default=None, max_length=50)
    vaccinated_date: Optional[date] = None
    expiry_date: Optional[date] = None
    status: Optional[VaccineStatus] = None
    certificate_url: Optional[str] = Field(default=None, max_length=255)
    remark: Optional[str] = None


class VaccineResp(VaccineBase):
    id: int
    pet_id: int
    created_at: Optional[date] = None

    model_config = {"from_attributes": True}


class PetResp(PetBase, TimestampMixin):
    id: int
    owner_id: int
    is_active: bool
    owner: Optional["OwnerSimpleResp"] = None
    vaccines: List[VaccineResp] = []

    model_config = {"from_attributes": True}


from app.schemas.owner import OwnerSimpleResp
PetResp.model_rebuild()
