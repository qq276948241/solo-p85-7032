from datetime import datetime, date
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Date, DateTime,
    Text, ForeignKey, Enum, UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
import enum

from app.database import Base


class StoreStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"
    MAINTENANCE = "maintenance"


class PetGender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    UNKNOWN = "unknown"


class VaccineStatus(str, enum.Enum):
    VALID = "valid"
    EXPIRED = "expired"
    PENDING = "pending"


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"


class BookingType(str, enum.Enum):
    DAY_CARE = "day_care"
    BOARDING = "boarding"
    OVERNIGHT = "overnight"


class EmployeeRole(str, enum.Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    CARETAKER = "caretaker"
    RECEPTIONIST = "receptionist"


class ShiftType(str, enum.Enum):
    MORNING = "morning"
    AFTERNOON = "afternoon"
    NIGHT = "night"
    FULL = "full"


class FeedingStatus(str, enum.Enum):
    NORMAL = "normal"
    LITTLE = "little"
    NONE = "none"
    REFUSED = "refused"


class StoolStatus(str, enum.Enum):
    NORMAL = "normal"
    SOFT = "soft"
    DIARRHEA = "diarrhea"
    CONSTIPATED = "constipated"
    NONE = "none"


class ReminderChannel(str, enum.Enum):
    WECHAT = "wechat"
    SMS = "sms"
    PHONE = "phone"
    IN_APP = "in_app"
    MANUAL = "manual"


class ReminderStatus(str, enum.Enum):
    PENDING = "pending"
    NOTIFIED = "notified"
    ACKNOWLEDGED = "acknowledged"
    IGNORED = "ignored"


class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    address = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=False)
    capacity = Column(Integer, nullable=False, default=20)
    status = Column(Enum(StoreStatus), default=StoreStatus.OPEN)
    daily_rate = Column(Float, nullable=False, default=120.0)
    hourly_rate = Column(Float, nullable=False, default=20.0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    bookings = relationship("Booking", back_populates="store")
    employees = relationship("Employee", back_populates="store")


class Owner(Base):
    __tablename__ = "owners"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False, index=True)
    wechat = Column(String(50))
    email = Column(String(100))
    address = Column(String(255))
    remark = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    pets = relationship("Pet", back_populates="owner")


class Pet(Base):
    __tablename__ = "pets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    species = Column(String(50), nullable=False)
    breed = Column(String(100))
    gender = Column(Enum(PetGender), default=PetGender.UNKNOWN)
    birthday = Column(Date)
    weight = Column(Float)
    color = Column(String(50))
    chip_number = Column(String(50))
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False, index=True)
    avatar_url = Column(String(255))
    allergies = Column(Text)
    dietary_notes = Column(Text)
    behavioral_notes = Column(Text)
    medical_notes = Column(Text)
    remark = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    owner = relationship("Owner", back_populates="pets")
    vaccines = relationship("Vaccine", back_populates="pet", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="pet")
    care_records = relationship("CareRecord", back_populates="pet")
    assignments = relationship("PetAssignment", back_populates="pet", cascade="all, delete-orphan")


class Vaccine(Base):
    __tablename__ = "vaccines"

    id = Column(Integer, primary_key=True, index=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    manufacturer = Column(String(100))
    batch_number = Column(String(50))
    vaccinated_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=False)
    status = Column(Enum(VaccineStatus), default=VaccineStatus.VALID)
    certificate_url = Column(String(255))
    remark = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    pet = relationship("Pet", back_populates="vaccines")


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False)
    phone = Column(String(20), nullable=False, index=True)
    id_card = Column(String(18), unique=True)
    role = Column(Enum(EmployeeRole), default=EmployeeRole.CARETAKER)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True)
    avatar_url = Column(String(255))
    hire_date = Column(Date, default=date.today)
    is_active = Column(Boolean, default=True)
    remark = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    store = relationship("Store", back_populates="employees")
    schedules = relationship("EmployeeSchedule", back_populates="employee", cascade="all, delete-orphan")
    assignments = relationship("PetAssignment", back_populates="employee", cascade="all, delete-orphan")
    care_records = relationship("CareRecord", back_populates="caretaker")


class EmployeeSchedule(Base):
    __tablename__ = "employee_schedules"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    work_date = Column(Date, nullable=False, index=True)
    shift_type = Column(Enum(ShiftType), nullable=False)
    start_time = Column(String(10))
    end_time = Column(String(10))
    remark = Column(String(255))
    created_at = Column(DateTime, default=datetime.now)

    __table_args__ = (
        UniqueConstraint("employee_id", "work_date", "shift_type", name="uix_emp_date_shift"),
    )

    employee = relationship("Employee", back_populates="schedules")


