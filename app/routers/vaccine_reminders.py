"""
疫苗提醒模块 API
=======================================
接口总览：
- GET    /api/vaccine-reminders/due             实时查询「30天内到期 / 已过期」的疫苗
- POST   /api/vaccine-reminders/generate        扫描并落库为 PENDING 提醒记录（定时任务可调用）
- GET    /api/vaccine-reminders/records         查询提醒记录（可按门店/状态过滤）
- GET    /api/vaccine-reminders/stats           提醒统计概览
- PATCH  /api/vaccine-reminders/{id}/notified   标记「已通知主人」
- PATCH  /api/vaccine-reminders/{id}/acknowledged  主人确认收到/已安排打针
- PATCH  /api/vaccine-reminders/{id}/ignored    忽略此提醒

⚠️ 本文件只负责：接请求 → 参数校验 → 调用 service → 返回结果
所有业务逻辑（日期判断、过期判定、查询组装、数据填充）都在 app/services/vaccination_service.py
"""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import ReminderStatus
from app.schemas.vaccine_reminder import (
    VaccineDueQuery, VaccineDueResult,
    VaccineReminderCreate, VaccineReminderResp,
    VaccineReminderMarkNotified, VaccineReminderStats,
)
from app.schemas.common import ApiResponse
from app.services import vaccination_service as svc

router = APIRouter(prefix="/api/vaccine-reminders", tags=["疫苗提醒"])


# ---------------------------------------------------------------------------
# 实时动态查询
# ---------------------------------------------------------------------------

@router.get(
    "/due",
    response_model=ApiResponse[VaccineDueResult],
    summary="查询疫苗到期提醒明细",
    description="""
实时查询未来 N 天内到期 + 已过期的疫苗列表。

**返回字段说明：**
- pet_name / pet_species / pet_breed：宠物名 + 品种
- owner_name / owner_phone / owner_wechat：主人联系方式
- vaccine_name：该打哪种疫苗
- vaccinated_date：上次打疫苗时间
- expiry_date：到期日
- days_to_expiry：距到期天数（负数=已过期天数，例如 -5 = 超期 5 天）
- is_expired：是否已过期
- store_id / store_name：该宠物最近一次寄养关联的门店（如果有）

**典型场景：**
- `within_days=30&include_expired=true`（默认）：未来 30 天 + 已过期，用于前台看板
- `store_id=1`：只查朝阳店
- `keyword=王`：按主人名/电话搜
""",
)
def get_due_vaccines(
    store_id: Optional[int] = Query(default=None, description="门店ID，空=全部门店"),
    within_days: int = Query(default=30, ge=1, le=365, description="未来 N 天内到期"),
    include_expired: bool = Query(default=True, description="是否包含已经过期的疫苗"),
    include_only_not_acknowledged: bool = Query(default=False, description="仅返回尚未处理的"),
    keyword: Optional[str] = Query(default=None, description="关键词搜索：宠物名/主人名/电话"),
    db: Session = Depends(get_db),
):
    query = VaccineDueQuery(
        store_id=store_id,
        within_days=within_days,
        include_expired=include_expired,
        include_only_not_acknowledged=include_only_not_acknowledged,
        keyword=keyword,
    )
    return ApiResponse(data=svc.find_due_vaccines(db, query))


# ---------------------------------------------------------------------------
# 批量生成提醒记录
# ---------------------------------------------------------------------------

@router.post(
    "/generate",
    response_model=ApiResponse,
    summary="扫描并批量生成提醒记录",
    description="""
扫描到期疫苗，把每一条落库为 `vaccination_reminders` 表中的 PENDING 记录。

**特性：**
- 同一疫苗若已有 PENDING/NOTIFIED 记录则跳过，避免重复
- 生成后可通过 `/records` 查，可点击「标记已通知」推进状态
- **后续定时任务每天调用一次即可**：每天 8 点跑一次 POST /generate
""",
)
def generate_reminders(
    body: VaccineReminderCreate,
    db: Session = Depends(get_db),
):
    count, ids = svc.generate_reminder_records(
        db,
        store_id=body.store_id,
        within_days=body.within_days,
        include_expired=body.include_expired,
        default_channel=body.default_channel,
    )
    return ApiResponse(
        message=f"已生成 {count} 条提醒记录",
        data={"count": count, "ids": ids},
    )


