"""
疫苗提醒业务逻辑层（Service Layer）
=====================================

设计要点：
1. 所有方法接受 db: Session 作为参数，由调用方（路由 / 定时任务）注入，service 内部绝不自己建 Session
2. 所有公开方法返回结构化数据（Pydantic 对象 / (int, List[int]) / None），绝不直接返回 ORM 实例，方便单元测试
3. 提醒规则（30 天阈值、7 天紧急阈值等）统一从 constants.py 读取，后续改阈值只动一处
4. 日期判断逻辑全部封装成纯函数，便于单测覆盖
5. 时区约定：全系统统一使用「服务器本地时区」，所有 DATE / DATETIME 显式用 _get_today() / _get_now() 取，避免跨天边界误差
6. 全局容错：所有公开方法 + 单条宠物循环都有 try/except 兜底，异常走 logging，绝不让一只宠物的脏数据导致整个接口 500
"""

import logging
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
    UNVACCINATED_MARK, UNVACCINATED_DATE_SENTINEL, UNVACCINATED_DAYS_SENTINEL,
)
from app.services.constants import (
    DEFAULT_WITHIN_DAYS,
    URGENT_WITHIN_DAYS,
    DEFAULT_REMINDER_CHANNEL,
    ACTIVE_REMINDER_STATUSES,
    MIN_WITHIN_DAYS,
    MAX_WITHIN_DAYS,
)

logger = logging.getLogger(__name__)


# =========================================================================
# 时区统一：所有日期 / 时间都从这里取，避免散落在代码里出现跨天边界不一致
# =========================================================================
# 约定：全系统使用服务器本地时区。
#      若后续多门店跨时区部署，请统一改成 UTC 存储 + 业务层按门店时区转换。

def _get_today() -> date:
    """统一获取「今日」，避免多处 date.today() 在跨天临界点取值不一致。"""
    return date.today()


def _get_now() -> datetime:
    """统一获取「当前时间」，给 notified_at 等字段用。"""
    return datetime.now()


# =========================================================================
# 纯函数：日期 & 规则判断（便于单测覆盖，不依赖数据库）
# =========================================================================

def compute_days_to_expiry(expiry_date: date, today: Optional[date] = None) -> int:
    """返回距到期天数；负数表示已过期 N 天。"""
    today = today or _get_today()
    # 显式把两边都转成 date，防止传进来 datetime 导致的类型隐式问题
    expiry = datetime(year=expiry_date.year, month=expiry_date.month, day=expiry_date.day).date()
    t = datetime(year=today.year, month=today.month, day=today.day).date()
    return (expiry - t).days


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
    try:
        rows = (
            db.query(Booking.pet_id, Booking.store_id, Booking.checkin_date)
            .filter(Booking.pet_id.in_(pet_ids))
            .order_by(Booking.pet_id, Booking.checkin_date.desc())
            .all()
        )
        store_ids: List[int] = [sid for _, sid, _ in rows if sid]
        store_name_map: dict[int, str] = {}
        if store_ids:
            store_rows = (
                db.query(Store.id, Store.name)
                .filter(Store.id.in_(list(set(store_ids))))
                .all()
            )
            store_name_map = {sid: name for sid, name in store_rows}

        result: dict[int, Tuple[Optional[int], Optional[str]]] = {}
        seen: set[int] = set()
        for pet_id, store_id, _cd in rows:
            if pet_id in seen:
                continue
            seen.add(pet_id)
            result[pet_id] = (store_id, store_name_map.get(store_id))
        return result
    except Exception as e:
        logger.exception(f"[vaccination_service] 构建宠物-门店映射失败: {e}")
        return {}


