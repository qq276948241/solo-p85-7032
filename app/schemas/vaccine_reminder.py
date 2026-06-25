from typing import Optional, List
from datetime import date, datetime
from pydantic import BaseModel, Field

from app.models.models import ReminderStatus, ReminderChannel


class VaccineDueItem(BaseModel):
    """单条即将到期/已过期的疫苗提醒明细"""

    vaccine_id: int = Field(description="疫苗记录ID")
    pet_id: int = Field(description="宠物ID")
    pet_name: str = Field(description="宠物名字")
    pet_species: Optional[str] = Field(default=None, description="物种（狗/猫/...）")
    pet_breed: Optional[str] = Field(default=None, description="品种")
    pet_avatar_url: Optional[str] = Field(default=None, description="宠物头像")

    owner_id: int = Field(description="主人ID")
    owner_name: str = Field(description="主人姓名")
    owner_phone: str = Field(description="主人联系电话")
    owner_wechat: Optional[str] = Field(default=None, description="主人微信号")

    store_id: Optional[int] = Field(default=None, description="最近预约关联门店ID（可能为空）")
    store_name: Optional[str] = Field(default=None, description="最近预约关联门店名")

    vaccine_name: str = Field(description="该打哪种疫苗")
    vaccinated_date: date = Field(description="上次接种时间")
    expiry_date: date = Field(description="到期时间")
    days_to_expiry: int = Field(description="距离到期天数，负数表示已过期天数")
    is_expired: bool = Field(description="是否已过期")


class VaccineDueQuery(BaseModel):
    """查询参数"""

    store_id: Optional[int] = Field(default=None, description="按门店过滤，空=全部门店")
    within_days: int = Field(default=30, ge=1, le=365, description="未来 N 天内到期，默认30天")
    include_expired: bool = Field(default=True, description="是否包含已经过期的疫苗")
    include_only_not_acknowledged: bool = Field(
        default=False, description="仅返回尚未被确认/忽略的提醒"
    )
    keyword: Optional[str] = Field(default=None, description="搜索：宠物名/主人名/电话")


class VaccineDueResult(BaseModel):
    """批量查询返回"""

    total: int = Field(description="总数")
    expired_count: int = Field(description="已过期数量")
    expiring_soon_count: int = Field(description="即将到期数量（within_days范围内且未过期）")
    list: List[VaccineDueItem]


class VaccineReminderCreate(BaseModel):
    """生成提醒记录请求（供定时任务/手动批量生成调用）"""

    store_id: Optional[int] = None
    within_days: int = 30
    include_expired: bool = True
    default_channel: ReminderChannel = ReminderChannel.MANUAL


class VaccineReminderMarkNotified(BaseModel):
    """标记已通知请求"""

    channel: ReminderChannel = Field(default=ReminderChannel.MANUAL, description="通知渠道")
    note: Optional[str] = Field(default=None, description="备注（如：已微信联系，主人周末带宠物来打针）")
    notified_by: Optional[int] = Field(default=None, description="操作人ID")


class VaccineReminderResp(BaseModel):
    """提醒记录响应"""

    id: int
    vaccine_id: int
    pet_id: int
    owner_id: int
    store_id: Optional[int] = None
    vaccine_name: str
    expiry_date: date
    days_to_expiry: int
    is_expired: bool
    status: ReminderStatus
    channel: ReminderChannel
    notified_at: Optional[datetime] = None
    notified_by: Optional[int] = None
    note: Optional[str] = None

    pet_name: Optional[str] = None
    owner_phone: Optional[str] = None

    model_config = {"from_attributes": True}


class VaccineReminderStats(BaseModel):
    """提醒统计概览"""

    total_pending: int = 0
    total_notified: int = 0
    total_acknowledged: int = 0
    total_ignored: int = 0
    expired_pending: int = 0
    expiring_in_7_days: int = 0
