from typing import List, Optional
from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.database import get_db
from app.models.models import Booking, Pet, Store, BookingStatus
from app.schemas.booking import (
    BookingCreate, BookingResp, BookingUpdate,
    FeeCalcReq, FeeCalcResp, BookingAvailabilityReq, BookingAvailabilityResp,
)
from app.schemas.common import ApiResponse, PageResult
from app.utils.helpers import generate_booking_no, calc_fee, calc_date_overlap

router = APIRouter(prefix="/api/bookings", tags=["寄养预约"])


def _check_conflict(
    db: Session,
    store_id: int,
    checkin_date: date,
    checkout_date: date,
    exclude_booking_id: Optional[int] = None,
) -> tuple[int, int]:
    store = db.query(Store).filter(Store.id == store_id).first()
    if not store:
        raise HTTPException(status_code=400, detail="门店不存在")
    capacity = store.capacity

    conflict_query = db.query(Booking).filter(
        Booking.store_id == store_id,
        Booking.status.in_([
            BookingStatus.PENDING,
            BookingStatus.CONFIRMED,
            BookingStatus.CHECKED_IN,
        ]),
    )
    if exclude_booking_id:
        conflict_query = conflict_query.filter(Booking.id != exclude_booking_id)

    conflict_bookings = conflict_query.all()
    current_count = 0
    for b in conflict_bookings:
        if calc_date_overlap(checkin_date, checkout_date, b.checkin_date, b.checkout_date):
            current_count += 1
    return current_count, capacity


@router.post("/calc-fee", response_model=ApiResponse[FeeCalcResp])
def calc_booking_fee(data: FeeCalcReq, db: Session = Depends(get_db)):
    store = db.query(Store).filter(Store.id == data.store_id).first()
    if not store:
        raise HTTPException(status_code=400, detail="门店不存在")
    total_days, daily_rate, subtotal, total_amount = calc_fee(
        daily_rate=store.daily_rate,
        checkin_date=data.checkin_date,
        checkout_date=data.checkout_date,
        extra_fee=data.extra_fee,
        discount=data.discount,
    )
    return ApiResponse(
        data=FeeCalcResp(
            total_days=total_days,
            daily_rate=daily_rate,
            subtotal=subtotal,
            extra_fee=data.extra_fee,
            discount=data.discount,
            total_amount=total_amount,
        )
    )


@router.post("/check-availability", response_model=ApiResponse[BookingAvailabilityResp])
def check_availability(data: BookingAvailabilityReq, db: Session = Depends(get_db)):
    current_count, capacity = _check_conflict(
        db,
        store_id=data.store_id,
        checkin_date=data.checkin_date,
        checkout_date=data.checkout_date,
        exclude_booking_id=data.exclude_booking_id,
    )
    available = current_count < capacity
    if available:
        message = f"当前时段可预约，剩余容量 {capacity - current_count} 位"
    else:
        message = f"当前时段已满，容量 {capacity}，已预约 {current_count} 位"
    return ApiResponse(
        data=BookingAvailabilityResp(
            available=available,
            current_count=current_count,
            capacity=capacity,
            message=message,
        )
    )


@router.post("", response_model=ApiResponse[BookingResp])
def create_booking(data: BookingCreate, db: Session = Depends(get_db)):
    pet = db.query(Pet).filter(Pet.id == data.pet_id).first()
    if not pet:
        raise HTTPException(status_code=400, detail="宠物不存在")
    store = db.query(Store).filter(Store.id == data.store_id).first()
    if not store:
        raise HTTPException(status_code=400, detail="门店不存在")

    current_count, capacity = _check_conflict(
        db, data.store_id, data.checkin_date, data.checkout_date
    )
    if current_count >= capacity:
        raise HTTPException(
            status_code=400,
            detail=f"该门店该时段已满（{current_count}/{capacity}），无法预约",
        )

    total_days, daily_rate, subtotal, total_amount = calc_fee(
        daily_rate=store.daily_rate,
        checkin_date=data.checkin_date,
        checkout_date=data.checkout_date,
        extra_fee=data.extra_fee,
        discount=data.discount,
    )
    booking_no = generate_booking_no()

    booking_data = data.model_dump()
    booking_data.update({
        "booking_no": booking_no,
        "total_days": total_days,
        "daily_rate": daily_rate,
        "total_amount": total_amount,
    })
    booking = Booking(**booking_data)
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return ApiResponse(data=BookingResp.model_validate(booking))


