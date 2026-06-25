"""
疫苗提醒业务逻辑层（Service Layer）
=====================================

设计要点：
1. 所有方法接受 db: Session 作为参数，由调用方（路由 / 定时任务）注入，service 内部绝不自己建 Session
2. 所有公开方法返回结构化数据（Pydantic 对象 / (int, List[int]) / None），绝不直接返回 ORM 实例，方便单元测试
3. 提醒规则（30 天阈值、7 天紧急阈值等）统一从 constants.py 读取，后续改阈值只动一处
4. 日期判断逻辑全部封装成私有函数，便于单测覆盖
"""

from datetime import date, datetime, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.models import (
    Vaccine, Pet, Owner, Booking, Store,
    VaccinationReminder, ReminderStatus, ReminderChannel,
)
from app.schemas.vaccine_reminder import (
    VaccineDueQuery, VaccineDueItem, VaccineDueResult,
    VaccineReminderResp, VaccineReminderStats,
)
from app.services.constants import (
    DEFAULT_WITHIN_DAYS,
    URGENT_WITHIN_DAYS,
    DEFAULT_REMINDER_CHANNEL,
    ACTIVE_REMINDER_STATUSES,
    MIN_WITHIN_DAYS,
    MAX_WITHIN_DAYS,
)


# =========================================================================
# 纯函数：日期 & 规则判断（便于单测覆盖，不依赖数据库）
# =========================================================================

def compute_days_to_expiry(expiry_date: date, today: Optional[date] = None) -> int:
    """返回距到期天数；负数表示已过期 N 天。"""
    today = today or date.today()
    return (expiry_date - today).days


def is_expired(days_to_expiry: int) -> bool:
    return days_to_expiry < 0


def is_expiring_soon(days_to_expiry: int, threshold: int = URGENT_WITHIN_DAYS) -> bool:
    """在 [0, threshold] 天范围内（含 0 天）算即将到期。"""
    return 0 <= days_to_expiry <= threshold


def is_within_horizon(days_to_expiry: int, within_days: int, include_expired: bool) -> bool:
    """判断一条疫苗记录是否在当前查询的目标范围内。"""
    if include_expired:
        return days_to_expiry <= within_days
    return 0 <= days_to_expiry <= within_days


def clamp_within_days(within_days: int) -> int:
    """防止 within_days 越界。"""
    return max(MIN_WITHIN_DAYS, min(MAX_WITHIN_DAYS, within_days))


# =========================================================================
# 私有工具：数据组装
# =========================================================================

def _build_pet_store_map(db: Session, pet_ids: List[int]) -> dict[int, Tuple[Optional[int], Optional[str]]]:
    """批量查每只宠物最近一次 booking 对应的 (store_id, store_name)。"""
    if not pet_ids:
        return {}
    # 按 pet_id + checkin_date desc 排序，取每只 pet 的第一条
    rows = (
        db.query(Booking.pet_id, Booking.store_id, Booking.checkin_date)
        .filter(Booking.pet_id.in_(pet_ids))
        .order_by(Booking.pet_id, Booking.checkin_date.desc())
        .all()
    )
    store_ids: List[int] = [sid for _, sid, _ in rows if sid]
    store_name_map: dict[int, str] = {}
    if store_ids:
        store_rows = db.query(Store.id, Store.name).filter(Store.id.in_(list(set(store_ids)))).all()
        store_name_map = {sid: name for sid, name in store_rows}

    result: dict[int, Tuple[Optional[int], Optional[str]]] = {}
    seen: set[int] = set()
    for pet_id, store_id, _cd in rows:
        if pet_id in seen:
            continue
        seen.add(pet_id)
        result[pet_id] = (store_id, store_name_map.get(store_id))
    return result


def _reminder_orm_to_schema(db: Session, rec: VaccinationReminder) -> VaccineReminderResp:
    """ORM → Pydantic；顺带把 pet_name / owner_phone 也查出来（路由层完全不碰 ORM）。"""
    obj = VaccineReminderResp.model_validate(rec)
    if rec.pet_id:
        pet = db.query(Pet.name).filter(Pet.id == rec.pet_id).first()
        if pet:
            obj.pet_name = pet[0]
    if rec.owner_id:
        owner = db.query(Owner.phone).filter(Owner.id == rec.owner_id).first()
        if owner:
            obj.owner_phone = owner[0]
    return obj


# =========================================================================
# 公开方法：到期疫苗动态查询
# =========================================================================