def _reminder_orm_to_schema(db: Session, rec: VaccinationReminder) -> VaccineReminderResp:
    """ORM → Pydantic；顺带把 pet_name / owner_phone 也查出来（路由层完全不碰 ORM）。"""
    try:
        obj = VaccineReminderResp.model_validate(rec)
        if rec.pet_id:
            try:
                pet = db.query(Pet.name).filter(Pet.id == rec.pet_id).first()
                if pet:
                    obj.pet_name = pet[0]
            except Exception as inner_e:
                logger.warning(f"[vaccination_service] 查询宠物名失败 pet_id={rec.pet_id}: {inner_e}")
        if rec.owner_id:
            try:
                owner = db.query(Owner.phone).filter(Owner.id == rec.owner_id).first()
                if owner:
                    obj.owner_phone = owner[0]
            except Exception as inner_e:
                logger.warning(f"[vaccination_service] 查询主人电话失败 owner_id={rec.owner_id}: {inner_e}")
        return obj
    except Exception as e:
        logger.exception(f"[vaccination_service] ORM转Schema失败 reminder_id={rec.id}: {e}")
        # 降级：返回最基础的字段，避免整条记录没了
        return VaccineReminderResp(
            id=rec.id,
            vaccine_id=rec.vaccine_id,
            pet_id=rec.pet_id,
            owner_id=rec.owner_id,
            store_id=rec.store_id,
            vaccine_name=rec.vaccine_name or UNVACCINATED_MARK,
            expiry_date=rec.expiry_date or UNVACCINATED_DATE_SENTINEL,
            days_to_expiry=rec.days_to_expiry if rec.days_to_expiry is not None else 0,
            is_expired=bool(rec.is_expired),
            status=rec.status or ReminderStatus.PENDING,
            channel=rec.channel or ReminderChannel.MANUAL,
        )


def _safe_date(value) -> date:
    """把数据库里读出来的 date/datetime 安全转成 date，防止 NULL / 类型错乱。"""
    if value is None:
        return UNVACCINATED_DATE_SENTINEL
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    # 其他异常类型，降级成约定值
    logger.warning(f"[vaccination_service] 日期字段类型异常: {type(value)} value={value}")
    return UNVACCINATED_DATE_SENTINEL


# =========================================================================
# 公开方法：到期疫苗动态查询
# =========================================================================