@router.get("", response_model=ApiResponse[PageResult[BookingResp]])
def list_bookings(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    store_id: Optional[int] = None,
    pet_id: Optional[int] = None,
    status: Optional[BookingStatus] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    keyword: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(Booking)
    if store_id:
        query = query.filter(Booking.store_id == store_id)
    if pet_id:
        query = query.filter(Booking.pet_id == pet_id)
    if status:
        query = query.filter(Booking.status == status)
    if start_date:
        query = query.filter(Booking.checkout_date >= start_date)
    if end_date:
        query = query.filter(Booking.checkin_date <= end_date)
    if keyword:
        query = query.join(Pet).filter(
            or_(
                Booking.booking_no.like(f"%{keyword}%"),
                Pet.name.like(f"%{keyword}%"),
            )
        )
    total = query.count()
    items = (
        query.order_by(Booking.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    data = PageResult(
        total=total,
        page=page,
        page_size=page_size,
        list=[BookingResp.model_validate(i) for i in items],
    )
    return ApiResponse(data=data)


@router.get("/{booking_id}", response_model=ApiResponse[BookingResp])
def get_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="预约不存在")
    return ApiResponse(data=BookingResp.model_validate(booking))


@router.put("/{booking_id}", response_model=ApiResponse[BookingResp])
def update_booking(booking_id: int, data: BookingUpdate, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="预约不存在")

    update_data = data.model_dump(exclude_unset=True)

    need_recalc = any(k in update_data for k in [
        "checkin_date", "checkout_date", "extra_fee", "discount"
    ])
    if need_recalc:
        ci = update_data.get("checkin_date", booking.checkin_date)
        co = update_data.get("checkout_date", booking.checkout_date)
        if "checkin_date" in update_data or "checkout_date" in update_data:
            current_count, capacity = _check_conflict(
                db, booking.store_id, ci, co, exclude_booking_id=booking_id
            )
            if current_count >= capacity:
                raise HTTPException(
                    status_code=400,
                    detail=f"该门店该时段已满（{current_count}/{capacity}），无法修改",
                )
        extra = update_data.get("extra_fee", booking.extra_fee)
        disc = update_data.get("discount", booking.discount)
        store = db.query(Store).filter(Store.id == booking.store_id).first()
        total_days, daily_rate, subtotal, total_amount = calc_fee(
            daily_rate=store.daily_rate,
            checkin_date=ci,
            checkout_date=co,
            extra_fee=extra,
            discount=disc,
        )
        update_data["total_days"] = total_days
        update_data["daily_rate"] = daily_rate
        update_data["total_amount"] = total_amount

    for k, v in update_data.items():
        setattr(booking, k, v)
    db.commit()
    db.refresh(booking)
    return ApiResponse(data=BookingResp.model_validate(booking))


@router.patch("/{booking_id}/status", response_model=ApiResponse[BookingResp])
def update_booking_status(
    booking_id: int,
    status: BookingStatus = Query(..., description="目标状态"),
    db: Session = Depends(get_db),
):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="预约不存在")
    booking.status = status
    db.commit()
    db.refresh(booking)
    return ApiResponse(data=BookingResp.model_validate(booking))


@router.delete("/{booking_id}", response_model=ApiResponse)
def cancel_booking(booking_id: int, db: Session = Depends(get_db)):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="预约不存在")
    booking.status = BookingStatus.CANCELLED
    db.commit()
    return ApiResponse(message="预约已取消")