def find_due_vaccines(db: Session, query: VaccineDueQuery) -> VaccineDueResult:
    """
    动态查询未来 N 天内到期 / 已过期的疫苗列表。
    返回 VaccineDueResult（完全 Pydantic 结构化）。
    """
    today = date.today()
    within_days = clamp_within_days(query.within_days or DEFAULT_WITHIN_DAYS)
    horizon = today + timedelta(days=within_days)

    # ---- 基础查询：疫苗 + 宠物 + 主人 ----
    q = (
        db.query(Vaccine, Pet, Owner)
        .join(Pet, Vaccine.pet_id == Pet.id)
        .join(Owner, Pet.owner_id == Owner.id)
        .filter(Pet.is_active == True)
    )

    # ---- 时间范围过滤（只做粗筛，真正的判定走纯函数）----
    if query.include_expired:
        q = q.filter(Vaccine.expiry_date <= horizon)
    else:
        q = q.filter(and_(Vaccine.expiry_date >= today, Vaccine.expiry_date <= horizon))

    # ---- 门店过滤：取该宠物最近一次 booking 的门店 ----
    if query.store_id:
        sub_booking = (
            db.query(Booking.pet_id, Booking.store_id)
            .distinct(Booking.pet_id)
            .order_by(Booking.pet_id, Booking.checkin_date.desc())
            .subquery()
        )
        q = q.join(sub_booking, sub_booking.c.pet_id == Pet.id).filter(
            sub_booking.c.store_id == query.store_id
        )

    # ---- 关键词搜索 ----
    if query.keyword:
        kw = f"%{query.keyword}%"
        q = q.filter(
            or_(
                Pet.name.like(kw),
                Owner.name.like(kw),
                Owner.phone.like(kw),
                Vaccine.name.like(kw),
            )
        )

    rows = q.order_by(Vaccine.expiry_date.asc()).all()

    # ---- 批量查「宠物→最近门店」 ----
    pet_ids = list({p.id for _, p, _ in rows})
    pet_store_map = _build_pet_store_map(db, pet_ids)

    # ---- 组装（核心日期判断走纯函数）----
    items: List[VaccineDueItem] = []
    expired_count = 0
    expiring_soon_count = 0

    for v, p, o in rows:
        days = compute_days_to_expiry(v.expiry_date, today)
        if not is_within_horizon(days, within_days, query.include_expired):
            continue

        expired_flag = is_expired(days)
        if expired_flag:
            expired_count += 1
        elif is_expiring_soon(days):
            expiring_soon_count += 1

        store_id, store_name = pet_store_map.get(p.id, (None, None))

        items.append(VaccineDueItem(
            vaccine_id=v.id,
            pet_id=p.id,
            pet_name=p.name,
            pet_species=p.species,
            pet_breed=p.breed,
            pet_avatar_url=p.avatar_url,
            owner_id=o.id,
            owner_name=o.name,
            owner_phone=o.phone,
            owner_wechat=o.wechat,
            store_id=store_id,
            store_name=store_name,
            vaccine_name=v.name,
            vaccinated_date=v.vaccinated_date,
            expiry_date=v.expiry_date,
            days_to_expiry=days,
            is_expired=expired_flag,
        ))

    return VaccineDueResult(
        total=len(items),
        expired_count=expired_count,
        expiring_soon_count=expiring_soon_count,
        list=items,
    )


# =========================================================================
# 公开方法：批量生成提醒记录（给定时任务用）
# =========================================================================

def generate_reminder_records(
    db: Session,
    store_id: Optional[int],
    within_days: int = DEFAULT_WITHIN_DAYS,
    include_expired: bool = True,
    default_channel: ReminderChannel = ReminderChannel(DEFAULT_REMINDER_CHANNEL),
) -> Tuple[int, List[int]]:
    """
    扫描到期疫苗，为每一条还「未处理完成」的疫苗生成一条 PENDING 提醒记录。
    返回 (新增数量, 新增记录ID列表) —— 纯数据，不含 ORM 对象。
    """
    due = find_due_vaccines(db, VaccineDueQuery(
        store_id=store_id,
        within_days=within_days,
        include_expired=include_expired,
    ))

    new_ids: List[int] = []
    active_statuses = [ReminderStatus(s) for s in ACTIVE_REMINDER_STATUSES]

    for item in due.list:
        existing = (
            db.query(VaccinationReminder.id)
            .filter(
                VaccinationReminder.vaccine_id == item.vaccine_id,
                VaccinationReminder.status.in_(active_statuses),
            )
            .first()
        )
        if existing:
            continue

        rec = VaccinationReminder(
            vaccine_id=item.vaccine_id,
            pet_id=item.pet_id,
            owner_id=item.owner_id,
            store_id=item.store_id,
            vaccine_name=item.vaccine_name,
            expiry_date=item.expiry_date,
            days_to_expiry=item.days_to_expiry,
            is_expired=item.is_expired,
            status=ReminderStatus.PENDING,
            channel=default_channel,
        )
        db.add(rec)
        db.flush()
        new_ids.append(rec.id)

    db.commit()
    return len(new_ids), new_ids