def find_due_vaccines(db: Session, query: VaccineDueQuery) -> VaccineDueResult:
    """
    动态查询未来 N 天内到期 / 已过期 / 从未接种的疫苗列表。
    全程有 try/except 兜底，异常不会抛到路由层，降级返回空结果。

    查询分两部分：
      1) 有疫苗记录的宠物 → INNER JOIN Vaccine → 过滤到期范围
      2) 从未接种的宠物  → LEFT JOIN IS NULL 查出 → 标记 is_unvaccinated
    """
    today = _get_today()
    within_days = clamp_within_days(query.within_days or DEFAULT_WITHIN_DAYS)
    horizon = today + timedelta(days=within_days)

    try:
        items: List[VaccineDueItem] = []
        expired_count = 0
        expiring_soon_count = 0
        collected_pet_ids: set[int] = set()

        # -------------------------------------------------------------------
        # Part 1：有疫苗记录的宠物（按范围过滤）
        # -------------------------------------------------------------------
        try:
            q = (
                db.query(Vaccine, Pet, Owner)
                .join(Pet, Vaccine.pet_id == Pet.id)
                .join(Owner, Pet.owner_id == Owner.id)
                .filter(Pet.is_active == True)
            )
            # 时间粗筛
            if query.include_expired:
                q = q.filter(Vaccine.expiry_date <= horizon)
            else:
                q = q.filter(and_(Vaccine.expiry_date >= today, Vaccine.expiry_date <= horizon))

            # 门店过滤
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

            # 关键词搜索
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

            # 批量查宠物-门店映射
            pet_ids_from_rows = list({p.id for _, p, _ in rows})
            pet_store_map = _build_pet_store_map(db, pet_ids_from_rows)

            # 单条容错：一只宠物脏数据不影响其他
            for v, p, o in rows:
                try:
                    vacc_date = _safe_date(v.vaccinated_date)
                    exp_date = _safe_date(v.expiry_date)
                    days = compute_days_to_expiry(exp_date, today)
                    if not is_within_horizon(days, within_days, query.include_expired):
                        continue

                    expired_flag = is_expired(days)
                    if expired_flag:
                        expired_count += 1
                    elif is_expiring_soon(days):
                        expiring_soon_count += 1

                    store_id, store_name = pet_store_map.get(p.id, (None, None))
                    collected_pet_ids.add(p.id)

                    items.append(VaccineDueItem(
                        vaccine_id=v.id,
                        pet_id=p.id,
                        pet_name=p.name or "(无名宠物)",
                        pet_species=p.species,
                        pet_breed=p.breed,
                        pet_avatar_url=p.avatar_url,
                        owner_id=o.id,
                        owner_name=o.name or "(无名主人)",
                        owner_phone=o.phone or "",
                        owner_wechat=o.wechat,
                        store_id=store_id,
                        store_name=store_name,
                        vaccine_name=v.name or "(未知疫苗)",
                        vaccinated_date=vacc_date,
                        expiry_date=exp_date,
                        days_to_expiry=days,
                        is_expired=expired_flag,
                        is_unvaccinated=False,
                    ))
                except Exception as row_e:
                    logger.warning(
                        f"[vaccination_service] 组装单条疫苗提醒失败 "
                        f"vaccine_id={getattr(v, 'id', '?')} pet_id={getattr(p, 'id', '?')}: {row_e}"
                    )
                    continue
        except Exception as part1_e:
            logger.exception(f"[vaccination_service] Part1(有疫苗记录)查询失败: {part1_e}")

        # -------------------------------------------------------------------
        # Part 2：从未接种过疫苗的宠物（LEFT JOIN IS NULL 等价写法）
        # -------------------------------------------------------------------
        if query.include_unvaccinated:
            try:
                # 从未接种的宠物：vaccine 表中查不到对应 pet_id 的
                unvacc_subq = db.query(Vaccine.pet_id).distinct().subquery()
                unvacc_q = (
                    db.query(Pet, Owner)
                    .join(Owner, Pet.owner_id == Owner.id)
                    .filter(Pet.is_active == True)
                    .filter(~Pet.id.in_(unvacc_subq))
                )

                # 门店过滤（同样按最近一次 booking 关联门店）
                if query.store_id:
                    sub_booking = (
                        db.query(Booking.pet_id, Booking.store_id)
                        .distinct(Booking.pet_id)
                        .order_by(Booking.pet_id, Booking.checkin_date.desc())
                        .subquery()
                    )
                    unvacc_q = unvacc_q.join(
                        sub_booking, sub_booking.c.pet_id == Pet.id
                    ).filter(sub_booking.c.store_id == query.store_id)

                # 关键词搜索
                if query.keyword:
                    kw = f"%{query.keyword}%"
                    unvacc_q = unvacc_q.filter(
                        or_(
                            Pet.name.like(kw),
                            Owner.name.like(kw),
                            Owner.phone.like(kw),
                        )
                    )

                unvacc_rows = unvacc_q.order_by(Pet.id.asc()).all()

                unvacc_pet_ids = list({p.id for p, _ in unvacc_rows})
                unvacc_store_map = _build_pet_store_map(db, unvacc_pet_ids)

                for p, o in unvacc_rows:
                    try:
                        # 如果 Part1 里已经处理过（理论上不会，但保险起见去重）
                        if p.id in collected_pet_ids:
                            continue

                        store_id, store_name = unvacc_store_map.get(p.id, (None, None))
                        collected_pet_ids.add(p.id)

                        items.append(VaccineDueItem(
                            vaccine_id=None,
                            pet_id=p.id,
                            pet_name=p.name or "(无名宠物)",
                            pet_species=p.species,
                            pet_breed=p.breed,
                            pet_avatar_url=p.avatar_url,
                            owner_id=o.id,
                            owner_name=o.name or "(无名主人)",
                            owner_phone=o.phone or "",
                            owner_wechat=o.wechat,
                            store_id=store_id,
                            store_name=store_name,
                            vaccine_name=UNVACCINATED_MARK,
                            vaccinated_date=UNVACCINATED_DATE_SENTINEL,
                            expiry_date=UNVACCINATED_DATE_SENTINEL,
                            days_to_expiry=UNVACCINATED_DAYS_SENTINEL,
                            is_expired=False,
                            is_unvaccinated=True,
                        ))
                    except Exception as row_e:
                        logger.warning(
                            f"[vaccination_service] 组装未接种宠物提醒失败 "
                            f"pet_id={getattr(p, 'id', '?')}: {row_e}"
                        )
                        continue
            except Exception as part2_e:
                logger.exception(f"[vaccination_service] Part2(未接种宠物)查询失败: {part2_e}")

        return VaccineDueResult(
            total=len(items),
            expired_count=expired_count,
            expiring_soon_count=expiring_soon_count,
            list=items,
        )

    except Exception as outer_e:
        logger.exception(f"[vaccination_service] find_due_vaccines 整体异常，降级返回空结果: {outer_e}")
        return VaccineDueResult(total=0, expired_count=0, expiring_soon_count=0, list=[])


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
    返回 (新增数量, 新增记录ID列表)。
    未接种宠物不生成提醒记录（因为没有具体的疫苗可打，交给门店人工沟通首次免疫方案）。
    """
    try:
        due = find_due_vaccines(db, VaccineDueQuery(
            store_id=store_id,
            within_days=within_days,
            include_expired=include_expired,
            include_unvaccinated=False,  # 未接种宠物暂不自动生成记录
        ))

        new_ids: List[int] = []
        active_statuses = [ReminderStatus(s) for s in ACTIVE_REMINDER_STATUSES]

        for item in due.list:
            try:
                if item.is_unvaccinated or item.vaccine_id is None:
                    continue
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
            except Exception as row_e:
                logger.warning(
                    f"[vaccination_service] 生成单条提醒记录失败 "
                    f"vaccine_id={item.vaccine_id} pet_id={item.pet_id}: {row_e}"
                )
                db.rollback()
                continue

        db.commit()
        return len(new_ids), new_ids

    except Exception as outer_e:
        logger.exception(f"[vaccination_service] generate_reminder_records 整体异常: {outer_e}")
        try:
            db.rollback()
        except Exception:
            pass
        return 0, []


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
    try:
        rec = db.query(VaccinationReminder).filter(VaccinationReminder.id == reminder_id).first()
        if not rec:
            return None
        rec.status = ReminderStatus.NOTIFIED
        rec.channel = channel
        rec.notified_at = _get_now()  # 统一时间源
        rec.notified_by = notified_by
        if note:
            rec.note = note
        db.commit()
        db.refresh(rec)
        return _reminder_orm_to_schema(db, rec)
    except Exception as e:
        logger.exception(f"[vaccination_service] mark_as_notified 异常 id={reminder_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return None


def mark_as_acknowledged(
    db: Session,
    reminder_id: int,
    note: Optional[str] = None,
) -> Optional[VaccineReminderResp]:
    try:
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
    except Exception as e:
        logger.exception(f"[vaccination_service] mark_as_acknowledged 异常 id={reminder_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return None


def mark_as_ignored(
    db: Session,
    reminder_id: int,
    reason: Optional[str] = None,
) -> Optional[VaccineReminderResp]:
    try:
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
    except Exception as e:
        logger.exception(f"[vaccination_service] mark_as_ignored 异常 id={reminder_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return None


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
    try:
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
    except Exception as e:
        logger.exception(f"[vaccination_service] list_reminder_records 异常: {e}")
        return []


# =========================================================================
# 公开方法：统计概览
# =========================================================================

def get_stats(db: Session, store_id: Optional[int] = None) -> VaccineReminderStats:
    """返回结构化统计对象。"""
    try:
        q = db.query(VaccinationReminder)
        if store_id:
            q = q.filter(VaccinationReminder.store_id == store_id)
        all_records = q.all()

        stats = VaccineReminderStats()
        for r in all_records:
            try:
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
            except Exception as inner_e:
                logger.warning(
                    f"[vaccination_service] 统计单条记录异常 id={getattr(r, 'id', '?')}: {inner_e}"
                )
                continue
        return stats
    except Exception as e:
        logger.exception(f"[vaccination_service] get_stats 异常: {e}")
        return VaccineReminderStats()
