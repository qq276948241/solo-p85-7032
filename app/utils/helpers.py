import uuid
from datetime import datetime, date
from typing import Optional


def generate_booking_no() -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = uuid.uuid4().hex[:6].upper()
    return f"B{ts}{rand}"


def calc_total_days(checkin_date: date, checkout_date: date) -> int:
    delta = checkout_date - checkin_date
    return max(delta.days, 1)


def calc_fee(
    daily_rate: float,
    checkin_date: date,
    checkout_date: date,
    extra_fee: float = 0.0,
    discount: float = 0.0,
) -> tuple[int, float, float, float]:
    total_days = calc_total_days(checkin_date, checkout_date)
    subtotal = round(daily_rate * total_days, 2)
    total_amount = round(subtotal + extra_fee - discount, 2)
    if total_amount < 0:
        total_amount = 0.0
    return total_days, daily_rate, subtotal, total_amount


def calc_date_overlap(
    checkin1: date, checkout1: date, checkin2: date, checkout2: date
) -> bool:
    return checkin1 < checkout2 and checkin2 < checkout1