class PetAssignment(Base):
    __tablename__ = "pet_assignments"

    id = Column(Integer, primary_key=True, index=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, index=True)
    assigned_date = Column(Date, nullable=False, default=date.today)
    is_primary = Column(Boolean, default=True)
    remark = Column(String(255))
    created_at = Column(DateTime, default=datetime.now)

    pet = relationship("Pet", back_populates="assignments")
    employee = relationship("Employee", back_populates="assignments")
    booking = relationship("Booking", back_populates="assignments")


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    booking_no = Column(String(32), nullable=False, unique=True, index=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    booking_type = Column(Enum(BookingType), nullable=False, default=BookingType.BOARDING)
    checkin_date = Column(Date, nullable=False, index=True)
    checkout_date = Column(Date, nullable=False, index=True)
    checkin_time = Column(String(10))
    checkout_time = Column(String(10))
    total_days = Column(Integer, nullable=False)
    daily_rate = Column(Float, nullable=False)
    extra_fee = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    total_amount = Column(Float, nullable=False)
    paid_amount = Column(Float, default=0.0)
    status = Column(Enum(BookingStatus), default=BookingStatus.PENDING, index=True)
    pickup_person = Column(String(50))
    pickup_phone = Column(String(20))
    dropoff_person = Column(String(50))
    dropoff_phone = Column(String(20))
    items_brought = Column(Text)
    remark = Column(Text)
    created_by = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        Index("ix_booking_store_date", "store_id", "checkin_date", "checkout_date"),
    )

    pet = relationship("Pet", back_populates="bookings")
    store = relationship("Store", back_populates="bookings")
    care_records = relationship("CareRecord", back_populates="booking", cascade="all, delete-orphan")
    assignments = relationship("PetAssignment", back_populates="booking", cascade="all, delete-orphan")


class CareRecord(Base):
    __tablename__ = "care_records"

    id = Column(Integer, primary_key=True, index=True)
    booking_id = Column(Integer, ForeignKey("bookings.id"), nullable=False, index=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    caretaker_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    record_date = Column(Date, nullable=False, default=date.today, index=True)
    record_time = Column(String(10), nullable=False)

    feeding = Column(Boolean, default=False)
    feeding_status = Column(Enum(FeedingStatus))
    feeding_food = Column(String(255))
    feeding_amount = Column(String(50))
    feeding_note = Column(String(255))

    walking = Column(Boolean, default=False)
    walking_duration = Column(Integer)
    walking_note = Column(String(255))

    stool = Column(Boolean, default=False)
    stool_status = Column(Enum(StoolStatus))
    stool_count = Column(Integer, default=0)
    stool_note = Column(String(255))

    water = Column(Boolean, default=False)
    water_note = Column(String(255))

    grooming = Column(Boolean, default=False)
    grooming_note = Column(String(255))

    mood = Column(String(50))
    temperature = Column(Float)
    weight = Column(Float)

    general_note = Column(Text)
    abnormal_flag = Column(Boolean, default=False)
    abnormal_note = Column(Text)

    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    booking = relationship("Booking", back_populates="care_records")
    pet = relationship("Pet", back_populates="care_records")
    caretaker = relationship("Employee", back_populates="care_records")
    photos = relationship("CarePhoto", back_populates="care_record", cascade="all, delete-orphan")


class CarePhoto(Base):
    __tablename__ = "care_photos"

    id = Column(Integer, primary_key=True, index=True)
    care_record_id = Column(Integer, ForeignKey("care_records.id"), nullable=False, index=True)
    photo_url = Column(String(255), nullable=False)
    photo_type = Column(String(50))
    caption = Column(String(255))
    created_at = Column(DateTime, default=datetime.now)

    care_record = relationship("CarePhoto", back_populates="photos")


class VaccinationReminder(Base):
    __tablename__ = "vaccination_reminders"

    id = Column(Integer, primary_key=True, index=True)
    vaccine_id = Column(Integer, ForeignKey("vaccines.id"), nullable=False, index=True)
    pet_id = Column(Integer, ForeignKey("pets.id"), nullable=False, index=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), index=True)
    vaccine_name = Column(String(100), nullable=False)
    expiry_date = Column(Date, nullable=False, index=True)
    days_to_expiry = Column(Integer, nullable=False)
    is_expired = Column(Boolean, default=False, index=True)
    status = Column(Enum(ReminderStatus), default=ReminderStatus.PENDING, index=True)
    channel = Column(Enum(ReminderChannel), default=ReminderChannel.MANUAL)
    notified_at = Column(DateTime)
    notified_by = Column(Integer)
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    vaccine = relationship("Vaccine")
    pet = relationship("Pet")
    owner = relationship("Owner")
    store = relationship("Store")
