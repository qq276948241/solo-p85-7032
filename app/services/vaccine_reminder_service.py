"""
疫苗提醒业务逻辑层（Service Layer）
======================================
设计原则：
1. 所有业务计算放在这里，路由层只做参数校验 + 调用 + 返回
2. 可被定时任务直接调用（无需走 HTTP），后续加 APScheduler 很方便
3. 数据分两层：
   - 实时动态查询：从 vaccines+pets+owners+bookings 实时拉取到期列表，最准确
   - 持久化提醒记录：把某次生成的提醒写入 vaccination_reminders 表，用来跟踪通知状态
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
    VaccineReminderStats,
)


# ---------------------------------------------------------------------------
# 核心查询：拉取即将到期 / 已过期的疫苗明细
# ---------------------------------------------------------------------------

def find_due_vaccines(
    db: Session,
    query: VaccineDueQuery,
) -> VaccineDueResult:
    """
    动态计算未来 within_days 天内到期 + 已过期的疫苗。
    不依赖 vaccination_reminders 表（那只是通知日志）。
    """
    today = date.today()
    horizon = today + timedelta(days=query.within_days)

    # 构建基础查询：疫苗 + 宠物 + 主人
    q = (
        db.query(Vaccine, Pet, Owner)
        .join(Pet, Vaccine.pet_id == Pet.id)
        .join(Owner, Pet.owner_id == Owner.id)
        .filter(Pet.is_active == True)
    )

    # ---- 时间范围过滤 ----
    if query.include_expired:
        # 已过期 + 未来 within_days 天
        q = q.filter(Vaccine.expiry_date <= horizon)
    else:
        # 只看未来 within_days 天内到期但尚未过期
        q = q.filter(and_(Vaccine.expiry_date >= today, Vaccine.expiry_date <= horizon))

    # ---- 门店过滤 ----
    # 疫苗本身不直接关联门店，取宠物最近一次 booking 的门店
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

    # ---- 预先查好每只宠物最近一次的预约（关联门店名）----
    pet_store_map: dict[int, Tuple[Optional[int], Optional[str]]] = {}
    pet_ids = list({p.id for _, p, _ in rows})
    if pet_ids:
        # 用窗口思路：取每只 pet 最新 checkin 的 booking + 对应 store
        sub = (
            db.query(
                Booking.pet_id,
                Booking.store_id,
                Booking.checkin_date,
            )
            .filter(Booking.pet_id.in_(pet_ids))
            .order_by(Booking.pet_id, Booking.checkin_date.desc())
            .all()
        )
        seen = set()
        for pet_id, store_id, _cd in sub:
            if pet_id in seen:
                continue
            seen.add(pet_id)
            store = db.query(Store.name).filter(Store.id == store_id).first()
            pet_store_map[pet_id] = (store_id, store[0] if store else None)

    # ---- 组装结果 ----
    items: List[VaccineDueItem] = []
    expired_count = 0
    expiring_soon_count = 0

    for v, p, o in rows:
        days_to_expiry = (v.expiry_date - today).days
        is_expired = days_to_expiry < 0

        if is_expired:
            expired_count += 1
        else:
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
            days_to_expiry=days_to_expiry,
            is_expired=is_expired,
        ))

    return VaccineDueResult(
        total=len(items),
        expired_count=expired_count,
        expiring_soon_count=expiring_soon_count,
        list=items,
    )


# ---------------------------------------------------------------------------
# 把动态查询到的到期疫苗，落库为提醒记录（供后续跟踪通知状态）
# ---------------------------------------------------------------------------

def generate_reminder_records(
    db: Session,
    store_id: Optional[int],
    within_days: int = 30,
    include_expired: bool = True,
    default_channel: ReminderChannel = ReminderChannel.MANUAL,
) -> Tuple[int, List[VaccinationReminder]]:
    """
    扫描到期疫苗，为每一条还没有「未处理」提醒记录的疫苗生成一条 PENDING。
    返回：新增数量 + 新增记录列表
    去重规则：同一 vaccine_id 若已有 status in (PENDING, NOTIFIED) 记录则跳过。
    """
    result = find_due_vaccines(db, VaccineDueQuery(
        store_id=store_id,
        within_days=within_days,
        include_expired=include_expired,
    ))

    new_records: List[VaccinationReminder] = []
    for item in result.list:
        existing = (
            db.query(VaccinationReminder)
            .filter(
                VaccinationReminder.vaccine_id == item.vaccine_id,
                VaccinationReminder.status.in_([
                    ReminderStatus.PENDING,
                    ReminderStatus.NOTIFIED,
                ]),
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
        new_records.append(rec)

    db.commit()
    return len(new_records), new_records


# ---------------------------------------------------------------------------
# 提醒记录：状态流转
# ---------------------------------------------------------------------------

def mark_as_notified(
    db: Session,
    reminder_id: int,
    channel: ReminderChannel = ReminderChannel.MANUAL,
    note: Optional[str] = None,
    notified_by: Optional[int] = None,
) -> Optional[VaccinationReminder]:
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
    return rec


def mark_as_acknowledged(
    db: Session,
    reminder_id: int,
    note: Optional[str] = None,
) -> Optional[VaccinationReminder]:
    rec = db.query(VaccinationReminder).filter(VaccinationReminder.id == reminder_id).first()
    if not rec:
        return None
    rec.status = ReminderStatus.ACKNOWLEDGED
    if note:
        rec.note = (rec.note or "") + ("；" if rec.note else "") + note
    db.commit()
    db.refresh(rec)
    return rec


def mark_as_ignored(
    db: Session,
    reminder_id: int,
    reason: Optional[str] = None,
) -> Optional[VaccinationReminder]:
    rec = db.query(VaccinationReminder).filter(VaccinationReminder.id == reminder_id).first()
    if not rec:
        return None
    rec.status = ReminderStatus.IGNORED
    if reason:
        rec.note = (rec.note or "") + ("；" if rec.note else "") + f"忽略原因：{reason}"
    db.commit()
    db.refresh(rec)
    return rec


# ---------------------------------------------------------------------------
# 查询提醒记录（按状态 / 门店 / 主人）
# ---------------------------------------------------------------------------

def list_reminder_records(
    db: Session,
    store_id: Optional[int] = None,
    status: Optional[ReminderStatus] = None,
    only_expired: bool = False,
    owner_id: Optional[int] = None,
) -> List[VaccinationReminder]:
    q = db.query(VaccinationReminder)
    if store_id:
        q = q.filter(VaccinationReminder.store_id == store_id)
    if status:
        q = q.filter(VaccinationReminder.status == status)
    if only_expired:
        q = q.filter(VaccinationReminder.is_expired == True)
    if owner_id:
        q = q.filter(VaccinationReminder.owner_id == owner_id)
    return q.order_by(VaccinationReminder.expiry_date.asc()).all()


# ---------------------------------------------------------------------------
# 统计概览
# ---------------------------------------------------------------------------

def get_stats(db: Session, store_id: Optional[int] = None) -> VaccineReminderStats:
    q = db.query(VaccinationReminder)
    if store_id:
        q = q.filter(VaccinationReminder.store_id == store_id)

    all_records = q.all()
    today = date.today()
    in_7_days = today + timedelta(days=7)

    stats = VaccineReminderStats()
    for r in all_records:
        if r.status == ReminderStatus.PENDING:
            stats.total_pending += 1
            if r.is_expired:
                stats.expired_pending += 1
            elif r.expiry_date <= in_7_days:
                stats.expiring_in_7_days += 1
        elif r.status == ReminderStatus.NOTIFIED:
            stats.total_notified += 1
        elif r.status == ReminderStatus.ACKNOWLEDGED:
            stats.total_acknowledged += 1
        elif r.status == ReminderStatus.IGNORED:
            stats.total_ignored += 1
    return stats