# =========================================================================
# 公开方法：提醒记录状态流转（全返回 VaccineReminderResp / None）
# =========================================================================

def mark_as_notified(
    db: Session,
    reminder_id: int,
    channel: ReminderChannel = ReminderChannel(DEFAULT_REMINDER_CHANNEL),
    note: Optional[str] = None,
    notified_by: Optional[int] = None,
) -> Optional[VaccineReminderResp]:
    rec = db.query(VaccinationReminder).filter(VaccinationReminder.id == reminder_id).first()
    if not rec:
        return None
    rec.status = ReminderStatus.NOTIFIED
    rec.channel = channel
    rec.notified_at = datetime.now()
    rec.notified_by = notified_by
    if note:
        rec.note = note
    db.commit()
    db.refresh(rec)
    return _reminder_orm_to_schema(db, rec)


def mark_as_acknowledged(
    db: Session,
    reminder_id: int,
    note: Optional[str] = None,
) -> Optional[VaccineReminderResp]:
    rec = db.query(VaccinationReminder).filter(VaccinationReminder.id == reminder_id).first()
    if not rec:
        return None
    rec.status = ReminderStatus.ACKNOWLEDGED
    if note:
        current = rec.note or ""
        rec.note = (current + "；" + note) if current else note
    db.commit()
    db.refresh(rec)
    return _reminder_orm_to_schema(db, rec)


def mark_as_ignored(
    db: Session,
    reminder_id: int,
    reason: Optional[str] = None,
) -> Optional[VaccineReminderResp]:
    rec = db.query(VaccinationReminder).filter(VaccinationReminder.id == reminder_id).first()
    if not rec:
        return None
    rec.status = ReminderStatus.IGNORED
    if reason:
        current = rec.note or ""
        suffix = f"忽略原因：{reason}"
        rec.note = (current + "；" + suffix) if current else suffix
    db.commit()
    db.refresh(rec)
    return _reminder_orm_to_schema(db, rec)


# =========================================================================
# 公开方法：查询提醒记录列表
# =========================================================================

def list_reminder_records(
    db: Session,
    store_id: Optional[int] = None,
    status: Optional[ReminderStatus] = None,
    only_expired: bool = False,
    owner_id: Optional[int] = None,
) -> List[VaccineReminderResp]:
    """返回 List[VaccineReminderResp]，已填好 pet_name / owner_phone，路由层完全不用查 ORM。"""
    q = db.query(VaccinationReminder)
    if store_id:
        q = q.filter(VaccinationReminder.store_id == store_id)
    if status:
        q = q.filter(VaccinationReminder.status == status)
    if only_expired:
        q = q.filter(VaccinationReminder.is_expired == True)
    if owner_id:
        q = q.filter(VaccinationReminder.owner_id == owner_id)
    recs = q.order_by(VaccinationReminder.expiry_date.asc()).all()
    return [_reminder_orm_to_schema(db, r) for r in recs]


# =========================================================================
# 公开方法：统计概览
# =========================================================================

def get_stats(db: Session, store_id: Optional[int] = None) -> VaccineReminderStats:
    """返回结构化统计对象。"""
    q = db.query(VaccinationReminder)
    if store_id:
        q = q.filter(VaccinationReminder.store_id == store_id)
    all_records = q.all()

    stats = VaccineReminderStats()
    for r in all_records:
        if r.status == ReminderStatus.PENDING:
            stats.total_pending += 1
            if r.is_expired:
                stats.expired_pending += 1
            elif is_expiring_soon(r.days_to_expiry):
                stats.expiring_in_7_days += 1
        elif r.status == ReminderStatus.NOTIFIED:
            stats.total_notified += 1
        elif r.status == ReminderStatus.ACKNOWLEDGED:
            stats.total_acknowledged += 1
        elif r.status == ReminderStatus.IGNORED:
            stats.total_ignored += 1
    return stats