# ---------------------------------------------------------------------------
# 查询提醒记录
# ---------------------------------------------------------------------------

@router.get(
    "/records",
    response_model=ApiResponse[List[VaccineReminderResp]],
    summary="查询提醒记录列表",
    description="""
查询已落库的提醒记录（带状态跟踪）。
和 `/due` 的区别：这里查的是生成的「任务单」，带 PENDING / NOTIFIED 等状态。
""",
)
def list_records(
    store_id: Optional[int] = Query(default=None, description="门店过滤"),
    status: Optional[ReminderStatus] = Query(default=None, description="提醒状态"),
    only_expired: bool = Query(default=False, description="只看已过期"),
    owner_id: Optional[int] = Query(default=None, description="按主人过滤"),
    db: Session = Depends(get_db),
):
    data = svc.list_reminder_records(
        db, store_id=store_id, status=status,
        only_expired=only_expired, owner_id=owner_id,
    )
    return ApiResponse(data=data)


# ---------------------------------------------------------------------------
# 统计概览
# ---------------------------------------------------------------------------

@router.get(
    "/stats",
    response_model=ApiResponse[VaccineReminderStats],
    summary="提醒统计",
    description="返回各状态的提醒数量，超期未处理的有多少，7 天内到期的有多少。",
)
def get_reminder_stats(
    store_id: Optional[int] = Query(default=None, description="门店过滤"),
    db: Session = Depends(get_db),
):
    return ApiResponse(data=svc.get_stats(db, store_id=store_id))


# ---------------------------------------------------------------------------
# 状态流转
# ---------------------------------------------------------------------------

@router.patch(
    "/{reminder_id}/notified",
    response_model=ApiResponse[VaccineReminderResp],
    summary="标记「已通知主人」",
    description="客服打完电话 / 发完微信后点一下，记录通知渠道与备注。",
)
def mark_notified(
    reminder_id: int,
    body: VaccineReminderMarkNotified,
    db: Session = Depends(get_db),
):
    result = svc.mark_as_notified(
        db,
        reminder_id=reminder_id,
        channel=body.channel,
        note=body.note,
        notified_by=body.notified_by,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="提醒记录不存在")
    return ApiResponse(data=result)


@router.patch(
    "/{reminder_id}/acknowledged",
    response_model=ApiResponse[VaccineReminderResp],
    summary="标记「主人已确认 / 已安排打针」",
    description="主人反馈会去打，或者已经打完，更新为已确认状态。",
)
def mark_acknowledged(
    reminder_id: int,
    note: Optional[str] = Body(default=None, description="备注，例如主人回复本周六来"),
    db: Session = Depends(get_db),
):
    result = svc.mark_as_acknowledged(db, reminder_id, note=note)
    if result is None:
        raise HTTPException(status_code=404, detail="提醒记录不存在")
    return ApiResponse(data=result)


@router.patch(
    "/{reminder_id}/ignored",
    response_model=ApiResponse[VaccineReminderResp],
    summary="忽略该提醒",
    description="例如：已打完但系统里还没更新记录；或主人明确暂不打。",
)
def mark_ignored(
    reminder_id: int,
    reason: Optional[str] = Body(default=None, description="忽略原因"),
    db: Session = Depends(get_db),
):
    result = svc.mark_as_ignored(db, reminder_id, reason=reason)
    if result is None:
        raise HTTPException(status_code=404, detail="提醒记录不存在")
    return ApiResponse(data=result)
